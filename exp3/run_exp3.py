"""Exp3 — 지붕 명제의 첫 실물: "틀린 발화는 담보를 잃는다".

Anvil 로컬 체인에 LabToken+BondManager 배포 후, 에이전트 3종이
Exp1 논리 문제 100건에 각각 담보를 걸고(submitClaim) 답한다.
판정자(judge)는 합성 정답지로 settle — 오답이면 슬래싱.

에이전트:
  honest      — 정답지 그대로 답함 (완벽한 검증 뒷받침의 대리)
  extractor   — Exp1의 추출기+기호 검증기 파이프라인 (우리 AI)
  hallucinator— 동전 던지기 (근거 없는 발화의 대리)

정직성 주석: judge가 정답을 아는 것은 실험실 설정이다. 실제 체계에서 judge를
ZK 증명·도전 게임으로 대체하는 것이 후속 연구이며, 여기서는 경제 골격만 검증한다.
"""
import hashlib
import json
import subprocess
import sys
import time
import urllib.request

RPC = "http://127.0.0.1:8546"
KEY0 = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"  # anvil #0 = judge/배포자
ACCTS = None  # anvil 기본 언락 계정 (RPC로 조회)
N_PROBLEMS = 100
STAKE = 50 * 10**18
MINT = 100 * 10**18
MIN_BOND = 1 * 10**18

sys.path.insert(0, "/Users/yubbi/iis-lab/exp1")


def rpc(method, params):
    req = urllib.request.Request(RPC, json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        out = json.loads(r.read())
    if "error" in out:
        raise RuntimeError(f"{method}: {out['error']}")
    return out["result"]


def send(frm, to, data):
    return rpc("eth_sendTransaction", [{"from": frm, "to": to, "data": data, "gas": "0x7a1200"}])


def call(to, data):
    return rpc("eth_call", [{"to": to, "data": data}, "latest"])


def pad(x, n=64):
    return x.rjust(n, "0")


def enc_addr(a):
    return pad(a[2:].lower())


def enc_uint(v):
    return pad(hex(v)[2:])


SIG_CACHE = {}


def sig(s):
    if s not in SIG_CACHE:
        SIG_CACHE[s] = subprocess.run(["cast", "sig", s], capture_output=True,
                                      text=True).stdout.strip()
    return SIG_CACHE[s]


def claim_hash(i, answer):
    return "0x" + hashlib.sha256(f"exp3:{i}:{answer}".encode()).hexdigest()


def main():
    # 1) Anvil 기동
    anvil = subprocess.Popen(["anvil", "--port", "8546", "--silent"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                rpc("eth_chainId", [])
                break
            except Exception:
                time.sleep(0.2)
        accts = rpc("eth_accounts", [])
        judge, honest, extractor_a, hallu = accts[0], accts[1], accts[2], accts[3]
        print(f"anvil up. judge={judge[:10]}… agents=3", flush=True)

        # 2) 배포
        def deploy(name, args):
            cmd = ["forge", "create", f"src/{name}.sol:{name}", "--rpc-url", RPC,
                   "--private-key", KEY0, "--broadcast"]
            if args:
                cmd += ["--constructor-args"] + args
            r = subprocess.run(cmd, capture_output=True, text=True,
                               cwd="/Users/yubbi/iis-lab/exp3/contracts")
            for line in r.stdout.splitlines():
                if "Deployed to:" in line:
                    return line.split()[-1]
            raise RuntimeError(r.stdout + r.stderr)

        token = deploy("LabToken", [])
        bm = deploy("BondManager", [token, judge, str(MIN_BOND), "60"])
        print(f"LabToken={token}\nBondManager={bm}", flush=True)

        # 3) 배분·승인·예치
        s_mint = sig("mint(address,uint256)")
        s_appr = sig("approve(address,uint256)")
        s_stake = sig("stake(uint256)")
        s_submit = sig("submitClaim(bytes32)")
        s_settle = sig("settle(uint256,bool,bytes32)")
        s_agents = sig("agents(address)")
        for a in (honest, extractor_a, hallu):
            send(judge, token, s_mint + enc_addr(a) + enc_uint(MINT))
            send(a, token, s_appr + enc_addr(bm) + "f" * 64)
            send(a, bm, s_stake + enc_uint(STAKE))
        print("staked 50 IISLAB each", flush=True)

        def bonded(a):
            raw = call(bm, s_agents + enc_addr(a))[2:]
            return int(raw[0:64], 16) / 1e18

        # 4) 우리 AI 준비 (Exp1 추출기 학습)
        print("training extractor (Exp1)…", flush=True)
        import numpy as np
        from data import build_vocab, encode_sent, gen_dataset  # noqa: E402
        from models import Extractor  # noqa: E402
        from data import ENTITIES  # noqa: E402
        from train import SENT_LEN, pipeline_predict, train_extractor  # noqa: E402
        rng = np.random.default_rng(42)
        vocab = build_vocab()
        train_data = gen_dataset(3000, seed=1)
        ext = Extractor(len(vocab), n_ent=len(ENTITIES), d=64)
        sents, gold = [], []
        for d in train_data:
            for s, g in zip(d["sents"], d["gold"]):
                sents.append(encode_sent(s, vocab, SENT_LEN))
                gold.append([int(g[0]), int(g[1]), int(g[2])])
        train_extractor(ext, np.array(sents)[:20000], np.array(gold)[:20000], 40, rng)

        problems = gen_dataset(N_PROBLEMS, seed=5)[:N_PROBLEMS]

        # 5) 본 실험: 담보 걸린 발화 100건 × 3 에이전트
        traj = {"honest": [bonded(honest)], "extractor": [bonded(extractor_a)],
                "hallucinator": [bonded(hallu)]}
        cid = 0
        coin = np.random.default_rng(7)
        for i, prob in enumerate(problems):
            answers = {
                "honest": (honest, prob["label"]),
                "extractor": (extractor_a, pipeline_predict(ext, prob, vocab)),
                "hallucinator": (hallu, int(coin.integers(2))),
            }
            for name, (addr, ans) in answers.items():
                send(addr, bm, s_submit + claim_hash(i, ans)[2:])
                violated = int(ans != prob["label"])
                ev = claim_hash(i, f"evidence:{prob['label']}")
                send(judge, bm, s_settle + enc_uint(cid) + enc_uint(violated) + ev[2:])
                cid += 1
            for name, (addr, _) in answers.items():
                traj[name].append(bonded(addr))
            if (i + 1) % 20 == 0:
                print(f"  {i+1}/{N_PROBLEMS}  bonds: " +
                      " ".join(f"{k}={traj[k][-1]:.0f}" for k in traj), flush=True)

        results = {
            "n_problems": N_PROBLEMS, "stake_initial": STAKE / 1e18,
            "min_bond_per_claim": MIN_BOND / 1e18,
            "final_bonds": {k: v[-1] for k, v in traj.items()},
            "slashes": {k: round(traj[k][0] - traj[k][-1]) for k in traj},
            "contracts": {"LabToken": token, "BondManager": bm},
            "claims_total": cid,
        }
        json.dump({"results": results, "trajectories": traj},
                  open("/Users/yubbi/iis-lab/exp3/out/results.json", "w"), indent=2)
        print(json.dumps(results, indent=2), flush=True)

        # 6) 그래프
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 4.5))
        styles = {"honest": ("#3a9a5c", "honest (gold-backed)"),
                  "extractor": ("#dd7733", "extractor + symbolic verifier (ours)"),
                  "hallucinator": ("#aa4444", "hallucinator (coin flip)")}
        for k, (c, lb) in styles.items():
            ax.plot(range(len(traj[k])), traj[k], color=c, label=lb, lw=2)
        ax.set_xlabel("bonded claims (logic problems answered)")
        ax.set_ylabel("bond balance (IISLAB)")
        ax.set_title("Exp3: every utterance is bonded — wrong utterances lose stake\n"
                     "(Anvil local chain, BondManager, judge = synthetic ground truth)")
        ax.legend(); ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig("/Users/yubbi/iis-lab/exp3/out/bond_trajectories.png", dpi=140)
        print("plot saved", flush=True)
    finally:
        anvil.terminate()


if __name__ == "__main__":
    main()
