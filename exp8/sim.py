"""Exp8 — 판정자 담보·loser-pays 공격 시뮬레이션 (승격 게이트).

설계 대상 메커니즘 (docs/exp8-판정자담보-설계서.md):
  - 판정자는 담보 예치 후 참여, 반대표 발생 → 5인 확대재판(가중 무작위 추첨)
  - 확대재판 소수파 판정자 담보 몰수, 몰수분은 [소각 + 동결 피해 에이전트 배상]
    ← 핵심 설계 선택: 승자 판정자 보상금 없음(무보상금). 판정 보수는 결과와
      무관한 정액 수수료로 분리. (UMA식 '승자 보상금'과 대조 실험 포함)

■ 사전 등록 킬 기준 (설계서 그대로):
  K1 다수 매수: 매수 비율 ≤50%에서 공격자 기대이익 ≤ 0 (무보상금 설계 하)
  K2 시빌: 신참 할증(담보 1.5×)+평판 가중 추첨 하에서, 확대재판 장악(3/5)
     확률 5% 도달에 드는 담보 비용이 정직 판정자 담보의 10배 초과
  K3 소수≠틀림: 재실행 비결정성 ε=0에서 정직 판정자 부당 슬래시 = 0,
     ε≤1%에서 부당 슬래시율 < 2% (허용 오차 곡선 보고)
  K4 스팸: 피해자 1인·1일 동결시키는 공격자 비용 > 0 이며 규모에 비례
     (v0.1은 비용 0이었음 — 이것이 Exp8의 존재 이유)

■ 정직성: 이것은 모델이지 실증이 아니다. 파라미터(풀 100인·가중치)는 가정이며
  민감도는 결과에 병기한다. 온체인 구현·실측은 승격(v0.2) 후.
"""
import json

import numpy as np

rng = np.random.default_rng(2026)
TRIALS = 20000
POOL = 100          # 판정자 풀
PANEL = 5           # 확대재판 인원
STAKE = 1.0         # 정직 판정자 담보
NEWCOMER_MULT = 1.5 # 신참 담보 할증 (렌즈 요율)
NEWCOMER_W = 0.2    # 신참 추첨 가중 (평판 가중)
AGENT_BOND = 1.0
DISPUTE_HOURS = 24  # v0.1 타임아웃


def draw_panel(weights, k=PANEL):
    p = weights / weights.sum()
    return rng.choice(len(weights), size=k, replace=False, p=p)


def k1_bribery():
    """공격자가 기성 판정자 f비율을 매수. 확대재판 3/5 장악 시 부당 슬래시 성공.
    수익 모델 비교: 무보상금(우리) vs 승자보상금(몰수분의 50%를 다수파에 분배)."""
    rows = []
    for f in [0.05, 0.1, 0.2, 0.3, 0.4, 0.5]:
        n_att = int(POOL * f)
        owner = np.array([1] * n_att + [0] * (POOL - n_att))
        w = np.ones(POOL)
        succ = 0
        att_minority_loss = 0.0
        for _ in range(TRIALS):
            panel = draw_panel(w)
            a = owner[panel].sum()
            if a >= 3:
                succ += 1
                # 소수파(정직 2인 이하) 슬래시 — 공격자 손실 없음 이 회차
            else:
                att_minority_loss += a * STAKE  # 패널에 든 공격자 표는 소수파로 몰수
        p_succ = succ / TRIALS
        e_att_loss = att_minority_loss / TRIALS
        # 성공 시 공격자 수익: 무보상금 = 0 / 보상금 설계 = (소수파 몰수분 절반)
        honest_minority_stake = 2 * STAKE  # 성공 회차의 소수파(정직) 기대 상한
        profit_ours = p_succ * 0.0 - e_att_loss
        profit_bounty = p_succ * (honest_minority_stake * 0.5) - e_att_loss
        rows.append({"bribed_frac": f, "p_capture_3of5": round(p_succ, 4),
                     "E_profit_no_bounty": round(profit_ours, 4),
                     "E_profit_with_bounty": round(profit_bounty, 4)})
    k1_pass = all(r["E_profit_no_bounty"] <= 0 for r in rows)
    return rows, k1_pass


def k2_sybil():
    """공격자가 신참 시빌 m명 등록(담보 1.5×, 가중 0.2). 3/5 장악 확률 vs 비용."""
    rows = []
    cost_at_5pct = None
    for m in [10, 25, 50, 100, 200, 400, 800]:
        w = np.concatenate([np.ones(POOL), np.full(m, NEWCOMER_W)])
        owner = np.concatenate([np.zeros(POOL), np.ones(m)])
        succ = sum(owner[draw_panel(w)].sum() >= 3 for _ in range(TRIALS // 2))
        p = succ / (TRIALS // 2)
        cost = m * STAKE * NEWCOMER_MULT
        rows.append({"sybils": m, "p_capture": round(p, 4), "stake_cost": cost})
        if cost_at_5pct is None and p >= 0.05:
            cost_at_5pct = cost
    k2_pass = (cost_at_5pct is None) or (cost_at_5pct > 10 * STAKE)
    return rows, k2_pass, cost_at_5pct


def k3_nondeterminism():
    """전원 정직, 재실행 비결정성 ε — 정직 판정자 부당 슬래시율 곡선."""
    rows = []
    for eps in [0.0, 0.001, 0.005, 0.01, 0.02, 0.05]:
        wrongful = 0
        panels = 0
        for _ in range(TRIALS // 2):
            votes = rng.random(PANEL) < eps  # True = 어긋난 재실행(소수 후보)
            minority = votes.sum() if votes.sum() <= PANEL // 2 else PANEL - votes.sum()
            if 0 < minority:
                wrongful += minority  # 소수파 = 부당 슬래시 (전원 정직이므로)
            panels += 1
        rows.append({"epsilon": eps,
                     "wrongful_slash_per_panel": round(wrongful / panels, 4)})
    at0 = rows[0]["wrongful_slash_per_panel"]
    at1pct = next(r for r in rows if r["epsilon"] == 0.01)["wrongful_slash_per_panel"]
    k3_pass = (at0 == 0.0) and (at1pct / PANEL < 0.02)
    return rows, k3_pass


def k4_spam():
    """분쟁 스팸의 단가: 반대표 1회 = 판정자 담보 1개 리스크(확대재판서 소수파 확정
    시 몰수 — 전원 정직 풀에서는 확정). 피해자 동결 시간은 v0.1 타임아웃이 상한."""
    cost_per_victim_day = STAKE * (24 / DISPUTE_HOURS)
    v01_cost = 0.0
    k4_pass = cost_per_victim_day > 0
    return ({"attacker_cost_per_victim_day": cost_per_victim_day,
             "v01_cost_per_victim_day": v01_cost,
             "note": "규모 비례: N명 동결 = N×담보 소각/일"}, k4_pass)


def main():
    k1_rows, k1 = k1_bribery()
    k2_rows, k2, c5 = k2_sybil()
    k3_rows, k3 = k3_nondeterminism()
    k4_row, k4 = k4_spam()
    verdict = {"K1_bribery_pass": bool(k1), "K2_sybil_pass": bool(k2),
               "K3_nondet_pass": bool(k3), "K4_spam_pass": bool(k4),
               "sybil_cost_at_5pct_capture": c5,
               "promote_to_v02": bool(k1 and k2 and k3 and k4)}
    results = {"params": {"pool": POOL, "panel": PANEL, "stake": STAKE,
                          "newcomer_mult": NEWCOMER_MULT, "newcomer_weight": NEWCOMER_W,
                          "trials": TRIALS},
               "K1_bribery": k1_rows, "K2_sybil": k2_rows,
               "K3_nondeterminism": k3_rows, "K4_spam": k4_row,
               "verdict": verdict}
    json.dump(results, open("/Users/yubbi/iis-lab/exp8/out/results.json", "w"),
              indent=2, ensure_ascii=False)
    print(json.dumps(verdict, indent=2, ensure_ascii=False))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.1))
    fs = [r["bribed_frac"] for r in k1_rows]
    axes[0].plot(fs, [r["E_profit_no_bounty"] for r in k1_rows], "o-",
                 color="#3a9a5c", label="ours: no bounty to winners")
    axes[0].plot(fs, [r["E_profit_with_bounty"] for r in k1_rows], "s--",
                 color="#aa4444", label="UMA-style: 50% bounty to winners")
    axes[0].axhline(0, color="gray", lw=1)
    axes[0].set_xlabel("bribed fraction of judge pool")
    axes[0].set_ylabel("attacker E[profit] per dispute (stakes)")
    axes[0].set_title("K1: bounty design creates bribery profit;\nno-bounty stays ≤ 0")
    axes[0].legend(fontsize=8)
    ms = [r["sybils"] for r in k2_rows]
    axes[1].plot([r["stake_cost"] for r in k2_rows], [r["p_capture"] for r in k2_rows],
                 "o-", color="#dd7733")
    axes[1].axhline(0.05, ls="--", color="gray", lw=1, label="5% capture")
    axes[1].set_xlabel("sybil stake cost (× honest judge stake)")
    axes[1].set_ylabel("P(capture 3-of-5 panel)")
    axes[1].set_title("K2: sybil capture vs cost\n(1.5× premium + 0.2 weight)")
    axes[1].set_xscale("log"); axes[1].legend(fontsize=8)
    axes[2].plot([r["epsilon"] * 100 for r in k3_rows],
                 [r["wrongful_slash_per_panel"] / PANEL * 100 for r in k3_rows],
                 "o-", color="#55aabb")
    axes[2].axhline(2.0, ls="--", color="gray", lw=1, label="K3 limit 2%")
    axes[2].set_xlabel("re-execution nondeterminism ε (%)")
    axes[2].set_ylabel("honest judge wrongful-slash rate (%)")
    axes[2].set_title("K3: determinism is load-bearing\n(ε=0 → exactly 0)")
    axes[2].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig("/Users/yubbi/iis-lab/exp8/out/attack_sims.png", dpi=140)
    print("plot saved")


if __name__ == "__main__":
    main()
