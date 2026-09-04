"""RT-0033 계산 — VETERAN_WEIGHT=5 결탁 포획 확률과 최소 자본 비용.

핵심 재해석(코드 재검토로 확인): docstring이 우려한 "블록해시 그라인딩"보다 훨씬 싼
공격이 있다 — 결탁 판정자 집단이 여러 개의 서로 다른 사건을 독립적으로 열면(매번
judgeFee만 내고, requestHash가 다르니 시드도 자연히 독립적) 그라인딩 없이도 "우연히
전원 자기편"이 나오는 사건이 나올 때까지 그냥 반복하면 된다. blockhash 그라인딩은
검증자(제안자) 권한이 필요하지만, 이 "사건 쇼핑"은 자본만 있으면 누구나 가능하다.

계산: 초심 패널(3석)이 결탁측 지분(전원 veteran, 가중치 5)으로 전부 채워질 확률을
가중 비복원추출(순차 제거, Plackett-Luce 모델)로 정확히 계산 — k<=5라 순열 완전열거로
정확값(근사·몬테카를로 아님).

재현: python3 rt0033_veteran_capture.py
"""
import itertools
from fractions import Fraction

VETERAN_WEIGHT = 5
PANEL_SIZE = 3
EXPANDED_SIZE = 5


def p_exact_capture(weights_by_id: dict, collude_ids: set, k: int) -> Fraction:
    """전체 draw k석이 collude_ids 전원(정확히 |collude_ids|==k)에게 돌아갈 확률.
    Plackett-Luce 순차추출 — 순열 완전열거로 정확값(분수)."""
    assert len(collude_ids) == k
    total_w = sum(weights_by_id.values())
    p = Fraction(0)
    for order in itertools.permutations(collude_ids):
        term = Fraction(1)
        remaining = total_w
        for pid in order:
            term *= Fraction(weights_by_id[pid], remaining)
            remaining -= weights_by_id[pid]
        p += term
    return p


def scenario(name, n_veteran_total, n_newcomer_total, n_collude_veteran, k):
    """풀 구성: n_veteran_total 명(가중치5) + n_newcomer_total 명(가중치1),
    그중 n_collude_veteran 명이 결탁(전부 veteran). k석 전부 결탁측 확률 계산."""
    weights = {}
    for i in range(n_veteran_total):
        weights[f"v{i}"] = VETERAN_WEIGHT
    for i in range(n_newcomer_total):
        weights[f"n{i}"] = 1
    collude_ids = {f"v{i}" for i in range(n_collude_veteran)}
    p = p_exact_capture(weights, collude_ids, k)
    total_pool = n_veteran_total + n_newcomer_total
    return {
        "name": name, "pool_size": total_pool, "veterans": n_veteran_total,
        "newcomers": n_newcomer_total, "colluding_veterans": n_collude_veteran, "seats": k,
        "p_capture_float": float(p), "p_capture_frac": f"{p.numerator}/{p.denominator}",
    }


def attempts_for_success(p, target=0.90):
    """P(N회 독립시도 중 >=1회 성공) >= target 을 만족하는 최소 N."""
    if p <= 0:
        return None
    import math
    n = math.log(1 - target) / math.log(1 - p)
    return math.ceil(n)


def main():
    scenarios = [
        scenario("소형 풀, 초심 3석, 결탁 3인(전원 풀 장악)", 3, 7, 3, PANEL_SIZE),
        scenario("소형 풀, 초심 3석, 결탁 3/10명 veteran", 5, 5, 3, PANEL_SIZE),
        scenario("중형 풀, 초심 3석, 결탁 3/30명 veteran(veteran 10명 중 3)", 10, 20, 3, PANEL_SIZE),
        scenario("대형 풀, 초심 3석, 결탁 3/100명 veteran(veteran 20명 중 3)", 20, 80, 3, PANEL_SIZE),
        scenario("대형 풀, 초심 3석, 결탁 3/100명 veteran(veteran 5명 중 3 — 소수만 veteran)", 5, 95, 3, PANEL_SIZE),
    ]
    JUDGE_FEE_TOKENS = 9  # exp30/sim.py FEE=9e18 실측값 기준(사건당 개설 수수료)
    print(f"{'시나리오':45} {'풀크기':>6} {'P(포획)':>12} {'90% 성공까지 시도수':>16} {'자본비용(judgeFee배수)':>18}")
    for s in scenarios:
        p = s["p_capture_float"]
        n90 = attempts_for_success(p, 0.90)
        cost = n90 * JUDGE_FEE_TOKENS if n90 else None
        print(f"{s['name']:45} {s['pool_size']:>6} {p:>12.6f} {n90 if n90 else '-':>16} "
              f"{cost if cost else '-':>18}")
    print()
    print("정확 분수(첫 시나리오, 완전 장악):", scenarios[0]["p_capture_frac"])

    # 확장재판(5석)까지 뚫어야 하는 경우 — 초심에서 1명이라도 정직 판정자가 섞이면 분쟁->확대.
    # 확대재판까지 전부 뚫으려면 5석 전부 결탁 필요(그래야 만장일치처럼 settle).
    print()
    print("=== 참고: 확대재판(5석)까지 완전 장악하려면 ===")
    s5 = scenario("결탁 5명(veteran) vs 나머지 25명(veteran10+newcomer15 혼합 근사)", 10, 20, 5, EXPANDED_SIZE)
    print(s5)
    n90_5 = attempts_for_success(s5["p_capture_float"], 0.90)
    print(f"90% 성공까지 시도수: {n90_5}, 비용: judgeFee x {n90_5 if n90_5 else '-'}")


if __name__ == "__main__":
    main()
