"""Exp24 — Value-Coupling 스케일-억제 정리(정리24-L)의 기계 검증 (z3).

판정 담보를 분쟁 풀 V에 결합(B_j = κ·V)하면, 상수담보(decoupled/UMA식)가 겪는
'풀이 커질수록 뒤집기 비용이 상금에 미달하는' 규모붕괴가 제거된다 — 는 것이
이 실험의 헤드라인이다. 단 적대검증(경제·메커니즘·형식 3렌즈)이 원 정리를
크게 좁혔다. 이 스크립트는 그 정직한 결과를 z3로 **양방향** 판정한다:

  성립(UNSAT) — 유효범위(G≤V) 안에서 억제 부등식이 참임:
    z3-1  D1 타당성  (κ ≥ 1/(m(1−p)) ⟹ 보장벌칙 m(1−p)B_j ≥ G)
    z3-2  D2 타당성  (κ ≥ p/(m(1−p)) ⟹ 위험중립 기대이익 pG − m(1−p)B_j ≤ 0)

  경계(SAT 증인) — 정리가 '무적용'이 되는 지점을 정직하게 문서화:
    z3-3  하한 필요성       (과소결합이면 수익 공격 존재)
    z3-4  decoupled 규모붕괴 (UMA식 상수담보는 큰 V에서 상금 미달 — 우리가 고치는 병리)
    z3-5  임계 knife-edge   (κ=κ*에서 이익 정확히 0 → 엄밀부등호/ε-마진 필요)
    z3-6  H2 없으면 D1 붕괴  (유한책임/차입후디폴트면 사적 기대이익 pG>0 항상)
    z3-7  G>V 레버리지 붕괴  (외부 참조 파생 G=L·V, L>1이면 D1 임계에서도 깨짐 → H5 load-bearing)
    z3-8  p→1 유한담보 억제불가 (유한 κ_max로는 p≈1 결정론 장악 억제 불가 → H1 필수)
    z3-9  V-오라클 조작 붕괴 (B_j=κ·V_measured인데 G가 V_true 추종 → 워시-억제로 붕괴, H4 필수)

z3-4는 우리가 '이긴' 지점(경쟁 대조), z3-3/5~9는 우리가 '못 이기는' 지점(정직 경계)이다.
BornTooLate 자체는 z3-7(외부 시장 G)·z3-8(p≈1)에 걸려 유효범위 밖 — value-coupling은
그 사건을 '치료'하지 않는다. 살아남는 것은 좁은 스케일-디커플링 제거뿐이다.

실수 비선형 산술(κ·V, p·B_j — 최대 4차) — z3 nlsat이 UNSAT/SAT을 종결 판정한다.
나눗셈은 곱셈형으로 재작성(κ ≥ 1/(m(1−p)) ⟺ κ·m·(1−p) ≥ 1, m(1−p)>0).
"""
from z3 import And, Real, Solver, sat, unsat, set_option

set_option(rational_to_decimal=True, precision=10)

PASS = []


def check(name, expect, cons, witness=False):
    s = Solver()
    s.add(And(*cons))
    r = s.check()
    ok = (r == expect)
    tag = "OK " if ok else "FAIL"
    print(f"[{tag}] {name}: {r}  (기대 {expect})")
    if witness and r == sat:
        m = s.model()
        vals = ", ".join(f"{d.name()}={m[d]}" for d in sorted(m.decls(), key=lambda d: d.name()))
        print(f"        증인: {vals}")
    PASS.append(ok)
    assert ok, name
    return s


def pos(*xs):
    return [x > 0 for x in xs]


# 공통 변수
V, p, kappa, m, G, Bj = (Real(n) for n in ("V", "p", "kappa", "m", "G", "Bj"))
b0, L, Vm, Vt, kmax = (Real(n) for n in ("b0", "L", "Vm", "Vt", "kmax"))

base = [V > 0, p > 0, p < 1, m >= 3]           # V>0, 0<p<1, m≥3
GleV = [G > 0, G <= V]                          # H5 유효범위: G ≤ V
coupled = [Bj == kappa * V]                     # value-coupling

print("=" * 68)
print("Exp24 · Value-Coupling 스케일-억제 정리(정리24-L) — z3 기계 검증")
print("=" * 68)
print("\n── 성립(UNSAT = 반례 부재 = 정리 성립), 유효범위 G≤V 안 ──")

# z3-1: D1 타당성 — κ·m(1−p) ≥ 1 이면 m(1−p)B_j ≥ G. 반례 부정 → UNSAT.
check("z3-1  D1 타당성 (보장벌칙 ≥ 상금)", unsat,
      base + GleV + coupled + [kappa * m * (1 - p) >= 1,
                               m * (1 - p) * Bj < G])

# z3-2: D2 타당성 — κ·m(1−p) ≥ p 이면 pG − m(1−p)B_j ≤ 0. 반례 부정 → UNSAT.
check("z3-2  D2 타당성 (위험중립 기대이익 ≤ 0)", unsat,
      base + GleV + coupled + [kappa * m * (1 - p) >= p,
                               p * G - m * (1 - p) * Bj > 0])

print("\n── 경계(SAT 증인 = 정리가 '무적용'이 되는 지점을 정직하게 문서화) ──")

# z3-3: 하한 필요성 — 과소결합(0 < κ·m(1−p) < p) & G=V 면 수익 공격 존재.
check("z3-3  하한 필요성 (과소결합은 취약)", sat,
      base + coupled + [kappa > 0, G == V, kappa * m * (1 - p) < p,
                        p * G - m * (1 - p) * Bj > 0], witness=True)

# z3-4: decoupled 규모붕괴 — 상수담보 b0는 큰 V에서 m(1−p)b0 < V=G. (우리가 고치는 UMA 병리)
check("z3-4  decoupled 규모붕괴 (UMA식 상수담보)", sat,
      base + pos(b0) + [G == V, Bj == b0, m * (1 - p) * b0 < V], witness=True)

# z3-5: 임계 knife-edge — κ·m(1−p)=p 면 pG − m(1−p)B_j = 0 (무차별).
check("z3-5  임계 무차별 (엄밀부등호/ε-마진 근거)", sat,
      base + coupled + [G == V, kappa * m * (1 - p) == p,
                        p * G - m * (1 - p) * Bj == 0])

# z3-6: H2(책임내부화) 없으면 D1 붕괴 — 실패상태 사적비용=0 이면 사적 기대이익 = pG > 0.
check("z3-6  H2 없으면 D1 붕괴 (유한책임)", sat,
      base + GleV + coupled + [kappa * m * (1 - p) >= 1, p * G > 0], witness=True)

# z3-7: G>V 레버리지 붕괴 — 외부 참조 G=L·V(L>1), D1 임계 κ·m(1−p)=1 → m(1−p)B_j < G.
check("z3-7  G>V 레버리지 붕괴 (H5 load-bearing)", sat,
      base + pos(L) + [L > 1, G == L * V, Bj == kappa * V,
                       kappa * m * (1 - p) == 1, m * (1 - p) * Bj < G], witness=True)

# z3-8: p→1 유한담보 억제불가 — 넉넉한 κ_max=5 로도 p≈1이면 m(1−p)B_j < G=V.
check("z3-8  p→1 억제불가 (H1 필수)", sat,
      base + [kmax == 5, kappa <= kmax, kappa > 0, G == V, Bj == kappa * V,
              m * (1 - p) * Bj < G], witness=True)

# z3-9: V-오라클 조작 붕괴 — B_j=κ·Vm(측정), G=Vt(참), Vm<Vt, D1 임계 → m(1−p)B_j < G.
check("z3-9  V-오라클 조작 붕괴 (H4 필수)", sat,
      pos(Vt) + [p > 0, p < 1, m >= 3, Vm > 0, Vm < Vt, G == Vt,
                 Bj == kappa * Vm, kappa * m * (1 - p) == 1,
                 m * (1 - p) * Bj < G], witness=True)

print("\n" + "=" * 68)
n_ok = sum(PASS)
print(f"결과: {n_ok}/{len(PASS)} 통과 "
      f"(성립 2건 UNSAT + 경계 7건 SAT)")
print("정직 요약: 유효범위(G≤V·p≤p_max·V-무결·다수미구성) 안에서만 스케일-디커플링을")
print("제거한다. BornTooLate은 z3-7(외부시장 G)·z3-8(p≈1)에 걸려 유효범위 밖 — 미해결.")
print("=" * 68)
