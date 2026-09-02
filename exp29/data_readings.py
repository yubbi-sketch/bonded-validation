"""Exp29 — Exp1 데이터 생성기 확장 (프로토콜 렌즈): 열거 해석집합 I 가 본문에 명시된 문제.

`data_ambig.py`(경제 렌즈: ref/omit/polar/dialect 노이즈 + 슬롯 oracle)와 **상보적**이다 —
저쪽은 '텍스트에 없는 정보'(후보는 문맥·전체 엔티티), 이쪽은 '텍스트가 스스로 열거한 해석집합'
(Exp25 의 저자 열거 I 와 같은 지위). 둘 다 라벨은 폐포로 기계 계산, 의존성 NumPy 뿐.

정식화:
  문제 = (자연어 문장들, 열거된 I = {r_1..r_k}, 요청자의 진짜 해석 θ* ∈ I)
  pin(S, r_i) 는 Exp1 문법의 완전한 문장열 → 라벨 L_i 는 폐포로 계산.
  · decisive ⟺ ∃ i,j: L_i ≠ L_j   — 되묻지 않으면 답이 갈린다 (되묻기 정당, 규칙 R8 non-vacuous)
  · vacuous  ⟺ ∀ i,j: L_i = L_j   — 어느 해석이든 답이 같다 (되묻기 낭비)
  되묻기 = "θ 가 무엇인가". 답 = θ*. 새 발화 r' = pin(S, θ*) — 판정 가능 문장으로 환원.

범주 (Exp1 4범주는 대조군으로 그대로 재사용):
  ambig_ref   : 질의 전제가 대명사 '그것' — 지시 대상이 I 로 열거 ("그것 은 X 또는 Y 이다")
  omit_target : 규칙 하나의 결론이 '무언가' — 후보가 I 로 열거
  omit_rule   : 규칙 하나 통째 누락 ("규칙 하나 는 나중에 알려준다") — I = 후보 (from,to) 쌍
정직성: I 는 본문에 명시 열거된다 — 열거 밖 해석(Exp25 z3-5)·과소열거(Exp25 한계3)는 이 데이터가
다루지 않는다. 데이터 생성기이지 '자연어 모호성 일반'의 모델이 아니다. __main__ 은 자가검사만 한다.
"""
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "exp1"))
from data import (ENTITIES, RULE_NEG, RULE_POS, Q_POS_DIRECT, Q_NEG_DIRECT,  # noqa: E402
                  closure, gen_example, build_vocab)

PRON = "그것"
HOLE = "무언가"
MISSING_RULE = "규칙 하나 는 나중에 알려준다 ."
Q_PRON = ["{p} 이 생기면 {b} 가 생기는가 ?", "{p} 이 발생하면 {b} 로 이어지는가 ?"]
ENUM = "{h} 은 {alts} 이다 ."          # 해석집합 열거 문장
EXTRA_TOKENS = [PRON, HOLE, "이", "은", "또는", "이다", "규칙", "하나", "나중에", "알려준다", "누락"]


def build_vocab_readings():
    """Exp1 어휘 뒤에 새 토큰만 추가(기존 인덱스 불변)."""
    vocab = build_vocab()
    for w in EXTRA_TOKENS:
        if w not in vocab:
            vocab[w] = len(vocab)
    return vocab


def _enum_sentence(hole, alts):
    return ENUM.format(h=hole, alts=" 또는 ".join(ENTITIES[a] for a in alts))


def _render_rules(rules, rng):
    sents, gold = [], []
    for f, t, p in rules:
        tpl = rng.choice(RULE_POS if p == +1 else RULE_NEG)
        sents.append(tpl.format(x=ENTITIES[f], y=ENTITIES[t]))
        gold.append((f, t, 0 if p == +1 else 1))
    return sents, gold


def _base(rng):
    ex = gen_example(rng)
    return ex["rules"], ex["query"]


def gen_ambig_ref(rng, k_read=None):
    """질의 전제 = '그것', 후보 I = 본문 엔티티 중 k개."""
    rules, (a, b, pol) = _base(rng)
    ents = sorted({e for f, t, _ in rules for e in (f, t)})
    k = k_read or int(rng.integers(2, 4))
    if len(ents) < k:
        return None
    alts = [int(x) for x in rng.choice(ents, size=k, replace=False)]
    theta = int(rng.integers(k))
    sents, gold = _render_rules(rules, rng)
    sents.append(_enum_sentence(PRON, alts))
    q_tpl = rng.choice(Q_PRON if pol == +1 else ["{p} 이 생기면 {b} 가 사라지는가 ?"])
    sents.append(q_tpl.format(p=PRON, b=ENTITIES[b]))
    readings, labels = [], []
    for r in alts:
        pinned = list(sents[:-2]) + [(rng.choice(Q_POS_DIRECT) if pol == +1 else rng.choice(Q_NEG_DIRECT))
                                     .format(a=ENTITIES[r], b=ENTITIES[b])]
        readings.append(pinned)
        labels.append(int((b, pol) in closure(rules, r)))
    return {"cat": "ambig_ref", "sents": sents, "gold_rules": gold, "rules": rules,
            "query_template": (None, b, pol), "alts": alts, "readings": readings,
            "labels": labels, "theta": theta, "decisive": len(set(labels)) > 1}


def gen_omit_target(rng, k_read=None):
    """규칙 하나의 결론이 '무언가' — 후보 I 열거."""
    rules, (a, b, pol) = _base(rng)
    if len(rules) < 2:
        return None
    j = int(rng.integers(len(rules)))
    f0, t0, p0 = rules[j]
    ents = sorted({e for f, t, _ in rules for e in (f, t)} | {a, b})
    k = k_read or int(rng.integers(2, 4))
    pool = [e for e in ents if e != f0]
    if len(pool) < k:
        return None
    alts = [int(x) for x in rng.choice(pool, size=k, replace=False)]
    if t0 not in alts:
        alts[0] = int(t0)
    theta = alts.index(int(t0))
    sents, gold = _render_rules(rules, rng)
    sents[j] = (rng.choice(RULE_POS if p0 == +1 else RULE_NEG)).format(x=ENTITIES[f0], y=HOLE)
    sents.append(_enum_sentence(HOLE, alts))
    q = (rng.choice(Q_POS_DIRECT) if pol == +1 else rng.choice(Q_NEG_DIRECT)).format(a=ENTITIES[a], b=ENTITIES[b])
    sents.append(q)
    readings, labels = [], []
    for r in alts:
        rr = list(rules)
        rr[j] = (f0, int(r), p0)
        pinned = list(sents[:-2])
        pinned[j] = (RULE_POS[0] if p0 == +1 else RULE_NEG[0]).format(x=ENTITIES[f0], y=ENTITIES[r])
        pinned.append(q)
        readings.append(pinned)
        labels.append(int((b, pol) in closure(rr, a)))
    return {"cat": "omit_target", "sents": sents, "gold_rules": gold, "rules": rules,
            "query_template": (a, b, pol), "alts": alts, "readings": readings,
            "labels": labels, "theta": theta, "decisive": len(set(labels)) > 1}


def gen_omit_rule(rng, k_read=None):
    """규칙 하나 통째 누락 — 후보 I = (from,to) 쌍 k개 (그중 하나가 진짜)."""
    rules, (a, b, pol) = _base(rng)
    if len(rules) < 2:
        return None
    j = int(rng.integers(len(rules)))
    f0, t0, p0 = rules[j]
    ents = sorted({e for f, t, _ in rules for e in (f, t)} | {a, b})
    k = k_read or int(rng.integers(2, 4))
    cands = [(int(f), int(t)) for f in ents for t in ents if f != t and (f, t) != (f0, t0)]
    if len(cands) < k - 1:
        return None
    idx = rng.choice(len(cands), size=k - 1, replace=False)
    alts = [(int(f0), int(t0))] + [cands[i] for i in idx]
    rng.shuffle(alts)
    theta = alts.index((int(f0), int(t0)))
    visible = [r for i, r in enumerate(rules) if i != j]
    sents, gold = _render_rules(visible, rng)
    sents.append(MISSING_RULE)
    sents.append("누락 규칙 은 " + " 또는 ".join(f"{ENTITIES[f]} 가 {ENTITIES[t]} 를 부른다" for f, t in alts) + " 이다 .")
    q = (rng.choice(Q_POS_DIRECT) if pol == +1 else rng.choice(Q_NEG_DIRECT)).format(a=ENTITIES[a], b=ENTITIES[b])
    sents.append(q)
    readings, labels = [], []
    for f, t in alts:
        rr = visible + [(f, t, p0)]
        pinned = list(sents[:-3]) + [(RULE_POS[0] if p0 == +1 else RULE_NEG[0]).format(x=ENTITIES[f], y=ENTITIES[t]), q]
        readings.append(pinned)
        labels.append(int((b, pol) in closure(rr, a)))
    return {"cat": "omit_rule", "sents": sents, "gold_rules": gold, "rules": visible,
            "query_template": (a, b, pol), "alts": alts, "readings": readings,
            "labels": labels, "theta": theta, "decisive": len(set(labels)) > 1}


GENS = {"ambig_ref": gen_ambig_ref, "omit_target": gen_omit_target, "omit_rule": gen_omit_rule}


def gen_dataset_readings(n, seed, decisive_share=0.5, cats=("ambig_ref", "omit_target", "omit_rule")):
    """범주별 균등, decisive:vacuous 비율을 decisive_share 로 기각 샘플링."""
    rng = np.random.default_rng(seed)
    out = []
    per_cat = n // len(cats)
    for cat in cats:
        want_dec = int(round(per_cat * decisive_share))
        got = {True: 0, False: 0}
        tries = 0
        while got[True] + got[False] < per_cat and tries < 200 * per_cat:
            tries += 1
            ex = GENS[cat](rng)
            if ex is None:
                continue
            d = ex["decisive"]
            cap = want_dec if d else per_cat - want_dec
            if got[d] >= cap:
                continue
            got[d] += 1
            out.append(ex)
    rng.shuffle(out)
    return out


def resolve(example, i):
    """되묻기 답 i 를 받은 뒤의 새 발화 문장열 (pin). 판정 가능 문장으로 환원된 r'."""
    return list(example["readings"][i]), int(example["labels"][i])


def simulated_counterpart(example, delta, rng):
    """상대(요청자) 모사: 확률 δ 로 진짜 해석 θ* 를 답하고, 아니면 침묵(None)."""
    return int(example["theta"]) if rng.random() < delta else None


if __name__ == "__main__":
    vocab = build_vocab_readings()
    base = build_vocab()
    assert all(vocab[w] == i for w, i in base.items()), "Exp1 어휘 인덱스가 바뀌었다"
    data = gen_dataset_readings(300, seed=29)
    print(f"vocab: exp1={len(base)} ext={len(vocab)} n={len(data)}")
    print("cat:", Counter(d["cat"] for d in data))
    print("decisive:", Counter((d["cat"], d["decisive"]) for d in data))
    print("|I|:", Counter(len(d["alts"]) for d in data))
    for cat in GENS:
        ex = next(d for d in data if d["cat"] == cat)
        print(f"\n[{cat}] decisive={ex['decisive']} labels={ex['labels']} theta={ex['theta']}")
        for s in ex["sents"]:
            print("   ", s)
        pinned, lab = resolve(ex, ex["theta"])
        print("  -> pinned r' (last 2):", pinned[-2:], "label", lab)
    missing = {w for d in data for s in d["sents"] + [x for r in d["readings"] for x in r]
               for w in s.split() if w not in vocab}
    print("\nmissing tokens:", sorted(missing) if missing else "none")
    assert not missing
    print("self-check OK (생성기 자가검사 — 실험 아님)")
