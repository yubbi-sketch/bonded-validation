"""Exp29 — 되묻기 게이트 대수의 z3 검사 (설계 단계 · EXP29.md §4).

라벨 규약(Exp27 계승): [THM] 정리(UNSAT 기대) · [WIT] 한계 증인(SAT 기대) · [ENC] 인코딩 확인.
"통과 수"는 성과 지표가 아니다. 셋은 급이 다르다.

기호: B 담보, R 정답 보상, c 되묻기 비용, p 현재 정답 확률, pp 되묻기 후 정답 확률,
      rho 되묻기 표적 슬롯의 top-1 확률(완전 해소 모델 pp = p/rho), tau = B/(B+R).
실행: .venv-halmos/bin/python exp29/prove.py  → exp29/out/prove.json
"""
import json
import os

from z3 import (And, Implies, Int, Not, Or, Real, RealVal, Solver, sat, unsat)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

B, R, c, p, pp, rho, v_ask, p2, phat = (Real(n) for n in "B R c p pp rho v_ask p2 phat".split())
tau = B / (B + R)
V = lambda x: x * R - (1 - x) * B          # 답변 기대이익
dom = And(B > 0, R > 0, c >= 0)

results = []


def check(name, label, expect, formula, note):
    s = Solver()
    s.add(formula)
    r = s.check()
    ok = (r == expect)
    model = str(s.model()) if r == sat else ""
    results.append({"id": name, "label": label, "expect": str(expect), "got": str(r), "pass": ok,
                    "note": note, "witness": model[:200]})
    print(f"[{label}] {name}: {r} (expect {expect}) {'OK' if ok else 'FAIL'} — {note}")
    if model and label == "WIT":
        print(f"        witness: {model[:160]}")
    return ok


# ── C1 [THM] Chow(1970) 등가: 정답 0·오답 B+R·기각 R 비용이면 기각 임계 1−R/(B+R) = τ* ──
# 부정: V(p) ≥ 0 과 (1−p)(B+R) ≤ R 이 어긋나는 p 존재?
check("C1_chow_equivalence", "THM", unsat,
      And(dom, p >= 0, p <= 1, Not((V(p) >= 0) == ((1 - p) * (B + R) <= R))),
      "τ*=B/(B+R) 는 Chow 기각 규칙의 아핀 재표기 (우리 계산, 원문 인용 아님)")

# ── C2 [THM] 바닥: ASK 옵션 값이 무엇이든 ANSWER 가 선택되면 p ≥ τ* ──
# 부정: p < τ* 인데 V(p) ≥ max(0, v_ask) 로 ANSWER 선택?
check("C2_ask_never_lowers_floor", "THM", unsat,
      And(dom, p >= 0, p <= 1, p < tau, V(p) >= 0, V(p) >= v_ask),
      "되묻기 옵션은 답변 임계 τ* 를 절대 낮추지 못함 (Exp18 K2 보존 근거)")

# ── C3 [THM] 되묻기 후 답변 임계: p<τ* 에서 '묻고 답함' > 기권 ⟺ pp > τ* + c/(B+R) ──
check("C3_post_ask_threshold", "THM", unsat,
      And(dom, pp >= 0, pp <= 1, Not((V(pp) - c > 0) == (pp > tau + c / (B + R)))),
      "τ*_ask = τ* + c/(B+R): 비용 c 는 임계를 위로만 민다")

# ── C4 [THM] 묻기 vs 지금 답하기(p ≥ τ*): −c + V(pp) > V(p) ⟺ (pp−p)(B+R) > c ──
check("C4_ask_vs_answer_now", "THM", unsat,
      And(dom, p >= tau, p <= 1, pp >= 0, pp <= 1, Not((V(pp) - c > V(p)) == ((pp - p) * (B + R) > c))),
      "되묻기 이득 조건 = 정보가치 (pp−p)(B+R) 가 비용 c 를 넘을 때")

# ── C3δ [THM] 응답률 δ: 무응답이면 0(잠긴 것 없음). p<τ* 에서 '묻고 답함' > 기권 ⟺ pp > τ* + c/(δ(B+R)) ──
delta = Real("delta")
check("C3d_post_ask_threshold_delta", "THM", unsat,
      And(dom, delta > 0, delta <= 1, pp >= 0, pp <= 1,
          Not((-c + delta * V(pp) > 0) == (pp > tau + c / (delta * (B + R))))),
      "τ*_ask(δ) = τ* + c/(δ(B+R)) — 기제 렌즈 Z3 와 동일식, 다른 인코딩")

# ── C4δ [THM] p ≥ τ*, 무응답이면 원 요청에 p 로 답함(폴백): 묻는 게 이득 ⟺ δ(pp−p)(B+R) > c ──
check("C4d_ask_vs_answer_now_delta", "THM", unsat,
      And(dom, delta > 0, delta <= 1, p >= tau, p <= 1, pp >= 0, pp <= 1,
          Not((-c + delta * V(pp) + (1 - delta) * V(p) > V(p)) == (delta * (pp - p) * (B + R) > c))),
      "폴백 모델(경제 렌즈 V_ask 형)에서도 정보가치 조건은 δ 로 할인될 뿐 형태 불변")

# ── C4b [THM] 완전 해소 모델 pp = p/rho 에서 표적은 rho 최소 슬롯(최약고리) ──
rho2 = Real("rho2")
check("C4b_weakest_link_is_target", "THM", unsat,
      And(dom, p > 0, p <= 1, rho > 0, rho <= 1, rho2 > 0, rho2 <= 1, p <= rho, p <= rho2,
          rho < rho2, Not(p / rho >= p / rho2)),
      "rho 가 작을수록 pp 가 큼 → Exp2 최약고리가 되묻기 표적 선택기")

# ── H1 [WIT] 보류(HOLD) 모델: 정산 시각 T = Tmax + n·d, n 무계 → 임의 상한 초과 가능 ──
n = Int("n")
Tmax, d, L = Real("Tmax"), Real("d"), Real("L")
check("H1_hold_unbounded_delay", "WIT", sat,
      And(Tmax > 0, d > 0, L == 10 * Tmax, n >= 0, Tmax + n * d > L),
      "A2A input-required 류 보류: 되묻기 n 회로 정산이 임의 상한 L 을 넘는 증인 존재")

# ── N1 [ENC] 새 발화(NEW) 모델: 정산 시각은 n 의 함수가 아니다 → 항상 ≤ Tmax ──
check("N1_new_utterance_bounded", "ENC", unsat,
      And(Tmax > 0, d > 0, n >= 0, Tmax > Tmax),  # T(n) ≡ Tmax; 초과 조건은 자기모순
      "R3 무보류: 정산 시각 ≡ Tmax (인코딩 확인 — 구조는 Halmos 로 구현 라운드에 확인)")

# ── M1 [WIT] 자기 신고 확신만 보는 게이트는 낚시 ASK 와 정직 ASK 를 구분 못 한다 ──
tau_ask = tau + c / (B + R)
check("M1_self_reported_indistinguishable", "WIT", sat,
      And(dom, p >= tau, p <= 1, p2 >= 0, p2 < tau, phat >= 0, phat < tau_ask,
          # 두 세계의 관측(phat)이 같고 게이트는 phat 만 읽는다 → 같은 판정
          True),
      "진짜 p≥τ*(낚시)와 p<τ*(정직)가 같은 신고 phat 를 낼 수 있음 (Exp28 B3 재현)")

# ── M2 [ENC] 바인딩(phat ≡ p): ASK 정당성 술어는 공개값의 함수 → 같은 공개값이면 같은 판정 ──
just = lambda x, r: (x / r - x) * (B + R) > c
x1, x2, r1, r2 = Real("x1"), Real("x2"), Real("r1"), Real("r2")
check("M2_bound_confidence_decidable", "ENC", unsat,
      And(dom, x1 == x2, r1 == r2, r1 > 0, r1 <= 1, x1 >= 0, x1 <= r1, Not(just(x1, r1) == just(x2, r2))),
      "로짓 바인딩 하에서 '되묻기가 정당했다' 는 공개값으로 결정가능 (회로는 미구현, 인터페이스만)")

# ── 수치 확인(설계 문서 §4.4 예시) ──
s = Solver()
s.add(B == 5, R == 1, c == RealVal("0.05"))
s.check()
m = s.model()
tau_num = 5 / 6
tau_ask_num = tau_num + 0.05 / 6
print(f"numeric: B=5 R=1 c=0.05 → τ*={tau_num:.4f}, τ*_ask={tau_ask_num:.4f}")

summary = {k: sum(1 for r in results if r["label"] == k) for k in ("THM", "WIT", "ENC")}
all_ok = all(r["pass"] for r in results)
out = {"experiment": "exp29", "stage": "design-algebra", "checks": results, "summary": summary,
       "all_pass": all_ok, "numeric": {"B": 5, "R": 1, "c": 0.05, "tau_star": tau_num, "tau_ask": tau_ask_num}}
json.dump(out, open(os.path.join(OUT, "prove.json"), "w"), indent=2, ensure_ascii=False)
print(f"summary: {summary} all_pass={all_ok}")
if not all_ok:
    raise SystemExit(1)
