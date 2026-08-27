"""Exp23 — 프로덕션 STARK 이식의 골든 레퍼런스: 정수 전용 추출기 순전파.

프로덕션 STARK/zkVM(risc0/plonky2 등)은 실수 아니라 정수를 증명한다. ezkl은
고정소수점 회로였고(Exp14/16), zkVM 게스트는 순수 정수 프로그램이다. 이 파일은
그 게스트가 정확히 재현해야 할 **정수 전용 순전파**를 파이썬 i64로 명세하고,
float argmax와의 일치를 실측한다. prover에 독립인 이식의 진짜 핵심.

명세: scale S=2^11(ezkl param_scale=11 일치). 가중치·활성은 정수, 곱 후 S로
재스케일(내림 나눗셈=결정론). tanh는 정수 룩업(입력 범위 실측 [-125134,90620]).
누적 폭: 79k MAC × (2^11)^2 ≈ 2^39 < i64 — 오버플로 없음.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, "../exp1")
from data import ENTITIES, build_vocab, encode_sent, gen_dataset  # noqa: E402
from models import Extractor  # noqa: E402
from train import SENT_LEN, train_extractor  # noqa: E402

S = 1 << 11            # 고정소수점 스케일 (ezkl param_scale=11)
D = 64
TANH_LO, TANH_HI = -125134, 90620   # ezkl 실측 룩업 범위


def q(x):  # float → 정수 고정소수점
    return int(round(x * S))


def qv(a):
    return [q(x) for x in np.asarray(a).ravel()]


def rescale(x):  # 곱 후 스케일 복원 (결정론 내림)
    return x // S if x >= 0 else -((-x) // S)


def build_tanh_lut():
    """정수 tanh 룩업: 입력(스케일 S) → 출력(스케일 S). zkVM에선 이 표를 증명 대상에 포함."""
    lut = {}
    for xi in range(TANH_LO, TANH_HI + 1):
        lut[xi] = q(np.tanh(xi / S))
    return lut


def int_forward(ext, ids, TANH):
    """정수 전용 추출기 순전파 — zkVM 게스트가 재현할 명세. 입력 ids(정수 토큰)."""
    E = [qv(ext.E.d[i]) for i in range(ext.E.d.shape[0])]
    g = qv(ext.g.d); Win = [qv(ext.Win.d[i]) for i in range(D)]
    a_gate = q(1.0 / (1.0 + np.exp(-ext.a_raw.d[0])))  # 게이트 상수(접힘)
    # per-dim 게이트: 벡터
    a_vec = [q(1.0 / (1.0 + np.exp(-v))) for v in ext.a_raw.d]
    b_vec = qv(ext.b.d)
    a2_vec = [q(1.0 / (1.0 + np.exp(-v))) for v in ext.a2_raw.d]
    b2_vec = qv(ext.b2.d)
    Wm = [qv(ext.Wm.d[i]) for i in range(D)]
    Wl = [qv(ext.Wl.d[i]) for i in range(D)]
    Wl2 = [qv(ext.Wl2.d[i]) for i in range(D)]
    Wfrom = [qv(ext.Wfrom.d[i]) for i in range(D)]
    Wto = [qv(ext.Wto.d[i]) for i in range(D)]
    Wneg = [qv(ext.Wneg.d[i]) for i in range(D)]

    T = len(ids)
    x = [E[t] for t in ids]                       # 임베딩 룩업 (정수)
    # rmsnorm: ms = mean(x^2); inv = 1/sqrt(ms+eps) — 정수 근사(부동소수 rsqrt를
    # 스케일 유지 정수로). zkVM에선 rsqrt를 룩업/제약으로. 여기선 결정론 정수 계산.
    u = []
    for t in range(T):
        ms = sum((xi * xi) for xi in x[t]) // D          # 스케일 S^2
        inv = int(round(S * S / (np.sqrt(ms / (S * S)) * S + 1e-12))) if ms > 0 else S
        xn = [rescale(rescale(x[t][k] * inv) * g[k]) for k in range(D)]
        # Win 투영
        ut = [rescale(sum(xn[k] * Win[k][j] for k in range(D))) for j in range(D)]
        u.append(ut)
    # 정방향 스캔
    h = [0] * D; acc = [0] * D
    for t in range(T):
        h = [rescale(h[k] * a_vec[k]) + rescale(u[t][k] * b_vec[k]) for k in range(D)]
        acc = [acc[k] + h[k] for k in range(D)]
    # 역방향 스캔
    h2 = [0] * D
    for t in range(T - 1, -1, -1):
        h2 = [rescale(h2[k] * a2_vec[k]) + rescale(u[t][k] * b2_vec[k]) for k in range(D)]
    accm = [acc[k] // T for k in range(D)]
    pre = []
    for j in range(D):
        s = (sum(accm[k] * Wm[k][j] for k in range(D))
             + sum(h[k] * Wl[k][j] for k in range(D))
             + sum(h2[k] * Wl2[k][j] for k in range(D)))
        pre.append(rescale(s))
    enc = [TANH.get(max(TANH_LO, min(TANH_HI, p)), q(np.tanh(p / S))) for p in pre]
    log_from = [rescale(sum(enc[k] * Wfrom[k][j] for k in range(D))) for j in range(len(ENTITIES))]
    log_to = [rescale(sum(enc[k] * Wto[k][j] for k in range(D))) for j in range(len(ENTITIES))]
    log_neg = [rescale(sum(enc[k] * Wneg[k][j] for k in range(D))) for j in range(2)]
    return log_from, log_to, log_neg


def main():
    rng = np.random.default_rng(2026)
    vocab = build_vocab()
    train = gen_dataset(3000, seed=1); test = gen_dataset(800, seed=2)
    ext = Extractor(len(vocab), n_ent=len(ENTITIES), d=D)
    sents, gold = [], []
    for ex in train:
        for s, gd in zip(ex["sents"], ex["gold"]):
            sents.append(encode_sent(s, vocab, SENT_LEN)); gold.append([int(x) for x in gd])
    train_extractor(ext, np.array(sents)[:20000], np.array(gold)[:20000], 40, rng)

    ts = []
    for ex in test:
        for s, _ in zip(ex["sents"], ex["gold"]):
            ts.append(encode_sent(s, vocab, SENT_LEN))
    ts = np.array(ts[:100])

    TANH = build_tanh_lut()
    match = 0; max_abs = 0
    for i in range(len(ts)):
        ids = [int(t) for t in ts[i]]
        lf, lt, ln = int_forward(ext, ids, TANH)
        ff, ft, fn = ext.forward(ts[i:i + 1])
        max_abs = max(max_abs, max(abs(v) for v in lf + lt + ln))
        if (int(np.argmax(lf)) == int(ff.d.argmax()) and
                int(np.argmax(lt)) == int(ft.d.argmax()) and
                int(np.argmax(ln)) == int(fn.d.argmax())):
            match += 1
    rate = match / len(ts)
    acc_bits = max_abs.bit_length()
    res = {
        "scale": S, "param_scale_ezkl": 11, "n_test": len(ts),
        "int_vs_float_argmax_match": match, "match_rate": rate,
        "max_abs_logit_int": max_abs, "logit_bits": acc_bits,
        "accumulator_note": "79k MAC × (2^11)^2 ≈ 2^39 < i64(63b) — 오버플로 없음",
        "tanh_lut_size": len(TANH), "tanh_range": [TANH_LO, TANH_HI],
        "verdict": {"golden_ref_matches_float": bool(rate >= 0.95)},
        "honesty": "정수 전용 명세 = zkVM 게스트가 재현할 계산(prover 독립). rsqrt는 "
                   "결정론 정수 근사(게스트에선 룩업/제약으로 대체). 프로덕션 prover 실행은 "
                   "Rust 툴체인 필요 — 이 환경엔 없음(별도 머신).",
    }
    os.makedirs("out", exist_ok=True)
    json.dump(res, open("out/results.json", "w"), indent=2, ensure_ascii=False)
    print(f"정수 argmax == float argmax: {match}/{len(ts)} = {rate:.0%}")
    print(f"최대 로짓 정수 {max_abs} ({acc_bits}비트) · tanh LUT {len(TANH)}개")
    print(json.dumps(res["verdict"], ensure_ascii=False))


if __name__ == "__main__":
    main()
