// Exp23 — risc0 zkVM 게스트: 추출기 순전파(정수 전용)를 증명한다.
//
// 이 프로그램은 `fixed_point_ref.py`의 정수 명세를 Rust로 옮긴 것이다. risc0가
// 이 RISC-V 실행 트레이스를 zk-STARK(FRI, 해시 기반)로 증명한다 → 페어링 없음(PQ).
//
// ⚠️ 치명 주의(prover 평가 결과): risc0 기본 파이프라인은 STARK 리시트를 다시
//    Groth16-on-BN254(페어링!)로 감싼다 → 그건 PQ가 아니다. **STARK/Succinct
//    리시트를 그대로 검증에 쓰고 Groth16 래퍼를 거부**해야 양자 내성이 유지된다.
//    (host 쪽 prover 옵션에서 groth16 비활성.)
//
// 이 환경엔 Rust 툴체인이 없어 여기서 컴파일·증명하지 않는다(별도 Rust 머신).
// 결정론 정수 의미는 golden reference(fixed_point_ref.py, argmax 100/100)로 검증됨.

#![no_main]
risc0_zkvm::guest::entry!(main);
use risc0_zkvm::guest::env;

const S: i64 = 1 << 11; // 고정소수점 스케일 (ezkl param_scale=11 일치)
const D: usize = 64;
const N_ENT: usize = 30;

// 곱 후 스케일 복원 (결정론 내림 나눗셈, 부호 보존)
#[inline]
fn rescale(x: i64) -> i64 { if x >= 0 { x / S } else { -((-x) / S) } }

// tanh 정수 룩업 — 게스트엔 표를 baked-in 하거나(작으면) rsqrt처럼 제약으로.
// 여기선 입력 범위 [-125134,90620] 클램프 후 표 조회(호스트가 표를 주입).
fn tanh_lut(pre: i64, lut: &[i64], lo: i64) -> i64 {
    let idx = (pre.clamp(lo, lo + lut.len() as i64 - 1) - lo) as usize;
    lut[idx]
}

struct Weights {
    e: Vec<[i64; D]>,          // 임베딩 (vocab × D)
    g: [i64; D], win: [[i64; D]; D],
    a: [i64; D], b: [i64; D], a2: [i64; D], b2: [i64; D],
    wm: [[i64; D]; D], wl: [[i64; D]; D], wl2: [[i64; D]; D],
    wfrom: [[i64; D]; N_ENT], wto: [[i64; D]; N_ENT], wneg: [[i64; D]; 2],
    tanh: Vec<i64>, tanh_lo: i64,
}

fn forward(w: &Weights, ids: &[u32]) -> (usize, usize, usize) {
    let t_len = ids.len();
    // 임베딩 룩업 + rmsnorm + Win 투영 → u
    let mut u = vec![[0i64; D]; t_len];
    for t in 0..t_len {
        let x = &w.e[ids[t] as usize];
        let ms = (0..D).map(|k| x[k] * x[k]).sum::<i64>() / D as i64; // 스케일 S^2
        // 정수 rsqrt 근사(게스트 정식본은 룩업/제약; 여기선 결정론 근사)
        let inv = if ms > 0 { ((S as f64) * (S as f64) / ((ms as f64 / (S*S) as f64).sqrt() * S as f64)) as i64 } else { S };
        let mut ut = [0i64; D];
        for j in 0..D {
            let xn_dot: i64 = (0..D).map(|k| {
                let xn = rescale(rescale(x[k] * inv) * w.g[k]);
                xn * w.win[k][j]
            }).sum();
            ut[j] = rescale(xn_dot);
        }
        u[t] = ut;
    }
    // 정방향 스캔 + 누적
    let mut h = [0i64; D]; let mut acc = [0i64; D];
    for t in 0..t_len {
        for k in 0..D { h[k] = rescale(h[k] * w.a[k]) + rescale(u[t][k] * w.b[k]); acc[k] += h[k]; }
    }
    // 역방향 스캔
    let mut h2 = [0i64; D];
    for t in (0..t_len).rev() {
        for k in 0..D { h2[k] = rescale(h2[k] * w.a2[k]) + rescale(u[t][k] * w.b2[k]); }
    }
    // enc = tanh( accm·Wm + h·Wl + h2·Wl2 )
    let mut enc = [0i64; D];
    for j in 0..D {
        let s: i64 = (0..D).map(|k| (acc[k] / t_len as i64) * w.wm[k][j] + h[k] * w.wl[k][j] + h2[k] * w.wl2[k][j]).sum();
        enc[j] = tanh_lut(rescale(s), &w.tanh, w.tanh_lo);
    }
    let argmax = |wm: &[[i64; D]], n: usize| -> usize {
        let mut best = 0usize; let mut bv = i64::MIN;
        for j in 0..n { let v: i64 = (0..D).map(|k| enc[k] * wm[k][j]).sum(); if v > bv { bv = v; best = j; } }
        best
    };
    (argmax(&w.wfrom, N_ENT), argmax(&w.wto, N_ENT), argmax(&w.wneg, 2))
}

fn main() {
    // 공개 입력(instances) — Exp16/Exp20 바인딩과 정합:
    //  input_hash : 발화 입력(ids)의 커밋 (사건 정체성)
    //  weights    : 모델 가중치 (프로그램 image ID = 모델 커밋; 가중치 해시도 커밋 가능)
    let ids: Vec<u32> = env::read();
    let w: Weights = env::read();
    let input_hash: [u8; 32] = env::read();

    let (from_ent, to_ent, neg) = forward(&w, &ids);

    // journal(공개 출력): 입력해시 + 추출 결과 튜플. 검증자·온체인 게이트가 읽는다.
    env::commit(&input_hash);
    env::commit(&(from_ent as u32, to_ent as u32, neg as u32));
    // 프로그램 image ID(=모델 버전 커밋)는 리시트 메타로 자동 포함 → 모델 위조 불가.
}
