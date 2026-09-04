"""Exp29 — 되묻기 루프 · 경제 렌즈 설계 검산 (킬기준 판정 아님).

목적: 설계 문서(design-economics.md §3)의 3분할 결정 규칙과 정리 후보를
실행 전에 검산한다. 킬기준 K1~K4 의 실험 자체는 이 스크립트가 아니다.

  행동  answer(담보 B, 정답 +R / 오답 −B) · abstain(0) · ask(담보 0, 비용 c, 응답률 α)
  신호  κ = 최약고리 소프트맥스(능력, Exp2 신호) · w̃ = 질의문 해석 top-1 질량(의도 확정도)
        p̃ = w̃·κ (보정 가정: 직답 시 정답확률)
  규칙  V0(q) = max(0, q(B+R) − B)   [Chow 1970 = Exp18 τ* = B/(B+R)]
        ask  ⟺ α·(V0(κ) − V0(p̃)) > c
        else answer ⟺ p̃ ≥ τ* , else abstain

검산 항목
  C1 ask 비활성(c=∞)이면 규칙 = Chow(직답 ⟺ p̃ ≥ τ*)            [격자 전수]
  C2 ask 활성 시 answer 영역 ⊆ Chow answer, abstain 영역 ⊆ Chow abstain [격자 전수]
  C3 정책 가치 ≥ Chow 가치 (점별)                                     [격자 전수]
  C4 합성 분포에서 담보점수/문제 · 커버리지 · ask율 (c, α 격자)          [표]
  Z1 [THM] τ* 불변: answer≻abstain ⟺ p ≥ B/(B+R), ask 존재와 무관       [z3 UNSAT]
  Z2 [WIT] 응답 보상 R_q > 0 이면 자문자답 시빌 쌍 순이득 > 0 가능        [z3 SAT]
  Z3 [THM] R_q = 0 이면 시빌 쌍 순이득 ≤ 0                            [z3 UNSAT]
순수 NumPy + z3, 시드 고정.
"""
import json
import os

import numpy as np
import z3

B, R = 10.0, 15.0
TAU = B / (B + R)          # 0.4
SEED = 2029
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)


def v0(q):
    return np.maximum(0.0, q * (B + R) - B)


def decide(kappa, w, c, alpha, ask_enabled=True):
    """벡터화 3분할. 반환: 0=abstain 1=answer 2=ask."""
    p = w * kappa
    chow = (p >= TAU).astype(int)
    if not ask_enabled:
        return chow
    gain = alpha * (v0(kappa) - v0(p))
    act = np.where(gain > c, 2, chow)
    return act


def value(kappa, w, c, alpha, act):
    """정책의 기대 담보점수(1라운드 근시안). ask: −c + α·V0(κ) + (1−α)·V0(p̃)."""
    p = w * kappa
    v_ans = p * (B + R) - B
    v_ask = -c + alpha * v0(kappa) + (1 - alpha) * v0(p)
    return np.where(act == 1, v_ans, np.where(act == 2, v_ask, 0.0))


def grid_checks():
    ks = np.linspace(0.0, 1.0, 201)
    ws = np.linspace(0.5, 1.0, 101)
    K, W = np.meshgrid(ks, ws, indexing="ij")
    K, W = K.ravel(), W.ravel()
    res = {}
    # C1
    chow = decide(K, W, c=np.inf, alpha=1.0)
    res["C1_ask_disabled_equals_chow"] = bool(np.array_equal(chow, ((W * K) >= TAU).astype(int)))
    # C2·C3 over (c, α) grid
    c2, c3 = True, True
    for c in (0.0, 0.5, 2.0, 5.0):
        for a in (1.0, 0.7, 0.3):
            act = decide(K, W, c, a)
            ans_sub = np.all(((act == 1) & (chow == 1)) == (act == 1))
            abs_sub = np.all(((act == 0) & (chow == 0)) == (act == 0))
            c2 &= bool(ans_sub and abs_sub)
            v_pol = value(K, W, c, a, act)
            v_chow = value(K, W, c, a, chow)
            c3 &= bool(np.all(v_pol >= v_chow - 1e-12))
    res["C2_answer_and_abstain_regions_subset_of_chow"] = c2
    res["C3_policy_value_ge_chow_pointwise"] = c3
    # 닫힌형 ask 문턱 검산: p̃ ≥ τ* 구간에서 ask ⟺ (1−w̃) > ε_q = c/(α κ (B+R))
    c, a = 2.0, 1.0
    act = decide(K, W, c, a)
    mask = (W * K) >= TAU
    eps = c / (a * np.maximum(K, 1e-9) * (B + R))
    closed = ((1 - W) > eps)
    # 경계 (1−w̃ = ε_q) 는 부동소수 동률 — 규칙·닫힌형 모두 '>' 라 경계 자체는 정의상 ask 아님. 경계 제외 비교.
    interior = mask & (np.abs((1 - W) - eps) > 1e-9)
    res["C5_closed_form_ask_threshold_matches_off_boundary"] = bool(
        np.array_equal(act[interior] == 2, closed[interior]))
    res["C5_boundary_ties_excluded"] = int((mask & ~interior).sum())
    return res


def synthetic_table(rng):
    """합성 (κ, w̃) 분포 — 설계 검산용(실데이터 아님). Exp2 보정 표를 흉내: κ 대부분 높음."""
    n = 200_000
    hi = rng.beta(20, 1.2, n)
    lo = rng.uniform(0.3, 0.9, n)
    kappa = np.where(rng.random(n) < 0.85, hi, lo)
    amb = rng.random(n) < 0.30
    w = np.where(amb, rng.uniform(0.5, 0.8, n), 1.0)
    rows = []
    chow = decide(kappa, w, np.inf, 1.0)
    p = w * kappa
    rows.append({
        "policy": "chow(abstain-only, Exp2/18)", "c": None, "alpha": None,
        "score_per_problem": float(value(kappa, w, 0, 1, chow).mean()),
        "coverage": float((chow == 1).mean()), "ask_rate": 0.0,
        "expected_wrong_rate": float(((1 - p) * (chow == 1)).mean()),
        "coverage_on_ambiguous": float((chow[amb] == 1).mean()),
    })
    for c in (0.5, 2.0):
        for a in (1.0, 0.5):
            act = decide(kappa, w, c, a)
            # ask 후 최종 커버리지: 응답(α) 시 κ≥τ* 면 답, 무응답 시 Chow(p̃)
            final_cov = (act == 1).mean() + ((act == 2) * (a * (kappa >= TAU) + (1 - a) * (p >= TAU))).mean()
            # 기대 오답률: 직답 (1−p̃); ask 후 응답 답변 (1−κ); 무응답 폴백 (1−p̃)
            wrong = ((act == 1) * (1 - p)).mean() + ((act == 2) * (a * (kappa >= TAU) * (1 - kappa)
                     + (1 - a) * (p >= TAU) * (1 - p))).mean()
            rows.append({
                "policy": "ask-loop(myopic EVPI)", "c": c, "alpha": a,
                "score_per_problem": float(value(kappa, w, c, a, act).mean()),
                "coverage": float(final_cov), "ask_rate": float((act == 2).mean()),
                "expected_wrong_rate": float(wrong),
                "coverage_on_ambiguous": float(((act[amb] == 1) | (act[amb] == 2)).mean()),
            })
    return rows


def z3_checks():
    out = {}
    s = z3.Solver()
    p, b, r = z3.Reals("p b r")
    s.add(b > 0, r > 0, p >= 0, p <= 1)
    pref = p * r - (1 - p) * b >= 0
    thr = p >= b / (b + r)
    s.add(z3.Xor(pref, thr))            # 둘이 다른 (p,b,r) 존재?
    out["Z1_tau_star_invariant_UNSAT"] = (s.check() == z3.unsat)

    # 시빌 쌍: 같은 주체가 질문·응답. 응답 보상 R_q, 질문 가스 g_q>0, 응답 가스 g_r>0.
    s2 = z3.Solver()
    rq, gq, gr = z3.Reals("rq gq gr")
    s2.add(gq > 0, gr > 0, rq > 0)
    s2.add(rq - gq - gr > 0)
    out["Z2_response_reward_enables_sybil_farm_SAT"] = (s2.check() == z3.sat)
    if s2.check() == z3.sat:
        m = s2.model()
        out["Z2_witness"] = {str(d): str(m[d]) for d in m.decls()}

    s3 = z3.Solver()
    rq3, gq3, gr3 = z3.Reals("rq3 gq3 gr3")
    s3.add(gq3 > 0, gr3 > 0, rq3 == 0)
    s3.add(rq3 - gq3 - gr3 > 0)
    out["Z3_zero_response_reward_no_farm_UNSAT"] = (s3.check() == z3.unsat)
    return out


def main():
    rng = np.random.default_rng(SEED)
    res = {"params": {"B": B, "R": R, "tau_star": TAU, "seed": SEED},
           "grid": grid_checks(), "synthetic": synthetic_table(rng), "z3": z3_checks(),
           "label": "설계 검산 — 킬기준 판정 아님. 합성 (κ,w̃) 분포는 실데이터가 아니다."}
    json.dump(res, open(os.path.join(OUT, "policy_econ.json"), "w"), indent=2, ensure_ascii=False)
    print("τ* =", TAU)
    print("grid:", json.dumps(res["grid"], ensure_ascii=False))
    print("z3  :", json.dumps({k: v for k, v in res["z3"].items() if k != "Z2_witness"}, ensure_ascii=False))
    for row in res["synthetic"]:
        print(f"{row['policy']:<32} c={row['c']} α={row['alpha']}  score={row['score_per_problem']:.3f} "
              f"cov={row['coverage']:.3f} ask={row['ask_rate']:.3f} wrong={row['expected_wrong_rate']:.4f} "
              f"cov_amb={row['coverage_on_ambiguous']:.3f}")


if __name__ == "__main__":
    main()
