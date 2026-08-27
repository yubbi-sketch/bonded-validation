"""Exp25 — 담보된 명세(bonded specification) 탐지층의 기계 검증 (z3).

사건 B(Strategy BTC 매도 시장, $80M+): "5/31까지 매도"가 event-time인가 disclosure-time인가라는
결의 기준의 정의 모호성. 판정 슬래시로는 못 고침(정답이 명확해야 벌하는데 정의가 미정).
아이디어: 결의 명세를 술어로 형식화해, 자금 유입 *전에* 모호성을 기계 탐지하고 저자 담보에 건다.

이 스크립트는 그 **탐지층**만 검증한다(인센티브·컨트랙트 불변식은 미검증 산문 — 정직 §참고).
모호성 = 명명된 두 해석이 어떤 세계상태 ω에서 불일치(DISAGREEMENT) 또는 R(ω)=UNDEFINED.
판정은 SAT(모호 증인 존재)/UNSAT(반례 부재 = 무모호 증명)의 이분.

적대검증 3렌즈가 원 주장을 크게 좁혔다(전부 needs-scoping) — 이 세션 5번째 자기교정.
정직 헤드라인(종합 연구원): **담보된 명세는 사건 B를 '해결'하지 못한다.** 오직 '형식화 가능한
좁은 슬라이스'(열거된 crisp 해석쌍 불일치 + UNDEFINED)만 자금 전에 표면화한다.

  못박아 닫히는 것(UNSAT):  z3-2·z3-4 타이밍 pin,  z3-7 UNDEFINED 가드,
                            z3-11 gradable threshold 커밋,  z3-14 Ω 멤버십(건전성 회복)
  치명적 무능(UNSAT이 곧 '못 고침'): z3-9 — 사건 B엔 독립 event 오라클이 없어 event-pin ≡
                            disclosure-pin → 이 못박기가 사건 B에 대해 공허(vacuous)
  탐지되는 모호성 + 정직 경계(SAT): z3-1 사건B 타이밍 재현 · z3-3 UNDEFINED 구멍 ·
                            z3-5 열거밖 제3해석 · z3-6 비교자 포함성 · z3-8 오라클 측정분쟁 ·
                            z3-10 술어수준('질권도 매도?' — 사건B의 *지배적* 모호성) ·
                            z3-12 미커밋 gradable · z3-13 Ω 미검증 false-positive
"""
import json
from pathlib import Path
from z3 import And, Bool, If, Int, Not, Or, Implies, Solver, sat, unsat

YES, NO = 1, 0
PASS = []
LOG = []


def check(cid, note, expect, cons, witness=None):
    s = Solver()
    s.add(And(*cons))
    r = s.check()
    ok = (r == expect)
    print(f"[{'OK ' if ok else 'FAIL'}] {cid} {note}: {r} (기대 {expect})")
    if witness and r == sat:
        m = s.model()
        print("        증인: " + ", ".join(f"{v}={m[v]}" for v in witness))
    PASS.append(ok)
    LOG.append({"id": cid, "note": note, "expected": str(expect), "result": str(r), "ok": ok})
    assert ok, cid
    return s


# 세계상태 필드
et, dt, dl = Int("et"), Int("dt"), Int("dl")          # event_time, disc_time, deadline
settle, o1, o2 = Int("settle"), Int("o1"), Int("o2")  # settlement / oracle1 / oracle2 event_time
frac, t1, t2 = Int("frac"), Int("t1"), Int("t2")      # sold_fraction, thresholds
has_filing, is_pledge, plain_sale = Bool("has_filing"), Bool("is_pledge"), Bool("plain_sale")


def by(x):          # "x ≤ deadline 이면 YES(1) 아니면 NO(0)" (inclusive reading)
    return If(x <= dl, YES, NO)


print("=" * 70)
print("Exp25 · 담보된 명세 탐지층 — z3 기계 검증 (사건 B: 결의 기준 모호성)")
print("=" * 70)
print("\n── 사건 B 타이밍 모호성: 탐지(SAT) → 못박아 닫기(UNSAT) ──")

# z3-1: 미명세 I={event,disclosure}, Strategy 세계 → 두 해석 불일치 (SAT)
check("z3-1", "사건B 타이밍 모호성 재현", sat,
      [et <= dl, dt > dl, by(et) != by(dt)], witness=[et, dt, dl])

# z3-2: event-time 단일 해석으로 못박음 → 불일치 불가 (UNSAT)
check("z3-2", "event-pin 무모호 증명", unsat,
      [by(et) != by(et)])

# z3-4: disclosure-time 단일 해석도 무모호(대칭) (UNSAT)
check("z3-4", "disclosure-pin 무모호(대칭)", unsat,
      [by(dt) != by(dt)])

print("\n── UNDEFINED 구멍: 탐지(SAT) → 총함수 가드로 닫기(UNSAT) ──")

spec_refs_disc = Bool("spec_refs_disc")
undef = And(spec_refs_disc, Not(has_filing))     # disclosure 참조인데 파일링 부재

# z3-3: 파일링 부재 → R=UNDEFINED (SAT)
check("z3-3", "UNDEFINED 구멍 존재", sat,
      [spec_refs_disc, Not(has_filing), undef], witness=[spec_refs_disc, has_filing])

# z3-7: 총함수 가드(disc ⇒ has_filing) 부여 시 UNDEFINED 소거 (UNSAT)
check("z3-7", "가드로 UNDEFINED 닫힘", unsat,
      [Implies(spec_refs_disc, has_filing), undef])

print("\n── 치명적 무능: 사건 B는 이 층으로 '못 고침' (UNSAT = 공허) ──")

obs_et = Int("obs_et")   # 독립 오라클 없이 오직 공시로만 관측된 event_time
# z3-9: 사건 B에서 obs_et==dt → event-pin ≡ disclosure-pin, 분리 불가 (UNSAT)
check("z3-9", "event-pin≡disclosure-pin(사건B 철회)", unsat,
      [obs_et == dt, If(obs_et <= dl, YES, NO) != by(dt)])

print("\n── 정직 경계: 이 층이 '못 잡는' 모호성 클래스 (SAT) ──")

# z3-5: event/disclosure 다 못박아도 열거밖 제3해석 settlement-time 불일치 (SAT)
check("z3-5", "열거밖 제3해석(settlement)", sat,
      [et <= dl, settle > dl, by(et) != by(settle)], witness=[et, settle, dl])

# z3-6: 비교자 포함성 ≤ vs < 가 et==dl 에서 갈림 (SAT)
check("z3-6", "비교자 포함성 축", sat,
      [et == dl, If(et <= dl, YES, NO) != If(et < dl, YES, NO)], witness=[et, dl])

# z3-8: 명세 무모호라도 event_time 측정 두 오라클 불일치 (SAT) — 측정층, 판정담보 소관
check("z3-8", "오라클 측정분쟁(별 층)", sat,
      [o1 <= dl, o2 > dl, If(o1 <= dl, YES, NO) != If(o2 <= dl, YES, NO)], witness=[o1, o2, dl])

# z3-10: 타이밍 다 못박아도 '질권을 매도로 치나' 술어수준 불일치 (SAT) — 사건 B의 *지배적* 모호성
r_broad = If(And(Or(is_pledge, plain_sale), et <= dl), YES, NO)   # 질권도 매도로 침
r_narrow = If(And(plain_sale, et <= dl), YES, NO)                 # 실매도만
check("z3-10", "술어수준('질권도 매도?')=사건B 지배 모호성", sat,
      [is_pledge, Not(plain_sale), et <= dl, r_broad != r_narrow], witness=[is_pledge, plain_sale, et])

print("\n── gradable 술어: 미커밋 누출(SAT) → threshold 커밋으로 닫기(UNSAT) ──")

def geq(x, t):
    return If(x >= t, YES, NO)

# z3-12: threshold 미커밋(t1<t2)이면 그 사이 fraction에서 불일치 (SAT)
check("z3-12", "미커밋 gradable 누출", sat,
      [t1 < t2, t1 <= frac, frac < t2, geq(frac, t1) != geq(frac, t2)], witness=[t1, t2, frac])

# z3-11: threshold 커밋(t1==t2)이면 무모호 (UNSAT)
check("z3-11", "gradable threshold 커밋으로 닫힘", unsat,
      [t1 == t2, geq(frac, t1) != geq(frac, t2)])

print("\n── 건전성: Ω 미검증 false-positive(SAT) → 멤버십 가드로 회복(UNSAT) ──")

# z3-13: 정직 spec(실현도메인 et==dt)인데 멤버십 미검증 → 배제된 ω*로 false-positive (SAT)
check("z3-13", "Ω 미검증 false-positive(불건전)", sat,
      [et <= dl, dt > dl, by(et) != by(dt)], witness=[et, dt, dl])

# z3-14: 검증자가 ω*∈Ω_committed(et==dt) 멤버십 강제 → false-positive 불가 (UNSAT)
check("z3-14", "Ω 멤버십 가드로 건전성 회복", unsat,
      [et == dt, by(et) != by(dt)])

Path("results.json").write_text(json.dumps({
    "experiment": "exp25",
    "title": "Bonded Specification — detection layer (Case B: Strategy BTC sale market)",
    "layer": "specification (NOT verdict) — orthogonal to exp13/exp24 slashing",
    "z3_version": "4.12.6",
    "generated_by": "exp25/prove.py (verified run, 14 checks)",
    "checks": LOG,
    "summary": (f"{sum(PASS)}/{len(PASS)} pass. 6 UNSAT (closure/vacuity) + 8 SAT "
                "(Strategy reproduction + honest boundaries). z3-9 UNSAT is the machine proof "
                "that bonded spec does NOT fix Case B (no independent event oracle -> event-pin "
                "== disclosure-pin). Dominant real ambiguity is predicate-level (z3-10) / "
                "unenumerated (z3-5), outside detection. Only detection layer is machine-verified; "
                "contract invariants INV-1..10 and the incentive dilemma are unverified prose."),
}, ensure_ascii=False, indent=2))

print("\n" + "=" * 70)
u = sum(PASS)
print(f"결과: {u}/{len(PASS)} 통과  (무모호/닫힘 6건 UNSAT + 모호/경계 8건 SAT)")
print("정직 헤드라인: 담보된 명세는 사건 B를 '해결'하지 못한다. z3-9(UNSAT)가")
print("그 기계적 증거 — 독립 event 오라클이 없어 못박기가 공허. 지배적 모호성은")
print("술어수준(z3-10)·열거밖(z3-5)이라 탐지 밖. 오직 '형식화 가능한 좁은 슬라이스'만")
print("자금 전 표면화한다. value-coupling이 BornTooLate를 못 고쳤듯, 이 층도 사건 B를")
print("'표면화 대상으로 좁게 재정의'할 뿐 소멸시키지 않는다.")
print("=" * 70)
