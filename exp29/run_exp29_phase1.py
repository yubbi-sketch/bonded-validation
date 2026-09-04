"""Exp29 Phase 1 — 오프라인 NumPy 시뮬레이션. 사전등록 킬기준 K1·K2 실측(EXP29.md §5-6).

추출기: Exp1/Exp2 와 동일 절차(같은 seed·같은 학습 데이터·같은 에폭)로 재학습 없이 재현 —
단 임베딩 테이블은 Exp29 확장 어휘(build_vocab_readings)로 잡는다(신규 토큰 없이는
encode_sent 가 KeyError). 신규 토큰 행은 Exp1 학습 데이터에 등장하지 않으므로 그래디언트를
받지 않는다 — "재학습 없이 재사용"의 실제 구현.

정책 5종: speak_always · abstain_only(Chow/WALLA 대조군 1, U_ask 배제) · ask_policy(우리) ·
ask_always(Mirage 스팸) · oracle(θ* 를 아는 상한).

재현: python3 run_exp29_phase1.py
"""
import json
import sys
import time

import numpy as np

sys.path.insert(0, "/Users/yubbi/iis-lab/exp1")
from data import ENTITIES, build_vocab, encode_sent, gen_dataset  # noqa: E402
from models import Extractor  # noqa: E402
from train import train_extractor  # noqa: E402
from verifier import SymbolicLogicVerifier  # noqa: E402

from data_readings import (  # noqa: E402
    build_vocab_readings, gen_dataset_readings, resolve, simulated_counterpart,
)
from policy import decide  # noqa: E402

SENT_LEN = 24  # Exp29 최장 문장(22토큰) 여유 포함; Exp1 원문(≤14)은 패딩만 늘어남


def softmax(z):
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def predict_with_conf(ext, sents, vocab):
    ids = np.array([encode_sent(s, vocab, SENT_LEN) for s in sents])
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


def train_frozen_extractor(vocab):
    rng = np.random.default_rng(42)
    ext = Extractor(len(vocab), n_ent=len(ENTITIES), d=64)
    train_data = gen_dataset(3000, seed=1)
    sents, gold = [], []
    for d in train_data:
        for s, g in zip(d["sents"], d["gold"]):
            sents.append(encode_sent(s, vocab, SENT_LEN))
            gold.append([int(g[0]), int(g[1]), int(g[2])])
    train_extractor(ext, np.array(sents)[:20000], np.array(gold)[:20000], 40, rng)
    return ext


def readings_AC(ext, vocab, readings):
    A = np.zeros(len(readings))
    C = np.zeros(len(readings))
    for i, r in enumerate(readings):
        A[i], C[i] = predict_with_conf(ext, r, vocab)
    return A, C


def run_episode(ex, policy, B, R, kappa, delta, n_max, ext, vocab, rng, control=False):
    """단일 문제 1스레드 실행. 반환 dict(score, wrong, asked, depth, vacuous_ask, legit_decisive_pred)."""
    if control:
        readings = [ex["sents"]]
        labels = [int(ex["label"])]
        theta = 0
        decisive = False  # k=1, "결정성" 개념 자체가 없음(단일 해석)
    else:
        readings = ex["readings"]
        labels = [int(x) for x in ex["labels"]]
        theta = int(ex["theta"])
        decisive = bool(ex["decisive"])

    A, C = readings_AC(ext, vocab, readings)
    legit_decisive_pred = bool(len(set(A.tolist())) > 1) if len(A) > 1 else False

    k = len(A)
    p = np.ones(k) / k
    cur_A, cur_C, cur_p = A, C, p
    cur_true_label = labels[theta]
    depth = 0
    score = 0.0
    asked_any = False
    vacuous_ask = False

    while True:
        kk = len(cur_A)
        mass1 = float(cur_p[cur_A == 1].sum())
        lhat = 1 if mass1 >= 0.5 else 0

        if policy == "oracle":
            score += R
            return dict(score=score, wrong=False, asked=asked_any, depth=depth,
                        vacuous_ask=vacuous_ask, legit_decisive_pred=legit_decisive_pred)

        if policy == "speak_always":
            act = "speak"
        elif policy == "abstain_only":
            q_speak = float(cur_C.min()) * max(mass1, 1.0 - mass1)
            act = "speak" if (q_speak * R - (1.0 - q_speak) * B) > 0 else "abstain"
        elif policy == "ask_policy":
            act, _, _ = decide(cur_p, cur_A, cur_C, B, R, kappa, delta)
        elif policy == "ask_always":
            act = "ask" if (kk > 1 and depth < n_max) else "speak"
        else:
            raise ValueError(policy)

        if act == "abstain":
            return dict(score=score, wrong=False, asked=asked_any, depth=depth,
                        vacuous_ask=vacuous_ask, legit_decisive_pred=legit_decisive_pred)

        if act == "speak":
            correct = (lhat == cur_true_label)
            score += R if correct else -B
            return dict(score=score, wrong=not correct, asked=asked_any, depth=depth,
                        vacuous_ask=vacuous_ask, legit_decisive_pred=legit_decisive_pred)

        # act == "ask"
        asked_any = True
        score -= kappa
        depth += 1
        if kk > 1 and not decisive:
            vacuous_ask = True  # R8: 갈리지 않는 곳에서 물었다 = vacuous
        answered_theta = None if control else simulated_counterpart(ex, delta, rng)
        if answered_theta is None or depth > n_max:
            return dict(score=score, wrong=False, asked=asked_any, depth=depth,
                        vacuous_ask=vacuous_ask, legit_decisive_pred=legit_decisive_pred)
        pinned_sents, pinned_label = resolve(ex, answered_theta)
        a_i, c_i = predict_with_conf(ext, pinned_sents, vocab)
        cur_A, cur_C, cur_p = np.array([a_i]), np.array([c_i]), np.array([1.0])
        cur_true_label = pinned_label
        # loop: 재판정(다음 반복에서 speak/abstain/ask 재평가, 보통 depth<=1 에서 종결)


def summarize(rows, n):
    asked = sum(r["asked"] for r in rows)
    wrong = sum(r["wrong"] for r in rows)
    vac = sum(r["vacuous_ask"] for r in rows if r["asked"])
    return dict(
        n=n,
        bond_per_problem=round(sum(r["score"] for r in rows) / n, 4),
        wrong_rate_total=round(wrong / n, 5),
        ask_rate=round(asked / n, 4),
        vacuous_ask_rate=round(vac / max(asked, 1), 4),
        depth_hist={d: sum(1 for r in rows if r["depth"] == d) for d in sorted(set(r["depth"] for r in rows))},
    )


def main():
    t0 = time.perf_counter()
    vocab = build_vocab_readings()
    print("== 추출기 학습(Exp1/Exp2 절차 재현, 확장어휘 임베딩)", flush=True)
    ext = train_frozen_extractor(vocab)

    print("== 데이터 생성", flush=True)
    ambig = gen_dataset_readings(900, seed=29, decisive_share=0.5)
    control = gen_dataset(800, seed=2)
    rng_sim = np.random.default_rng(2029)

    PARAM_SETS = [(5.0, 1.0), (2.0, 3.0)]
    KAPPAS = [0.0, 0.05, 0.1, 0.2]
    N_MAX = 2

    results = {"n_ambig": len(ambig), "n_control": len(control), "sweeps": [], "delta0_rows": []}

    # 사전계산: 예제별 (A,C,legit_decisive_pred) 캐시 — 정책과 무관, 재사용
    print("== 예제별 추출기 추론 캐시(900+800문제 × 해석수)", flush=True)
    ac_cache_ambig = [readings_AC(ext, vocab, ex["readings"]) for ex in ambig]
    legit_pred = [bool(len(set(A.tolist())) > 1) if len(A) > 1 else False for A, C in ac_cache_ambig]
    legit_true = [bool(ex["decisive"]) for ex in ambig]
    k2a_agree = sum(int(p == t) for p, t in zip(legit_pred, legit_true)) / len(ambig)

    for (B, R) in PARAM_SETS:
        for kappa in KAPPAS:
            for delta in (1.0, 0.5):
                row = {"B": B, "R": R, "kappa": kappa, "delta": delta}
                for policy in ("speak_always", "abstain_only", "ask_policy", "ask_always"):
                    rows = [run_episode(ex, policy, B, R, kappa, delta, N_MAX, ext, vocab, rng_sim)
                            for ex in ambig]
                    row[policy] = summarize(rows, len(ambig))
                results["sweeps"].append(row)
            # delta=0 박제(K1d) — ask_policy 만
            rows0 = [run_episode(ex, "ask_policy", B, R, kappa, 0.0, N_MAX, ext, vocab, rng_sim)
                     for ex in ambig]
            results["delta0_rows"].append({"B": B, "R": R, "kappa": kappa,
                                            "ask_policy_delta0": summarize(rows0, len(ambig))})

    # 대조군 Exp1 800문제 — ask_policy 의 ask 율(K1c), B=5,R=1 kappa=0.05 delta=1 기준
    B, R, kappa, delta = 5.0, 1.0, 0.05, 1.0
    ctrl_rows = [run_episode({"sents": d["sents"], "label": d["label"]}, "ask_policy",
                              B, R, kappa, delta, N_MAX, ext, vocab, rng_sim, control=True)
                 for d in control]
    ctrl_summary = summarize(ctrl_rows, len(control))
    results["control_ask_policy"] = {"B": B, "R": R, "kappa": kappa, "delta": delta, **ctrl_summary}

    # ---- 킬기준 판정 ----
    def get(policy_name, B, R, kappa, delta):
        for row in results["sweeps"]:
            if row["B"] == B and row["R"] == R and row["kappa"] == kappa and row["delta"] == delta:
                return row[policy_name]
        return None

    verdict = {}
    # K1(a): decisive 부분집합 이득 — decisive만 필터링해서 재계산 필요 -> 별도 pass
    decisive_idx = [i for i, ex in enumerate(ambig) if ex["decisive"]]

    def summarize_subset(policy, B, R, kappa, delta, idxs):
        rows = [run_episode(ambig[i], policy, B, R, kappa, delta, N_MAX, ext, vocab, rng_sim) for i in idxs]
        return summarize(rows, len(idxs))

    k1a_gains = {}
    for (B, R) in PARAM_SETS:
        for kappa in KAPPAS:
            ask_dec = summarize_subset("ask_policy", B, R, kappa, 1.0, decisive_idx)
            abst_dec = summarize_subset("abstain_only", B, R, kappa, 1.0, decisive_idx)
            gain_dec = ask_dec["bond_per_problem"] - abst_dec["bond_per_problem"]
            ask_all = get("ask_policy", B, R, kappa, 1.0)
            abst_all = get("abstain_only", B, R, kappa, 1.0)
            gain_all = ask_all["bond_per_problem"] - abst_all["bond_per_problem"]
            k1a_gains[f"B{B}_R{R}_k{kappa}"] = {"gain_decisive": round(gain_dec, 4),
                                                 "gain_all": round(gain_all, 4)}
    min_gain_at_005 = min(v["gain_decisive"] for k, v in k1a_gains.items() if "_k0.05" in k)
    all_kappa_min_gain = min(v["gain_decisive"] for v in k1a_gains.values())
    verdict["K1a"] = {
        "gain_decisive_at_kappa0.05_min_over_BR": round(min_gain_at_005, 4),
        "gain_all_kappa_le_0.1_nonneg": all(v["gain_all"] >= 0 for k, v in k1a_gains.items()
                                             if float(k.split("_k")[1]) <= 0.1),
        "min_gain_over_all_kappa_grid": round(all_kappa_min_gain, 4),
        "pass_ge_0.10": bool(min_gain_at_005 >= 0.10),
        "kill_lt_0.05_anywhere": bool(all_kappa_min_gain < 0.05),
        "detail": k1a_gains,
    }
    worst_wrong = max(get("ask_policy", B, R, k, 1.0)["wrong_rate_total"]
                       for (B, R) in PARAM_SETS for k in KAPPAS)
    verdict["K1b"] = {"worst_wrong_rate_total": round(worst_wrong, 5), "pass_le_0.005": bool(worst_wrong <= 0.005)}
    verdict["K1c"] = {"control_ask_rate": ctrl_summary["ask_rate"], "pass_le_0.02": bool(ctrl_summary["ask_rate"] <= 0.02)}
    verdict["K1d"] = {"rows": results["delta0_rows"]}
    verdict["K2a"] = {"agreement_rate": round(k2a_agree, 4), "pass_ge_0.98": bool(k2a_agree >= 0.98)}

    spam_flag_rate_num, spam_flag_rate_den = 0, 0
    for i, ex in enumerate(ambig):
        if not ex["decisive"]:
            spam_flag_rate_den += 1
            if legit_pred[i] is False:
                spam_flag_rate_num += 1
    spam_flag_rate = spam_flag_rate_num / max(spam_flag_rate_den, 1)
    spam_score = get("ask_always", 5.0, 1.0, 0.05, 1.0)["bond_per_problem"]
    honest_score = get("ask_policy", 5.0, 1.0, 0.05, 1.0)["bond_per_problem"]
    verdict["K2b"] = {"vacuous_flagged_rate": round(spam_flag_rate, 4),
                       "spam_bond_per_problem": spam_score, "honest_ask_bond_per_problem": honest_score,
                       "pass": bool(spam_flag_rate >= 0.95 and spam_score <= honest_score)}

    results["verdict"] = verdict
    results["train_seconds"] = round(time.perf_counter() - t0, 1)

    import os
    os.makedirs("out", exist_ok=True)
    json.dump(results, open("out/phase1_results.json", "w"), indent=2, ensure_ascii=False)
    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    print(f"\ndone in {results['train_seconds']}s -> out/phase1_results.json")


if __name__ == "__main__":
    main()
