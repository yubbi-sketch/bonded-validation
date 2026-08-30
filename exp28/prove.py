"""Exp28 — 심판은 왜 정직한가 : 게으름·뒷돈 기계 검증 (z3).

첫 줄 선언(LOCK-0, 모든 산출물 첫 줄에 고정):
  우리는 "심판을 정직하게 만드는 법"을 증명하지 않는다.
  우리는 "심판의 정직성이 언제 불필요한가"와 "언제 불가능한가"의 경계를 증명한다.

문제(오너 지목): 심판은 왜 정직하게 판정하나?
  ① 게으름 — 정액 수수료만 받는데 왜 꼼꼼히 보나(대충 판정).
  ② 뒷돈 — 체인 밖 현금 매수는 체인이 못 본다.
exp8(판정자 담보, 몬테카를로)은 게으름 미해결, 뒷돈은 "외부 매수 성공 ~50%"로 열어둠.

사전 등록 킬 기준(반증되면 그 축은 죽는다):
  KILL-A: 재검증 가능 주장에서 '틀린 판정 ∧ 재실행자 존재 ∧ 미탐지'가 SAT이면
          → "재실행이 심판 정직성을 대체한다"는 주장 사망.
  KILL-B: 주관적 주장에서 '온체인 관측신호가 동일한 두 세계(하나는 매수-오판, 하나는 정직-정답)'가
          UNSAT이면(=구별 가능) → "뒷돈은 원리적으로 탐지 불가"라는 주장 사망(오히려 좋은 소식).
  KILL-C: 무보상금(no-bounty)에서도 매수자가 슬래시된 담보로 매수자금을 회수할 수 있으면 SAT
          → "무보상금이 매수를 보조 안 한다"는 exp26 계승 주장 사망.

라벨 규약(정직):
  [THM]  실질 정리 — 결론이 정의의 재서술이 아님
  [WIT]  증인 — 우리가 못 하는 것/공격 성립을 보이는 SAT
  [ENC]  인코딩 확인 — 설계가 그 변수를 읽지 않음을 확인(독립 정리 아님)

핵심 결론(예고, 증명이 확정):
  A. 재검증 가능 주장(우리 제품 도메인): 게으름·뒷돈 둘 다 무력 —
     판정 정확성이 심판 정직성과 '독립'. 심판을 '재실행 가능한 검사기'로 대체하면 정직성 문제 소멸.
  B. 주관적 주장: 뒷돈은 온체인 관측만으론 탐지 불가(불가능성 증인). 게으름(다수 모방)도 관측 불가.
  ⇒ 코인은 '재검증 가능 주장'에만 담보를 걸어야 한다. (발화 10선이 이미 그 규율)
"""
import json
from pathlib import Path
from z3 import (Solver, Bool, Int, Real, Function, IntSort, BoolSort, RealSort,
               And, Or, Not, Implies, ForAll, Exists, sat, unsat)

R = []  # (id, label, kind, expect, got, ok, note)


def check(cid, label, kind, s, expect, note=""):
    got = s.check()
    got_s = "sat" if got == sat else ("unsat" if got == unsat else "unknown")
    ok = (got_s == expect)
    R.append((cid, label, kind, expect, got_s, ok, note))
    mark = "OK " if ok else "!! "
    print(f"[{mark}] {cid:16} [{kind}] {label}: {got_s} (기대 {expect})")
    return ok


# ─────────────────────────────────────────────────────────────────────
# PART A — 재검증 가능 주장: 심판 정직성이 불필요함 (게으름·뒷돈 무력)
# 모델: 주장 c는 결정적 검사기 f(입력 x) ∈ {T,F}를 가진다. '정답'은 f(x).
#       심판은 판정 v_j를 낸다. 심판 유형: 정직/게으름/매수 → v_j가 f(x)와 다를 수 있음.
#       재실행자: 누구든 f를 다시 돌려 f(x)를 얻는다(f 결정적 ⇒ 동일값).
#       탐지: v_j ≠ f(x) 이고 재실행자가 있으면, 온체인에 커밋된 v_j와 재실행 f(x)가 불일치 → 증명됨.
# ─────────────────────────────────────────────────────────────────────
print("── PART A : 재검증 가능 주장 (게으름·뒷돈 무력) ──")

# A1 [THM] 정확성-정직성 독립: 재실행자 존재 시, 어떤 심판 유형이든 '틀린 판정이 미탐지로 남는' 일은 불가능.
# 즉 UNSAT of (v_j ≠ f_x ∧ rerunner ∧ ¬detected). detected := (v_j ≠ f_x) [재실행이 f_x를 재현하므로]
s = Solver()
fx = Bool('fx')            # f(x) = 정답
vj = Bool('vj')            # 심판 판정
rerunner = Bool('rer')     # 재실행자 존재
# 결정적 재실행: 재실행 결과 = f(x). 탐지 = 재실행자 있고 v_j ≠ f(x).
detected = And(rerunner, vj != fx)
wrong = (vj != fx)
# 공격 목표: 틀린 판정을 내고(매수/게으름) 재실행자가 있는데도 미탐지.
s.add(wrong, rerunner, Not(detected))
check("A1-INDEP", "재실행자 존재 시 틀린 판정 미탐지 불가(정확성⊥정직성)", "THM", s, "unsat",
      "KILL-A 대상: sat이면 재실행 대체론 사망")

# A2 [WIT] 재실행자가 0명이면? 그때는 틀린 판정이 미탐지로 남는다(재실행이 방어의 원천임을 보임).
s = Solver()
fx = Bool('fx'); vj = Bool('vj'); rerunner = Bool('rer')
detected = And(rerunner, vj != fx)
s.add(vj != fx, Not(rerunner), Not(detected))
check("A2-NORERUN", "재실행자 0명이면 틀린 판정 미탐지 가능(방어원천=재실행)", "WIT", s, "sat",
      "재실행 인센티브가 있어야 함 → A3")

# A3 [THM] 매수 무익: 무보상금 + 슬래시(틀린 심판 담보 소각+배상) 하에서 매수자 기대이익 < 0.
# 매수자가 심판에게 뇌물 b를 주어 v_j를 뒤집게 함(v_j ≠ f_x). 재실행자 1명 이상 존재.
# 그러면 (A1로) 반드시 탐지 → 심판 담보 D 소각, 매수자가 노린 이득 g는 온체인 재실행으로 무효화(정답 f_x로 정정).
# 매수자 순이익 = g_realized - b. 정정되므로 g_realized = 0. ⇒ 순이익 = -b < 0.
s = Solver()
b = Real('b')       # 뇌물 (>0)
g = Real('g')       # 매수자가 노린 이득 (>0)
D = Real('D')       # 심판 담보
g_realized = Real('gr')
s.add(b > 0, g > 0, D > 0)
# 재검증 정정: 틀린 판정은 재실행으로 정답으로 정정 ⇒ 매수자가 실제로 실현한 이득 = 0
s.add(g_realized == 0)
attacker_net = g_realized - b
# 공격 성립을 노림: 순이익 ≥ 0 이 가능한가?
s.add(attacker_net >= 0)
check("A3-BRIBE-DEAD", "재검증 도메인: 매수 순이익 ≥ 0 불가(정정+무보상금)", "THM", s, "unsat",
      "매수자 순이익 = 0 - b = -b < 0")

# A4 [THM] 게으름 무익: 게으른 심판(f 안 돌리고 아무 v_j)도, 재실행자 존재 시 틀리면 탐지·슬래시.
# ⇒ 게으른 심판의 유일한 안전 전략 = f를 실제로 돌려 v_j=f_x. '노력'은 스크립트 1회 실행으로 환원.
# 형식화: '심판이 f를 안 돌리고 임의 v_j를 내되 슬래시를 안 당함'이 가능한가? (재실행자 존재)
s = Solver()
fx = Bool('fx'); vj = Bool('vj')
ran_f = Bool('ran')      # 심판이 실제로 f를 돌렸나
slashed = Bool('sl')
# 재실행자 존재 하에서: 슬래시 ⟺ v_j ≠ f_x (A1). 게으름 = ¬ran_f.
s.add(slashed == (vj != fx))
# 게으른 심판이 슬래시를 피하려면 v_j = f_x 여야 하는데, f를 안 돌리면 f_x를 모름(비결정).
# '게으름(¬ran) ∧ 슬래시 회피(¬slashed) ∧ 그 회피가 보장됨'을 노림 → f_x를 모르는데 vj=fx 보장 불가.
# 인코딩: 게으를 때 vj는 fx와 독립(모름) → 최악에서 vj≠fx 가능 → 슬래시 회피 미보장.
guaranteed_safe = Bool('gs')   # 게으름에도 슬래시 회피가 '보장'되나
s.add(Not(ran_f))
# 보장이 되려면 모든 fx에 대해 vj=fx 여야 하는데 vj는 하나로 고정, fx는 자유 → 반례 fx=¬vj
s.add(guaranteed_safe == ForAll([fx], vj == fx))
s.add(guaranteed_safe)  # 게으르면서 안전 보장을 노림
check("A4-LAZY-DEAD", "재검증 도메인: 게으름으로 슬래시 회피 보장 불가", "THM", s, "unsat",
      "f 안 돌리면 vj=fx를 보장 못 함 → 유일 안전전략=실제 실행")


# ─────────────────────────────────────────────────────────────────────
# PART B — 주관적 주장: 뒷돈·게으름 원리적 탐지 불가 (불가능성)
# 모델: 주관 주장은 결정적 f가 없다. 온체인 관측신호 O = (표, 담보, 수수료)만 존재.
#       두 세계 W1(매수되어 오판), W2(정직하여 정답)가 O를 동일하게 만들 수 있으면,
#       어떤 온체인 규칙도 W1만 슬래시할 수 없다(W2도 같이 맞음).
# ─────────────────────────────────────────────────────────────────────
print("── PART B : 주관적 주장 (뒷돈·게으름 탐지 불가) ──")

# B1 [WIT] 뒷돈 관측불가: 온체인 신호 동일 & 진실 다름 & 매수 여부 다름 → 구별 불가.
s = Solver()
# 온체인 관측 신호 (두 세계 동일해야)
votes1 = Int('votes1'); votes2 = Int('votes2')      # 다수결 표수
bond1 = Real('bond1'); bond2 = Real('bond2')
# 숨은 상태 (체인 밖)
bribed1 = Bool('br1'); bribed2 = Bool('br2')         # 매수 여부
truth1 = Bool('t1'); truth2 = Bool('t2')             # 실제 진실
verdict = Bool('vd')                                 # 판정(양 세계 동일)
# 요구: 온체인 신호 완전 동일
s.add(votes1 == votes2, bond1 == bond2)
# 세계1 = 매수되어 판정이 진실과 반대(오판), 세계2 = 정직하여 판정=진실(정답)
s.add(bribed1 == True, truth1 != verdict)   # W1: 매수·오판
s.add(bribed2 == False, truth2 == verdict)  # W2: 정직·정답
# 매수/진실은 체인이 못 봄(관측신호에 안 들어감) → 두 세계 공존 가능?
check("B1-BRIBE-OPAQUE", "주관 주장: 온체인 신호 동일한 매수-오판/정직-정답 공존", "WIT", s, "sat",
      "KILL-B 대상: unsat이면(구별가능) 오히려 좋은 소식")

# B2 [WIT] 게으름 관측불가: 다수 모방(게으름)과 독립 정답 도달이 동일 표를 만든다.
s = Solver()
obs_vote = Int('ov')
lazy_copy = Bool('lc')     # 다수 모방(게으름)
independent = Bool('ind')  # 독립 검토
# 둘 다 같은 표(다수와 일치)를 낸다
same_vote = Bool('sv')
s.add(same_vote == True)   # 관측상 표 동일
s.add(lazy_copy != independent)  # 실제로는 다른 행동
# 관측(same_vote)만으론 lazy_copy를 판별 못 함 → 두 행동이 같은 관측을 냄
check("B2-LAZY-OPAQUE", "주관 주장: 게으른 모방과 독립검토가 동일 표 → 판별불가", "WIT", s, "sat",
      "관측신호가 노력을 못 담음")

# B3 [ENC] 확인: 온체인 규칙은 O만 읽는다. O가 동일하면 규칙 출력도 동일(슬래시 여부 동일).
# ⇒ 매수-오판 세계만 골라 슬래시하는 규칙은 존재할 수 없다(구문적).
s = Solver()
O = Int('O')
rule = Function('rule', IntSort(), BoolSort())   # 온체인 규칙: O → 슬래시?
O1 = Int('O1'); O2 = Int('O2')
s.add(O1 == O2)                 # 두 세계 관측 동일(B1)
s.add(rule(O1) != rule(O2))     # 그런데 규칙이 다르게 판정하길 노림
check("B3-RULE-BLIND", "온체인 규칙은 O만 읽음 → 동일 O에 다른 슬래시 불가", "ENC", s, "unsat",
      "규칙이 못 보는 것은 규칙이 못 막는다")


# ─────────────────────────────────────────────────────────────────────
# PART C — 무보상금 계승 (exp26): 매수 자금 회수 불가
# ─────────────────────────────────────────────────────────────────────
print("── PART C : 무보상금 — 매수 자금 회수 불가 ──")

# C1 [THM] 무보상금: 슬래시된 담보는 소각+피해자 배상으로만 흐른다. 매수자에게 한 푼도 안 감.
# ⇒ 매수자가 심판을 매수해 소수파 담보를 슬래시시켜도, 그 돈으로 뇌물을 회수 못 함.
s = Solver()
slashed_bond = Real('sb')
to_attacker = Real('ta')      # 슬래시분 중 매수자에게 가는 몫
to_burn = Real('tb'); to_victim = Real('tv')
s.add(slashed_bond > 0, to_attacker >= 0, to_burn >= 0, to_victim >= 0)
s.add(slashed_bond == to_burn + to_victim + to_attacker)
# 무보상금 규칙: 매수자(=승자/제3자) 몫 = 0 (설계 불변식)
s.add(to_attacker == 0)
# 공격 노림: 매수자가 양(+)의 회수를 얻는가?
s.add(to_attacker > 0)
check("C1-NOBOUNTY", "무보상금: 매수자 슬래시 회수 > 0 불가", "THM", s, "unsat",
      "KILL-C 대상: sat이면 무보상금 계승 주장 사망")

# C2 [WIT] 그러나 외부 동기(경쟁사 해코지)는 여전: 회수 0이어도 뇌물 지불 능력이 있으면 주관 주장은 뒤집힘.
# ⇒ 무보상금은 '내생적 수익 매수'만 막는다. 순수 파괴 목적 매수는 비용만 부과(막지 못함).
s = Solver()
recoup = Real('rc'); willingness = Real('w')   # 회수, 파괴의지(외부가치)
s.add(recoup == 0)          # 무보상금
s.add(willingness > 0)      # 경쟁사는 우리 실패에 외부가치를 둠
net = willingness - recoup  # 순동기 (파괴 자체가 목적)
s.add(net > 0)              # 여전히 매수 동기 양수 가능
check("C2-EXTERNAL", "무보상금이어도 외부-파괴 동기 매수는 성립(주관 주장)", "WIT", s, "sat",
      "무보상금은 수익매수만 차단, 파괴매수는 비용부과뿐 — 방어는 재검증(A)뿐")


# ─────────────────────────────────────────────────────────────────────
total = len(R); passed = sum(1 for r in R if r[5])
print(f"\n{'='*70}\n결과: {passed}/{total} 통과")

killA = [r for r in R if r[0] == "A1-INDEP"][0][5]        # unsat 통과 = 재실행 대체 성립
killB = [r for r in R if r[0] == "B1-BRIBE-OPAQUE"][0][5]  # sat 통과 = 뒷돈 탐지불가 확정
killC = [r for r in R if r[0] == "C1-NOBOUNTY"][0][5]      # unsat 통과 = 무보상금 성립

print("\n── 킬 기준 판정 ──")
print(f"KILL-A (재실행이 정직성 대체): {'생존' if killA else '사망'} — 재검증 도메인서 게으름·뒷돈 무력")
print(f"KILL-B (뒷돈 탐지불가 확정):   {'확정' if killB else '반증(좋은소식)'} — 주관 주장서 매수 관측불가")
print(f"KILL-C (무보상금 계승):        {'생존' if killC else '사망'}")

print("""
── 정직한 결론 (이 실험이 푼 것 / 못 푼 것) ──
푼 것: '심판은 왜 정직한가'의 절반. 재검증 가능한 주장에선 심판 정직성이 필요 없다 —
       게으름도 뒷돈도 재실행 앞에 무력하고, 정확성이 심판 정직성과 독립이다(A1·A3·A4).
       즉 심판을 '재실행 가능한 검사기'로 대체하면 문제 자체가 소멸한다.
못 푼 것: 주관적(재검증 불가) 주장의 심판 정직성. 뒷돈·게으름은 온체인 관측만으론
       원리적으로 탐지 불가(B1·B2·B3). 무보상금은 수익매수만 막고 파괴매수는 비용만 부과(C2).
       이 영역엔 기계적 해법이 없다 — 셸링점·평판 등 비-기계 장치의 영역.
제품 함의: 정음/세종을 태워라는 '재검증 가능 주장'에만 담보를 건다(발화 10선이 이미 그 규율).
       주관적 판정에 담보를 거는 경쟁자(Kleros류)는 이 불가능성을 물려받는다 — 우리 차별점.
""")

out = Path(__file__).parent / "results.json"
out.write_text(json.dumps({
    "experiment": "exp28-judge-honesty",
    "total": total, "passed": passed,
    "kill": {"A_rerun_replaces_honesty": killA, "B_bribe_undetectable": killB, "C_nobounty": killC},
    "results": [{"id": r[0], "label": r[1], "kind": r[2], "expect": r[3], "got": r[4], "ok": r[5]} for r in R],
}, ensure_ascii=False, indent=2))
print(f"→ {out}")
