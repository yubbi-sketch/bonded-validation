"""Exp29 — 결정 규칙의 대수 명제 z3 스케치 (설계 단계, 사전등록 전 자기검증).

라벨 규약 (Exp27/30 계승): [THM] 정리 (부정이 UNSAT) · [WIT] 한계 증인 (SAT) · [ENC] 인코딩 확인.
'통과 수'는 성과 지표가 아니다. 이 스크립트는 문서 §3 의 식이 대수적으로 맞는지만 본다 —
메커니즘 안전성·컨트랙트 불변식은 다루지 않는다(컨트랙트 무수정이 설계의 전제).

재현: cd exp29 && ../.venv-halmos/bin/python prove_sketch.py
"""
from z3 import And, Implies, Not, Or, Real, RealVal, Solver, sat, unsat, If

results = []


def check(name, kind, formula, expect):
    s = Solver()
    s.add(formula)
    r = s.check()
    ok = (r == expect)
    results.append((name, kind, str(r), "PASS" if ok else "FAIL"))
    print(f"[{kind}] {name}: {r} ({'PASS' if ok else 'FAIL'})")
    return s


B, R, c, pi, kappa, delta, q = Real("B"), Real("R"), Real("c"), Real("pi"), Real("kappa"), Real("delta"), Real("q")
dom = And(B > 0, R > 0, c >= 0, c <= 1, pi >= 0, pi <= 1, kappa >= 0, delta > 0, delta <= 1)
tau_star = B / (B + R)


def U(x):
    return x * R - (1 - x) * B


def pos(x):
    return If(x > 0, x, RealVal(0))


# Z1 [THM] τ* 특성화: U_speak(q) ≥ 0 ⟺ q ≥ B/(B+R)  — 새 발화 r' 에도 동일 (되묻기가 τ* 를 바꾸지 않음)
check("Z1 tau* characterization (Chow 1970 affine form)", "THM",
      And(dom, q >= 0, q <= 1, Not(Or(And(U(q) >= 0, q >= tau_star), And(U(q) < 0, q < tau_star)))), unsat)

# Z2 [THM] 옵션가치 비음: 2해석 라벨 갈림, 동일 c. q_speak = c·max(π,1−π) ≤ c.
#          E_θ[max(U(c),0)] − max(U(q_speak),0) ≥ 0
qs = c * If(pi >= 1 - pi, pi, 1 - pi)
gain = pos(U(c)) - pos(U(qs))
check("Z2 option value of asking is non-negative", "THM", And(dom, gain < 0), unsat)

# Z3 [THM] τ_ask 특성화: q_speak < τ* 구간에서  δ·gain > κ  ⟺  c > τ* + κ/(δ(B+R))
tau_ask = tau_star + kappa / (delta * (B + R))
lhs = delta * pos(U(c)) - kappa > 0          # ask beats abstain (=0)  [q_speak < τ* 이면 speak < 0]
rhs = c > tau_ask
check("Z3 tau_ask = tau* + kappa/(delta(B+R))", "THM",
      And(dom, qs < tau_star, Not(Or(And(lhs, rhs), And(Not(lhs), Not(rhs))))), unsat)

# Z4 [THM] τ_ask ≥ τ*: 되묻기는 '답한 뒤 확신이 τ* 를 여유 κ/(δ(B+R)) 만큼 넘길 때'만 정당 — 문턱이 내려가지 않는다
check("Z4 tau_ask >= tau* (asking never lowers the bar)", "THM", And(dom, tau_ask < tau_star), unsat)

# Z5 [WIT] '보류(hold)' 의미론의 잠금 무계: 상대가 t_ans 뒤에 답하면 hold 는 t_ans 만큼 담보를 잠근다.
#          ∀ 상한 T 에 대해 t_ans > T 인 세계가 존재 (SAT 증인) — A2A input-required·Reality.eth 대조군.
#          우리(새 발화) 모드 B 잠금 = W (Exp30), 모드 P = 0 — t_ans 와 독립.
T, t_ans, W = Real("T"), Real("t_ans"), Real("W")
lock_hold = t_ans
lock_ours_B = W
check("Z5 hold-semantics lock exceeds any bound T (witness)", "WIT",
      And(T > 0, W > 0, t_ans >= 0, lock_hold > T, lock_ours_B <= W), sat)

# Z6 [ENC] 우리 모드 B 잠금은 t_ans 와 무관하게 W 이하 — 되묻기 횟수 n 과도 무관(각 발화가 독립 W)
n = Real("n")
check("Z6 ours: lock <= W regardless of t_ans and depth n", "ENC",
      And(W > 0, t_ans >= 0, n >= 0, Not(lock_ours_B <= W)), unsat)

# Z7 [THM] κ 를 '되묻기 수수료'로 원 발화 담보에서 떼면(Gemini 안) τ* 가 (B−κ)/(B+R) 로 내려가 기권이 준다
#          — 되묻기 비용은 담보에서 떼면 안 되고(ERC 불변식 2) 별도 κ 로만 (문서 §3.4)
tau_fee = (B - kappa) / (B + R)
check("Z7 abstain-fee from bond lowers tau* (why kappa must be separate)", "THM",
      And(dom, kappa > 0, kappa < B, Not(tau_fee < tau_star)), unsat)

print()
thm = sum(1 for _, k, _, ok in results if k == "THM" and ok == "PASS")
wit = sum(1 for _, k, _, ok in results if k == "WIT" and ok == "PASS")
enc = sum(1 for _, k, _, ok in results if k == "ENC" and ok == "PASS")
fails = [n_ for n_, _, _, ok in results if ok != "PASS"]
print(f"[THM] {thm} · [WIT] {wit} · [ENC] {enc} · FAIL {len(fails)} {fails}")
