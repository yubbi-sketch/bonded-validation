"""Exp10 — P3 zkML 정찰: 24k 추출기는 ZK 회로에 올라가는가.

질문: "소수=틀림"의 온체인 증명(판정자가 추출기 재실행을 zk로 증명)으로 가는
첫 관문 — 우리 추출기(Exp1, 24,384 파라미터)가 ZK 친화적인가를 실측한다.
전체 회로 구현은 이 정찰의 범위가 아니다. 측정만 한다:

  A. 고정소수점 양자화 생존성 — ZK 회로는 정수 연산만 한다. float 추출기를
     스케일 2^f 고정소수점으로 접었을 때 슬롯 정확도가 살아남는가. (실측)
  B. 회로 규모 — 순전파 1회의 MAC·비선형 수를 정확히 세고, halo2/ezkl식
     제약 행수를 보수적으로 추정한다. (계산이지 실측 아님 — 명기)

■ 사전 등록 킬 기준 (실행 전 박제):
  K1. f=12 (스케일 4096) 양자화에서 슬롯 정확도 하락 > 1%p → "양자화 재학습
      필요" 판정 (즉시 기각은 아니고 다음 단계 비용이 늘어남을 등재).
  K2. 추정 제약 행수 > 2^24 → 노트북 증명 불가 판정, P3 접근 재설계.
■ 정직성 라벨:
  - B의 행수 추정은 ezkl 공개 벤치마크와의 자릿수 비교용 근사치다. 증명 시간
    실측은 ezkl 툴체인 이식(다음 단계) 몫이다.
  - 비선형(sigmoid·tanh·rsqrt)은 룩업 테이블 가정 — ezkl의 실제 방식.

재현: python3 recon.py  (시드 고정, ~1분)
"""
import json
import sys
import time

import numpy as np

sys.path.insert(0, "../exp1")
from autograd import Adam, cross_entropy  # noqa: E402
from data import ENTITIES, build_vocab, encode_sent, gen_dataset  # noqa: E402
from models import Extractor  # noqa: E402
from train import SENT_LEN, train_extractor  # noqa: E402

D = 64
FRACS = [8, 10, 12, 14]  # 고정소수점 소수부 비트 후보


def quant(x, f):
    """스케일 2^f 고정소수점 시뮬레이션 (fake quantization)."""
    s = float(1 << f)
    return np.round(x * s) / s


def forward_quantized(ext, ids, f):
    """Extractor.forward의 정수 회로 시뮬레이션 — 모든 가중치와 각 연산 뒤
    활성값을 2^-f 격자로 스냅. 비선형은 '양자화 입력 → 양자화 출력' 룩업 가정."""
    E = quant(ext.E.d, f)
    g = quant(ext.g.d, f)
    Win = quant(ext.Win.d, f)
    Wm = quant(ext.Wm.d, f)
    Wl = quant(ext.Wl.d, f)
    Wl2 = quant(ext.Wl2.d, f)
    Wfrom = quant(ext.Wfrom.d, f)
    Wto = quant(ext.Wto.d, f)
    Wneg = quant(ext.Wneg.d, f)
    # 게이트 a=sigmoid(a_raw)는 상수 — 회로 컴파일 시점에 접어둔다(비선형 0개)
    a = quant(1.0 / (1.0 + np.exp(-ext.a_raw.d)), f)
    b = quant(ext.b.d, f)
    a2 = quant(1.0 / (1.0 + np.exp(-ext.a2_raw.d)), f)
    b2 = quant(ext.b2.d, f)

    B, T = ids.shape
    x = E[ids]                                   # (B,T,D) 임베딩 룩업
    ms = (x * x).mean(axis=-1, keepdims=True)
    inv = quant(1.0 / np.sqrt(ms + 1e-8), f)     # rsqrt — 룩업
    u = quant(quant(x * inv * g, f) @ Win, f)
    h = np.zeros((B, D)); acc = np.zeros((B, D))
    for t in range(T):
        h = quant(h * a + u[:, t] * b, f)
        acc = quant(acc + h, f)
    h2 = np.zeros((B, D))
    for t in range(T - 1, -1, -1):
        h2 = quant(h2 * a2 + u[:, t] * b2, f)
    pre = quant(quant(acc * (1.0 / T), f) @ Wm + h @ Wl + h2 @ Wl2, f)
    enc = quant(np.tanh(pre), f)                 # tanh — 룩업
    return enc @ Wfrom, enc @ Wto, enc @ Wneg


def op_census(T=SENT_LEN, d=D, n_ent=len(ENTITIES)):
    """순전파 1회(문장 1개)의 정확한 연산 수."""
    macs = {
        "rmsnorm_scale": T * d,          # x*inv*g
        "proj_Win": T * d * d,
        "scan_fwd": T * d * 2,           # h*a + u*b
        "scan_acc": T * d,
        "scan_bwd": T * d * 2,
        "enc_3matmul": 3 * d * d,
        "heads": d * (2 * n_ent + 2),
    }
    lookups = {
        "embedding_rows": T,
        "rsqrt": T,                      # 문장당 T개 (토큰별 rmsnorm)
        "tanh": d,
    }
    return macs, lookups


def estimate_rows(macs_total, lookups_total, rows_per_mac=4, rows_per_lookup=2):
    """halo2/ezkl식 보수 추정 — MAC당 4행(양자화 재스케일 포함), 룩업당 2행.
    근사치임을 결과에 명기한다."""
    return macs_total * rows_per_mac + lookups_total * rows_per_lookup


def main():
    t0 = time.perf_counter()
    rng = np.random.default_rng(2026)
    vocab = build_vocab()
    train = gen_dataset(3000, seed=1)
    test = gen_dataset(800, seed=2)

    ext = Extractor(len(vocab), n_ent=len(ENTITIES), d=D)
    sents, gold = [], []
    for ex in train:
        for s, gd in zip(ex["sents"], ex["gold"]):
            sents.append(encode_sent(s, vocab, SENT_LEN))
            gold.append([int(gd[0]), int(gd[1]), int(gd[2])])
    sents = np.array(sents); gold = np.array(gold)
    cap = min(len(gold), 20000)
    print("== 추출기 학습 (Exp1 설정 재현)", flush=True)
    train_extractor(ext, sents[:cap], gold[:cap], 40, rng)

    ts, tg = [], []
    for ex in test:
        for s, gd in zip(ex["sents"], ex["gold"]):
            ts.append(encode_sent(s, vocab, SENT_LEN))
            tg.append([int(gd[0]), int(gd[1]), int(gd[2])])
    ts = np.array(ts); tg = np.array(tg)

    lf, lt, ln = ext.forward(ts)
    def slot_acc(pf, pt, pn):
        ok = ((pf.argmax(-1) == tg[:, 0]) & (pt.argmax(-1) == tg[:, 1])
              & (pn.argmax(-1) == tg[:, 2]))
        return float(ok.mean())
    acc_float = slot_acc(lf.d, lt.d, ln.d)
    print(f"== float 슬롯 정확도: {acc_float:.4f} (n={len(tg)})", flush=True)

    quant_results = {}
    for f in FRACS:
        qf, qt_, qn = forward_quantized(ext, ts, f)
        a = slot_acc(qf, qt_, qn)
        quant_results[f] = {"slot_acc": round(a, 4),
                            "drop_pp": round((acc_float - a) * 100, 2)}
        print(f"   f={f:2d} (스케일 {1<<f:5d}): {a:.4f} (하락 {quant_results[f]['drop_pp']}%p)",
              flush=True)

    macs, lookups = op_census()
    macs_total = sum(macs.values())
    lookups_total = sum(lookups.values())
    rows = estimate_rows(macs_total, lookups_total)
    print(f"== 회로 규모: MAC {macs_total:,} · 룩업 {lookups_total} · "
          f"추정 행수 {rows:,} (≈2^{int(np.ceil(np.log2(rows)))})", flush=True)

    k1_pass = quant_results[12]["drop_pp"] <= 1.0
    k2_pass = rows <= (1 << 24)
    verdict = {
        "K1_quant_f12_drop_pp": quant_results[12]["drop_pp"],
        "K1_pass": bool(k1_pass),
        "K2_estimated_rows": rows,
        "K2_rows_log2": int(np.ceil(np.log2(rows))),
        "K2_pass": bool(k2_pass),
        "go": bool(k1_pass and k2_pass),
    }
    out = {
        "float_slot_acc": round(acc_float, 4),
        "n_test_sentences": int(len(tg)),
        "quantization": quant_results,
        "op_census": {"macs": macs, "lookups": lookups,
                      "macs_total": macs_total, "lookups_total": lookups_total},
        "row_estimate": {"rows": rows,
                         "assumptions": "MAC당 4행 + 룩업당 2행 (보수적 근사 — 실측 아님)"},
        "verdict": verdict,
        "runtime_seconds": round(time.perf_counter() - t0, 1),
        "seed": 2026,
    }
    import os
    os.makedirs("out", exist_ok=True)
    with open("out/results.json", "w") as fp:
        json.dump(out, fp, indent=2, ensure_ascii=False)
    print(json.dumps(verdict, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
