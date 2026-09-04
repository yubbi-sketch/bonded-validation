"""Exp29 — 학습·측정 렌즈: 추출기 불확실성 측도 4종 + 되묻기 표적(슬롯 정보가치). 순수 NumPy.

입력: 추출기 헤드 사후분포 P = {"from": (n_sent, n_ent), "to": (n_sent, n_ent), "neg": (n_sent, 2)}
      — Exp2 `predict_with_conf` 의 softmax(lf)·softmax(lt)·softmax(ln) 그대로. 마지막 행이 질의.
출력: u1 최약고리(Exp2) · u2 엔트로피 · u3 슬롯 마진 · u4 답 뒤집힘(검증기 인식) · Δ_j 슬롯 정보가치 · 표적 j*.

정의(설계 문서 design-learning.md §4.2·§4.3):
  u1 = min_{i,h} max_v q_{i,h}(v)
  u2 = 1 − max_{i,h} H(q_{i,h}) / log|V_h|
  u3 = min_{i,h} [q^{(1)}_{i,h} − q^{(2)}_{i,h}]
  u4 = max(P(A=1), P(A=0)),  A = verifier(Z),  Z ~ Π_{i,h} q_{i,h}   (지지집합 곱이 작으면 정확 열거, 아니면 K 표본)
  Δ_j = Σ_v q_j(v)·u4(P | z_j = v) − u4(P) ≥ 0  (max 의 볼록성),  j* = argmax_j Δ_j

이 파일은 측도 정의와 자가검사다 — 학습·킬기준 판정(run_exp29.py, 미작성)이 아니다.
__main__ 은 실제 추출기 없이 '모의 사후분포'(gold 에 봉우리, 모호 슬롯은 후보 위 균등)로 측도의 **구조적 성질만** 검사한다:
  (i)  결정 예제(clean)에서 u4 = 1, Δ ≡ 0
  (ii) 답-유관 모호 슬롯에서 u4 < 1 ∧ argmax Δ = 그 슬롯      (모의 분포에서는 구성상 참 — K1 결과가 아니다)
  (iii) 답-무관 불확실성(방해 규칙 슬롯 퍼짐)에서 u1·u2·u3 는 떨어지지만 u4 = 1·Δ ≡ 0  — u4 만 '유관/무관'을 가른다
  (iv) Δ_j ≥ 0 (정확 열거 모드)
  (v)  pin_slot(oracle) 뒤 gold 파스의 검증기 답 = 라벨 (생성기·검증기 정합)
실제 추출기 사후분포에서 이 성질이 얼마나 유지되는지가 K1 이다.
"""
import itertools
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "exp1"))
sys.path.insert(0, HERE)
from data import ENTITIES, closure  # noqa: E402
from verifier import SymbolicLogicVerifier  # noqa: E402

HEADS = ("from", "to", "neg")
EPS = 1e-6       # 지지집합 절단 확률
CAP = 4096       # 정확 열거 상한(지지집합 곱)


# ────────────────────────────── 검증기 ──────────────────────────────
def verify(parse):
    """parse: (n_sent, 3) int — 행 0..n-2 규칙 (from, to, neg), 마지막 행 질의. 답 ∈ {0,1}."""
    v = SymbolicLogicVerifier()
    for f, t, n in parse[:-1]:
        v.add_rule(int(f), int(t), neg=bool(n))
    f, t, n = parse[-1]
    return int(v.derives(int(f), int(t), target_neg=bool(n)))


# ────────────────────────────── 측도 u1~u3 (표준) ──────────────────────────────
def u1_weakest_link(P):
    return float(min(P[h].max(-1).min() for h in HEADS))


def u2_entropy(P):
    worst = 0.0
    for h in HEADS:
        q = np.clip(P[h], 1e-12, 1.0)
        H = -(q * np.log(q)).sum(-1) / np.log(q.shape[-1])
        worst = max(worst, float(H.max()))
    return 1.0 - worst


def u3_margin(P):
    m = 1.0
    for h in HEADS:
        s = np.sort(P[h], axis=-1)
        m = min(m, float((s[:, -1] - s[:, -2]).min()))
    return m


# ────────────────────────────── 측도 u4 (검증기 인식) ──────────────────────────────
def _supports(P):
    sup = []
    size = 1
    n = P["from"].shape[0]
    for i in range(n):
        for h in HEADS:
            q = P[h][i]
            idx = np.flatnonzero(q > EPS)
            if len(idx) == 0:
                idx = np.array([int(q.argmax())])
            pr = q[idx] / q[idx].sum()
            sup.append((idx, pr))
            size *= len(idx)
    return sup, size, n


def answer_dist(P, K=64, rng=None):
    """P(A=1) — 지지집합 곱 ≤ CAP 이면 정확 열거('exact'), 아니면 K 표본('mc')."""
    sup, size, n = _supports(P)
    parse = np.zeros((n, 3), int)
    if size <= CAP:
        p1 = 0.0
        for combo in itertools.product(*[range(len(s[0])) for s in sup]):
            w = 1.0
            for k, (idx, pr) in enumerate(sup):
                parse[k // 3, k % 3] = idx[combo[k]]
                w *= pr[combo[k]]
            p1 += w * verify(parse)
        return float(p1), "exact"
    rng = rng if rng is not None else np.random.default_rng(0)
    cnt = 0
    for _ in range(K):
        for k, (idx, pr) in enumerate(sup):
            parse[k // 3, k % 3] = idx[rng.choice(len(idx), p=pr)]
        cnt += verify(parse)
    return cnt / K, "mc"


def u4_flip(P, K=64, rng=None):
    """(u4, 최빈 답 â, 모드). u4 = 파스 표본 중 최빈 답과 일치하는 비율(정확 열거면 확률)."""
    p1, mode = answer_dist(P, K=K, rng=rng)
    return max(p1, 1.0 - p1), (1 if p1 >= 0.5 else 0), mode


def all_measures(P, K=64, rng=None):
    u4, ahat, mode = u4_flip(P, K=K, rng=rng)
    return {"u1": u1_weakest_link(P), "u2": u2_entropy(P), "u3": u3_margin(P), "u4": u4,
            "answer": ahat, "u4_mode": mode}


# ────────────────────────────── 되묻기 표적 Δ_j ──────────────────────────────
def slot_voi(P, K=64, rng=None):
    """Δ_j = Σ_v q_j(v)·u4(P|z_j=v) − u4(P). 반환 (dict {(i,h): Δ}, j*). 지지집합 1 인 슬롯은 Δ=0."""
    base, _, _ = u4_flip(P, K=K, rng=rng)
    n = P["from"].shape[0]
    out = {}
    for i in range(n):
        for h in HEADS:
            q = P[h][i]
            idx = np.flatnonzero(q > EPS)
            if len(idx) < 2:
                out[(i, h)] = 0.0
                continue
            pr = q[idx] / q[idx].sum()
            exp = 0.0
            for v, w in zip(idx, pr):
                Pv = {k: P[k].copy() for k in HEADS}
                Pv[h][i] = 0.0
                Pv[h][i][v] = 1.0
                exp += w * u4_flip(Pv, K=K, rng=rng)[0]
            out[(i, h)] = float(exp - base)
    jstar = max(out, key=out.get)
    return out, jstar


def candidates_for(P, slot, m=3):
    """되묻기 선택지: 슬롯 사후분포 상위 m 값(질문 템플릿 렌더용). none 옵션은 호출자가 붙인다."""
    i, h = slot
    q = P[h][i]
    top = np.argsort(-q)[:m]
    return [int(v) for v in top if q[v] > EPS]


# ────────────────────────────── 모의 사후분포 (자가검사 전용) ──────────────────────────────
def mock_posterior(ex, n_ent=len(ENTITIES), residual=1e-9):
    """gold 에 봉우리(지지집합 1), 모호 슬롯은 후보 위 균등. 실제 추출기가 아니다."""
    n = len(ex["sents"])
    P = {"from": np.full((n, n_ent), residual), "to": np.full((n, n_ent), residual), "neg": np.full((n, 2), residual)}
    for i, (f, t, ng) in enumerate(ex["gold"]):
        P["from"][i][f] = 1.0
        P["to"][i][t] = 1.0
        P["neg"][i][ng] = 1.0
    for (i, h) in ex["ambig_slots"]:
        c = list(ex["candidates"][(i, h)])
        P[h][i][:] = residual
        P[h][i][c] = 1.0 / len(c)
    for h in HEADS:
        P[h] /= P[h].sum(-1, keepdims=True)
    return P


def _irrelevant_spread(ex, rng, n_ent=len(ENTITIES)):
    """clean 예제에서 답을 바꾸지 않는 규칙 'to' 슬롯을 찾아 후보 3개 위로 퍼뜨린 모의 분포 (없으면 None)."""
    qa, qb, qpol = ex["query"]
    rules = [tuple(r) for r in ex["rules"]]
    label = (qb, qpol) in closure(rules, qa)
    order = list(range(len(rules)))
    rng.shuffle(order)
    for si in order:
        f, t, p = rules[si]
        others = [e for e in rng.permutation(n_ent).tolist() if e != t][:2]
        cands = [t] + others
        same = True
        for v in cands:
            rr = list(rules)
            rr[si] = (f, v, p)
            if ((qb, qpol) in closure(rr, qa)) != label:
                same = False
                break
        if same:
            P = mock_posterior(ex)
            P["to"][si][:] = 1e-9
            P["to"][si][cands] = 1.0 / 3
            P["to"][si] /= P["to"][si].sum()
            return P, (si, "to")
    return None, None


if __name__ == "__main__":
    from data_ambig import answer_relevant, gen_dataset_ext, pin_slot  # noqa: E402

    rng = np.random.default_rng(2029)
    data = gen_dataset_ext(400, seed=11, split="test")
    by = {}
    stats = {"exact": 0, "mc": 0}
    viol_nonneg = 0
    for ex in data:
        P = mock_posterior(ex)
        m = all_measures(P)
        stats[m["u4_mode"]] += 1
        d, j = slot_voi(P)
        viol_nonneg += sum(1 for v in d.values() if v < -1e-9)
        rel = answer_relevant(ex)
        key = (ex["noise"], rel)
        r = by.setdefault(key, {"n": 0, "u4lt1": 0, "target_hit": 0, "u1": [], "u2": [], "u3": [], "u4": []})
        r["n"] += 1
        r["u4lt1"] += m["u4"] < 1 - 1e-9
        r["target_hit"] += (j in ex["ambig_slots"]) if ex["ambig_slots"] else 0
        for k in ("u1", "u2", "u3", "u4"):
            r[k].append(m[k])

    print("모의 사후분포 위 측도 성질 (실제 추출기 아님 — 구조 검사):")
    print(f"  u4 계산 모드: {stats}   Δ_j < 0 위반: {viol_nonneg}")
    print(f"  {'noise':8s} {'relevant':8s} {'n':>4s} {'u4<1':>6s} {'j*∈ambig':>9s} {'u1':>6s} {'u2':>6s} {'u3':>6s} {'u4':>6s}")
    ok_i = ok_ii = True
    for key in sorted(by):
        r = by[key]
        noise, rel = key
        line = (f"  {noise:8s} {str(rel):8s} {r['n']:4d} {r['u4lt1']:6d} {r['target_hit']:9d} "
                f"{np.mean(r['u1']):6.3f} {np.mean(r['u2']):6.3f} {np.mean(r['u3']):6.3f} {np.mean(r['u4']):6.3f}")
        print(line)
        if noise in ("clean", "dialect"):
            ok_i &= r["u4lt1"] == 0
        elif rel:
            ok_ii &= (r["u4lt1"] == r["n"]) and (r["target_hit"] == r["n"])
        else:
            ok_i &= r["u4lt1"] == 0
    assert ok_i, "(i) 결정 예제 또는 답-무관 모호 예제에서 u4<1"
    assert ok_ii, "(ii) 답-유관 모호 예제에서 u4<1 또는 표적 불일치"
    assert viol_nonneg == 0, "(iv) Δ_j 비음 위반"

    # (iii) 답-무관 불확실성: u1~u3 는 떨어지고 u4 는 1 — u4 만 유관/무관을 가른다
    found = 0
    u1s, u4s, dmax = [], [], []
    for ex in (d for d in data if d["noise"] == "clean"):
        P, slot = _irrelevant_spread(ex, rng)
        if P is None:
            continue
        m = all_measures(P)
        d, j = slot_voi(P)
        u1s.append(m["u1"]); u4s.append(m["u4"]); dmax.append(max(d.values()))
        found += 1
        if found >= 60:
            break
    print(f"  (iii) 답-무관 퍼짐 {found}건: mean u1={np.mean(u1s):.3f} (≈1/3) · mean u4={np.mean(u4s):.3f} (=1) · max Δ={max(dmax):.2e}")
    assert found > 0 and abs(np.mean(u1s) - 1 / 3) < 1e-6 and min(u4s) > 1 - 1e-9 and max(dmax) < 1e-9

    # (v) 핀 후 gold 파스의 검증기 답 = 라벨 (생성기·검증기 정합)
    mism = 0
    n_pin = 0
    for ex in data:
        if not ex["ambig_slots"]:
            continue
        slot = ex["ambig_slots"][0]
        pinned = pin_slot(ex, slot, ex["oracle"][slot])
        a = verify(np.array(pinned["gold"], int))
        mism += a != pinned["label"]
        n_pin += 1
    print(f"  (v) pin_slot(oracle) 후 verify(gold) ≠ label: {mism}/{n_pin}")
    assert mism == 0
    print("measures self-check OK (모의 분포 위 구조 검사 — K1 판정 아님)")
