"""Exp30 K3 — 억지력 조건부 재시뮬 (Anvil, Exp3 방식).

환각 에이전트(동전 던지기) vs 캘리브레이션 기권 에이전트, 각 100 발화. 정직 판정자 3인,
도전자 1명이 주장을 확률 q 로 개설한다. q ∈ {1, 0.5, 0} 세 행을 전부 박제한다:
  q = 1   : 모든 주장이 판정됨 — v0.2.1 과 동치 (Exp3 기록 50→8 의 재현 조건)
  q = 0.5 : 절반만 판정
  q = 0   : 아무도 도전하지 않음 — 전부 창 W 뒤 무손실 소멸 (예상: 환각 손실 0)

사전등록 킬기준(EXP30.md K3): q = 1 에서 환각 담보 50 → ≤ 10, 캘리브 ≥ 49. 환각 담보 > 25 잔존 → KILL.

정직성 주석:
  · 캘리브 에이전트는 Exp1 추출기 재학습 없이 '확신 c ≥ τ 이면 답(오류율 1%), 아니면 기권' 하는
    합성 대리다(Exp2 규칙의 골격). 판정자는 합성 정답지를 안다(실험실 설정, Exp3 과 동일).
  · q 는 외생 파라미터다 — 판정 수요 붕괴 → q → 0 자기강화는 모델 밖(EXP30.md §7-2).
  · 미개설 주장은 발화 직후 W 를 넘겨(evm_increaseTime) 즉시 소멸시킨다 — 담보 50 으로
    100 발화를 돌리기 위한 시간 압축이며, 정산 순서·금액에는 영향이 없다.
"""
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACTS = HERE.parent / "exp3" / "contracts"
RPC = "http://127.0.0.1:8547"
KEY0 = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"  # anvil #0 = 배포자·민터
N_PROBLEMS = 100
STAKE = 50 * 10**18
MINT = 100 * 10**18
MIN_BOND = 10**18
UNBOND = 3600
PER_CASE_BOND = 10 * 10**18
FEE = 10**18
VOTE_T = 3600
DISP_T = 86400
W = 86400
ENTRY = 15 * 10**18
TAU = 0.85
CALIB_ERR = 0.01
QS = [float(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [1.0, 0.5, 0.0]


def rpc(method, params):
    req = urllib.request.Request(RPC, json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.loads(r.read())
    if "error" in out:
        raise RuntimeError(f"{method}: {out['error']}")
    return out["result"]


def _reason(frm, to, data):
    """실패 tx 를 eth_call 로 재생해 Error(string) 사유를 읽는다 (디버그용)."""
    try:
        rpc("eth_call", [{"from": frm, "to": to, "data": data}, "latest"])
        return "(call ok — state-dependent)"
    except RuntimeError as e:
        msg = str(e)
        i = msg.find("0x08c379a0")
        if i >= 0:
            hexs = msg[i + 10:]
            hexs = "".join(ch for ch in hexs if ch in "0123456789abcdefABCDEF")
            try:
                ln = int(hexs[64:128], 16)
                return bytes.fromhex(hexs[128:128 + 2 * ln]).decode(errors="replace")
            except Exception:
                pass
        return msg[:200]


def send(frm, to, data):
    h = rpc("eth_sendTransaction", [{"from": frm, "to": to, "data": data, "gas": "0x7a1200"}])
    rcpt = None
    for _ in range(100):  # anvil automine 는 해시 반환 직후 영수증이 잠깐 비어 있을 수 있다(실측: 1/3000 tx)
        rcpt = rpc("eth_getTransactionReceipt", [h])
        if rcpt is not None:
            break
        time.sleep(0.02)
    if rcpt is None:
        raise RuntimeError(f"no receipt: to={to} sel={data[:10]}")
    if rcpt.get("status") != "0x1":
        raise RuntimeError(f"tx failed: to={to} sel={data[:10]} reason={_reason(frm, to, data)}")
    return h


def call(to, data):
    return rpc("eth_call", [{"to": to, "data": data}, "latest"])


SIG_CACHE = {}


def sig(s):
    if s not in SIG_CACHE:
        SIG_CACHE[s] = subprocess.run(["cast", "sig", s], capture_output=True, text=True).stdout.strip()
    return SIG_CACHE[s]


def _w(x):
    return x.rjust(64, "0")


def enc(types, values):
    """최소 ABI 인코더 — address·uint·bytes32·bool(정적) + string(동적)."""
    head, tail = [], []
    n_head = 32 * len(types)
    for t, v in zip(types, values):
        if t == "string":
            b = v.encode()
            data = _w(hex(len(b))[2:]) + (b.hex() + "0" * ((64 - len(b.hex()) % 64) % 64) if b else "")
            head.append(None)
            tail.append(data)
        elif t == "address":
            head.append(_w(v[2:].lower()))
        elif t == "bytes32":
            head.append(v[2:].lower().rjust(64, "0"))
        elif t == "bool":
            head.append(_w("1" if v else "0"))
        else:
            head.append(_w(hex(int(v))[2:]))
    out, off, ti = "", n_head, 0
    dyn = [d for d in tail]
    for h in head:
        if h is None:
            out += _w(hex(off)[2:])
            off += len(dyn[ti]) // 2
            ti += 1
        else:
            out += h
    return out + "".join(dyn)


def fn(signature, *values):
    types = signature[signature.index("(") + 1:-1].split(",") if signature.endswith("()") is False else []
    types = [t for t in types if t]
    return sig(signature) + enc(types, values)


def claim_hash(q, i, who, ans):
    return "0x" + hashlib.sha256(f"exp30:{q}:{i}:{who}:{ans}".encode()).hexdigest()


class Rng:
    """결정론 LCG — numpy 없이 재현성 확보."""
    def __init__(self, seed):
        self.s = seed & 0xFFFFFFFFFFFFFFFF

    def u(self):
        self.s = (6364136223846793005 * self.s + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return (self.s >> 11) / float(1 << 53)

    def bit(self):
        return 1 if self.u() < 0.5 else 0


def deploy(spec, args):
    """spec = 'File.sol:Contract' (Erc8004Registries.sol 은 두 컨트랙트를 담는다)."""
    cmd = ["forge", "create", f"src/{spec}", "--rpc-url", RPC,
           "--private-key", KEY0, "--broadcast"]
    if args:
        cmd += ["--constructor-args"] + [str(a) for a in args]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(CONTRACTS))
    for line in r.stdout.splitlines():
        if "Deployed to:" in line:
            return line.split()[-1]
    raise RuntimeError(r.stdout + r.stderr)


def run_q(q, log):
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
        deployer, hallu, calib, challenger = accts[0], accts[1], accts[2], accts[3]
        judges = accts[4:7]
        stranger = accts[7]

        token = deploy("LabToken.sol:LabToken", [])
        id_reg = deploy("Erc8004Registries.sol:IdentityRegistry", [])
        val_reg = deploy("Erc8004Registries.sol:ValidationRegistry", [])
        nonce = int(rpc("eth_getTransactionCount", [deployer, "latest"]), 16)
        predicted = subprocess.run(["cast", "compute-address", deployer, "--nonce", str(nonce + 1)],
                                   capture_output=True, text=True).stdout.strip().split()[-1]
        bv = deploy("BondedValidatorV3.sol:BondedValidatorV3", [token, id_reg, val_reg, predicted, MIN_BOND, UNBOND, W])
        panel = deploy("BondedJudgePanelV3.sol:BondedJudgePanelV3", [bv, PER_CASE_BOND, FEE, VOTE_T, DISP_T, 3])
        assert panel.lower() == predicted.lower(), f"panel prediction failed {panel} != {predicted}"
        log(f"  q={q}: LabToken={token} BV3={bv} Panel3={panel}")

        # 신원·담보
        ids = {}
        next_id = 1
        for who, a in (("hallu", hallu), ("calib", calib)):
            send(deployer, token, fn("mint(address,uint256)", a, MINT))
            send(a, id_reg, fn("register(string)", f"agent://{who}"))
            ids[who] = next_id; next_id += 1
            send(a, token, fn("approve(address,uint256)", bv, 2**256 - 1))
            send(a, bv, fn("stake(uint256,uint256)", ids[who], STAKE))
        for j in judges:
            send(deployer, token, fn("mint(address,uint256)", j, MINT))
            send(j, id_reg, fn("register(string)", "agent://judge"))
            jid = next_id; next_id += 1
            send(j, token, fn("approve(address,uint256)", panel, 2**256 - 1))
            send(j, panel, fn("registerJudge(uint256,uint256)", jid, ENTRY))
        send(deployer, token, fn("mint(address,uint256)", challenger, 1000 * 10**18))
        send(challenger, token, fn("approve(address,uint256)", panel, 2**256 - 1))

        s_agents = sig("agents(uint256)")

        def bonded(who):
            raw = call(bv, s_agents + _w(hex(ids[who])[2:]))[2:]
            return int(raw[0:64], 16) / 1e18

        def settled(h):
            return int(call(bv, fn("claimSettled(bytes32)", h))[2:], 16) == 1

        traj = {"hallucinator": [bonded("hallu")], "calibrated": [bonded("calib")]}
        counts = {"opened": 0, "lapsed": 0, "slashed_hallu": 0, "slashed_calib": 0,
                  "abstained": 0, "hallu_wrong": 0, "calib_answered": 0, "calib_wrong": 0}
        rng_label, rng_coin, rng_conf, rng_open, rng_err = Rng(5), Rng(7), Rng(11), Rng(13), Rng(17)

        for i in range(N_PROBLEMS):
            label = rng_label.bit()
            # 환각: 동전
            h_ans = rng_coin.bit()
            # 캘리브: 확신 c ≥ τ 이면 답(1% 오류), 아니면 기권
            c = rng_conf.u()
            if c >= TAU:
                c_ans = label if rng_err.u() >= CALIB_ERR else 1 - label
                c_abstain = False
                counts["calib_answered"] += 1
            else:
                c_ans, c_abstain = "abstain", True
                counts["abstained"] += 1
            open_it = rng_open.u() < q
            for who, addr, ans, abst in (("hallu", hallu, h_ans, False), ("calib", calib, c_ans, c_abstain)):
                h = claim_hash(q, i, who, ans)
                send(addr, bv, fn("requestValidation(uint256,string,bytes32)", ids[who], "", h))
                wrong = (not abst) and ans != label
                if who == "hallu" and wrong:
                    counts["hallu_wrong"] += 1
                if who == "calib" and wrong:
                    counts["calib_wrong"] += 1
                if open_it:
                    counts["opened"] += 1
                    send(challenger, panel, fn("openCase(bytes32)", h))
                    send(stranger, panel, fn("drawPanel(bytes32)", h))   # 다음 블록(automine)
                    for jx, j in enumerate(judges):
                        if abst:
                            score, tag = 50, "abstain"
                        elif wrong:
                            score, tag = 0, "wrong"
                        else:
                            score, tag = 100, "correct"
                        try:
                            send(j, panel, fn("voteVerdict(bytes32,uint8,string,bytes32)", h, score, tag, "0x" + "0" * 64))
                        except RuntimeError as e:
                            st = call(panel, fn("caseStatus(bytes32)", h))
                            raise RuntimeError(f"vote failed i={i} who={who} judge#{jx} score={score} tag={tag} "
                                               f"phase={int(st[2:66], 16)} initialVotes={int(st[130:194], 16)} settled={settled(h)} :: {e}")
                    if wrong:
                        counts["slashed_" + who] += 1
                else:
                    rpc("evm_increaseTime", [W + 1])
                    rpc("evm_mine", [])
                    send(stranger, bv, fn("settleUnchallenged(bytes32)", h))
                    counts["lapsed"] += 1
                assert settled(h), "claim not settled"
            traj["hallucinator"].append(bonded("hallu"))
            traj["calibrated"].append(bonded("calib"))
            if (i + 1) % 25 == 0:
                log(f"    {i+1}/{N_PROBLEMS} bonds: hallu={traj['hallucinator'][-1]:.0f} calib={traj['calibrated'][-1]:.0f}")

        return {"q": q, "final_bonds": {k: v[-1] for k, v in traj.items()},
                "slashes": {k: round(traj[k][0] - traj[k][-1]) for k in traj},
                "counts": counts, "contracts": {"LabToken": token, "BondedValidatorV3": bv,
                                                  "BondedJudgePanelV3": panel},
                "trajectories": traj}
    finally:
        anvil.terminate()
        anvil.wait()


def main():
    lines = []

    def log(s):
        print(s, flush=True)
        lines.append(s)

    log(f"Exp30 K3 — anvil 재시뮬, N={N_PROBLEMS}, stake={STAKE/1e18:.0f}, W={W}s, q ∈ {QS}")
    rows = []
    for q in QS:
        log(f"▶ q = {q}")
        rows.append(run_q(q, log))
    # 사전등록 킬기준 대조 (EXP30.md K3)
    r1 = next(r for r in rows if r["q"] == 1.0)
    hallu_q1 = r1["final_bonds"]["hallucinator"]
    calib_q1 = r1["final_bonds"]["calibrated"]
    passed = hallu_q1 <= 10 and calib_q1 >= 49
    killed = hallu_q1 > 25
    log("")
    log("| q | 환각 담보 (50→) | 캘리브 담보 (50→) | 개설 | 소멸 | 환각 오답 | 캘리브 답/기권/오답 |")
    log("|---|---|---|---|---|---|---|")
    for r in rows:
        c = r["counts"]
        log(f"| {r['q']} | {r['final_bonds']['hallucinator']:.0f} | {r['final_bonds']['calibrated']:.0f} | "
            f"{c['opened']} | {c['lapsed']} | {c['hallu_wrong']} | {c['calib_answered']}/{c['abstained']}/{c['calib_wrong']} |")
    log("")
    log(f"K3 (q=1): 환각 {hallu_q1:.0f} ≤ 10 ∧ 캘리브 {calib_q1:.0f} ≥ 49 → {'PASS' if passed else 'FAIL'}"
        f"{' · KILL(환각 > 25)' if killed else ''}")
    out = {"n_problems": N_PROBLEMS, "stake_initial": STAKE / 1e18, "W": W, "tau": TAU,
           "calib_err": CALIB_ERR, "rows": rows,
           "k3": {"hallu_q1": hallu_q1, "calib_q1": calib_q1, "pass": passed, "kill": killed},
           "log": lines}
    (HERE / "out").mkdir(exist_ok=True)
    (HERE / "out" / "sim.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    log("→ exp30/out/sim.json 기록")
    sys.exit(0 if not killed else 2)


if __name__ == "__main__":
    main()
