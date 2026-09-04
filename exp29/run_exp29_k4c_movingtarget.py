"""Exp29 K4(c) — 이동표적 요청자: A 아래 정답인 에이전트가 슬래시되지 않는가 (온체인 Anvil).

공격 시나리오: 요청자가 답 A 로 명료화해줘서 에이전트가 A 전제로 옳게 말했는데(r'),
나중에 "사실 B 를 의도했다"며 판정을 뒤집으려 한다. 컨트랙트 무수정.

방어 구조(코드 확인, EXP29.md R4):
  requestHash' = keccak(canonical(r‖Q.id‖A.id‖pin(S,θ*)‖...)) — 전제(A)가 해시 자체에 박힘.
  requestValidation 은 require(!claimExists[requestHash], "dup claim") — 같은 해시 재개설 불가.
검증할 것: (1) 같은 해시로 재개설 시도 -> 전부 revert (2) '다른 해석'은 반드시 별개 해시 r''
  가 되고, r'' 을 아무리 돌려도 이미 정산된 r' 의 상태(정산 여부·담보 잔액)는 바뀌지 않는다.

재현: python3 run_exp29_k4c_movingtarget.py [N] (기본 40, anvil 자동 기동/종료)
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP30 = HERE.parent / "exp30"
sys.path.insert(0, str(EXP30))
from sim import sig, fn  # noqa: E402  (순수 함수 — RPC 전역 상태 없음)

RPC = "http://127.0.0.1:8549"
CONTRACTS = EXP30.parent / "exp3" / "contracts"
KEY0 = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
MIN_BOND = 10**18
UNBOND = 3600
W = 86400
STAKE = 20 * 10**18
MINT = 100 * 10**18
PER_CASE_BOND = 10 * 10**18  # exp30/sim.py 와 동일 비율
FEE = 10**18
JUDGE_ENTRY = 15 * 10**18
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40


def _rpc(method, params):
    import urllib.request
    req = urllib.request.Request(RPC, json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read())
    if "error" in d:
        raise RuntimeError(d["error"])
    return d["result"]


def _reason(data_hex_err):
    return data_hex_err


def _send(frm, to, data, expect_revert=False):
    try:
        h = _rpc("eth_sendTransaction", [{"from": frm, "to": to, "data": data, "gas": "0x7a1200"}])
    except RuntimeError as e:
        if expect_revert:
            return None, str(e)
        raise
    rcpt = None
    for _ in range(150):
        rcpt = _rpc("eth_getTransactionReceipt", [h])
        if rcpt is not None:
            break
        time.sleep(0.02)
    if rcpt is None:
        raise RuntimeError(f"no receipt to={to} sel={data[:10]}")
    if rcpt.get("status") != "0x1":
        if expect_revert:
            return h, "reverted (status 0x0)"
        raise RuntimeError(f"tx failed to={to} sel={data[:10]}")
    if expect_revert:
        raise AssertionError(f"expected revert but tx succeeded: to={to} sel={data[:10]}")
    return h, rcpt


def deploy_local(spec, args):
    cmd = ["forge", "create", f"src/{spec}", "--rpc-url", RPC, "--private-key", KEY0, "--broadcast"]
    if args:
        cmd += ["--constructor-args"] + [str(a) for a in args]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(CONTRACTS))
    for line in r.stdout.splitlines():
        if "Deployed to:" in line:
            return line.split()[-1]
    raise RuntimeError(r.stdout + r.stderr)


def h_A(i):
    return "0x" + hashlib.sha256(f"exp29:k4c:{i}:interpretation-A".encode()).hexdigest()


def h_B(i):
    return "0x" + hashlib.sha256(f"exp29:k4c:{i}:interpretation-B-movingtarget".encode()).hexdigest()


def main():
    t0 = time.perf_counter()
    n_accounts = N + 10
    anvil = subprocess.Popen(["anvil", "--port", "8549", "--silent", "--accounts", str(n_accounts)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                _rpc("eth_chainId", [])
                break
            except Exception:
                time.sleep(0.2)
        accts = _rpc("eth_accounts", [])
        deployer, stranger, challenger = accts[0], accts[1], accts[2]
        judges = accts[3:6]
        agent_addrs = accts[6:6 + N]

        token = deploy_local("LabToken.sol:LabToken", [])
        id_reg = deploy_local("Erc8004Registries.sol:IdentityRegistry", [])
        val_reg = deploy_local("Erc8004Registries.sol:ValidationRegistry", [])
        nonce = int(_rpc("eth_getTransactionCount", [deployer, "latest"]), 16)
        predicted = subprocess.run(["cast", "compute-address", deployer, "--nonce", str(nonce + 1)],
                                    capture_output=True, text=True).stdout.strip().split()[-1]
        bv = deploy_local("BondedValidatorV3.sol:BondedValidatorV3", [token, id_reg, val_reg, predicted, MIN_BOND, UNBOND, W])
        panel = deploy_local("BondedJudgePanelV3.sol:BondedJudgePanelV3", [bv, PER_CASE_BOND, FEE, 3600, 86400, 3])
        assert panel.lower() == predicted.lower()
        print(f"BV3={bv} Panel3={panel}  N={N}", flush=True)

        ids = {}
        for i, a in enumerate(agent_addrs):
            _send(deployer, token, fn("mint(address,uint256)", a, MINT))
            _send(a, id_reg, fn("register(string)", f"agent://k4c-{i}"))
            aid = i + 1
            ids[a] = aid
            _send(a, token, fn("approve(address,uint256)", bv, 2**256 - 1))
            _send(a, bv, fn("stake(uint256,uint256)", aid, STAKE))
        for j in judges:
            _send(deployer, token, fn("mint(address,uint256)", j, MINT))
            _send(j, id_reg, fn("register(string)", "agent://judge"))
            jid = len(agent_addrs) + judges.index(j) + 1
            _send(j, token, fn("approve(address,uint256)", panel, 2**256 - 1))
            _send(j, panel, fn("registerJudge(uint256,uint256)", jid, JUDGE_ENTRY))
        _send(deployer, token, fn("mint(address,uint256)", challenger, 1000 * 10**18))
        _send(challenger, token, fn("approve(address,uint256)", panel, 2**256 - 1))

        def bonded(addr):
            aid = ids[addr]
            raw = _rpc("eth_call", [{"to": bv, "data": sig("agents(uint256)") + hex(aid)[2:].rjust(64, "0")}, "latest"])[2:]
            return int(raw[0:64], 16)

        def settled(h):
            return int(_rpc("eth_call", [{"to": bv, "data": fn("claimSettled(bytes32)", h)}, "latest"]), 16) == 1

        dup_reopen_reverts = 0
        original_untouched = 0
        bond_before_after = []

        print("== r' 개설(전제 A) -> 정직 판정(정답) -> 이동표적 시도", flush=True)
        for i, addr in enumerate(agent_addrs):
            hA = h_A(i)
            hB = h_B(i)
            # 1) 원 발화 r' — 전제 A 아래 정답으로 개설
            _send(addr, bv, fn("requestValidation(uint256,string,bytes32)", ids[addr], "", hA))
            bond_pre = bonded(addr)

            # 2) 정직 판정: 전제 A 아래 실제로 옳으므로 판정단 전원 correct(100) 표결
            _send(challenger, panel, fn("openCase(bytes32)", hA))
            _send(stranger, panel, fn("drawPanel(bytes32)", hA))
            for j in judges:
                _send(j, panel, fn("voteVerdict(bytes32,uint8,string,bytes32)", hA, 100, "correct", "0x" + "0" * 64))
            assert settled(hA), f"r'(A) not settled i={i}"
            bond_after_honest = bonded(addr)

            # 3) 이동표적 공격 (a): 같은 해시로 재개설 시도(다른 전제라 주장) -> dup claim 으로 막혀야 함
            _, reason = _send(addr, bv, fn("requestValidation(uint256,string,bytes32)", ids[addr], "", hA), expect_revert=True)
            if reason is not None:
                dup_reopen_reverts += 1

            # 3) 이동표적 공격 (b): 진짜 별개 해시(B, 다른 해석 주장)를 별도로 열고 오답으로 정산해도
            #    이미 정산된 r'(A) 의 상태·잔액은 그대로여야 한다.
            _send(addr, bv, fn("requestValidation(uint256,string,bytes32)", ids[addr], "", hB))
            _send(challenger, panel, fn("openCase(bytes32)", hB))
            _send(stranger, panel, fn("drawPanel(bytes32)", hB))
            for j in judges:
                _send(j, panel, fn("voteVerdict(bytes32,uint8,string,bytes32)", hB, 0, "wrong", "0x" + "0" * 64))
            assert settled(hB), f"r''(B) not settled i={i}"

            bond_final = bonded(addr)
            # r'(A) 는 정직 정산 직후 그대로 유지돼야 -> B 정산으로 인한 추가 변동은 hB 몫(슬래시)만이어야
            still_settled_A = settled(hA)
            if still_settled_A and bond_after_honest - MIN_BOND == bond_final:
                # B 가 오답이라 딱 MIN_BOND 만큼만 추가로 깎였고, A 몫은 안 건드려짐
                original_untouched += 1
            bond_before_after.append({"pre": bond_pre, "after_A_honest": bond_after_honest, "final_after_B": bond_final})

        verdict = {
            "n": N,
            "K4c_dup_reopen_reverts": dup_reopen_reverts,
            "K4c_dup_reopen_pass": bool(dup_reopen_reverts == N),
            "K4c_original_untouched_by_moving_target": original_untouched,
            "K4c_original_untouched_pass": bool(original_untouched == N),
            "sample_bonds": bond_before_after[:5],
            "contracts": {"LabToken": token, "BondedValidatorV3": bv, "BondedJudgePanelV3": panel},
        }
        import os
        os.makedirs(str(HERE / "out"), exist_ok=True)
        json.dump(verdict, open(str(HERE / "out" / "k4c_movingtarget_results.json"), "w"), indent=2, ensure_ascii=False)
        print(json.dumps(verdict, indent=2, ensure_ascii=False))
        print(f"\ndone in {time.perf_counter()-t0:.1f}s")
    finally:
        anvil.terminate()
        anvil.wait()


if __name__ == "__main__":
    main()
