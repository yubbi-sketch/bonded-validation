"""Exp26 — 도전자 공급 인센티브의 이중모순 (DILEMMA) 기계 검증 (z3).

Exp25 KILL-5(미해결)가 강제: 담보된 명세는 '도전자가 실제로 모호성 증인을 낸다'에 의존하는데,
보상을 시장규모에 걸면 wash(자작 파밍), 상수/무보상이면 free-rider 과소공급 — 정확히 고가치
시장에서 탐지가 무너진다. 이 스크립트는 그 딜레마의 논리구조를 z3로 양방향 판정한다.

적대검증 3렌즈(게임이론 needs-scoping · 메커니즘 BROKEN · 형식 needs-scoping)가 원 '삼중모순'
주장을 정정했다 — 이 세션 6번째 자기교정. 정정된 헤드라인:

  ★ 이중모순(DILEMMA), 삼중모순 아님. 유일한 impossibility는 (W)∧(S) 한 쌍.
    (W) 반-wash    ⟺ R ≤ B_spec           (공모 저자+도전자 조작이득 R−B_spec ≤ 0)
    (S) 가치-스케일 ⟹ R ≥ σ·V (개설후 무한)  (탐지유인이 harm에 비례)
    개설 후 σV > B_spec(고정) ⟹ R ≤ B_spec < σV ≤ R 모순 (CORE-WS UNSAT).
  ★ 결속은 '스칼라'가 아니라 '몰수자금 조달'이다 — 어떤 보상형태(랭크·복권·난이도)든
    기대지급 ≤ B_spec 이라 (S)를 못 벗어난다 (FORFEIT-INV UNSAT). 스칼라 주장보다 강함.
  ★ (F) free-rider는 코어의 코너가 아니다 (F-INDEP-1/2 SAT: W·S 어느 쪽과도 무충돌).
    전문탐색 amortization이면 소멸 가능 (F-DISSOLVE) — 셋 중 가장 느슨, 반증 최우선 표적.
  조건부 정리: V 유계면 해 존재 (REGIME-Vcap SAT). 무조건 impossibility 아님.
  탈출구 정직 판정:
    E1 담보 감사자 구독 = relabeling (E1-COLLAPSE SAT·E1-SEAL UNSAT: 봉합엔 value-coupling
       재수입 = Exp24 미해결 회귀). '탈출' 아님.
    E2 ★진짜 탈출(유일 미탐색): V-스케일을 도전자 보상이 아니라 '공격자 공격시점 담보'에
       부과(s_atk=σV, 보상은 flat ≤ B_spec). 정리는 도전자-보상 V-스케일만 금함(E2-SCALE SAT).
       단 '공격시점 V 관측가능성'에 게이트 — 관측 불가면 붕괴(E2-UNOBS SAT).
    E3 동적담보 = V-오라클 대가(Exp24 회귀). E4 스테이크 도전 = (S) 규모갭 잔존.
"""
import json
from pathlib import Path
from z3 import And, Real, Reals, Solver, sat, unsat

PASS = []
LOG = []


def check(cid, note, expect, cons, witness=None):
    s = Solver()
    s.add(And(*cons))
    r = s.check()
    ok = (r == expect)
    print(f"[{'OK ' if ok else 'FAIL'}] {cid:<13}{note}: {r} (기대 {expect})")
    if witness and r == sat:
        m = s.model()
        print("        증인: " + ", ".join(f"{v}={m[v]}" for v in witness))
    PASS.append(ok)
    LOG.append({"id": cid, "note": note, "expected": str(expect), "result": str(r), "ok": ok})
    assert ok, cid
    return s


R, B, V, sig = Reals("R B V sig")           # 보상, B_spec, 가치(harm), σ(비례상수)
ga, gc, c, kn = Reals("ga gc c kn")         # gas, gas, 탐색비용, 필요탐색 k_need
Msup, satk, s_sub, dlt, kap = Reals("Msup satk s_sub dlt kap")  # 침묵매수하한, 공격시점담보, 구독, 할인, 감사비
mm, flat = Reals("mm flat")                 # amortization 배수, 정액보상

print("=" * 72)
print("Exp26 · 도전자 공급 이중모순(DILEMMA) — z3 기계 검증")
print("=" * 72)
print("\n── 코어 (W)∧(S): 반-wash 닫힘 → 규모미달 → 이중모순 ──")

# A1-wash: R>B 면 공모 wash 순이득>0 (gas→0). (W) 필요성
check("A1-wash", "R>B → wash 이득>0", sat,
      [B > 0, R > B, ga >= 0, gc >= 0, R - B - ga - gc > 0], witness=[B, R])

# A2-close: R≤B ∧ gas≥0 이면 wash 이득>0 불가 → (W) ⟺ R≤B
check("A2-close", "(W)⟺R≤B 닫힘", unsat,
      [R <= B, ga >= 0, gc >= 0, R - B - ga - gc > 0])

# FORFEIT-INV: 임의 몰수조달 보상 Rpay≤B ∧ (S)Rpay≥σV ∧ σV>B  (형태 무관)
check("FORFEIT-INV", "몰수조달=결속(스칼라 아님)", unsat,
      [sig > 0, V > 0, R <= B, R >= sig * V, sig * V > B])

# C1-underscale: 어떤 고정 R에도 σV>R 인 V 존재
check("C1-underscale", "상수 보상 under-scaling", sat,
      [R > 0, sig > 0, V > 0, sig * V > R], witness=[R, V, sig])

# CORE-WS ★: R≤B(W) ∧ R≥σV(S) ∧ σV>B 동시 → 불가능
check("CORE-WS", "★이중모순 헤드라인", unsat,
      [B > 0, sig > 0, V > 0, R <= B, R >= sig * V, sig * V > B])

print("\n── (F) free-rider는 코어의 코너가 아니다 ──")

# F-INDEP-1: (W) ∧ (F 참여 kn·c≤R) 공존
check("F-INDEP-1", "W와 F 무충돌", sat,
      [R > 0, R <= B, kn > 0, c > 0, kn * c <= R], witness=[R, B, kn, c])

# F-INDEP-2: (S) ∧ (F 참여) 공존
check("F-INDEP-2", "S와 F 무충돌", sat,
      [sig > 0, V > 0, R >= sig * V, kn > 0, c > 0, kn * c <= R], witness=[R, V])

# F-UNDER: 과소공급 영역 kn·c>R, 내부점 R>0 (퇴화 R=0 제거)
check("F-UNDER", "free-rider 과소공급(느슨)", sat,
      [R > 0, c > 0, kn > 0, kn * c > R], witness=[R, c, kn])

# F-DISSOLVE: 전문탐색 amortization c/mm ⟹ 유효 k_eff=R·mm/c 로 참여회복
check("F-DISSOLVE", "amortization이면 (F) 소멸", sat,
      [R > 0, c > 0, kn > 0, mm > 0, R * mm / c >= kn], witness=[mm])

# F-HORN: 반대 뿔 — 무보상(benefit=0) ⟹ 사적 편익<c
check("F-HORN", "무보상→과소공급(반대 뿔)", sat,
      [c > 0, Real("benefit") == 0, Real("benefit") < c])

print("\n── 조건부성: V 유계면 impossibility 소멸 ──")

# REGIME-Vcap: V≤B/σ 안에서 R=σV≤B 해 존재
check("REGIME-Vcap", "V유계면 해 존재(조건부)", sat,
      [B > 0, sig > 0, V > 0, sig * V <= B, R == sig * V], witness=[B, V, R])

print("\n── 탈출구 정직 판정 ──")

# E1-W: 구독모델 bonus=0 ⟹ wash joint=−B<0 항상 → (W) 자명화
check("E1-W", "탈출1 (W) 자명화(bonus=0)", unsat,
      [B > 0, ga >= 0, gc >= 0, 0 - B - ga - gc > 0])

# E1-PART: 참여식 δ·s≥κ (VACUOUS — s≫κ면 항상 참)
check("E1-PART", "탈출1 참여식(VACUOUS)", sat,
      [dlt > 0, dlt < 1, s_sub > 0, kap > 0, dlt * s_sub >= kap], witness=[dlt, s_sub, kap])

# E1-COLLAPSE ★: Msup 정액이면 σV>Msup → 침묵매수 수익 (정리2 재적용)
check("E1-COLLAPSE", "★침묵매수 붕괴=relabeling", sat,
      [Msup > 0, sig > 0, V > 0, sig * V > Msup], witness=[Msup, V, sig])

# E1-SEAL: 봉합엔 Msup≥σV 필요 → value-coupling 재수입(Exp24 회귀)
check("E1-SEAL", "봉합=value-coupling 재수입", unsat,
      [Msup >= sig * V, sig * V > Msup])

# E2-SCALE ★: 도전자 보상 flat≤B ∧ 공격자 담보 s_atk=σV ∧ σV>B — 메커니즘측 V-스케일
check("E2-SCALE", "★진짜 탈출(공격자 담보)", sat,
      [B > 0, sig > 0, V > 0, flat > 0, flat <= B, satk == sig * V, sig * V > B],
      witness=[flat, satk, V])

# E2-UNOBS: 공격시점 V 미관측 ⟹ s_atk 정액화 → σV>s_atk 붕괴 (게이트)
check("E2-UNOBS", "탈출2 게이트(관측 필요)", sat,
      [satk > 0, sig > 0, V > 0, sig * V > satk], witness=[satk, V])

# E3-DYNBOND: 동적담보 B=σV top-up ⟹ R=σV가 (W)∧(S) 충족 (단 V-오라클 대가)
check("E3-DYNBOND", "탈출3 동적담보(V-오라클 대가)", sat,
      [sig > 0, V > 0, B == sig * V, R == sig * V, R <= B, R >= sig * V], witness=[B, R, V])

# E4-GAP: 스테이크 도전+환급, 보상 flat≤B ⟹ σV>flat 규모갭 잔존 ((S) 미완화)
check("E4-GAP", "탈출4 (S) 규모갭 잔존", sat,
      [flat > 0, flat <= B, sig > 0, V > 0, sig * V > flat], witness=[flat, V])

Path("results.json").write_text(json.dumps({
    "experiment": "exp26",
    "title": "Challenger-supply DILEMMA (Exp25 KILL-5): (W) anti-wash vs (S) value-scaling",
    "generated_by": "exp26/prove.py (verified run, 19 checks)",
    "z3_version": "4.12.6",
    "checks": LOG,
    "summary": ("19/19 pass (5 UNSAT + 14 SAT). CORE-WS UNSAT = (W R<=B_spec) & (S R>=sigma*V) "
                "infeasible when sigma*V>B_spec. FORFEIT-INV UNSAT: binding property is "
                "forfeiture-funding, not scalar (rank/lottery/difficulty all bounded by B_spec). "
                "It is a DILEMMA, not a trilemma: (F) free-rider is independent (F-INDEP) and can "
                "dissolve (F-DISSOLVE). Conditional, not unconditional (REGIME-Vcap SAT). Bonded-"
                "auditor subscription escape is RELABELING (E1-COLLAPSE SAT, E1-SEAL UNSAT -> "
                "sealing = re-importing value-coupling = Exp24 unsolved). Genuine escape: move "
                "V-scaling to the ATTACKER's attack-time bond, reward stays flat (E2-SCALE SAT), "
                "gated on attack-time V observability (E2-UNOBS SAT)."),
}, ensure_ascii=False, indent=2))

print("\n" + "=" * 72)
u = sum(PASS)
n_unsat = 5
print(f"결과: {u}/{len(PASS)} 통과  (성립/닫힘 {n_unsat} UNSAT + 증인/경계 {len(PASS)-n_unsat} SAT)")
print("정직 헤드라인: (W)∧(S) 이중모순은 '몰수자금 조달·V-스케일을 도전자보상에·정적담보·V무한'")
print("클래스에서만 진짜(CORE-WS UNSAT). (F)는 코어 아님·소멸가능. 감사자 구독은 relabeling")
print("(E1-COLLAPSE). 유일한 진짜 탈출은 V-스케일을 '공격자 담보'로 옮기는 것(E2-SCALE) — 단")
print("'공격시점 V 관측가능성'이 대가. 공짜 탈출은 없다.")
print("=" * 72)
