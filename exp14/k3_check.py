"""K3 — 회로 양자화 출력 argmax vs float, 테스트 20문장 (EXP14.md 킬 기준)."""
import asyncio, inspect, json, sys
import numpy as np
sys.path.insert(0, "../exp1")
from data import ENTITIES, build_vocab, encode_sent, gen_dataset
from models import Extractor
from train import SENT_LEN, train_extractor

rng = np.random.default_rng(2026)
vocab = build_vocab()
train = gen_dataset(3000, seed=1); test = gen_dataset(800, seed=2)
ext = Extractor(len(vocab), n_ent=len(ENTITIES), d=64)
sents, gold = [], []
for ex in train:
    for s, gd in zip(ex["sents"], ex["gold"]):
        sents.append(encode_sent(s, vocab, SENT_LEN)); gold.append([int(g) for g in gd])
train_extractor(ext, np.array(sents)[:20000], np.array(gold)[:20000], 40, rng)

ts = []
for ex in test:
    for s, _ in zip(ex["sents"], ex["gold"]):
        ts.append(encode_sent(s, vocab, SENT_LEN))
ts = np.array(ts[:20])

import ezkl
async def wit(ids, i):
    json.dump({"input_data": [ids.astype(float).flatten().tolist()]}, open(f"out/in{i}.json","w"))
    v = ezkl.gen_witness(f"out/in{i}.json", "out/net.ezkl", f"out/w{i}.json")
    if inspect.isawaitable(v): await v
    w = json.load(open(f"out/w{i}.json"))
    po = w["pretty_elements"]["rescaled_outputs"]
    return [np.array([float(x) for x in o]).argmax() for o in po]

async def main():
    match = 0
    for i in range(20):
        circ = await wit(ts[i:i+1], i)
        lf, lt, ln = ext.forward(ts[i:i+1])
        ref = [lf.d.argmax(), lt.d.argmax(), ln.d.argmax()]
        match += int(circ == [int(r) for r in ref])
    rate = match / 20
    print(f"K3 argmax 일치: {match}/20 = {rate:.0%} (기준 >=95%) → {'PASS' if rate>=0.95 else 'FAIL'}")
    r = json.load(open("out/results.json"))
    r["K3_argmax_match_20"] = {"matched": match, "n": 20, "rate": rate, "pass": rate>=0.95}
    json.dump(r, open("out/results.json","w"), indent=2)

asyncio.run(main())
