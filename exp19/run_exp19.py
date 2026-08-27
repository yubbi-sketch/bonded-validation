"""Exp19 — 온체인 대량 파일럿(P7). Exp18의 창발 정직 균형을 실제 배포 로직 위에서.

Anvil에 LabToken·8004 레지스트리·BondedValidator 배포 → 다수 자율 에이전트가
지갑으로 등록·스테이크·발화, 오라클이 판정(정답 +R 온체인 전송·오답 −B 슬래시).
합리적 정책 p≥τ*=B/(B+R)만 답변. EXP19.md 킬 기준 준수.
"""
import hashlib
import json
import os
import subprocess
import time
import urllib.request

import numpy as np

RPC = "http://127.0.0.1:8555"
KEY0 = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
CDIR = "/Users/yubbi/iis-lab/exp3/contracts"
OUT = "out"

N_AGENTS = 40          # 자율 에이전트 수 (+ 오라클 1)
ROUNDS = 25            # 라운드 (총 발화 ~ N×ROUNDS)
B = 10**18            # minBond (사건당 담보 = 슬래시 단위)
R = 15 * 10**17       # 보상 1.5e18 → τ* = B/(B+R) = 0.4
TAU = B / (B + R)
STAKE = 15 * 10**18   # 초기 담보(15 사건분)
MINT = 20 * 10**18    # 에이전트 초기 지갑
SEED = 2026
os.makedirs(OUT, exist_ok=True)


def rpc(method, params):
    req = urllib.request.Request(RPC, json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        out = json.loads(r.read())
    if "error" in out:
        raise RuntimeError(f"{method}: {out['error']}")
    return out["result"]


LAST = {"h": None}
def send(frm, to, data):
    LAST["h"] = rpc("eth_sendTransaction",
                    [{"from": frm, "to": to, "data": data, "gas": "0x7a1200"}])
    return LAST["h"]


def flush():
    if LAST["h"] is None:
        return
    for _ in range(400):
        if rpc("eth_getTransactionReceipt", [LAST["h"]]) is not None:
            return
        time.sleep(0.03)
    raise RuntimeError("tx not mined")


def call(to, data):
    return rpc("eth_call", [{"to": to, "data": data}, "latest"])


def pad(x): return x.rjust(64, "0")
SIGS = {}
def sig(s):
    if s not in SIGS:
        SIGS[s] = subprocess.run(["cast", "sig", s], capture_output=True, text=True).stdout.strip()
    return SIGS[s]


def enc(selector, args):
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


def hsh(*parts):
    return "0x" + hashlib.sha256(":".join(str(p) for p in parts).encode()).hexdigest()


def main():
    anvil = subprocess.Popen(
        ["anvil", "--port", "8555", "--accounts", str(N_AGENTS + 1), "--silent",
         "--balance", "1000"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: rpc("eth_chainId", []); break
            except Exception: time.sleep(0.2)
        accts = rpc("eth_accounts", [])
        judge = accts[0]
        agents = accts[1:N_AGENTS + 1]
        print(f"anvil up · judge + {len(agents)} agents", flush=True)

        def deploy(name, args):
            cmd = ["forge", "create", f"src/{name.split(':')[0]}.sol:{name.split(':')[-1]}",
                   "--rpc-url", RPC, "--private-key", KEY0, "--broadcast"]
            if args: cmd += ["--constructor-args"] + args
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=CDIR)
            for line in r.stdout.splitlines():
                if "Deployed to:" in line: return line.split()[-1]
            raise RuntimeError(r.stdout + r.stderr)

        token = deploy("LabToken", [])
        idreg = deploy("Erc8004Registries:IdentityRegistry", [])
        valreg = deploy("Erc8004Registries:ValidationRegistry", [])
        bv = deploy("BondedValidator", [token, idreg, valreg, judge, str(B), "60"])
        print(f"BondedValidator={bv}", flush=True)

        s_reg = sig("register(string)")
        s_mint = sig("mint(address,uint256)")
        s_appr = sig("approve(address,uint256)")
        s_stake = sig("stake(uint256,uint256)")
        s_req = sig("requestValidation(uint256,string,bytes32)")
        s_verdict = sig("submitVerdict(bytes32,uint8,string,bytes32,string)")
        s_agents = sig("agents(uint256)")
        s_bal = sig("balanceOf(address)")

        rng = np.random.default_rng(SEED)
        # 유형 배정: 60% 합리적, 25% 도박꾼(저능력·무조건답변), 15% 겁쟁이
        kinds, mus = [], []
        for i in range(N_AGENTS):
            r = rng.random()
            if r < 0.60: kinds.append("rational"); mus.append(rng.uniform(0.45, 0.95))
            elif r < 0.85: kinds.append("gambler"); mus.append(rng.uniform(0.20, 0.40))
            else: kinds.append("coward"); mus.append(rng.uniform(0.3, 0.9))
        mus = np.array(mus)

        # 오라클 보상 풀 + 에이전트 등록·스테이크
        send(judge, token, enc(s_mint, [("a", judge), ("u", 100000 * 10**18)]))
        aid = {}
        for i, w in enumerate(agents):
            send(w, idreg, enc(s_reg, [("s", f"agent://iis/{i}")]))
            aid[w] = i + 1  # 등록 순서 = agentId
            send(judge, token, enc(s_mint, [("a", w), ("u", MINT)]))
            send(w, token, enc(s_appr, [("a", bv), ("u", 2**256 - 1)]))
            send(w, bv, enc(s_stake, [("u", i + 1), ("u", STAKE)]))
        flush()
        print("등록·스테이크 완료", flush=True)

        def staked(a):
            return int(call(bv, enc(s_agents, [("u", aid[a])]))[2:][:64], 16)
        def free(a):
            raw = call(bv, enc(s_agents, [("u", aid[a])]))[2:]
            return int(raw[:64], 16) - int(raw[64:128], 16)  # bonded - atRisk
        def wallet(a):
            return int(call(token, enc(s_bal, [("a", a)]))[2:], 16)

        start_net = {a: staked(a) + wallet(a) for a in agents}
        slash_total = 0
        for rnd in range(ROUNDS):
            confs = np.clip(mus + rng.normal(0, 0.12, N_AGENTS), 0.02, 0.98)
            for i, w in enumerate(agents):
                k = kinds[i]; p = confs[i]
                answer = (k == "gambler") or (k == "rational" and p >= TAU)
                if k == "coward": answer = False
                if answer and free(w) < B:
                    answer = False  # 담보 부족 → 강제 기권(파산)
                if not answer:
                    continue
                h = hsh("exp19", i, rnd)
                send(w, bv, enc(s_req, [("u", aid[w]), ("s", ""), ("b32", h)]))
                correct = rng.random() < p
                score, tag = (100, "correct") if correct else (0, "wrong")
                ev = hsh("ev", i, rnd)
                send(judge, bv, enc(s_verdict, [("b32", h), ("u", score), ("s", ""),
                                                ("b32", ev), ("s", tag)]))
                if correct:
                    send(judge, token, enc(sig("transfer(address,uint256)"),
                                           [("a", w), ("u", R)]))
                else:
                    slash_total += B
            flush()
            if (rnd + 1) % 5 == 0:
                nets = {k: [] for k in ("rational", "gambler", "coward")}
                for i, w in enumerate(agents):
                    nets[kinds[i]].append((staked(w) + wallet(w)) / 1e18)
                print(f"  라운드 {rnd+1}/{ROUNDS} 순부평균: " +
                      " ".join(f"{k}={np.mean(v):.1f}" for k, v in nets.items()), flush=True)

        flush()
        # 최종 집계
        by = {"rational": [], "gambler": [], "coward": []}
        bankrupt = {"rational": 0, "gambler": 0, "coward": 0}
        for i, w in enumerate(agents):
            net = staked(w) + wallet(w)
            by[kinds[i]].append(net / 1e18)
            if free(w) < B: bankrupt[kinds[i]] += 1
        # 토큰 보존 검사
        total_wallet = sum(wallet(a) for a in agents) + wallet(judge)
        total_staked = sum(staked(a) for a in agents)
        accounted = total_wallet + total_staked + slash_total
        minted = 100000 * 10**18 + N_AGENTS * MINT

        n = {k: len(v) for k, v in by.items()}
        mean = {k: (float(np.mean(v)) if v else 0.0) for k, v in by.items()}
        start_mean = np.mean([start_net[a] for a in agents]) / 1e18

        k1 = bool(n["gambler"] and mean["gambler"] < start_mean
                  and bankrupt["gambler"] >= n["gambler"] / 2)
        k2 = bool(mean["rational"] >= start_mean and mean["rational"] > mean["gambler"]
                  and (not n["coward"] or abs(mean["coward"] - start_mean) < 0.01))
        k3 = bool(accounted == minted)

        res = {
            "params": {"N": N_AGENTS, "rounds": ROUNDS, "B": B, "R": R, "tau_star": TAU,
                       "stake": STAKE, "start_net_avg": round(start_mean, 1)},
            "counts": n,
            "final_net_avg": {k: round(v, 1) for k, v in mean.items()},
            "bankrupt": bankrupt,
            "slash_total_tokens": slash_total // 10**18,
            "conservation": {"minted": str(minted), "accounted": str(accounted), "match": k3},
            "verdict": {"K1_gambler_bankrupt": k1, "K2_rational_survives": k2,
                        "K3_accounting_reconciles": k3,
                        "all_pass": bool(k1 and k2 and k3)},
            "seed": SEED,
        }
        json.dump(res, open(f"{OUT}/results.json", "w"), indent=2, ensure_ascii=False)
        print(f"\nτ*={TAU} · 시작 순부 {start_mean:.1f}")
        print(f"최종 순부: 합리적={mean['rational']:.1f}(n{n['rational']}) "
              f"도박꾼={mean['gambler']:.1f}(n{n['gambler']}) 겁쟁이={mean['coward']:.1f}(n{n['coward']})")
        print(f"파산: {bankrupt} · 슬래시 총 {slash_total//10**18} · 보존 {k3}")
        print(json.dumps(res["verdict"], indent=2, ensure_ascii=False))
    finally:
        anvil.terminate()


if __name__ == "__main__":
    main()
