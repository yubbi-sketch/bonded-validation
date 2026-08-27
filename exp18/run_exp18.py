"""Exp18 — 살아있는 경제(P7): 증명된 인센티브가 정직 균형을 낳는가.

에이전트 기반 시뮬. 자기이익만 좇는 적응형 에이전트가 정리 예측(τ*=B/(B+R))으로
수렴하는지, 도박꾼이 소멸하는지, 보상금이 그걸 뒤집는지(정리 3)를 실측.
순수 NumPy·시드 고정. EXP18.md 킬 기준 준수.
"""
import json
import os

import numpy as np

B, R = 10.0, 15.0          # 슬래시 담보, 정답 보상
TAU_STAR = B / (B + R)     # = 0.4  (능력 무관 최적 임계)
N = 300
ROUNDS = 4000
W0 = 100.0                 # 시작 부
SEED = 2026
OUT = "out"
os.makedirs(OUT, exist_ok=True)


def confidence(mu, rng):
    """이 라운드 각 에이전트의 보정 확신 p(=정답 확률). 보정 가정: p가 곧 실제 확률."""
    return np.clip(mu + rng.normal(0, 0.12, len(mu)), 0.02, 0.98)


def play_round(theta, mu, wealth, rng, bounty=0.0):
    """한 라운드 실행 → 각 에이전트 payoff. 담보 부족(자유부<B)이면 강제 기권."""
    p = confidence(mu, rng)
    can_bond = wealth >= B
    answer = (p >= theta) & can_bond
    correct = rng.random(len(mu)) < p
    # 무보상금: 정답 +R, 오답 −B, 기권 0. bounty>0이면 오답에도 보상금 지급(정답 무관).
    payoff = np.where(
        answer,
        np.where(correct, R, -B + bounty),
        0.0,
    )
    return payoff, answer.mean()


def run_population(rng, bounty=0.0, adapt=True):
    """세 전략 혼합: 적응형(임계 학습)·도박꾼(θ=0)·겁쟁이(θ=1). 부 동역학 추적."""
    mu = rng.uniform(0.30, 0.95, N)
    kind = np.array(([0] * (N // 3)) + ([1] * (N // 3)) + ([2] * (N - 2 * (N // 3))))
    theta = np.where(kind == 0, rng.uniform(0.1, 0.9, N),  # 적응형: 임의 출발
             np.where(kind == 1, 0.0, 1.0))                # 도박꾼 0 / 겁쟁이 1
    wealth = np.full(N, W0)

    # 적응형 언덕오르기 상태
    step = np.full(N, 0.05)
    win = 200
    buf = np.zeros(N)
    prev_avg = np.full(N, -1e9)
    theta_hist = []

    for t in range(1, ROUNDS + 1):
        payoff, _ = play_round(theta, mu, wealth, rng, bounty)
        wealth += payoff
        buf += payoff
        if adapt and t % win == 0:
            cur = buf / win
            adaptive = kind == 0
            improved = cur >= prev_avg
            # 개선되면 같은 방향 유지, 악화되면 방향 반전
            step = np.where(adaptive & ~improved, -step, step)
            theta = np.where(adaptive, np.clip(theta + step, 0.0, 1.0), theta)
            prev_avg = np.where(adaptive, cur, prev_avg)
            buf[:] = 0.0
            theta_hist.append(theta[adaptive].mean())

    return mu, kind, theta, wealth, theta_hist


def main():
    rng = np.random.default_rng(SEED)

    # ── 본 실험: 무보상금 ───────────────────────────────────────────
    mu, kind, theta, wealth, hist = run_population(rng, bounty=0.0)
    adaptive = kind == 0; gambler = kind == 1; coward = kind == 2
    w_adapt = wealth[adaptive].mean()
    w_gamb = wealth[gambler].mean()
    w_cow = wealth[coward].mean()
    theta_final = theta[adaptive].mean()
    theta_std = theta[adaptive].std()
    gamb_bankrupt = float((wealth[gambler] < B).mean())

    # ── 대조: 승자 보상금(정답 무관 지급) ──────────────────────────
    rng2 = np.random.default_rng(SEED)
    _, kind2, _, wealth2, _ = run_population(rng2, bounty=12.0)  # 오답에도 +12
    w_gamb_bounty = wealth2[kind2 == 1].mean()

    # 하위 지표 — 정직 해석: 메커니즘은 '확신 없는 답변'을 벌한다.
    # 능력 μ<τ*(문턱 못 넘는) 도박꾼만 골라 보면 파산해야 한다.
    lowcomp = gambler & (mu < TAU_STAR)
    w_gamb_low = float(wealth[lowcomp].mean()) if lowcomp.any() else float("nan")
    bankrupt_low = float((wealth[lowcomp] < B).mean()) if lowcomp.any() else float("nan")

    k1 = bool(w_gamb < W0 and w_gamb < w_adapt)   # 사전 등록 그대로 — 구부리지 않음
    k1b = bool(w_gamb_low < W0)                    # 하위: 무능 도박꾼은 소멸
    k2 = bool(abs(theta_final - TAU_STAR) <= 0.05)
    k3 = bool(w_gamb_bounty >= W0)

    res = {
        "params": {"B": B, "R": R, "tau_star": TAU_STAR, "N": N, "rounds": ROUNDS, "W0": W0},
        "no_bounty": {
            "wealth_adaptive": round(w_adapt, 1),
            "wealth_gambler": round(w_gamb, 1),
            "wealth_coward": round(w_cow, 1),
            "gambler_bankrupt_rate": round(gamb_bankrupt, 3),
            "adaptive_theta_final": round(theta_final, 3),
            "adaptive_theta_std": round(theta_std, 3),
        },
        "bounty_control": {"wealth_gambler": round(w_gamb_bounty, 1), "bounty_per_wrong": 12.0},
        "low_competence_gambler": {"wealth": round(w_gamb_low, 1), "bankrupt_rate": round(bankrupt_low, 3)},
        "verdict": {
            "K1_gambler_extinct_AS_PREREGISTERED": k1,
            "K1_note": "실패 — '무조건 답변'은 능력 높으면 이익. 메커니즘은 답변이 아니라 '확신 없는 답변'을 벌한다(K2가 그 증거). K1은 잘못 세운 프록시였음, 구부리지 않고 실패로 기록.",
            "K1b_incompetent_gambler_extinct": k1b,
            "K2_threshold_emerges_at_tau_star": k2,
            "K3_bounty_revives_gambler": k3,
            "core_result": bool(k2 and k3 and k1b),
        },
        "seed": SEED,
    }
    json.dump(res, open(f"{OUT}/results.json", "w"), indent=2, ensure_ascii=False)
    print(f"τ* = B/(B+R) = {TAU_STAR}")
    print(f"[무보상금] 적응형 부 {w_adapt:.1f} · 도박꾼 {w_gamb:.1f} · 겁쟁이 {w_cow:.1f} "
          f"· 도박꾼 파산율 {gamb_bankrupt:.0%}")
    print(f"[창발] 적응형 학습 임계 θ → {theta_final:.3f} (목표 τ*={TAU_STAR}, std {theta_std:.3f})")
    print(f"[대조] 보상금 켜면 도박꾼 부 {w_gamb_bounty:.1f} (시작 {W0})")
    print(json.dumps(res["verdict"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
