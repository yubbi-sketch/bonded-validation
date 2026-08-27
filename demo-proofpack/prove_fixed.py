"""demo-proofpack — 수정본(floor/floor)의 무희석 성질, 정수 수준 z3 증명.

성질(수정본): S,T,a > 0 (오버플로 배제 바운드 내)에서
    m           = (a*S) div T            (floor — 수정된 deposit 경로)
    backingB    = (S*T) div S  = T       (기존 주주 100% 보유)
    backingA    = (S*(T+a)) div (S+m)
    주장:  backingA >= T                  (예치가 기존 주주 백킹을 못 줄임)

버그본(ceil): m' = (a*S + T - 1) div T 이면 위반 가능(반례 존재 확인).

이 스크립트는 EVM uint256 나눗셈과 동일한 정수 div 시맨틱으로 판정한다.
바운드(S,T,a < 2^64)는 곱셈 오버플로 배제용 — Solidity 0.8 checked-math가
오버플로를 revert시키므로, 바운드 내에선 정수 산술 == EVM 산술이다.
Halmos 바이트코드 수준 UNSAT은 z3/yices 비선형 BV 약점으로 timeout —
그 갭을 이 정수 수준 증명이 메운다(리포트에 그대로 명시).
"""
from z3 import Ints, Solver, sat, unsat, set_option

set_option(rational_to_decimal=True)

S, T, a = Ints("S T a")
B = 2 ** 64

bounds = [S > 0, T > 0, a > 0, S < B, T < B, a < B]

print("=" * 66)
print("demo-proofpack · 수정본 무희석 — 정수 수준 z3 판정")
print("=" * 66)

# ── FIXED (floor): 반례 부재 = UNSAT 기대 ──
m_fixed = (a * S) / T                      # z3 Int '/' = Euclidean div (양수에선 floor)
backingA_fixed = (S * (T + a)) / (S + m_fixed)
s1 = Solver()
s1.add(bounds + [backingA_fixed < T])      # 위반 탐색
r1 = s1.check()
print(f"[{'OK ' if r1 == unsat else 'FAIL'}] FIXED  위반 탐색 → {r1} (기대 unsat = 전 바운드 무희석 증명)")
assert r1 == unsat

# ── BUGGY (ceil): 반례 존재 = SAT 기대 ──
m_bug = (a * S + T - 1) / T
backingA_bug = (S * (T + a)) / (S + m_bug)
s2 = Solver()
s2.add(bounds + [backingA_bug < T])
r2 = s2.check()
print(f"[{'OK ' if r2 == sat else 'FAIL'}] BUGGY  위반 탐색 → {r2} (기대 sat = 반례 존재)")
if r2 == sat:
    mdl = s2.model()
    print(f"        증인: S={mdl[S]}, T={mdl[T]}, a={mdl[a]}")
assert r2 == sat

print("-" * 66)
print("결론: 수정본은 바운드(< 2^64) 전체에서 무희석이 성립(UNSAT),")
print("버그본은 위반 증인이 존재(SAT). Halmos는 버그본 바이트코드 반례를,")
print("이 정수 증명은 수정본 부재 측을 담당한다 — 리포트에 분담 그대로 명시.")
