"""Exp29 — Exp1 합성 데이터 생성기의 '모호·정보누락·사투리' 확장 (exp1/data.py 무수정 래핑).

원칙(Exp1 계승): 세 모델 모두 자연어를 받는다. 라벨은 리터럴 그래프 폐포로 기계 계산(라벨 비용 0).
추가 원칙(Exp29): '결정 불가' 슬롯은 텍스트만으로는 복원할 수 없어야 하고, 그 정답(oracle)은
상대(counterparty)만 안다. 학습 gold 는 진짜 후보 분포에서 표본 — 모델이 퍼진 사후분포를 배우도록.

노이즈 범주:
  clean   : Exp1 원본 (direct/chain/invert/neg)                    — 결정 · 되묻기 불필요(대조)
  ref     : 엔티티 하나를 지시어(그것·이것·그런일)로 치환, 후보=앞 문장 엔티티 — 결정 불가 · 되묻기가 답
  omit    : 엔티티 하나를 자리표(문제·상황·일)로 치환, 후보=전체 엔티티     — 결정 불가 · 되묻기가 답
  polar   : 규칙 극성을 '달라진다/바꾼다'로 숨김(실극성 50/50, 라벨 재계산) — neg 헤드 결정 불가
  dialect : 사투리 템플릿 재렌더(학습 3종 + 테스트 전용 미학습 2종)         — 결정 · 되묻기 낭비

예제 필드(Exp1 + 추가): noise, ambig_slots=[(sent_idx, head)], oracle={(sent_idx,head): true_value},
candidates={(sent_idx,head): [후보값]}, dialect_heldout(bool).
이 파일은 데이터 생성기다 — 실험(run_exp29.py)이 아니다. __main__ 은 생성기 자가검사만 한다.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "exp1"))
from data import (ENTITIES, Q_NEG_DIRECT, Q_NEG_INVERT, Q_POS_DIRECT,  # noqa: E402
                  Q_POS_INVERT, RULE_NEG, RULE_POS, build_vocab, closure)

NOISE = ["clean", "ref", "omit", "polar", "dialect"]
HEADS = ["from", "to", "neg"]

REF_WORDS = ["그것", "이것", "그런일"]        # 지시어 — 후보는 컨텍스트에 있음
OMIT_WORDS = ["문제", "상황", "일"]          # 자리표 — 후보는 전체
POLAR_TPL = ["{x} 가 생기면 {y} 가 달라진다 .", "{x} 는 {y} 를 바꾼다 ."]   # 극성 숨김
DIALECT_SEEN = ["{x} 가 생기믄 {y} 가 생긴다 .", "{x} 나면 {y} 난다 .", "{x} 생기마 {y} 생긴다카이 ."]
DIALECT_HELDOUT = ["{x} 가 나믄 {y} 가 나는기라 .", "{x} 오믄 {y} 온다 ."]
DIALECT_NEG_SEEN = ["{x} 가 생기믄 {y} 가 없어진다 ."]
DIALECT_NEG_HELDOUT = ["{x} 오믄 {y} 사라지는기라 ."]

# 학습 혼합비 (사전등록 §5.1): clean 50%, 나머지 12.5% 씩
TRAIN_MIX = {"clean": 0.5, "ref": 0.125, "omit": 0.125, "polar": 0.125, "dialect": 0.125}


def _gen_rules(rng):
    """Exp1 gen_example 의 규칙·질의 생성부를 그대로 재현(렌더 전 단계)."""
    k = rng.integers(4, 8)
    ents = list(rng.choice(len(ENTITIES), size=k, replace=False))
    rules = []
    for i in range(k - 2):
        rules.append((int(ents[i]), int(ents[i + 1]), +1))
    for _ in range(rng.integers(0, 2)):
        a, b = rng.choice(ents, size=2, replace=False)
        rules.append((int(a), int(b), +1))
    if rng.random() < 0.6:
        a, b = rng.choice(ents, size=2, replace=False)
        rules.append((int(a), int(b), -1))
    rng.shuffle(rules)
    rules = rules[: rng.integers(3, 7)]
    qtype = rng.choice(["direct", "invert", "neg", "chain"])
    a, b = (int(x) for x in rng.choice(ents, size=2, replace=False))
    pol = -1 if qtype == "neg" else +1
    if qtype == "chain":
        a, b = int(ents[0]), int(ents[min(k - 2, 3)])
    return rules, (a, b, pol), str(qtype)


def _render_rule(f, t, p, rng, tpl=None):
    if tpl is None:
        tpl = rng.choice(RULE_POS if p == +1 else RULE_NEG)
    return tpl.format(x=ENTITIES[f], y=ENTITIES[t])


def _render_query(a, b, pol, qtype, rng):
    if qtype in ("direct", "chain"):
        tpl = rng.choice(Q_POS_DIRECT)
    elif qtype == "invert":
        tpl = rng.choice(Q_POS_INVERT)
    else:
        pool = Q_NEG_DIRECT + Q_NEG_INVERT
        tpl = pool[rng.integers(len(pool))]
    return tpl.format(a=ENTITIES[a], b=ENTITIES[b])


def _substitute(sent, ent_word, new_word):
    """문장에서 엔티티 단어 1회 치환 (토큰 단위, 첫 등장)."""
    toks = sent.split()
    for i, w in enumerate(toks):
        if w == ent_word:
            toks[i] = new_word
            return " ".join(toks)
    raise ValueError("entity token not found")


def gen_example_ext(rng, noise="clean", split="train"):
    rules, (qa, qb, qpol), qtype = _gen_rules(rng)
    ambig_slots, oracle, candidates = [], {}, {}
    heldout = False

    # ── polar: 규칙 하나의 실극성을 50/50 로 다시 뽑고(라벨 재계산) 극성 숨김 템플릿 사용
    polar_idx = None
    if noise == "polar":
        polar_idx = int(rng.integers(len(rules)))
        f, t, _ = rules[polar_idx]
        p_true = +1 if rng.random() < 0.5 else -1
        rules[polar_idx] = (f, t, p_true)

    label = (qb, qpol) in closure(rules, qa)

    # ── 렌더
    sents, gold = [], []
    dialect_idx = None
    if noise == "dialect":
        dialect_idx = int(rng.integers(len(rules)))
        heldout = (split == "test") and (rng.random() < 0.5)
    for i, (f, t, p) in enumerate(rules):
        if noise == "polar" and i == polar_idx:
            tpl = rng.choice(POLAR_TPL)
        elif noise == "dialect" and i == dialect_idx:
            if p == +1:
                tpl = rng.choice(DIALECT_HELDOUT if heldout else DIALECT_SEEN)
            else:
                tpl = rng.choice(DIALECT_NEG_HELDOUT if heldout else DIALECT_NEG_SEEN)
        else:
            tpl = None
        sents.append(_render_rule(f, t, p, rng, tpl))
        gold.append([f, t, 0 if p == +1 else 1])
    sents.append(_render_query(qa, qb, qpol, qtype, rng))
    gold.append([qa, qb, 0 if qpol == +1 else 1])

    if noise == "polar":
        ambig_slots.append((polar_idx, "neg"))
        oracle[(polar_idx, "neg")] = gold[polar_idx][2]
        candidates[(polar_idx, "neg")] = [0, 1]
        # 학습 gold: 진짜 후보 분포(50/50) 표본 — 이미 p_true 가 그 표본이므로 그대로

    # ── ref / omit: 엔티티 하나를 지시어·자리표로 치환
    if noise in ("ref", "omit"):
        # 치환 대상 문장: ref 는 앞 문장이 있어야(후보 ≥ 2) → i ≥ 1 인 규칙 또는 질의(30%)
        n_rules = len(rules)
        if noise == "ref":
            use_query = rng.random() < 0.3
            si = n_rules if use_query else int(rng.integers(1, n_rules))
        else:
            si = int(rng.integers(0, n_rules + 1))
        head = "from" if rng.random() < 0.5 else "to"
        hidx = 0 if head == "from" else 1
        true_ent = gold[si][hidx]
        prev_ents = sorted({g[0] for g in gold[:si]} | {g[1] for g in gold[:si]})
        if noise == "ref":
            cand = prev_ents if true_ent in prev_ents else sorted(set(prev_ents) | {true_ent})
            if len(cand) < 2:  # 후보 1개면 모호하지 않음 → 자리표 범주로 강등
                noise_eff = "omit"
                cand = list(range(len(ENTITIES)))
                word = REF_WORDS[rng.integers(len(REF_WORDS))]
            else:
                noise_eff = "ref"
                word = REF_WORDS[rng.integers(len(REF_WORDS))]
        else:
            noise_eff = "omit"
            cand = list(range(len(ENTITIES)))
            word = OMIT_WORDS[rng.integers(len(OMIT_WORDS))]
        sents[si] = _substitute(sents[si], ENTITIES[true_ent], word)
        ambig_slots.append((si, head))
        oracle[(si, head)] = int(true_ent)
        candidates[(si, head)] = [int(c) for c in cand]
        # 학습 gold: 후보 분포에서 표본(확신 있는 추측을 가르치지 않는다). 테스트 gold 는 진실.
        if split == "train":
            gold[si][hidx] = int(cand[rng.integers(len(cand))])
        noise = noise_eff

    return {
        "sents": sents,
        "gold": gold,
        "rules": rules,
        "query": (qa, qb, qpol),
        "label": int(label),
        "qtype": qtype,
        "noise": noise,
        "ambig_slots": ambig_slots,
        "oracle": oracle,
        "candidates": candidates,
        "dialect_heldout": bool(heldout),
    }


def pin_slot(example, slot, value):
    """되묻기 응답으로 슬롯을 핀: 문장을 재렌더(지시어→엔티티, 극성 확정). 새 예제(복사) 반환."""
    si, head = slot
    ex = dict(example)
    sents = list(ex["sents"])
    gold = [list(g) for g in ex["gold"]]
    if head == "neg":
        f, t, _ = ex["rules"][si]
        p = +1 if value == 0 else -1
        rng = np.random.default_rng(hash((si, value)) % (2**32))
        sents[si] = _render_rule(f, t, p, rng)
        gold[si][2] = int(value)
    else:
        toks = sents[si].split()
        pool = REF_WORDS + OMIT_WORDS
        for i, w in enumerate(toks):
            if w in pool:
                toks[i] = ENTITIES[value]
                break
        sents[si] = " ".join(toks)
        gold[si][0 if head == "from" else 1] = int(value)
    ex["sents"], ex["gold"] = sents, gold
    ex["ambig_slots"] = [s for s in ex["ambig_slots"] if s != slot]
    return ex


def answer_relevant(example):
    """결정 불가 슬롯의 후보값들 사이에서 검증기 답이 갈리는가 (K1 양성 정의)."""
    if not example["ambig_slots"]:
        return False
    qa, qb, qpol = example["query"]
    outcomes = set()
    for slot in example["ambig_slots"]:
        si, head = slot
        for v in example["candidates"][slot]:
            rules = [list(r) for r in example["rules"]]
            if si < len(rules):
                if head == "from":
                    rules[si][0] = v
                elif head == "to":
                    rules[si][1] = v
                else:
                    rules[si][2] = +1 if v == 0 else -1
                outcomes.add((qb, qpol) in closure([tuple(r) for r in rules], qa))
            else:  # 질의 슬롯
                a, b = (v, qb) if head == "from" else (qa, v)
                outcomes.add((b, qpol) in closure([tuple(r) for r in rules], a))
    return len(outcomes) > 1


def build_vocab_ext():
    """Exp1 어휘 뒤에 새 토큰만 추가(기존 인덱스 불변)."""
    vocab = build_vocab()
    extra = set()
    for tpl in POLAR_TPL + DIALECT_SEEN + DIALECT_HELDOUT + DIALECT_NEG_SEEN + DIALECT_NEG_HELDOUT:
        for w in tpl.replace("{x}", "").replace("{y}", "").split():
            extra.add(w)
    for w in REF_WORDS + OMIT_WORDS:
        extra.add(w)
    for w in sorted(extra):
        if w not in vocab:
            vocab[w] = len(vocab)
    return vocab


def gen_dataset_ext(n, seed, split="train", mix=None):
    rng = np.random.default_rng(seed)
    mix = mix or TRAIN_MIX
    names = list(mix.keys())
    probs = np.array([mix[k] for k in names]) / sum(mix.values())
    data = [gen_example_ext(rng, names[rng.choice(len(names), p=probs)], split) for _ in range(n)]
    pos = sum(d["label"] for d in data)
    while not (0.4 <= pos / len(data) <= 0.6):
        d = gen_example_ext(rng, names[rng.choice(len(names), p=probs)], split)
        need = 1 if pos / len(data) < 0.4 else 0
        if d["label"] == need:
            data.append(d)
            pos += d["label"]
    return data


if __name__ == "__main__":
    from collections import Counter
    vocab = build_vocab_ext()
    base = build_vocab()
    assert all(vocab[w] == i for w, i in base.items()), "Exp1 어휘 인덱스가 바뀌었다"
    print(f"vocab: exp1={len(base)} ext={len(vocab)} (+{len(vocab)-len(base)})")
    for split in ("train", "test"):
        data = gen_dataset_ext(1200, seed=7 if split == "train" else 8, split=split)
        cnt = Counter(d["noise"] for d in data)
        pos = sum(d["label"] for d in data) / len(data)
        rel = {k: np.mean([answer_relevant(d) for d in data if d["noise"] == k]) for k in NOISE}
        held = sum(d["dialect_heldout"] for d in data)
        maxtok = max(len(s.split()) for d in data for s in d["sents"])
        print(f"[{split}] n={len(data)} true={pos:.2f} noise={dict(cnt)} heldout={held} max_sent_tokens={maxtok}")
        print(f"[{split}] answer-relevant ambiguity rate by noise: " + ", ".join(f"{k}={v:.2f}" for k, v in rel.items()))
        for k in NOISE:
            ex = next(d for d in data if d["noise"] == k)
            print(f"  [{k}] label={ex['label']} qtype={ex['qtype']} ambig={ex['ambig_slots']} oracle={ex['oracle']}")
            for s in ex["sents"]:
                print("     ", s)
        # pin_slot 자가검사: 핀 후 모호 슬롯이 사라지고 gold 가 oracle 과 일치
        ex = next(d for d in data if d["noise"] in ("ref", "omit", "polar"))
        slot = ex["ambig_slots"][0]
        pinned = pin_slot(ex, slot, ex["oracle"][slot])
        si, head = slot
        assert pinned["ambig_slots"] == [] and pinned["gold"][si][HEADS.index(head)] == ex["oracle"][slot]
        assert all(w in vocab for s in pinned["sents"] for w in s.split()), "핀 후 어휘 밖 토큰"
        print(f"  pin_slot ok: {ex['sents'][si]!r} -> {pinned['sents'][si]!r}")
    print("self-check OK (생성기 자가검사 — 실험 아님)")
