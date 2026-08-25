"""exp1 본체 — 학습·3파전 평가·복잡도 실측·그래프 출력.

■ 사전 등록 킬 기준 (실행 전에 박제, 결과 보고 후 수정 금지):
  K1. [추출기+검증기] 종단 정확도가 함정 범주(invert+neg 합산)에서
      두 종단 베이스라인 중 최고 대비 +10%p 미만이면 → 추출기 접근 기각.
  K2. 어느 모델이든 전체 정확도가 다수결(항상 False 찍기) 이하면 학습 실패로 무효.
■ 정직성 라벨:
  - O(N^2) vs O(N) 절: '알려진 수학의 실측 확인'이며 새 주장이 아님.
  - 검증기 정확도 100%는 정의상 참이며 발견이 아님. 측정 대상은 추출 오류의 전파.
"""
import json
import time

import numpy as np

from autograd import Adam, cross_entropy
from data import ENTITIES, build_vocab, encode, encode_sent, gen_dataset
from models import Extractor, SSMClassifier, TransformerClassifier, count_params
from verifier import SymbolicLogicVerifier

MAX_LEN, SENT_LEN = 64, 14
N_TRAIN, N_TEST = 3000, 800
EPOCHS_E2E, EPOCHS_EXT, BATCH = 12, 40, 32


def batches(n, bs, rng):
    idx = rng.permutation(n)
    for i in range(0, n - bs + 1, bs):
        yield idx[i:i + bs]


def train_e2e(model, X, y, epochs, tag, rng, lr=3e-3):
    opt = Adam(model.params(), lr=lr)
    for ep in range(epochs):
        tot, nb = 0.0, 0
        for bi in batches(len(y), BATCH, rng):
            opt.zero_grad()
            loss = cross_entropy(model.forward(X[bi]), y[bi])
            loss.backward()
            opt.step()
            tot += float(loss.d); nb += 1
        print(f"  [{tag}] epoch {ep+1}/{epochs} loss={tot/nb:.4f}", flush=True)


def eval_e2e(model, X, y, qtypes):
    pred = model.forward(X).d.argmax(axis=-1)
    return per_category(pred, y, qtypes)


def per_category(pred, y, qtypes):
    res = {"overall": float((pred == y).mean())}
    for qt in sorted(set(qtypes)):
        m = np.array([q == qt for q in qtypes])
        res[qt] = float((pred[m] == y[m]).mean())
    return res


def train_extractor(ext, sents_ids, gold, epochs, rng, lr=3e-3):
    opt = Adam(ext.params(), lr=lr)
    frm, to, neg = gold[:, 0], gold[:, 1], gold[:, 2]
    for ep in range(epochs):
        tot, nb = 0.0, 0
        for bi in batches(len(frm), 64, rng):
            opt.zero_grad()
            lf, lt, ln = ext.forward(sents_ids[bi])
            loss = cross_entropy(lf, frm[bi]) + cross_entropy(lt, to[bi]) + cross_entropy(ln, neg[bi])
            loss.backward()
            opt.step()
            tot += float(loss.d); nb += 1
        opt.lr *= 0.93  # 후반 불안정 방지 감쇠
        print(f"  [extractor] epoch {ep+1}/{epochs} loss={tot/nb:.4f}", flush=True)


def pipeline_predict(ext, example, vocab):
    ids = np.array([encode_sent(s, vocab, SENT_LEN) for s in example["sents"]])
    lf, lt, ln = ext.forward(ids)
    f, t, n = lf.d.argmax(-1), lt.d.argmax(-1), ln.d.argmax(-1)
    v = SymbolicLogicVerifier()
    for i in range(len(ids) - 1):
        v.add_rule(int(f[i]), int(t[i]), neg=bool(n[i]))
    qi = len(ids) - 1
    return int(v.derives(int(f[qi]), int(t[qi]), target_neg=bool(n[qi])))


def complexity_bench(vocab_size):
    """알려진 수학의 실측 확인 — 어텐션 행렬 vs 상태 벡터, 시간·메모리."""
    d = 48
    rows = []
    for N in [64, 256, 1024, 4096]:
        x = np.random.randn(1, N, d)
        Wq = np.random.randn(d, d); Wk = np.random.randn(d, d); Wv = np.random.randn(d, d)
        t0 = time.perf_counter()
        q, k, v = x @ Wq, x @ Wk, x @ Wv
        att = q @ k.transpose(0, 2, 1) / np.sqrt(d)
        att = np.exp(att - att.max(-1, keepdims=True)); att /= att.sum(-1, keepdims=True)
        _ = att @ v
        t_att = time.perf_counter() - t0
        mem_att = att.nbytes  # N×N 행렬이 지배항

        a = np.random.rand(d); b = np.random.rand(d)
        u = x @ Wq
        t0 = time.perf_counter()
        h = np.zeros((1, d))
        for i in range(N):
            h = h * a + u[:, i, :] * b
        t_ssm = time.perf_counter() - t0
        mem_ssm = h.nbytes  # 고정 상태

        rows.append({"N": N, "attn_ms": t_att * 1e3, "ssm_ms": t_ssm * 1e3,
                     "attn_mem_bytes": int(mem_att), "ssm_mem_bytes": int(mem_ssm)})
        print(f"  N={N:5d}  attn {t_att*1e3:8.1f}ms/{mem_att/2**20:7.2f}MB   "
              f"ssm {t_ssm*1e3:8.1f}ms/{mem_ssm/1024:.2f}KB", flush=True)
    return rows


def main():
    rng = np.random.default_rng(42)
    vocab = build_vocab()
    print(f"== 데이터 생성: train={N_TRAIN} test={N_TEST} vocab={len(vocab)}", flush=True)
    train = gen_dataset(N_TRAIN, seed=1)
    test = gen_dataset(N_TEST, seed=2)

    Xtr = np.array([encode(d["sents"], vocab, MAX_LEN) for d in train])
    ytr = np.array([d["label"] for d in train])
    Xte = np.array([encode(d["sents"], vocab, MAX_LEN) for d in test])
    yte = np.array([d["label"] for d in test])
    qte = [d["qtype"] for d in test]
    majority = max(yte.mean(), 1 - yte.mean())

    tf = TransformerClassifier(len(vocab), T_len=MAX_LEN)
    ssm = SSMClassifier(len(vocab))
    ext = Extractor(len(vocab), n_ent=len(ENTITIES), d=64)
    print(f"== 파라미터: transformer={count_params(tf):,} ssm={count_params(ssm):,} "
          f"extractor={count_params(ext):,}", flush=True)

    print("== 종단 학습: Mini-Transformer", flush=True)
    t0 = time.perf_counter()
    train_e2e(tf, Xtr, ytr, EPOCHS_E2E, "transformer", rng)
    print("== 종단 학습: SSM", flush=True)
    train_e2e(ssm, Xtr, ytr, EPOCHS_E2E, "ssm", rng)

    print("== 추출기 학습 (문장→슬롯)", flush=True)
    sents, gold = [], []
    for d in train:
        for s, g in zip(d["sents"], d["gold"]):
            sents.append(encode_sent(s, vocab, SENT_LEN))
            gold.append([int(g[0]), int(g[1]), int(g[2])])
    sents = np.array(sents); gold = np.array(gold)
    cap = min(len(gold), 20000)
    train_extractor(ext, sents[:cap], gold[:cap], EPOCHS_EXT, rng)
    train_secs = time.perf_counter() - t0

    print("== 평가", flush=True)
    acc_tf = eval_e2e(tf, Xte, yte, qte)
    acc_ssm = eval_e2e(ssm, Xte, yte, qte)
    pred_pipe = np.array([pipeline_predict(ext, d, vocab) for d in test])
    acc_pipe = per_category(pred_pipe, yte, qte)

    # 추출 슬롯 정확도 (테스트셋 문장 단위)
    ts, tg = [], []
    for d in test:
        for s, g in zip(d["sents"], d["gold"]):
            ts.append(encode_sent(s, vocab, SENT_LEN))
            tg.append([int(g[0]), int(g[1]), int(g[2])])
    ts = np.array(ts); tg = np.array(tg)
    lf, lt, ln = ext.forward(ts)
    slot_ok = ((lf.d.argmax(-1) == tg[:, 0]) & (lt.d.argmax(-1) == tg[:, 1])
               & (ln.d.argmax(-1) == tg[:, 2]))
    slot_acc = float(slot_ok.mean())

    print("== 복잡도 실측 (알려진 수학의 확인 — 새 주장 아님)", flush=True)
    bench = complexity_bench(len(vocab))

    # 킬 판정
    trap = ["invert", "neg"]
    def trapacc(a):
        return float(np.mean([a[t] for t in trap if t in a]))
    best_base_trap = max(trapacc(acc_tf), trapacc(acc_ssm))
    k1_margin = trapacc(acc_pipe) - best_base_trap
    verdict = {
        "K1_trap_margin_pp": round(k1_margin * 100, 1),
        "K1_pass": bool(k1_margin >= 0.10),
        "K2_all_above_majority": bool(min(acc_tf["overall"], acc_ssm["overall"],
                                          acc_pipe["overall"]) > majority),
        "majority_baseline": round(float(majority), 3),
    }

    results = {
        "params": {"transformer": count_params(tf), "ssm": count_params(ssm),
                   "extractor": count_params(ext)},
        "accuracy": {"transformer": acc_tf, "ssm": acc_ssm, "pipeline": acc_pipe},
        "extraction_slot_accuracy": slot_acc,
        "complexity_bench": bench,
        "verdict": verdict,
        "train_seconds": round(train_secs, 1),
        "n_train": N_TRAIN, "n_test": N_TEST,
    }
    with open("out/results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(json.dumps(results["accuracy"], indent=2))
    print("VERDICT:", verdict, flush=True)

    make_plots(results)


def make_plots(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cats = ["overall", "direct", "chain", "invert", "neg"]
    names = ["transformer", "ssm", "pipeline"]
    labels = {"transformer": "Mini-Transformer (end-to-end)",
              "ssm": "SSM (end-to-end)", "pipeline": "Extractor + Symbolic Verifier"}
    colors = {"transformer": "#8888aa", "ssm": "#55aabb", "pipeline": "#dd7733"}

    fig, ax = plt.subplots(figsize=(9, 4.5))
    w = 0.26
    xs = np.arange(len(cats))
    for i, n in enumerate(names):
        vals = [res["accuracy"][n].get(c, 0) for c in cats]
        ax.bar(xs + (i - 1) * w, vals, w, label=labels[n], color=colors[n])
    ax.axhline(res["verdict"]["majority_baseline"], ls="--", c="gray", lw=1,
               label="majority baseline")
    ax.set_xticks(xs, ["overall", "direct", "chain (3+ hop)", "inverted (trap)", "negation"])
    ax.set_ylim(0, 1.05); ax.set_ylabel("accuracy")
    ax.set_title("Exp1: 3-way logic accuracy by category (natural-language input)")
    ax.legend(fontsize=8, loc="lower left")
    fig.tight_layout(); fig.savefig("out/accuracy.png", dpi=140); plt.close(fig)

    b = res["complexity_bench"]
    Ns = [r["N"] for r in b]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(Ns, [r["attn_ms"] for r in b], "o-", label="attention O(N^2)")
    axes[0].plot(Ns, [r["ssm_ms"] for r in b], "s-", label="SSM scan O(N)")
    axes[0].set_xlabel("sequence length N"); axes[0].set_ylabel("forward time (ms)")
    axes[0].set_xscale("log"); axes[0].set_yscale("log"); axes[0].legend()
    axes[0].set_title("Time vs length (measured)")
    axes[1].plot(Ns, [r["attn_mem_bytes"] / 2**20 for r in b], "o-", label="attention matrix (MB)")
    axes[1].plot(Ns, [r["ssm_mem_bytes"] / 2**20 for r in b], "s-", label="SSM state (MB)")
    axes[1].set_xlabel("sequence length N"); axes[1].set_ylabel("working memory (MB)")
    axes[1].set_xscale("log"); axes[1].set_yscale("log"); axes[1].legend()
    axes[1].set_title("Memory vs length (known math, confirmed)")
    fig.suptitle("Confirmation of known complexity — not a novel claim", fontsize=9, y=1.02)
    fig.tight_layout(); fig.savefig("out/complexity.png", dpi=140); plt.close(fig)
    print("plots saved: out/accuracy.png, out/complexity.png", flush=True)


if __name__ == "__main__":
    main()
