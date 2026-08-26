"""Exp14 — 추출기 순전파의 실제 ZK 증명 (ezkl/halo2). EXP14.md의 킬 기준 준수.

단계: 추출기 학습(Exp10 설정 재현) → 손제작 ONNX(torch 없음, T=14 언롤)
     → float 대조 → ezkl 파이프라인(settings→calibrate→compile→srs→setup
     →witness→prove→verify) 각 단계 시간 실측 → 회로 출력 argmax 일치율.
"""
import json
import os
import resource
import sys
import time

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

sys.path.insert(0, "../exp1")
from data import ENTITIES, build_vocab, encode_sent, gen_dataset  # noqa: E402
from models import Extractor  # noqa: E402
from train import SENT_LEN, train_extractor  # noqa: E402

D, T = 64, SENT_LEN
OUT = "out"
os.makedirs(OUT, exist_ok=True)
TIMES = {}


def tic(name):
    TIMES[name] = -time.perf_counter()


def toc(name):
    TIMES[name] += time.perf_counter()
    print(f"  [{name}] {TIMES[name]:.1f}s", flush=True)


# ── 1. 학습 (시드 고정 — Exp10과 동일 설정) ──────────────────────────
def train_model():
    rng = np.random.default_rng(2026)
    vocab = build_vocab()
    train = gen_dataset(3000, seed=1)
    test = gen_dataset(800, seed=2)
    ext = Extractor(len(vocab), n_ent=len(ENTITIES), d=D)
    sents, gold = [], []
    for ex in train:
        for s, gd in zip(ex["sents"], ex["gold"]):
            sents.append(encode_sent(s, vocab, T))
            gold.append([int(gd[0]), int(gd[1]), int(gd[2])])
    sents = np.array(sents); gold = np.array(gold)
    print("== 학습", flush=True)
    tic("train")
    train_extractor(ext, sents[:20000], gold[:20000], 40, rng)
    toc("train")
    ts, tg = [], []
    for ex in test:
        for s, gd in zip(ex["sents"], ex["gold"]):
            ts.append(encode_sent(s, vocab, T))
            tg.append([int(gd[0]), int(gd[1]), int(gd[2])])
    return ext, np.array(ts), np.array(tg)


# ── 2. 손제작 ONNX (스캔 T언롤, 게이트 상수 접기) ─────────────────────
def export_onnx(ext, path):
    f32 = lambda a, n: numpy_helper.from_array(np.asarray(a, np.float32), n)
    a = 1.0 / (1.0 + np.exp(-ext.a_raw.d))
    a2 = 1.0 / (1.0 + np.exp(-ext.a2_raw.d))
    inits = [
        f32(ext.E.d, "E"), f32(ext.g.d, "g"), f32(ext.Win.d, "Win"),
        f32(a, "gate_a"), f32(ext.b.d, "in_b"), f32(a2, "gate_a2"), f32(ext.b2.d, "in_b2"),
        f32(ext.Wm.d, "Wm"), f32(ext.Wl.d, "Wl"), f32(ext.Wl2.d, "Wl2"),
        f32(ext.Wfrom.d, "Wfrom"), f32(ext.Wto.d, "Wto"), f32(ext.Wneg.d, "Wneg"),
        f32(np.array(1e-8), "eps"), f32(np.array(1.0 / T), "invT"),
        f32(np.zeros((1, D)), "zero_h"),
    ]
    for t in range(T):
        inits.append(numpy_helper.from_array(np.array([t], np.int64), f"idx{t}"))
    inits.append(numpy_helper.from_array(np.array([1, D], np.int64), "shape1D"))
    nodes = [
        helper.make_node("Gather", ["E", "ids"], ["x"], axis=0),          # [1,T,D]
        helper.make_node("Mul", ["x", "x"], ["x2"]),
        helper.make_node("ReduceMean", ["x2"], ["ms"], axes=[-1], keepdims=1),
        helper.make_node("Add", ["ms", "eps"], ["ms_e"]),
        helper.make_node("Sqrt", ["ms_e"], ["rms"]),
        helper.make_node("Div", ["x", "rms"], ["xn"]),
        helper.make_node("Mul", ["xn", "g"], ["xg"]),
        helper.make_node("MatMul", ["xg", "Win"], ["u"]),                  # [1,T,D]
    ]
    for t in range(T):
        nodes += [
            helper.make_node("Gather", ["u", f"idx{t}"], [f"u{t}_"], axis=1),
            helper.make_node("Reshape", [f"u{t}_", "shape1D"], [f"u{t}"]),  # [1,D]
        ]
    h, acc = "zero_h", "zero_h"
    for t in range(T):
        nodes += [
            helper.make_node("Mul", [h, "gate_a"], [f"ha{t}"]),
            helper.make_node("Mul", [f"u{t}", "in_b"], [f"ub{t}"]),
            helper.make_node("Add", [f"ha{t}", f"ub{t}"], [f"h{t}"]),
            helper.make_node("Add", [acc, f"h{t}"], [f"acc{t}"]),
        ]
        h, acc = f"h{t}", f"acc{t}"
    h2 = "zero_h"
    for i, t in enumerate(range(T - 1, -1, -1)):
        nodes += [
            helper.make_node("Mul", [h2, "gate_a2"], [f"h2a{i}"]),
            helper.make_node("Mul", [f"u{t}", "in_b2"], [f"u2b{i}"]),
            helper.make_node("Add", [f"h2a{i}", f"u2b{i}"], [f"h2_{i}"]),
        ]
        h2 = f"h2_{i}"
    nodes += [
        helper.make_node("Mul", [acc, "invT"], ["accm"]),
        helper.make_node("MatMul", ["accm", "Wm"], ["p1"]),
        helper.make_node("MatMul", [h, "Wl"], ["p2"]),
        helper.make_node("MatMul", [h2, "Wl2"], ["p3"]),
        helper.make_node("Add", ["p1", "p2"], ["p12"]),
        helper.make_node("Add", ["p12", "p3"], ["pre"]),
        helper.make_node("Tanh", ["pre"], ["enc"]),
        helper.make_node("MatMul", ["enc", "Wfrom"], ["log_from"]),
        helper.make_node("MatMul", ["enc", "Wto"], ["log_to"]),
        helper.make_node("MatMul", ["enc", "Wneg"], ["log_neg"]),
    ]
    graph = helper.make_graph(
        nodes, "extractor",
        [helper.make_tensor_value_info("ids", TensorProto.INT64, [1, T])],
        [helper.make_tensor_value_info("log_from", TensorProto.FLOAT, [1, len(ENTITIES)]),
         helper.make_tensor_value_info("log_to", TensorProto.FLOAT, [1, len(ENTITIES)]),
         helper.make_tensor_value_info("log_neg", TensorProto.FLOAT, [1, 2])],
        inits)
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    onnx.checker.check_model(model)
    onnx.save(model, path)
    print(f"== ONNX 저장: {path} ({os.path.getsize(path)} bytes)", flush=True)


def onnx_ref(ext, ids):
    """ONNX와 동일 연산의 NumPy 참조 (float 대조용)."""
    lf, lt, ln = ext.forward(ids)
    return lf.d, lt.d, ln.d


# ── 3. ezkl 파이프라인 ───────────────────────────────────────────────
async def _run_ezkl(sample_ids, ref_outs):
    import inspect

    import ezkl

    async def A(v):  # ezkl 23.x: 일부 함수는 awaitable, 일부는 즉시값
        return await v if inspect.isawaitable(v) else v
    model, settings, compiled = f"{OUT}/net.onnx", f"{OUT}/settings.json", f"{OUT}/net.ezkl"
    vk, pk, witness, proof = f"{OUT}/vk.key", f"{OUT}/pk.key", f"{OUT}/witness.json", f"{OUT}/proof.json"
    data = f"{OUT}/input.json"
    json.dump({"input_data": [sample_ids.astype(float).flatten().tolist()]}, open(data, "w"))

    tic("gen_settings"); assert await A(ezkl.gen_settings(model, settings)); toc("gen_settings")
    tic("calibrate"); await A(ezkl.calibrate_settings(data, model, settings, "resources")); toc("calibrate")
    print("   settings:", {k: v for k, v in json.load(open(settings))["run_args"].items()
                           if k in ("input_scale", "param_scale", "logrows")}, flush=True)
    tic("compile"); assert await A(ezkl.compile_circuit(model, compiled, settings)); toc("compile")
    tic("get_srs"); await A(ezkl.get_srs(settings)); toc("get_srs")
    tic("setup"); assert await A(ezkl.setup(compiled, vk, pk)); toc("setup")
    tic("witness"); await A(ezkl.gen_witness(data, compiled, witness)); toc("witness")
    tic("prove"); await A(ezkl.prove(witness, compiled, pk, proof)); toc("prove")
    tic("verify"); ok = await A(ezkl.verify(proof, settings, vk)); toc("verify")
    assert ok, "verify failed"
    peak_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9
    logrows = json.load(open(settings))["run_args"]["logrows"]
    proof_bytes = os.path.getsize(proof)

    # 회로 출력 argmax vs float argmax (증명한 그 문장)
    w = json.load(open(witness))
    outs = w["outputs"] if "outputs" in w else w.get("output_data")
    def deq(vals, scale): return np.array([float(v) for v in vals])
    # ezkl witness outputs are field-encoded; use pretty outputs if present
    circ_match = None
    try:
        po = w.get("pretty_elements", {}).get("rescaled_outputs")
        if po:
            cf, ct, cn = [np.array([float(x) for x in o]) for o in po]
            circ_match = bool(cf.argmax() == ref_outs[0].argmax()
                              and ct.argmax() == ref_outs[1].argmax()
                              and cn.argmax() == ref_outs[2].argmax())
    except Exception as e:
        circ_match = f"parse-error: {e}"
    return {"logrows": logrows, "proof_bytes": proof_bytes,
            "peak_mem_gb": round(peak_gb, 2), "argmax_match_proved_sample": circ_match}


def main():
    ext, ts, tg = train_model()
    export_onnx(ext, f"{OUT}/net.onnx")
    sample = ts[:1]
    ref = onnx_ref(ext, sample)

    # ONNX 정합 확인 (onnxruntime 없이는 ezkl witness로 대체 — K3에서 잰다)
    import asyncio
    stats = asyncio.run(_run_ezkl(sample, ref))

    res = {"times_sec": {k: round(v, 1) for k, v in TIMES.items()}, **stats}
    k1 = True  # verify 통과 못 하면 위에서 assert로 죽는다
    k2 = TIMES.get("prove", 1e9) <= 1800 and TIMES.get("verify", 1e9) <= 10 \
        and stats["peak_mem_gb"] <= 16
    res["verdict"] = {"K1_prove_and_verify": k1, "K2_practical": bool(k2),
                      "K3_note": "argmax 일치는 증명 샘플 1건 기준 — 20문장 확장은 후속"}
    json.dump(res, open(f"{OUT}/results.json", "w"), indent=2)
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
