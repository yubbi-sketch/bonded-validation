"""합성 다단계 인과 논리 데이터셋 생성기.

핵심 원칙(강령 G2): 세 모델 모두 '자연어'를 받는다 — 파싱된 튜플 입력 금지.
정답은 리터럴 그래프 폐포로 기계 계산되므로 라벨 비용 0.

문장 의미론:
  규칙  X⇒Y   : "X가 생기면 Y가 생긴다" 류
  규칙  X⇒¬Y  : "X가 생기면 Y가 사라진다" 류
  질의  A⇒B?  : 표면형 2종 — 직서형(A 먼저), 도치형(B 먼저) ← 표면 순서 함정
  질의  A⇒¬B? : 부정 질의
라벨 = 시작 리터럴 (A,+)에서 규칙 그래프로 목표 리터럴 도달 가능 여부.
"""
import numpy as np

ENTITIES = [
    "비", "홍수", "화재", "연기", "정전", "지진", "폭풍", "한파", "폭염", "가뭄",
    "사고", "부상", "지각", "정체", "고장", "누수", "곰팡이", "부식", "오염", "질병",
    "피로", "실수", "손실", "혼잡", "소음", "균열", "붕괴", "결빙", "침수", "폭발",
]

RULE_POS = [
    "{x} 가 생기면 {y} 가 생긴다 .",
    "{x} 는 {y} 를 부른다 .",
    "{x} 가 발생하면 {y} 로 이어진다 .",
    "만약 {x} 라면 {y} 가 따른다 .",
]
RULE_NEG = [
    "{x} 가 생기면 {y} 가 사라진다 .",
    "{x} 가 발생하면 {y} 는 없다 .",
]
# 질의 표면형: direct = 전제가 먼저 등장, inverted = 결론이 먼저 등장(순서 함정)
Q_POS_DIRECT = ["{a} 가 생기면 {b} 가 생기는가 ?", "{a} 가 발생하면 {b} 로 이어지는가 ?"]
Q_POS_INVERT = ["{b} 가 생기는 것은 {a} 가 생겼을 때 따라오는가 ?",
                "{b} 로 이어지는가 {a} 가 발생하면 ?"]
Q_NEG_DIRECT = ["{a} 가 생기면 {b} 가 사라지는가 ?", "{a} 가 발생하면 {b} 는 없는가 ?"]
Q_NEG_INVERT = ["{b} 가 사라지는 것은 {a} 가 생겼을 때 따라오는가 ?"]


def closure(rules, start):
    """rules: [(from_ent, to_ent, pol)] (전제는 항상 양). start 엔티티에서 도달 리터럴 집합."""
    reach = {(start, +1)}
    frontier = [(start, +1)]
    adj = {}
    for f, t, p in rules:
        adj.setdefault(f, []).append((t, p))
    while frontier:
        ent, pol = frontier.pop()
        if pol != +1:
            continue  # 전제는 양 리터럴만 발화
        for t, p in adj.get(ent, []):
            if (t, p) not in reach:
                reach.add((t, p))
                frontier.append((t, p))
    return reach


def gen_example(rng):
    k = rng.integers(4, 8)
    ents = list(rng.choice(len(ENTITIES), size=k, replace=False))
    # 사슬 + 여분 간선 + 부정 간선 1개 이하 + 무관 방해 규칙
    rules = []
    for i in range(k - 2):
        rules.append((ents[i], ents[i + 1], +1))
    for _ in range(rng.integers(0, 2)):
        a, b = rng.choice(ents, size=2, replace=False)
        rules.append((int(a), int(b), +1))
    if rng.random() < 0.6:
        a, b = rng.choice(ents, size=2, replace=False)
        rules.append((int(a), int(b), -1))
    rng.shuffle(rules)
    rules = rules[: rng.integers(3, 7)]

    # 질의 유형 선택
    qtype = rng.choice(["direct", "invert", "neg", "chain"])
    a, b = (int(x) for x in rng.choice(ents, size=2, replace=False))
    pol = +1
    if qtype == "neg":
        pol = -1
    if qtype == "chain":  # 3홉 이상 강제: 사슬 양끝
        a, b = ents[0], ents[min(k - 2, 3)]
        a, b = int(a), int(b)
    label = (b, pol) in closure(rules, a)

    # 문장 렌더링
    sents, gold = [], []
    for f, t, p in rules:
        tpl = rng.choice(RULE_POS if p == +1 else RULE_NEG)
        sents.append(tpl.format(x=ENTITIES[f], y=ENTITIES[t]))
        gold.append((f, t, 0 if p == +1 else 1))
    if qtype in ("direct", "chain"):
        tpl = rng.choice(Q_POS_DIRECT)
    elif qtype == "invert":
        tpl = rng.choice(Q_POS_INVERT)
    else:
        pool = Q_NEG_DIRECT + Q_NEG_INVERT
        tpl = pool[rng.integers(len(pool))]
    sents.append(tpl.format(a=ENTITIES[a], b=ENTITIES[b]))
    gold.append((a, b, 0 if pol == +1 else 1))

    return {
        "sents": sents,            # 자연어 문장 목록 (마지막 = 질의)
        "gold": gold,              # 문장별 (from, to, neg) — 추출기 학습 감독용
        "rules": rules,
        "query": (a, b, pol),
        "label": int(label),
        "qtype": str(qtype),
    }


def build_vocab():
    words = set()
    for tpl_set in [RULE_POS, RULE_NEG, Q_POS_DIRECT, Q_POS_INVERT, Q_NEG_DIRECT, Q_NEG_INVERT]:
        for tpl in tpl_set:
            for w in tpl.replace("{x}", "").replace("{y}", "").replace("{a}", "").replace("{b}", "").split():
                words.add(w)
    vocab = ["<pad>", "<sep>"] + ENTITIES + sorted(words)
    return {w: i for i, w in enumerate(vocab)}


def encode(sents, vocab, max_len):
    """전체 문장을 <sep>로 이어 하나의 토큰열로 (종단 모델용)."""
    ids = []
    for s in sents:
        ids += [vocab[w] for w in s.split()] + [vocab["<sep>"]]
    ids = ids[:max_len]
    return ids + [vocab["<pad>"]] * (max_len - len(ids))


def encode_sent(s, vocab, max_len):
    ids = [vocab[w] for w in s.split()][:max_len]
    return ids + [vocab["<pad>"]] * (max_len - len(ids))


def gen_dataset(n, seed):
    rng = np.random.default_rng(seed)
    data = [gen_example(rng) for _ in range(n)]
    # 라벨 균형 보정: True/False 비율 40~60% 밖이면 부족쪽 추가 생성
    pos = sum(d["label"] for d in data)
    while not (0.4 <= pos / len(data) <= 0.6):
        d = gen_example(rng)
        need = 1 if pos / len(data) < 0.4 else 0
        if d["label"] == need:
            data.append(d)
            pos += d["label"]
    return data


if __name__ == "__main__":
    vocab = build_vocab()
    data = gen_dataset(200, seed=7)
    pos = sum(d["label"] for d in data)
    from collections import Counter
    print(f"vocab={len(vocab)} n={len(data)} true={pos/len(data):.2f}")
    print(Counter(d["qtype"] for d in data))
    ex = data[0]
    for s in ex["sents"]:
        print("  ", s)
    print("  gold:", ex["gold"], "label:", ex["label"], ex["qtype"])
    lens = [len(encode(d["sents"], vocab, 999)) - (999 - len(encode(d["sents"], vocab, 999))) for d in data[:50]]
    print("max concat tokens ~", max(len([w for s in d['sents'] for w in s.split()]) + len(d['sents']) for d in data))
