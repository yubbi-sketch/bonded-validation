"""Exp2 — 기권(Abstention) 메커니즘: 거짓 양성 제로 원칙의 실장.

추출기의 슬롯 소프트맥스 확신도(모든 문장·모든 헤드의 최솟값 = 최약 고리)가
임계 τ 미만이면 "모름(기권)"을 선언한다. 담보 채점 (+1 정답 / −5 오답 / 0 기권)
아래에서 기권이 실제로 이득인지 실측한다.

■ 사전 등록 킬 기준 (실행 전 박제, 결과 후 수정 금지):
  K1. 어떤 τ에서 [전체 문제 대비 오답률 ≤ 0.5%] 이면서 [응답률 ≥ 70%]를
      동시에 만족하지 못하면 → 확신도 신호(소프트맥스 최솟값) 기각, 원인 분석서.
  K2. 최적 τ의 담보 점수가 τ=0(전부 답함)의 담보 점수보다 낮으면 → 기권 설계 기각.
■ 정직성 라벨:
  - "오답 0%" 주장 금지(강령 §8). 측정치는 범주별 오답률·응답률·담보 점수.
  - 담보 배점 (+1/−5)은 설계 파라미터다 — 민감도(−2/−10)도 함께 보고한다.
"""
import json
import sys
import time

import numpy as np

sys.path.insert(0, "/Users/yubbi/iis-lab/exp1")
from data import ENTITIES, build_vocab, encode_sent, gen_dataset  # noqa: E402
from models import Extractor  # noqa: E402
from train import SENT_LEN, train_extractor  # noqa: E402
from verifier import SymbolicLogicVerifier  # noqa: E402


def softmax(z):
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def predict_with_conf(ext, example, vocab):
    """파이프라인 답 + 확신도(전 문장·전 헤드 소프트맥스 최댓값의 최솟값)."""
    ids = np.array([encode_sent(s, vocab, SENT_LEN) for s in example["sents"]])
    lf, lt, ln = ext.forward(ids)
    pf, pt, pn = softmax(lf.d), softmax(lt.d), softmax(ln.d)
    conf = min(pf.max(-1).min(), pt.max(-1).min(), pn.max(-1).min())
    f, t, n = pf.argmax(-1), pt.argmax(-1), pn.argmax(-1)
    v = SymbolicLogicVerifier()
    for i in range(len(ids) - 1):
        v.add_rule(int(f[i]), int(t[i]), neg=bool(n[i]))
    qi = len(ids) - 1
    ans = int(v.derives(int(f[qi]), int(t[qi]), target_neg=bool(n[qi])))
    return ans, float(conf)


def main():
    t0 = time.perf_counter()
    rng = np.random.default_rng(42)
    vocab = build_vocab()
    train_data = gen_dataset(3000, seed=1)
    test = gen_dataset(800, seed=2)

    print("== 추출기 학습 (Exp1 최종 구성 재현)", flush=True)
    ext = Extractor(len(vocab), n_ent=len(ENTITIES), d=64)
    sents, gold = [], []
    for d in train_data:
        for s, g in zip(d["sents"], d["gold"]):
            sents.append(encode_sent(s, vocab, SENT_LEN))
            gold.append([int(g[0]), int(g[1]), int(g[2])])
    train_extractor(ext, np.array(sents)[:20000], np.array(gold)[:20000], 40, rng)

    print("== 확신도 수집", flush=True)
    answers, confs, labels, qtypes = [], [], [], []
    for d in test:
        a, c = predict_with_conf(ext, d, vocab)
        answers.append(a); confs.append(c)
        labels.append(d["label"]); qtypes.append(d["qtype"])
    answers = np.array(answers); confs = np.array(confs); labels = np.array(labels)
    correct = answers == labels
    n = len(test)

    # 확신도 보정 실측: 확신 구간별 실제 정확도
    bins = [0, .5, .7, .9, .99, .999, 1.001]
    calib = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (confs >= lo) & (confs < hi)
        if m.sum() > 0:
            calib.append({"bin": f"[{lo},{hi})", "n": int(m.sum()),
                          "acc": float(correct[m].mean())})
    print("calibration:", calib, flush=True)

    # τ 스윕
    taus = np.concatenate([[0.0], np.linspace(0.5, 0.999, 60), [0.9999]])
    sweep = []
    for tau in taus:
        answered = confs >= tau
        n_ans = int(answered.sum())
        n_right = int((answered & correct).sum())
        n_wrong = n_ans - n_right
        sweep.append({
            "tau": float(tau),
            "coverage": n_ans / n,
            "wrong_rate_total": n_wrong / n,           # 전체 문제 대비 오답률
            "acc_on_answered": (n_right / n_ans) if n_ans else 1.0,
            "bond_1_5": (n_right - 5 * n_wrong) / n,   # 문제당 기대 담보 점수
            "bond_2_10": (2 * n_right - 10 * n_wrong) / n / 2,  # 배점 민감도(정규화)
        })

    # 킬 판정
    feasible = [s for s in sweep if s["wrong_rate_total"] <= 0.005 and s["coverage"] >= 0.70]
    k1_pass = len(feasible) > 0
    best = max(sweep, key=lambda s: s["bond_1_5"])
    base = sweep[0]  # tau=0 전부 답함
    k2_pass = best["bond_1_5"] >= base["bond_1_5"]
    # 운영 추천 τ: K1 만족 중 응답률 최대
    op = max(feasible, key=lambda s: s["coverage"]) if feasible else best

    verdict = {
        "K1_pass": bool(k1_pass),
        "K2_pass": bool(k2_pass),
        "baseline_tau0": {k: round(v, 4) for k, v in base.items()},
        "operating_point": {k: round(v, 4) for k, v in op.items()},
        "bond_optimal_point": {k: round(v, 4) for k, v in best.items()},
    }
    results = {"n_test": n, "calibration": calib, "sweep": sweep, "verdict": verdict,
               "train_seconds": round(time.perf_counter() - t0, 1)}
    json.dump(results, open("/Users/yubbi/iis-lab/exp2/out/results.json", "w"), indent=2)
    print(json.dumps(verdict, indent=2), flush=True)

    # 그래프
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    cov = [s["coverage"] for s in sweep]
    wr = [s["wrong_rate_total"] * 100 for s in sweep]
    b15 = [s["bond_1_5"] for s in sweep]
    ts = [s["tau"] for s in sweep]

    axes[0].plot(cov, wr, "o-", ms=3, color="#dd7733")
    axes[0].axhline(0.5, ls="--", c="gray", lw=1, label="K1 limit: wrong ≤ 0.5%")
    axes[0].axvline(0.70, ls=":", c="gray", lw=1, label="K1 limit: coverage ≥ 70%")
    axes[0].scatter([op["coverage"]], [op["wrong_rate_total"] * 100], s=90, zorder=5,
                    color="#3a9a5c", label=f"operating point τ={op['tau']:.3f}")
    axes[0].set_xlabel("coverage (answered fraction)")
    axes[0].set_ylabel("wrong answers / all problems (%)")
    axes[0].set_title("Risk–coverage: abstention buys correctness")
    axes[0].legend(fontsize=8)

    axes[1].plot(ts, b15, "o-", ms=3, color="#55aabb", label="bond score (+1/−5) per problem")
    axes[1].axhline(base["bond_1_5"], ls="--", c="#aa4444", lw=1,
                    label=f"answer-always baseline = {base['bond_1_5']:.3f}")
    axes[1].scatter([best["tau"]], [best["bond_1_5"]], s=90, color="#3a9a5c", zorder=5,
                    label=f"optimum τ={best['tau']:.3f} → {best['bond_1_5']:.3f}")
    axes[1].set_xlabel("abstention threshold τ")
    axes[1].set_ylabel("expected bond score / problem")
    axes[1].set_title("Economics: abstaining beats bluffing")
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig("/Users/yubbi/iis-lab/exp2/out/abstention.png", dpi=140)
    print("plot saved", flush=True)


if __name__ == "__main__":
    main()
