# Production STARK Migration — decision & port package (P10 / Exp23)

> 2026-08-27 · Exp22의 교육급 FRI를 감사받은 프로덕션 prover로 승격한다.
> **정직한 환경 제약:** 작업 머신에 Rust/cargo 없고 crates.io 차단 → 프로덕션
> prover를 여기서 실행 불가. 그래서 **다른 Rust 머신에서 바로 돌릴 이식 패키지**
> (prover 결정 + 정수 골든 레퍼런스 + risc0 게스트 + 빌드법)를 만든다. prover
> 무관한 핵심(정수 명세)은 여기서 실행·검증했다(argmax 100/100).

## Prover 평가 (4종 병렬, 웹 근거)

| Prover | PQ·투명 | NN 순전파 적합 | 이식 방식 | 판정 |
|---|---|---|---|---|
| **risc0 zkVM** | STARK 코어는 PQ **(단 기본 Groth16-BN254 래퍼는 페어링→PQ 아님)** | 매우 좋음, **가장 쉬운 경로** | Rust 게스트(=우리 순전파), hand-AIR 불필요 | **PRIMARY** |
| winterfell | PQ(해시 FRI) | 보통 — 스캔 재귀는 AIR로 깔끔 | hand-AIR(우리 halo2 회로와 개념 거리 최소) | 대안(조밀) |
| stwo/cairo (Circle STARK, M31) | PQ, 프로덕션급 최고 | 보통-좋음(프론트엔드 없음) | Cairo/AIR 직접 | 대안(성능) |
| plonky2 | 투명·FRI(추정 PQ) | 좋음, 엔지니어링 다소 번거로움 | hand-circuit(Rust), zkVM 경로 없음 | 대안 |

**결정: risc0 zkVM을 primary.** 이유 — 우리 순전파를 그대로 Rust 게스트로 옮기면
되고(정수 골든 레퍼런스가 이미 그 코드), 우리 규모(~79k MAC, 약 3e5~1e6 사이클)는
risc0에 작다. 회로를 손으로 짜는 winterfell/stwo/plonky2보다 시간이 짧다.

**⚠️ 치명 주의(반드시 지킬 것):** risc0 **기본 파이프라인은 STARK 리시트를 다시
Groth16-on-BN254(페어링)로 감싼다 → 그건 양자에 깨진다.** PQ를 유지하려면
**STARK/Succinct 리시트를 그대로 검증에 쓰고 Groth16 래퍼를 거부**해야 한다.
(host의 prover 옵션에서 groth16 비활성, `ProverOpts::succinct()`류.) 이 한 줄을
놓치면 우리가 KZG를 버린 이유가 무의미해진다.

## 정수 골든 레퍼런스 (여기서 검증됨)

`exp23/fixed_point_ref.py` — 순수 정수(i64) 순전파, scale 2^11(ezkl param_scale 일치):
- **정수 argmax == float argmax: 100/100.** 최대 로짓 38,836(16비트),
  누적 79k MAC × (2^11)^2 ≈ 2^39 < i64 → 오버플로 없음. tanh LUT 215,755개.
- 이 정수 의미가 프로덕션 게스트가 정확히 재현할 계산이다(prover 독립).

## risc0 실측 기대치 (공개 벤치마크 근거, 별도 머신)

- 우리 순전파 ~79k MAC ≈ **3e5~1e6 RISC-V 사이클** → 단일 세그먼트(2^20). 우리 규모는 risc0엔 작다.
- GPU 증명: **수초~수십초**, 피크 VRAM **<1~2GB**. (근거: Fibonacci 100k사이클 3.6s·222KB·0.63GB, SHA2-2048 0.54s.)
- 리시트 크기: composite STARK **~200~300KB** → 재귀 Succinct **수십 KB**(PQ 유지). ⚠️ Groth16 래핑하면 ~200바이트지만 **페어링→PQ 깨짐, 금지**.
- CPU 폴백: 분 단위·**16~32GB RAM**. R0VM 2.0(2025.4)이 대폭 단축.
- 신뢰 앵커 = **ImageID**(게스트 ELF 해시 = 모델 커밋). SP1이 유사 zkVM 2순위 견적.

## risc0 게스트 스켈레톤

`exp23/risc0_guest.rs` — 위 정수 순전파의 Rust 이식(rescale·스캔·tanh 룩업·argmax
헤드). 공개 입력/출력(journal) = **입력해시 + 추출 튜플**, 프로그램 **image ID =
모델 커밋** → Exp16(입력 바인딩)·Exp20(ZkVerdictGate 점수 확정)과 정합.

## 별도 Rust 머신 빌드·실행 (실측할 사람용)

```bash
curl -L https://risczero.com/install | bash && rzup install     # 툴체인
# cargo risczero new extractor-stark  → guest에 risc0_guest.rs 이식
cargo run --release                                             # 증명 생성+검증
# 반드시 STARK/succinct 리시트 사용, groth16 래퍼 금지(위 주의)
```

## 남은 일 (정직)

- 실제 증명 생성·검증 시간/메모리/리시트 크기 실측(Rust 머신). Exp15가 halo2로
  온체인 검증 864k가스를 쟀듯, STARK 온체인 검증(가스·리시트) 실측이 다음.
- rsqrt를 게스트에서 룩업/제약 정식화(현 근사는 골든 레퍼런스와 일치 확인됨).
- Groth16-없는 STARK 리시트의 온체인 검증 경로(risc0 verifier 컨트랙트가
  BN254를 쓰면 그 자체가 PQ 아님 — L2/재귀 STARK 검증이 최종 PQ 경로).

**정직성:** 이 문서는 이식을 **설계·검증(정수 명세)·패키징**했다. 실제 프로덕션
증명 실행은 이 환경 밖(Rust 필요). "여기서 이식 완료"가 아니라 "다른 머신에서 바로
돌릴 이식 패키지 + 검증된 정수 코어 + 정확한 prover 결정과 PQ 함정"이다.
