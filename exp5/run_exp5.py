"""Exp5 — BondedValidator v0: ERC-8004 위 발화자 담보 프로토콜 라이브 시연.

Exp3 시나리오의 8004 승격판:
  - 에이전트 3종이 Identity 레지스트리에 등록(agentId 발급)
  - 모든 발화가 Validation 레지스트리에 표준 이벤트로 기록
  - 우리 추출기는 Exp2의 기권 규칙(τ=0.9) 장착 — 저확신이면 "abstain"(무손실)
  - 종료 시 레지스트리 getSummary = 온체인 평판 점수 실측
"""
import hashlib
import json
import subprocess
import sys
import time
import urllib.request

RPC = "http://127.0.0.1:8547"
KEY0 = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
N_PROBLEMS = 100
STAKE = 50 * 10**18
MINT = 100 * 10**18
TAU = 0.9  # Exp2 관측 무오답점

sys.path.insert(0, "/Users/yubbi/iis-lab/exp1")
sys.path.insert(0, "/Users/yubbi/iis-lab/exp2")


def rpc(method, params):
    req = urllib.request.Request(RPC, json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        out = json.loads(r.read())
    if "error" in out:
        raise RuntimeError(f"{method}: {out['error']}")
    return out["result"]


LAST_TX = {"h": None}


def send(frm, to, data):
    h = rpc("eth_sendTransaction", [{"from": frm, "to": to, "data": data, "gas": "0x7a1200"}])
    LAST_TX["h"] = h
    return h


def flush():
    """마지막 tx가 채굴될 때까지 대기 — eth_call 읽기 전 상태 레이스 방지."""
    if LAST_TX["h"] is None:
        return
    for _ in range(200):
        if rpc("eth_getTransactionReceipt", [LAST_TX["h"]]) is not None:
            return
        time.sleep(0.05)
    raise RuntimeError("tx not mined in time")


def call(to, data):
    return rpc("eth_call", [{"to": to, "data": data}, "latest"])


def pad(x):
    return x.rjust(64, "0")


SIGS = {}


def sig(s):
    if s not in SIGS:
        SIGS[s] = subprocess.run(["cast", "sig", s], capture_output=True, text=True).stdout.strip()
    return SIGS[s]


def enc(selector, args):
    """미니 ABI 인코더 — ("u",int) ("a",addr) ("b32","0x..") ("s",str) 지원."""
    heads, tails = [], []
    n_head = len(args) * 32
    for t, v in args:
        if t == "u":
            heads.append(pad(hex(v)[2:]))
        elif t == "a":
            heads.append(pad(v[2:].lower()))
        elif t == "b32":
            heads.append(v[2:])
        elif t == "s":
            b = v.encode()
            data = pad(hex(len(b))[2:]) + (b.hex().ljust(((len(b) + 31) // 32) * 64, "0") if b else "")
            heads.append(pad(hex(n_head + sum(len(x) // 2 for x in tails))[2:]))
            tails.append(data)
    return selector + "".join(heads) + "".join(tails)


MODEL_VER = "extractor-v1-d64-bidir-tau0.9"


def claim_hash(agent, i, content="", answer=""):
    """내용 커밋: (에이전트, 문제 원문, 답, 모델 버전)을 전부 묶는다."""
    pre = f"exp5:{agent}:{i}:{MODEL_VER}:{content}:{answer}"
    return "0x" + hashlib.sha256(pre.encode()).hexdigest()


def main():
    anvil = subprocess.Popen(["anvil", "--port", "8547", "--silent"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                rpc("eth_chainId", [])
                break
            except Exception:
                time.sleep(0.2)
        accts = rpc("eth_accounts", [])
        judge, w_honest, w_ext, w_hallu = accts[0], accts[1], accts[2], accts[3]
        print("anvil(8547) up", flush=True)

        def deploy(name, args):
            cmd = ["forge", "create", f"src/{name.split(':')[0]}.sol:{name.split(':')[-1]}",
                   "--rpc-url", RPC, "--private-key", KEY0, "--broadcast"]
            if args:
                cmd += ["--constructor-args"] + args
            r = subprocess.run(cmd, capture_output=True, text=True,
                               cwd="/Users/yubbi/iis-lab/exp3/contracts")
            for line in r.stdout.splitlines():
                if "Deployed to:" in line:
                    return line.split()[-1]
            raise RuntimeError(r.stdout + r.stderr)

        token = deploy("LabToken", [])
        idreg = deploy("Erc8004Registries:IdentityRegistry", [])
        valreg = deploy("Erc8004Registries:ValidationRegistry", [])
        bv = deploy("BondedValidator", [token, idreg, valreg, judge,
                                       str(10**18), "60"])
        print(f"IdentityRegistry={idreg}\nValidationRegistry={valreg}\nBondedValidator={bv}", flush=True)

        s_reg = sig("register(string)")
        s_mint = sig("mint(address,uint256)")
        s_appr = sig("approve(address,uint256)")
        s_stake = sig("stake(uint256,uint256)")
        s_req = sig("requestValidation(uint256,string,bytes32)")
        s_verdict = sig("submitVerdict(bytes32,uint8,string,bytes32,string)")
        s_agents = sig("agents(uint256)")
        s_summary = sig("getSummary(uint256)")

        wallets = {"honest": w_honest, "extractor": w_ext, "hallucinator": w_hallu}
        agent_ids = {}
        for i, (name, w) in enumerate(wallets.items(), start=1):
            send(w, idreg, enc(s_reg, [("s", f"agent://iis/{name}")]))
            agent_ids[name] = i  # 등록 순서 = agentId
            send(judge, token, enc(s_mint, [("a", w), ("u", MINT)]))
            send(w, token, enc(s_appr, [("a", bv), ("u", 2**256 - 1)]))
            send(w, bv, enc(s_stake, [("u", i), ("u", STAKE)]))
        print("registered agentIds:", agent_ids, flush=True)

        def bonded(aid):
            return int(call(bv, enc(s_agents, [("u", aid)]))[2:][:64], 16) / 1e18

        def summary(aid):
            raw = call(valreg, enc(s_summary, [("u", aid)]))[2:]
            return int(raw[:64], 16), int(raw[64:128], 16)

        print("== 추출기 준비 (Exp1 구성 + Exp2 확신도)", flush=True)
        import numpy as np
        from data import ENTITIES, build_vocab, encode_sent, gen_dataset  # noqa
        from models import Extractor  # noqa
        from train import SENT_LEN, train_extractor  # noqa
        from run_exp2 import predict_with_conf  # noqa
        rng = np.random.default_rng(42)
        vocab = build_vocab()
        tr = gen_dataset(3000, seed=1)
        ext = Extractor(len(vocab), n_ent=len(ENTITIES), d=64)
        sents, gold = [], []
        for d in tr:
            for s, g in zip(d["sents"], d["gold"]):
                sents.append(encode_sent(s, vocab, SENT_LEN))
                gold.append([int(g[0]), int(g[1]), int(g[2])])
        train_extractor(ext, np.array(sents)[:20000], np.array(gold)[:20000], 40, rng)
        problems = gen_dataset(N_PROBLEMS, seed=9)[:N_PROBLEMS]

        traj = {k: [bonded(v)] for k, v in agent_ids.items()}
        counts = {k: {"correct": 0, "wrong": 0, "abstain": 0} for k in agent_ids}
        coin = np.random.default_rng(11)
        for i, prob in enumerate(problems):
            ans_ext, conf = predict_with_conf(ext, prob, vocab)
            moves = {
                "honest": (prob["label"], False),
                "extractor": (ans_ext, conf < TAU),
                "hallucinator": (int(coin.integers(2)), False),
            }
            content = " | ".join(prob["sents"])
            for name, (ans, abstain) in moves.items():
                aid, w = agent_ids[name], wallets[name]
                h = claim_hash(name, i, content, "abstain" if abstain else str(ans))
                send(w, bv, enc(s_req, [("u", aid), ("s", ""), ("b32", h)]))
                if abstain:
                    score, tag = 0, "abstain"
                    counts[name]["abstain"] += 1
                else:
                    right = ans == prob["label"]
                    score, tag = (100, "correct") if right else (0, "wrong")
                    counts[name]["correct" if right else "wrong"] += 1
                ev = "0x" + hashlib.sha256(f"ev:{i}:{prob['label']}".encode()).hexdigest()
                send(judge, bv, enc(s_verdict, [("b32", h), ("u", score), ("s", ""),
                                                ("b32", ev), ("s", tag)]))
            flush()
            for name in agent_ids:
                traj[name].append(bonded(agent_ids[name]))
            if (i + 1) % 20 == 0:
                print(f"  {i+1}/{N_PROBLEMS}  bonds: " +
                      " ".join(f"{k}={traj[k][-1]:.0f}" for k in traj), flush=True)

        flush()
        reputation = {k: summary(v) for k, v in agent_ids.items()}
        results = {
            "n_problems": N_PROBLEMS, "tau": TAU,
            "final_bonds": {k: v[-1] for k, v in traj.items()},
            "moves": counts,
            "onchain_reputation": {k: {"validations": c, "avg_score": a}
                                   for k, (c, a) in reputation.items()},
            "contracts": {"IdentityRegistry": idreg, "ValidationRegistry": valreg,
                          "BondedValidator": bv},
        }
        json.dump({"results": results, "trajectories": traj},
                  open("/Users/yubbi/iis-lab/exp5/out/results.json", "w"), indent=2)
        print(json.dumps(results, indent=2), flush=True)

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4),
                                 gridspec_kw={"width_ratios": [3, 2]})
        styles = {"honest": ("#3a9a5c", "honest"),
                  "extractor": ("#dd7733", "extractor + verifier + abstain(τ=0.9)"),
                  "hallucinator": ("#aa4444", "hallucinator")}
        for k, (c, lb) in styles.items():
            axes[0].plot(traj[k], color=c, label=lb, lw=2)
        axes[0].set_xlabel("bonded utterances"); axes[0].set_ylabel("bond (IISLAB)")
        axes[0].set_title("Exp5: speaker-bonded utterances on ERC-8004 registries")
        axes[0].legend(fontsize=8); axes[0].grid(alpha=0.3)
        names = list(agent_ids)
        avgs = [reputation[k][1] for k in names]
        axes[1].bar(names, avgs, color=[styles[k][0] for k in names])
        axes[1].set_ylabel("ValidationRegistry avg score (0–100)")
        axes[1].set_title("On-chain reputation (getSummary)")
        for i, v in enumerate(avgs):
            axes[1].text(i, v + 1, str(v), ha="center", fontsize=9)
        fig.tight_layout()
        fig.savefig("/Users/yubbi/iis-lab/exp5/out/bonded_validation.png", dpi=140)
        print("plot saved", flush=True)
    finally:
        anvil.terminate()


if __name__ == "__main__":
    main()
