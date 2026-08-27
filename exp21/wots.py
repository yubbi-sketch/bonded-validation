"""Exp21 — 해시기반 발화 서명(WOTS) 실측. EXP21.md 킬 기준 준수.

WOTS(Winternitz OTS) = SLH-DSA(FIPS 205)의 리프 프리미티브. 순수 SHA-256만
쓴다. 발화 커밋(requestHash‖score‖modelVer)에 서명해 "서명된 발화" 층을 PQ화.

정직성(적대 검증 반영, 2026-08-27):
 - K2는 체크섬을 실제로 격리 시험한다(무작위 타깃이 아니라 '지배' 타깃 구성).
 - K4는 일회용 성질을 실증한다(한 키로 두 번 서명 → 세 번째 위조 성공).
 - 이 단순화 WOTS(WOTS+ 비트마스크 생략)의 보안 환원은 프리이미지가 아니라
   **충돌 저항**에 기댄다: 고전 128비트(생일)·양자 BHT ~2^85. 따라서 이 데모는
   FIPS 205 WOTS+보다 '보수적'이지 않다(그 반대) — 비트마스크가 그걸 2차
   프리이미지로 낮춘다. 여기선 리프 프리미티브를 실측하고 표준을 인용한다.
"""
import hashlib
import json
import os
import time

import numpy as np

N = 32          # SHA-256 출력 바이트
W = 16          # Winternitz 파라미터 (base-16)
LEN1 = 64       # 256비트 / 4 = 64 메시지 자리
LEN2 = 3        # 체크섬 자리 (max checksum 960 < 16^3=4096)
LEN = LEN1 + LEN2  # 67
SEED = 2026


def H(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def chain(x: bytes, steps: int) -> bytes:
    for _ in range(steps):
        x = H(x)
    return x


def msg_digits(msg32: bytes):
    ds = []
    for byte in msg32:
        ds.append(byte >> 4)
        ds.append(byte & 0xF)
    return ds


def checksum_digits(ds):
    c = sum((W - 1) - d for d in ds)
    return [(c >> 8) & 0xF, (c >> 4) & 0xF, c & 0xF]


def full_digits(msg: bytes):
    d = msg_digits(H(msg))
    return d + checksum_digits(d)


def keygen(rng):
    sk = [rng.bytes(N) for _ in range(LEN)]
    pk = H(b"".join(chain(s, W - 1) for s in sk))
    return sk, pk


def sign_full(sk, digits):
    return [chain(sk[i], digits[i]) for i in range(LEN)]


def verify_full(pk, digits, sig):
    return H(b"".join(chain(sig[i], (W - 1) - digits[i]) for i in range(LEN))) == pk


def sign(sk, msg):
    return sign_full(sk, full_digits(msg))


def verify(pk, msg, sig):
    return verify_full(pk, full_digits(msg), sig)


def commit(request_hash, score, model_ver):
    return H(request_hash + bytes([score]) + model_ver.encode())


def main():
    rng = np.random.default_rng(SEED)

    # ── K1 정확성 ────────────────────────────────────────────────
    n_ok = n_tamper = 0
    TRIALS = 200
    t0 = time.perf_counter()
    for _ in range(TRIALS):
        sk, pk = keygen(rng)
        rh = rng.bytes(32); score = int(rng.integers(0, 101))
        msg = commit(rh, score, "extractor-v1-d64")
        sig = sign(sk, msg)
        if verify(pk, msg, sig):
            n_ok += 1
        bad_msg = commit(rh, (score + 1) % 101, "extractor-v1-d64")
        bad_sig = list(sig); bad_sig[0] = H(bad_sig[0])
        if (not verify(pk, bad_msg, sig)) and (not verify(pk, msg, bad_sig)):
            n_tamper += 1
    sv_ms = (time.perf_counter() - t0) / TRIALS * 1000

    # ── K2 체크섬 격리 위조 시험 (지배 타깃) ─────────────────────
    #   base 메시지 디짓을 '지배'(모두 ≥, 한 자리 ↑)하는 타깃을 직접 구성.
    #   메시지 자리는 전방 체이닝으로 위조 가능하지만, 그러면 체크섬이 내려가
    #   최소 한 자리는 역행(프리이미지)이 필요 → 위조 실패. 체크섬을 지우면
    #   같은 위조가 성공함을 대조로 보여 체크섬이 load-bearing임을 증명한다.
    sk, pk = keygen(rng)
    base_msg = commit(rng.bytes(32), 50, "extractor-v1-d64")
    D0 = full_digits(base_msg)
    base_sig = sign_full(sk, D0)
    # 지배 타깃: 15가 아닌 메시지 자리 하나를 +1 (나머지 동일)
    bump = next(i for i in range(LEN1) if D0[i] < W - 1)
    Dt_msg = D0[:LEN1].copy()
    Dt_msg[bump] += 1
    DT = Dt_msg + checksum_digits(Dt_msg)
    dominates = all(DT[i] >= D0[i] for i in range(LEN1)) and any(DT[i] > D0[i] for i in range(LEN1))
    checksum_decreased = any(DT[LEN1 + k] < D0[LEN1 + k] for k in range(LEN2))
    forged = [chain(base_sig[i], DT[i] - D0[i]) if DT[i] >= D0[i] else base_sig[i]
              for i in range(LEN)]
    forge_with_checksum = verify_full(pk, DT, forged)  # 기대 False
    # 대조: 체크섬 없는 스킴이면 같은 위조가 성공
    pk_nc = H(b"".join(chain(s, W - 1) for s in sk[:LEN1]))
    forged_nc = [chain(base_sig[i], Dt_msg[i] - D0[i]) for i in range(LEN1)]
    forge_no_checksum = (H(b"".join(chain(forged_nc[i], (W - 1) - Dt_msg[i])
                                    for i in range(LEN1))) == pk_nc)  # 기대 True
    k2 = bool(dominates and checksum_decreased and (not forge_with_checksum) and forge_no_checksum)

    # ── K4 일회용 실증 (한 키로 두 번 서명 → 세 번째 위조) ───────
    #   한 키로 m1·m2 서명 관측. 각 자리 최소높이 min(D1,D2)의 체인값을 안다.
    #   그 min을 '지배'(모두 ≥)하는 타깃은 전방만으로 위조 가능 → 검증 통과.
    #   같은 타깃을 단일 서명(D1)으로는 어떤 자리는 역행 필요 → 위조 불가.
    skR, pkR = keygen(rng)
    m1 = commit(rng.bytes(32), 30, "m"); m2 = commit(rng.bytes(32), 70, "m")
    D1, D2 = full_digits(m1), full_digits(m2)
    s1, s2 = sign_full(skR, D1), sign_full(skR, D2)
    lo = [min(D1[i], D2[i]) for i in range(LEN)]
    lo_val = [s1[i] if D1[i] <= D2[i] else s2[i] for i in range(LEN)]  # min높이 체인값
    DT3 = lo[:]  # min을 그대로 타깃(0 전방스텝)
    forged3 = lo_val[:]
    forge_two_sig = verify_full(pkR, DT3, forged3)          # 기대 True(위조 성공)
    # 단일 서명(s1)만으로 같은 DT3 위조: DT3[i]<D1[i]인 자리는 역행 필요 → 불가
    need_backward = any(DT3[i] < D1[i] for i in range(LEN))
    forged1 = [chain(s1[i], DT3[i] - D1[i]) if DT3[i] >= D1[i] else s1[i] for i in range(LEN)]
    forge_one_sig = verify_full(pkR, DT3, forged1)          # 기대 False
    k4 = bool(forge_two_sig and need_backward and (not forge_one_sig))

    # ── K3 양자 마진 (정직한 이중 가정) ──────────────────────────
    k3 = {
        "chain_preimage_classical": 256, "chain_preimage_grover": 128,
        "binding_collision_classical": 128, "binding_collision_bht_quantum_approx": 85,
        "honest_floor": "이 단순화 WOTS의 EU-CMA는 충돌 저항에 기댄다: 고전 128비트, "
                        "양자 BHT ~2^85. WOTS+ 비트마스크/키드 해시가 2차 프리이미지로 낮춘다.",
        "economic_core_note": "정리 2는 하드니스 가정 0(양자 계산 불변)이나, 그 보안은 "
                              "서명·zk 집행층이 PQ여야 성립 — 합성 주의(§quantum-resistance).",
    }

    k1 = bool(n_ok == TRIALS and n_tamper == TRIALS)
    res = {
        "params": {"N": N, "W": W, "LEN": LEN, "seed": SEED},
        "sizes_bytes": {"sk": LEN * N, "pk": N, "sig": LEN * N},
        "sign_verify_ms_per_op": round(sv_ms, 3),
        "K1_correctness": {"valid": n_ok, "trials": TRIALS, "tamper_rejected": n_tamper, "pass": k1},
        "K2_checksum_isolation": {"dominates": dominates, "checksum_decreased": checksum_decreased,
                                  "forge_with_checksum": forge_with_checksum,
                                  "forge_no_checksum": forge_no_checksum, "pass": k2},
        "K4_one_time": {"forge_two_sig": forge_two_sig, "single_sig_needs_backward": need_backward,
                        "forge_one_sig": forge_one_sig, "pass": k4},
        "K3_quantum_margin": k3,
        "verdict": {"all_pass": bool(k1 and k2 and k4)},
    }
    os.makedirs("out", exist_ok=True)
    json.dump(res, open("out/results.json", "w"), indent=2, ensure_ascii=False)
    print(f"[K1] 유효 {n_ok}/{TRIALS} · 변조기각 {n_tamper}/{TRIALS} → {k1}")
    print(f"[K2] 체크섬 격리: 지배={dominates} 체크섬감소={checksum_decreased} "
          f"위조(체크섬有)={forge_with_checksum} 위조(체크섬無)={forge_no_checksum} → {k2}")
    print(f"[K4] 일회용: 두서명위조={forge_two_sig} 단일역행필요={need_backward} "
          f"단일위조={forge_one_sig} → {k4}")
    print(f"[K3] 정직한 바닥: 충돌 고전128b·양자BHT~2^85 (프리이미지 아님). "
          f"경제코어는 집행층 PQ 전제.")
    print(f"     {sv_ms:.2f} ms/op · sk/pk/sig={LEN*N}/{N}/{LEN*N} B")
    print(json.dumps(res["verdict"], ensure_ascii=False))


if __name__ == "__main__":
    main()
