"""Exp13 — 무보상금 정리의 기계 검증 (z3).

docs/theorem-no-bounty.md의 대수 구조를 SMT로 검증한다:
  T2  (정리 2): ∀ p∈[0,1), B_a>0, B_j>0, m≥3, b:
        [b ≥ (1-p)·B_j  ∧  B_j·m·(1-p) ≥ p·B_a]  ⟹  p·B_a − m·b ≤ 0
      → 부정을 UNSAT으로 증명 (전 매개변수 공간).
  COR (따름정리): B_j = 10·B_a, m = 3 일 때 임계 p* = 30/31 —
      p ≤ 30/31이면 비수익(UNSAT), p > 30/31에선 수익 가능 사례 존재(SAT).
  T3  (정리 3): 보상금 w>0 도입 시 Π>0인 매개변수 존재(SAT 증인 출력),
      단 같은 매개변수에서 무보상금이면 Π ≤ 0임을 함께 검증.

전부 실수 산술(비선형) — z3 nlsat이 판정한다. 시뮬레이션 아님: 판정은
UNSAT(반례 부재 = 정리 성립) / SAT(증인 존재)의 이분법이다.
"""
from z3 import (And, Q, Real, Solver, sat, unsat, set_option)

set_option(rational_to_decimal=True, precision=10)


def check(name, expect, formula, show_model=False):
    s = Solver()
    s.add(formula)
    r = s.check()
    ok = "OK " if r == expect else "FAIL"
    print(f"[{ok}] {name}: {r} (기대 {expect})")
    if show_model and r == sat:
        print(f"       증인: {s.model()}")
    assert r == expect, name
    return s


p, Ba, Bj, m, b, w = Real("p"), Real("B_a"), Real("B_j"), Real("m"), Real("b"), Real("w")
DOMAIN = And(p >= 0, p < 1, Ba > 0, Bj > 0, m >= 3)

# ── T2: 정리 2 본체 — 부정이 UNSAT이면 전 공간에서 성립 ──────────────
premise = And(DOMAIN,
              b >= (1 - p) * Bj,                 # A3 매수 수락 제약 (p+ε 방어)
              Bj * m * (1 - p) >= p * Ba)        # 담보 비율 조건
profit = p * Ba - m * b                          # 공격자 기대이익 상한
check("T2 무보상금 비수익 (∀ 매개변수)", unsat, And(premise, profit > 0))

# 보조: 조건이 없으면 성립하지 않음을 정직하게 확인 (정리가 '조건부'인 이유)
check("T2' 조건 제거 시 반례 존재 (정리가 조건부인 이유)", sat,
      And(DOMAIN, b >= (1 - p) * Bj, profit > 0))

# ── COR: 현행 파라미터 B_j=10·B_a, m=3 → 임계 p* = 30/31 ─────────────
cur = And(DOMAIN, Bj == 10 * Ba, m == 3, b >= (1 - p) * Bj)
check("COR p ≤ 30/31이면 비수익", unsat, And(cur, p <= Q(30, 31), profit > 0))
check("COR p > 30/31에선 수익 가능 (임계의 타이트함)", sat,
      And(cur, p > Q(30, 31), b == (1 - p) * Bj, profit > 0))

# ── T3: 보상금 반례 — 같은 매개변수에서 (보상금 ⇒ 흑자, 무보상금 ⇒ 손실) ──
b_bounty = (1 - p) * Bj - p * w                  # 보상금이 수락 제약을 완화
profit_bounty = p * Ba - m * b_bounty
profit_nobounty = p * Ba - m * ((1 - p) * Bj)
witness = check("T3 보상금 존재 반례 (승자 상금 = 매수 자금)", sat,
                And(DOMAIN, w > 0, b_bounty >= 0,
                    profit_bounty > 0,           # 보상금 설계: 공격 흑자
                    profit_nobounty <= 0),       # 무보상금: 같은 조건서 손실
                show_model=True)

print("\n결론: 정리 2·따름정리·정리 3 전부 기계 검증 통과 —")
print("      '승자에게 상금을 주지 않는다'가 시뮬레이션 관측에서 정리가 됐다.")
