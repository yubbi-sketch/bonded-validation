"""Exp30 — 미개설 주장의 소멸(Optimistic Lapse): 경제 조건의 기계 검증 (z3).

EXP30.md §6 '경제' 항목을 SMT 로 판정한다. 스크래치(exp30-skeptic/refute.py·attack.py,
exp30-openlens/prove.py)의 유효 검사만 승격했고, 자명식(J2 류 항등식)은 뺐다.

라벨:  [THM] = 부정이 UNSAT → 전 매개변수 공간에서 성립(정리)
       [WIT] = SAT 증인 → '조건이 필요하다'는 반례의 존재 (한계·경계 표시)

기호:  B_a  에이전트 주장담보(minBondPerClaim)      F    개설 수수료(judgeFee)
       R_c  도전자(개설자) 상환(v0.3 = 0)              w    도전자의 '오답' 믿음 ∈ [0,1]
       q    거짓 주장이 창 W 안에 개설될 확률           ρ    개설된 거짓 주장이 실제로 슬래시될 확률
                                                          (정직 패널이면 1; B5·W1 에선 수수료 환류 비율로 재사용)
       G    거짓말의 외부 이득                          gas  개설 트랜잭션 비용 > 0
       N    정직 주장 수 · C 풀 장악 비용

전부 실수 산술(비선형) — z3 nlsat. 시뮬레이션 아님: UNSAT(반례 부재) / SAT(증인 존재).
독립 2차 솔버 교차검증은 ../xverify.py exp30 (cvc5).
"""
import json
from pathlib import Path

from z3 import And, Q, Real, Solver, sat, unsat, set_option

set_option(rational_to_decimal=True, precision=10)

RESULTS = []


def check(label, name, expect, formula, show_model=False):
    s = Solver()
    s.add(formula)
    r = s.check()
    ok = r == expect
    tag = "OK " if ok else "FAIL"
    print(f"[{tag}] [{label}] {name}: {r} (기대 {expect})")
    model = None
    if show_model and r == sat:
        model = str(s.model())
        print(f"       증인: {model}")
    RESULTS.append({"label": label, "name": name, "expect": str(expect), "got": str(r),
                    "ok": ok, "witness": model})
    assert ok, name
    return s


Ba, F, Rc, w, q, rho, G, gas, N, C = [Real(x) for x in "B_a F R_c w q rho G gas N C".split()]
DOM = And(Ba > 0, F >= 0, Rc >= 0, w >= 0, w <= 1, q >= 0, q <= 1, rho >= 0, rho <= 1, gas > 0)

print("── Q1. 조건부 억지 — 거짓말 기대이익 Π_lie = G − q·ρ·B_a (v0.2.1 은 q ≡ 1) ──")
Pi_lie = G - q * rho * Ba
check("THM", "Q1  q·ρ·B_a ≥ G ⟹ Π_lie ≤ 0", unsat,
      And(DOM, G >= 0, q * rho * Ba >= G, Pi_lie > 0))
check("THM", "Q1-v021 q = 1, ρ = 1, G ≤ B_a ⟹ Π_lie ≤ 0 (현행 항상판정과 동치)", unsat,
      And(DOM, q == 1, rho == 1, G >= 0, G <= Ba, Pi_lie > 0))
check("WIT", "Q1′ q < q* = G/(ρ·B_a) 이면 수익 가능한 거짓말 존재 (억지력은 q 에 조건부)", sat,
      And(DOM, rho > 0, G > 0, q * rho * Ba < G, Pi_lie > 0), show_model=True)
check("WIT", "Q1″ 분산피해형 거짓말(G 가 커도 q = 0)은 Π_lie = G > 0 (Exp30 §7-1 R3)", sat,
      And(DOM, q == 0, G > 0, Pi_lie > 0), show_model=True)

print("── S1/S6. 도전자 공급 불가능성 — R_c = 0 선택의 근거 ──")
check("THM", "S1  R_c ≤ F ⟹ 도전자 EV = w·R_c − F − gas < 0 (w = 1 이어도)", unsat,
      And(DOM, Rc <= F, w * Rc - F - gas >= 0))
# 연합(개설자+판정자) 수입의 결과의존 Δ: 슬래시 시 (F 환류) + R_c − F = R_c, 미슬래시 시 F − F = 0 ⇒ Δ = R_c
Delta = Rc
check("THM", "S6  [Δ = 0] ∧ [도전자 EV = w·R_c − F ≥ 0] ∧ F > 0 은 동시 불가", unsat,
      And(DOM, F > 0, Delta == 0, w * Rc - F >= 0))
check("WIT", "S6′ F = 0 이면 동시 가능 — 그러나 그리핑 비용 0(개설 무료)", sat,
      And(DOM, F == 0, Delta == 0, w * Rc - F >= 0), show_model=True)
check("WIT", "S6″ 도전자 EV ≥ 0 을 사려면 Δ = R_c > 0 이 강제된다 (정리 3 보조금의 개설자 이식)", sat,
      And(DOM, F > 0, w * Rc - F >= 0, Delta > 0), show_model=True)

print("── B5. 풀 장악(ρ = 환류 비율) 사건당 수익 = R_c + ρ·F − F ──")
capt = Rc + rho * F - F
check("THM", "B5  R_c = 0 ⟹ 장악해도 사건당 수익 ≤ 0 (v0.2.1 = v0.3)", unsat,
      And(DOM, Rc == 0, capt > 0))
check("WIT", "B5′ R_c > 0, ρ = 1 ⟹ 사건당 +R_c (장악 자기조달)", sat,
      And(DOM, Rc > 0, rho == 1, capt == Rc, capt > 0), show_model=True)
check("THM", "B5″ R_c = 0 ⟹ 어떤 N 으로도 장악비용 C > 0 회수 불가 (S7′)", unsat,
      And(DOM, Rc == 0, C > 0, N >= 0, N * Rc >= C))

print("── R1. 한계 박제 — v0.2.1 대비 기대벌칙 감소분 ──")
pen_v021 = rho * Ba          # 모든 주장이 판정됨 (q ≡ 1)
pen_v03 = q * rho * Ba       # 창 안 개설 확률 q
check("THM", "R1  ∀ q < 1, ρ = 1: 감소분 = (1−q)·B_a 정확 (다른 값 불가)", unsat,
      And(DOM, rho == 1, q < 1, pen_v021 - pen_v03 != (1 - q) * Ba))
check("THM", "R1′ ∀ q < 1, ρ > 0: v0.3 기대벌칙 < v0.2.1 기대벌칙 (엄격)", unsat,
      And(DOM, rho > 0, q < 1, pen_v03 >= pen_v021))
check("THM", "R1″ q = 1 이면 감소분 0 (창 안 도전이 확실하면 현행과 동치)", unsat,
      And(DOM, q == 1, pen_v021 - pen_v03 != 0))

print("── W1. wash — 에이전트 + 공모 개설자가 고의 오답을 슬래시당해 R_c 회수 ──")
wash = Rc - Ba - F + rho * F   # 공동 순이득 (ρ = 공모 판정자 수수료 환류)
check("THM", "W1  R_c = 0 ⟹ wash 공동이득 ≤ 0 (∀ ρ ≤ 1)", unsat,
      And(DOM, Rc == 0, wash > 0))
check("THM", "W1′ R_c ≤ B_a (Exp26 (W)) 이어도 ≤ 0", unsat,
      And(DOM, Rc <= Ba, wash > 0))
check("WIT", "W1″ R_c > B_a 면 wash 가능 (조건 필요성)", sat,
      And(DOM, Rc > Ba, rho == 1, wash > 0), show_model=True)

print("── T_max 산술 (증명 아님·기록): W + 2·voteTimeout + disputeTimeout ──")
W, VT, DT = 86400, 3600, 86400
T_MAX = W + 2 * VT + DT
print(f"     W={W} voteTimeout={VT} disputeTimeout={DT} → T_max = {T_MAX}s ({T_MAX/3600:.1f}h)")

n_ok = sum(1 for r in RESULTS if r["ok"])
print(f"\n결론: z3 판정 {len(RESULTS)}건 전부 기대와 일치 ({n_ok}/{len(RESULTS)}).")
print("  R_c = 0 이 지배적: 같은(0) 도전자 공급(S1)·엄격히 작은 공격면(B5·W1)·정리 3/Exp26 (W)/Exp27 정합.")
print("  대가(한계): 억지력은 q 에 조건부(Q1′), 감소분은 정확히 (1−q)·B_a (R1), 분산피해형은 q=0 (Q1″).")

out = {
    "exp": "exp30", "what": "Optimistic Lapse economic conditions (z3)",
    "n_checks": len(RESULTS), "n_ok": n_ok,
    "t_max_s": T_MAX,
    "checks": RESULTS,
}
Path(__file__).with_name("out").mkdir(exist_ok=True)
Path(__file__).with_name("out").joinpath("prove.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("→ exp30/out/prove.json 기록")
