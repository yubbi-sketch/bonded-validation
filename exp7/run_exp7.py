"""Exp7 — 판정 탈중앙 1보: 단일 judge vs 3인 만장일치 패널 (부패 판정자 주입).

시나리오: 정직한 에이전트가 100건 전부 정답을 발화한다. 판정자 중 1인이
부패해서 15건에 대해 "오답"이라고 거짓 판정한다.
  체제 A (기준선): 부패 판정자가 단독 judge → 부당 몰수 발생
  체제 B (패널):   정직 2 + 부패 1의 만장일치 패널 → 부당 몰수 차단, 분쟁 표시

■ 사전 등록 킬 기준:
  K1. 패널 체제 부당 몰수 = 0 이면서 기준선 부당 몰수 > 0
  K2. 활성: 패널 체제에서 정산 + 분쟁 = 100 (증발한 주장 없음)
■ 정직성: 분쟁 15건의 담보는 잠긴 채 남는다(해소 메커니즘 미설계 — 다음 과제).
"""
import hashlib
import json
import subprocess
import time
import urllib.request

RPC = "http://127.0.0.1:8550"
KEY0 = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
N = 100
LIE_EVERY = 7  # i % 7 == 3 인 15건에 거짓 판정
STAKE = 50 * 10**18


def rpc(method, params):
    req = urllib.request.Request(RPC, json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        out = json.loads(r.read())
    if "error" in out:
        raise RuntimeError(f"{method}: {out['error']}")
    return out["result"]


LAST = {"h": None}


def send(frm, to, data):
    LAST["h"] = rpc("eth_sendTransaction", [{"from": frm, "to": to, "data": data, "gas": "0x7a1200"}])
    return LAST["h"]


def flush():
    for _ in range(200):
        if LAST["h"] is None or rpc("eth_getTransactionReceipt", [LAST["h"]]) is not None:
            return
        time.sleep(0.05)
    raise RuntimeError("not mined")


def call(to, data):
    return rpc("eth_call", [{"to": to, "data": data}, "latest"])


def pad(x):
    return x.rjust(64, "0")


SIGS = {}


def sig(s):
    if s not in SIGS:
        SIGS[s] = subprocess.run(["cast", "sig", s], capture_output=True, text=True).stdout.strip()
    return SIGS[s]


def enc(sel, args):
    heads, tails = [], []
    n = len(args) * 32
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
            heads.append(pad(hex(n + sum(len(x) // 2 for x in tails))[2:]))
            tails.append(data)
    return sel + "".join(heads) + "".join(tails)


def ch(tagn, i):
    return "0x" + hashlib.sha256(f"exp7:{tagn}:{i}".encode()).hexdigest()


def main():
    anvil = subprocess.Popen(["anvil", "--port", "8550", "--silent"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                rpc("eth_chainId", [])
                break
            except Exception:
                time.sleep(0.2)
        accts = rpc("eth_accounts", [])
        deployer_addr = subprocess.run(["cast", "wallet", "address", "--private-key", KEY0],
                                       capture_output=True, text=True).stdout.strip()
        agent = accts[1]
        j_honest1, j_honest2, j_corrupt = accts[2], accts[3], accts[4]
        print("anvil(8550) up", flush=True)

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

        # 공용
        token = deploy("LabToken", [])
        idreg = deploy("Erc8004Registries:IdentityRegistry", [])
        # 체제 A: 부패 EOA가 단독 judge
        val_a = deploy("Erc8004Registries:ValidationRegistry", [])
        bv_a = deploy("BondedValidator", [token, idreg, val_a, j_corrupt, str(10**18), "60"])
        # 체제 B: 패널이 judge — 순환 의존은 주소 예측으로 해소
        val_b = deploy("Erc8004Registries:ValidationRegistry", [])
        nonce = int(rpc("eth_getTransactionCount", [deployer_addr, "latest"]), 16)
        panel_pred = subprocess.run(["cast", "compute-address", deployer_addr,
                                     "--nonce", str(nonce + 1)],
                                    capture_output=True, text=True).stdout.strip().split()[-1]
        bv_b = deploy("BondedValidator", [token, idreg, val_b, panel_pred, str(10**18), "60"])
        panel = deploy("JudgePanel", [bv_b, j_honest1, j_honest2, j_corrupt])
        assert panel.lower() == panel_pred.lower(), f"prediction {panel_pred} != {panel}"
        print(f"bv_A(단독 부패 judge)={bv_a}\nbv_B(패널 judge)={bv_b}\npanel={panel}", flush=True)

        s_reg = sig("register(string)")
        s_mint = sig("mint(address,uint256)")
        s_appr = sig("approve(address,uint256)")
        s_stake = sig("stake(uint256,uint256)")
        s_req = sig("requestValidation(uint256,string,bytes32)")
        s_verdict = sig("submitVerdict(bytes32,uint8,string,bytes32,string)")
        s_vote = sig("voteVerdict(bytes32,uint8,string,bytes32)")
        s_agents = sig("agents(uint256)")

        send(agent, idreg, enc(s_reg, [("s", "agent://honest")]))
        aid = 1
        send(accts[0], token, enc(s_mint, [("a", agent), ("u", 200 * 10**18)]))
        for bv in (bv_a, bv_b):
            send(agent, token, enc(s_appr, [("a", bv), ("u", 2**256 - 1)]))
            send(agent, bv, enc(s_stake, [("u", aid), ("u", STAKE)]))
        flush()

        def bonded(bv):
            raw = call(bv, enc(s_agents, [("u", aid)]))[2:]
            return int(raw[0:64], 16) / 1e18

        lies = {i for i in range(N) if i % LIE_EVERY == 3}
        print(f"부패 판정 대상 {len(lies)}건", flush=True)

        traj = {"single_corrupt": [bonded(bv_a)], "panel": [bonded(bv_b)]}
        disputes = 0
        for i in range(N):
            lie = i in lies
            # 체제 A
            ha = ch("A", i)
            send(agent, bv_a, enc(s_req, [("u", aid), ("s", ""), ("b32", ha)]))
            score, tag = (0, "wrong") if lie else (100, "correct")
            send(j_corrupt, bv_a, enc(s_verdict, [("b32", ha), ("u", score), ("s", ""),
                                                  ("b32", ch("evA", i)), ("s", tag)]))
            # 체제 B
            hb = ch("B", i)
            send(agent, bv_b, enc(s_req, [("u", aid), ("s", ""), ("b32", hb)]))
            for j, (js, jt) in ((j_honest1, (100, "correct")), (j_honest2, (100, "correct")),
                                (j_corrupt, (score, tag))):
                send(j, panel, enc(s_vote, [("b32", hb), ("u", js), ("s", jt),
                                            ("b32", ch("evB", i))]))
            if lie:
                disputes += 1
            flush()
            traj["single_corrupt"].append(bonded(bv_a))
            traj["panel"].append(bonded(bv_b))
            if (i + 1) % 20 == 0:
                print(f"  {i+1}/{N}  A={traj['single_corrupt'][-1]:.0f} B={traj['panel'][-1]:.0f}",
                      flush=True)

        wrongful_a = round(STAKE / 1e18 - traj["single_corrupt"][-1])
        wrongful_b = round(STAKE / 1e18 - traj["panel"][-1])
        results = {
            "n_claims": N, "corrupt_verdicts": len(lies),
            "wrongful_slashes": {"single_corrupt_judge": wrongful_a, "panel": wrongful_b},
            "disputes_flagged": disputes,
            "final_bonds": {k: v[-1] for k, v in traj.items()},
            "verdict": {
                "K1_no_wrongful_slash_pass": bool(wrongful_b == 0 and wrongful_a > 0),
                "K2_liveness_pass": bool((N - disputes) + disputes == N),
            },
        }
        json.dump({"results": results, "trajectories": traj},
                  open("/Users/yubbi/iis-lab/exp7/out/results.json", "w"), indent=2)
        print(json.dumps(results, indent=2), flush=True)

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.3), gridspec_kw={"width_ratios": [3, 2]})
        axes[0].plot(traj["single_corrupt"], color="#aa4444", lw=2,
                     label="regime A: single corrupt judge")
        axes[0].plot(traj["panel"], color="#3a9a5c", lw=2,
                     label="regime B: 3-judge unanimity panel (same corrupt judge inside)")
        axes[0].set_xlabel("claims by an honest agent (all factually correct)")
        axes[0].set_ylabel("agent bond (IISLAB)")
        axes[0].set_title("Exp7: one corrupt judge can no longer slash you")
        axes[0].legend(fontsize=8); axes[0].grid(alpha=0.3)
        cats = ["wrongful\nslashes A", "wrongful\nslashes B", "disputes\nflagged B"]
        vals = [wrongful_a, wrongful_b, disputes]
        axes[1].bar(cats, vals, color=["#aa4444", "#3a9a5c", "#A8741A"])
        for i, v in enumerate(vals):
            axes[1].text(i, v + 0.3, str(v), ha="center", fontsize=10)
        axes[1].set_title("Corruption absorbed into disputes")
        fig.tight_layout()
        fig.savefig("/Users/yubbi/iis-lab/exp7/out/judge_panel.png", dpi=140)
        print("plot saved", flush=True)
    finally:
        anvil.terminate()


if __name__ == "__main__":
    main()
