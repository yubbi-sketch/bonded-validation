"""Exp29 — 3분할 결정 규칙 (발화 / 되묻기 / 기권) — 순수 NumPy, 의존성 0.

게임 (Exp18 계승): 발화 = 담보 B 스테이크, 정답 +R, 오답 −B. 기권 = 0.
되묻기 = 비용 κ 를 내고, 확률 δ 로 해석 θ 를 알게 된 뒤 새 발화(r')를 연다. 원 발화는 기권(0).

기호:
  I = {r_1..r_k} 열거 해석집합, p_i = 해석 사전분포(추출기 소프트맥스 또는 균등),
  a_i ∈ {0,1} = 해석 i 로 못박았을 때 파이프라인 답(검증기, 결정론),
  c_i ∈ [0,1] = 해석 i 로 못박은 문장열에 대한 추출기 확신(최약고리 min-softmax, Exp2),
  τ* = B/(B+R)  (Chow 1970 기각 규칙의 아핀 재표기; Exp18 K2 가 창발 실측).

지금 답하기(ask 없이):  ℓ̂ = argmax_ℓ Σ_i p_i [a_i = ℓ],  q_speak = c_min · Σ_i p_i [a_i = ℓ̂]
  U_speak = q_speak·R − (1 − q_speak)·B
기권:                   U_abstain = 0
되묻기:                 U_ask = −κ + δ · Σ_i p_i · max(c_i·R − (1 − c_i)·B, 0)
                        (답이 안 오면(1−δ) 아무 것도 열리지 않고 0 — 잠긴 것이 없으므로)
결정 = argmax{U_speak, 0, U_ask}, 동률은 기권(보수적).

정리(문서 §3): U_speak ≥ 0 ⟺ q_speak ≥ τ*  — 새 발화 r' 에도 같은 τ* 가 적용된다(되묻기는 τ* 를 바꾸지 않는다).
대칭 2해석·c_i = c 일 때 q_speak < τ* 구간에서: ask ⟺ c > τ_ask := τ* + κ / (δ·(B+R)).
"""
import numpy as np


def tau_star(B, R):
    return B / (B + R)


def tau_ask(B, R, kappa, delta):
    return tau_star(B, R) + kappa / (delta * (B + R))


def u_speak(q, B, R):
    return q * R - (1.0 - q) * B


def decide(p, a, c, B, R, kappa, delta):
    """반환: (행동, 유틸 dict, 지금 답 ℓ̂). 행동 ∈ {'speak','ask','abstain'}."""
    p = np.asarray(p, float); a = np.asarray(a, int); c = np.asarray(c, float)
    p = p / p.sum()
    mass1 = float(p[a == 1].sum())
    lhat = 1 if mass1 >= 0.5 else 0
    q_speak = float(c.min()) * max(mass1, 1.0 - mass1)
    U = {"speak": u_speak(q_speak, B, R),
         "abstain": 0.0,
         "ask": -kappa + delta * float((p * np.maximum(u_speak(c, B, R), 0.0)).sum())}
    best = max(U.values())
    # 동률 우선순위: abstain > speak > ask  (보수적: 되묻기는 이득이 엄격히 클 때만)
    for act in ("abstain", "speak", "ask"):
        if U[act] == best:
            return act, U, lhat
    return "abstain", U, lhat


def _selftest():
    B, R = 5.0, 1.0            # Exp2 배점 (+1/−5) → τ* = 5/6 ≈ 0.833
    ts = tau_star(B, R)
    # (1) τ* 재현
    assert abs(u_speak(ts, B, R)) < 1e-12
    # (2) 대칭 2해석, 라벨 갈림, c 동일: ask ⟺ c > τ_ask  (수치 격자 검증)
    kappa, delta = 0.05, 1.0
    ta = tau_ask(B, R, kappa, delta)
    viol = 0
    for c in np.linspace(0.5, 0.999, 500):
        act, U, _ = decide([0.5, 0.5], [1, 0], [c, c], B, R, kappa, delta)
        q_speak = c * 0.5
        assert q_speak < ts
        want = "ask" if c > ta + 1e-9 else "abstain"
        viol += act != want
    # (3) vacuous(라벨 동일)이면 되묻기가 발화를 이기지 못한다 (κ>0, 정보가치 0)
    vac = 0
    for c in np.linspace(0.85, 0.999, 200):
        act, U, _ = decide([0.5, 0.5], [1, 1], [c, c], B, R, kappa, delta)
        vac += act == "ask"
    # (4) 상대가 절대 답 안 하면(δ=0) 되묻기는 −κ 라 절대 선택되지 않는다
    dead = 0
    for c in np.linspace(0.5, 0.999, 200):
        act, _, _ = decide([0.5, 0.5], [1, 0], [c, c], B, R, kappa, 0.0)
        dead += act == "ask"
    print(f"tau*={ts:.4f} tau_ask={ta:.4f} grid-violations={viol}/500 vacuous-asks={vac}/200 delta0-asks={dead}/200")
    assert viol == 0 and vac == 0 and dead == 0
    # (5) 정보가치(옵션가치) 비음: 무작위 인스턴스 10k
    rng = np.random.default_rng(29)
    neg = 0
    for _ in range(10000):
        k = int(rng.integers(2, 5))
        p = rng.dirichlet(np.ones(k)); a = rng.integers(0, 2, size=k); c = rng.uniform(0, 1, size=k)
        act, U, _ = decide(p, a, c, B, R, 0.0, 1.0)
        # κ=0, δ=1 이면 U_ask ≥ max(U_speak, 0) 이어야 (옵션가치 ≥ 0)
        neg += U["ask"] + 1e-12 < max(U["speak"], 0.0)
    print(f"option-value negative cases: {neg}/10000")
    assert neg == 0
    print("policy selftest OK")


if __name__ == "__main__":
    _selftest()
