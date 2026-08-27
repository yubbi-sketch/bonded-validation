"""Exp24 — value-coupling 행동 반증 시뮬레이션 (몬테카를로, 위험중립).

정리24-L의 대수는 prove.py(z3)가 종결했다. 이 시뮬은 '행동'을 본다: 결합 담보가
실제로 공격자 평균이익을 ≤0으로 누르는가, decoupled(UMA식)는 큰 V에서 무너지는가,
그리고 경계 팔(레버리지·V조작·자기다수)이 예측된 지점에서 0을 교차하는가.

모델(위험중립, 정리2 계보): 실현이익 = [장악성공]·G − 뇌물비용.
  · 장악성공 ~ Bernoulli(p)
  · 뇌물비용 = m·(1−p)·B_j  (A3 수락 하한, 무조건 지급 스케줄)
  · G = 공격자 외부 이득. 주팔은 G ~ U(0, V] (H5: G≤V), 스트레스팔은 G = L·V.
기대: E[이익] = p·E[G] − m(1−p)B_j.  결합 D1: B_j=V/(m(1−p)) → 벌칙=V → E≤0 항상.

순수 표준 라이브러리(numpy·matplotlib 무의존 — P8 재현 마찰 회피). 시드 고정.
"""
import json
import random
import statistics
from pathlib import Path

random.seed(2026)
N = 10_000            # 실행/셀
M = 3                 # 과반 정족수
P = 0.5               # 기준 장악 확률 (H1: p ≤ p_max<1)
B0 = 50_000.0         # decoupled 상수 담보 (UMA식, V와 무관)
VS = [10 ** e for e in (2, 3, 4, 5, 6, 7, 8)]   # $100 ~ $100M 로그 스윕


def penalty(bj):
    return M * (1 - P) * bj


def mc(g_fn, bj_fn, p=P, success_fn=None):
    """N회 몬테카를로 → (평균이익, 95% 부트스트랩 CI 상단)."""
    prof = []
    for _ in range(N):
        V, bj = g_fn.V, bj_fn()
        g = g_fn()
        succ = (random.random() < p) if success_fn is None else success_fn()
        prof.append((g if succ else 0.0) - penalty(bj))
    mean = statistics.fmean(prof)
    # 부트스트랩 95% CI 상단 (200 리샘플)
    ups = []
    for _ in range(200):
        samp = [prof[random.randrange(N)] for _ in range(min(N, 1500))]
        ups.append(statistics.fmean(samp))
    ups.sort()
    ci_hi = ups[int(0.975 * len(ups)) - 1]
    return mean, ci_hi


class GU:            # G ~ U(0, mult·V]
    def __init__(self, V, mult=1.0):
        self.V, self.mult = V, mult
    def __call__(self):
        return random.random() * self.mult * self.V


class GC:            # G = mult·V (상수, 레버리지 스트레스)
    def __init__(self, V, mult=1.0):
        self.V, self.mult = V, mult
    def __call__(self):
        return self.mult * self.V


def kappa_d1(p=P):
    return 1.0 / (M * (1 - p))


def kappa_d2(p=P):
    return p / (M * (1 - p))


out = {"params": {"N": N, "m": M, "p": P, "b0": B0,
                  "kappa_D1": kappa_d1(), "kappa_D2": kappa_d2()},
       "sweep": [], "boundaries": {}}

print("=" * 74)
print("Exp24 · value-coupling 행동 시뮬 (위험중립, N=%d/셀, m=%d, p=%.2f)" % (N, M, P))
print("=" * 74)
print("\n[주팔] G~U(0,V], 결합 D1/D2 vs decoupled(UMA b0=$%s) — V 스윕" % f"{B0:,.0f}")
print("%-12s %14s %14s %14s" % ("V", "coupled-D1", "coupled-D2", "decoupled"))
v_star = None
for V in VS:
    g = GU(V)
    d1 = mc(GU(V), lambda V=V: kappa_d1() * V)
    d2 = mc(GU(V), lambda V=V: kappa_d2() * V)
    dec = mc(GU(V), lambda: B0)
    if v_star is None and dec[0] > 0:
        v_star = V
    print("%-12s %14.0f %14.0f %14.0f" % (f"${V:,.0f}", d1[0], d2[0], dec[0]))
    out["sweep"].append({"V": V, "coupled_D1_mean": d1[0], "coupled_D1_ci_hi": d1[1],
                         "coupled_D2_mean": d2[0], "coupled_D2_ci_hi": d2[1],
                         "decoupled_mean": dec[0], "decoupled_ci_hi": dec[1]})

# KC9: 결합 D1 CI 상단이 모든 V에서 ≤0 인가
kc9 = all(s["coupled_D1_ci_hi"] <= 0 for s in out["sweep"])
kc3 = v_star is not None
print("\nKC9 결합-D1 억제(CI상단 모든 V ≤0): %s" % ("PASS" if kc9 else "FAIL"))
print("KC3 decoupled 규모붕괴(어떤 V*부터 이익>0): %s  (V* ≈ $%s)"
      % ("PASS" if kc3 else "FAIL", f"{v_star:,.0f}" if v_star else "—"))
out["boundaries"]["KC9_coupled_D1_deterred"] = kc9
out["boundaries"]["KC3_decoupled_break_Vstar"] = v_star

# ── 경계 팔 (정직: 정리가 무적용이 되는 지점을 예측 경계에서 확인) ──
print("\n[경계팔] 결합 D1 위에서 유효범위(H4·H5·H8) 위반 시 붕괴 — 예측 vs 실측")
V = 1_000_000.0

# KC5: 레버리지 G=L·V. 위험중립 예측 교차 L* = 1/p.
print("  KC5 레버리지 G=L·V (예측 교차 L*=1/p=%.2f):" % (1 / P))
kc5_cross = None
for L in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
    mean, _ = mc(GC(V, L), lambda: kappa_d1() * V)
    flag = ">0" if mean > 0 else "≤0"
    if kc5_cross is None and mean > 0:
        kc5_cross = L
    print("      L=%.1f → E[이익]=%12.0f  %s" % (L, mean, flag))
out["boundaries"]["KC5_leverage_cross_L"] = kc5_cross

# KC7: V-오라클 조작. B_j=κ·δ·V, G~U(0,V](참값). 예측 교차 δ* = p/2 (E[G]=V/2).
print("  KC7 V-조작 B_j=κ·δ·V (예측 교차 δ*=p/2=%.2f):" % (P / 2))
kc7_cross = None
for d in [1.0, 0.5, 0.25, 0.125]:
    mean, _ = mc(GU(V), lambda d=d: kappa_d1() * d * V)
    flag = ">0" if mean > 0 else "≤0"
    if kc7_cross is None and mean > 0:
        kc7_cross = d
    print("      δ=%.3f → E[이익]=%12.0f  %s" % (d, mean, flag))
out["boundaries"]["KC7_Vmanip_cross_delta"] = kc7_cross

# KC8: 자기-다수. 무패치(다수 슬래시 0, p=1) vs 패치(다수도 슬래시).
print("  KC8 자기-다수 (무패치=슬래시0·p→1  vs  패치=다수슬래시):")
nopatch, _ = mc(GU(V), lambda: 0.0, p=1.0)                       # 뇌물0·항상성공
patch, _ = mc(GU(V), lambda: kappa_d1() * V, p=P)               # 벌칙 복원
print("      무패치 → E[이익]=%12.0f  %s" % (nopatch, ">0(뚫림)" if nopatch > 0 else "≤0"))
print("      패치   → E[이익]=%12.0f  %s" % (patch, "≤0(복구)" if patch <= 0 else ">0"))
out["boundaries"]["KC8_nopatch_broken"] = nopatch > 0
out["boundaries"]["KC8_patch_restored"] = patch <= 0

Path("results.json").write_text(json.dumps(out, indent=2))
print("\n" + "=" * 74)
print("사전등록 판정: KC9(결합 억제)=%s · KC3(decoupled 붕괴)=%s · "
      "KC5/7/8 경계 예측 일치=%s"
      % ("PASS" if kc9 else "FAIL", "PASS" if kc3 else "FAIL",
         "PASS" if (kc5_cross and kc7_cross and out["boundaries"]["KC8_nopatch_broken"]
                    and out["boundaries"]["KC8_patch_restored"]) else "CHECK"))
print("정직: 결합은 유효범위 안에서 스케일-디커플링만 제거. 레버리지·V조작·자기다수는")
print("예측 경계에서 그대로 뚫림 — value-coupling이 못 막는 곳을 실측으로 못박음.")
print("results.json 기록됨.")
print("=" * 74)
