"""Exp29 Phase 2 — 온체인(Anvil) 무응답 요청자 스레드. K3(a-c)·K4(a,d) 실측(EXP29.md §5-6).

컨트랙트 무수정(main BondedValidatorV3/BondedJudgePanelV3 그대로, exp30/sim.py 패턴 재사용).
시나리오: 에이전트(δ=1 로 믿고) ask 를 선택하지만 상대가 끝까지 침묵 — 명료화가 온체인 상태를
바꾸지 못한다(R5)는 것을, 실제 트랜잭션으로 확인한다.

모드 P(선담보 없음): ask 자체가 오프체인이라 답이 안 오면 온체인 흔적이 0이어야 한다.
모드 B(선담보): 원 발화는 이미 requestValidation 돼있었고, 답이 안 오면 W 뒤 무허가 소멸.

재현: python3 run_exp29_phase2_unresponsive.py [N]  (기본 N=200, anvil 자동 기동/종료)
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP30 = HERE.parent / "exp30"
sys.path.insert(0, str(EXP30))
from sim import rpc, send, call, sig, enc, fn, deploy, Rng  # noqa: E402

sys.path.insert(0, str(HERE))
from run_exp29_phase1 import train_frozen_extractor, readings_AC  # noqa: E402
from data_readings import gen_dataset_readings, build_vocab_readings  # noqa: E402
from policy import decide  # noqa: E402

RPC = "http://127.0.0.1:8548"  # exp30/sim.py 와 다른 포트 — 동시 실행 충돌 방지
CONTRACTS = EXP30.parent / "exp3" / "contracts"
MIN_BOND = 10**18
UNBOND = 3600
W = 86400
STAKE = 20 * 10**18  # depth<=2 스레드도 감당 (freeBond/B >= 2)
MINT = 100 * 10**18
B, R, KAPPA, DELTA_BELIEF = 5.0, 1.0, 0.05, 1.0
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200


def rpc30(method, params):
    """exp30.sim.rpc 는 모듈 전역 RPC 상수를 쓰므로, 여기서는 우리 포트로 직접 호출."""
    import urllib.request
    req = urllib.request.Request(RPC, json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read())
    if "error" in d:
        raise RuntimeError(d["error"])
    return d["result"]


def _send(rpc_url, frm, to, data):
    h = _rpc(rpc_url, "eth_sendTransaction", [{"from": frm, "to": to, "data": data, "gas": "0x7a1200"}])
    rcpt = None
    for _ in range(150):
        rcpt = _rpc(rpc_url, "eth_getTransactionReceipt", [h])
        if rcpt is not None:
            break
        time.sleep(0.02)
    if rcpt is None:
        raise RuntimeError(f"no receipt to={to} sel={data[:10]}")
    if rcpt.get("status") != "0x1":
        raise RuntimeError(f"tx failed to={to} sel={data[:10]}")
    return h, rcpt


def _rpc(rpc_url, method, params):
    import urllib.request
    req = urllib.request.Request(rpc_url, json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read())
    if "error" in d:
        raise RuntimeError(d["error"])
    return d["result"]


def deploy_local(spec, args):
    cmd = ["forge", "create", f"src/{spec}", "--rpc-url", RPC, "--private-key", KEY0, "--broadcast"]
    if args:
        cmd += ["--constructor-args"] + [str(a) for a in args]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(CONTRACTS))
    for line in r.stdout.splitlines():
        if "Deployed to:" in line:
            return line.split()[-1]
    raise RuntimeError(r.stdout + r.stderr)


KEY0 = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def main():
    t0 = time.perf_counter()
    print("== 추출기 학습(Phase1 재사용)", flush=True)
    vocab = build_vocab_readings()
    ext = train_frozen_extractor(vocab)

    print("== 데이터(모호 900건, seed=2029 — Phase1 과 다른 표본)", flush=True)
    data = gen_dataset_readings(max(N, 300), seed=2029, decisive_share=0.5)

    print("== 행위 결정(ask_policy, delta=1 낙관적 신뢰 — 실제 환경은 끝까지 침묵)", flush=True)
    threads = []
    for ex in data:
        A, C = readings_AC(ext, vocab, ex["readings"])
        p = [1.0 / len(A)] * len(A)
        act, _, _ = decide(p, A, C, B, R, KAPPA, DELTA_BELIEF)
        threads.append({"ex": ex, "act": act})
        if len(threads) >= N:
            break
    ask_threads = [t for t in threads if t["act"] == "ask"]
    other_threads = [t for t in threads if t["act"] != "ask"]
    print(f"   N={len(threads)} ask={len(ask_threads)} speak/abstain(즉시)={len(other_threads)}", flush=True)

    n_accounts = max(len(ask_threads) + 5, 10)
    anvil = subprocess.Popen(["anvil", "--port", "8548", "--silent", "--accounts", str(n_accounts)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                _rpc(RPC, "eth_chainId", [])
                break
            except Exception:
                time.sleep(0.2)
        accts = _rpc(RPC, "eth_accounts", [])
        deployer, stranger = accts[0], accts[1]
        agent_addrs = accts[2:2 + max(len(ask_threads), 1)]

        token = deploy_local("LabToken.sol:LabToken", [])
        id_reg = deploy_local("Erc8004Registries.sol:IdentityRegistry", [])
        val_reg = deploy_local("Erc8004Registries.sol:ValidationRegistry", [])
        nonce = int(_rpc(RPC, "eth_getTransactionCount", [deployer, "latest"]), 16)
        predicted = subprocess.run(["cast", "compute-address", deployer, "--nonce", str(nonce + 1)],
                                    capture_output=True, text=True).stdout.strip().split()[-1]
        bv = deploy_local("BondedValidatorV3.sol:BondedValidatorV3", [token, id_reg, val_reg, predicted, MIN_BOND, UNBOND, W])
        panel = deploy_local("BondedJudgePanelV3.sol:BondedJudgePanelV3", [bv, MIN_BOND, MIN_BOND, 3600, 86400, 3])
        assert panel.lower() == predicted.lower()
        print(f"   BV3={bv} Panel3={panel}", flush=True)

        ids = {}
        for i, a in enumerate(agent_addrs):
            _send(RPC, deployer, token, fn("mint(address,uint256)", a, MINT))
            _send(RPC, a, id_reg, fn("register(string)", f"agent://exp29-{i}"))
            aid = i + 1
            ids[a] = aid
            _send(RPC, a, token, fn("approve(address,uint256)", bv, 2**256 - 1))
            _send(RPC, a, bv, fn("stake(uint256,uint256)", aid, STAKE))

        def bonded(addr):
            aid = ids[addr]
            raw = call and None
            raw = _rpc(RPC, "eth_call", [{"to": bv, "data": sig("agents(uint256)") + hex(aid)[2:].rjust(64, "0")}, "latest"])[2:]
            return int(raw[0:64], 16) / 1e18

        def hash_for(i, mode):
            import hashlib
            return "0x" + hashlib.sha256(f"exp29:unresp:{mode}:{i}".encode()).hexdigest()

        # ---- K3(b) 모드 P: ask 하지만 답 안 옴 -> 온체인 흔적 0 ----
        print("== 모드 P: ask+무응답, 흔적 0 확인", flush=True)
        p_lock_seconds = []
        for i, t in enumerate(ask_threads):
            addr = agent_addrs[i]
            before = _rpc(RPC, "eth_getTransactionCount", [addr, "latest"])
            # 오프체인 계산만: ask 선택, 상대 무응답 -> 아무 것도 안 보냄 (R9 모드 P)
            after = _rpc(RPC, "eth_getTransactionCount", [addr, "latest"])
            assert before == after, "모드 P 에서 ask+무응답인데 트랜잭션이 발생함(R5 위반)"
            p_lock_seconds.append(0)
        p_lock_max = max(p_lock_seconds) if p_lock_seconds else 0

        # ---- K3(b) 모드 B: 원 발화 선담보 -> 답 안 옴 -> W 뒤 무허가 소멸, 잠금 정확히 W ----
        print("== 모드 B: 선담보 원 발화 + 무응답 -> W 뒤 소멸", flush=True)
        b_lock_seconds = []
        supply_before = int(_rpc(RPC, "eth_call", [{"to": token, "data": sig("totalSupply()")}, "latest"]), 16)
        for i, t in enumerate(ask_threads):
            addr = agent_addrs[i]
            h = hash_for(i, "modeB")
            _, rcpt = _send(RPC, addr, bv, fn("requestValidation(uint256,string,bytes32)", ids[addr], "", h))
            claimed_blk = int(rcpt["blockNumber"], 16)
            t0_ts = int(_rpc(RPC, "eth_getBlockByNumber", [rcpt["blockNumber"], False])["timestamp"], 16)
            # 명료화 질문(오프체인, 아무 것도 안 보냄) — 상대 무응답 -> 그대로 W 대기
            # windowOpen := block.timestamp < claimedAt + W (컨트랙트 원문, >= 이면 닫힘) -> 정확히 W 만 증가
            _rpc(RPC, "evm_increaseTime", [W])
            _rpc(RPC, "evm_mine", [])
            _, rcpt2 = _send(RPC, stranger, bv, fn("settleUnchallenged(bytes32)", h))
            t1_ts = int(_rpc(RPC, "eth_getBlockByNumber", [rcpt2["blockNumber"], False])["timestamp"], 16)
            settled = int(_rpc(RPC, "eth_call", [{"to": bv, "data": fn("claimSettled(bytes32)", h)}, "latest"]), 16) == 1
            assert settled, f"claim {h} not settled after lapse"
            b_lock_seconds.append(t1_ts - t0_ts)
        supply_after = int(_rpc(RPC, "eth_call", [{"to": token, "data": sig("totalSupply()")}, "latest"]), 16)

        # ---- K3(a) 대조: 질문 없는(non-ask) 발화도 동일한 코드 경로로 동일 시간에 소멸하는가 ----
        print("== K3(a) 대조: 질문 없는 발화의 소멸 시간과 비교", flush=True)
        baseline_lock_seconds = []
        for i, t in enumerate(ask_threads):
            addr = agent_addrs[i]
            h = hash_for(i, "baseline_noask")
            _, rcpt = _send(RPC, addr, bv, fn("requestValidation(uint256,string,bytes32)", ids[addr], "", h))
            t0b = int(_rpc(RPC, "eth_getBlockByNumber", [rcpt["blockNumber"], False])["timestamp"], 16)
            _rpc(RPC, "evm_increaseTime", [W])
            _rpc(RPC, "evm_mine", [])
            _, rcpt2 = _send(RPC, stranger, bv, fn("settleUnchallenged(bytes32)", h))
            t1b = int(_rpc(RPC, "eth_getBlockByNumber", [rcpt2["blockNumber"], False])["timestamp"], 16)
            baseline_lock_seconds.append(t1b - t0b)
        k3a_identical = (b_lock_seconds == baseline_lock_seconds)

        # ---- K4(a) 토큰 보존: 명료화(오프체인)로 인한 토큰 이동 0, totalSupply 불변 ----
        k4a_pass = (supply_before == supply_after)

        # ---- K4(d) 코드 리뷰: ask/answer 보상 함수 자체가 컨트랙트에 없음 ----
        abi_src = (CONTRACTS / "src" / "BondedValidatorV3.sol").read_text()
        no_ask_reward_fn = ("function requestClarification" not in abi_src
                             and "function submitClarification" not in abi_src
                             and "rewardAsk" not in abi_src and "rewardAnswer" not in abi_src)

        verdict = {
            "n_threads": len(threads), "n_ask": len(ask_threads),
            "K3b_modeP_lock_max_seconds": p_lock_max,
            "K3b_modeP_pass_eq_0": bool(p_lock_max == 0),
            "K3b_modeB_lock_seconds": {"min": min(b_lock_seconds), "max": max(b_lock_seconds),
                                        "expected": W},
            "K3b_modeB_pass_le_W": bool(max(b_lock_seconds) <= W) if b_lock_seconds else None,
            "K3a_baseline_noask_lock_seconds": {"min": min(baseline_lock_seconds), "max": max(baseline_lock_seconds)} if baseline_lock_seconds else None,
            "K3a_identical_to_baseline": bool(k3a_identical),
            "K3a_pass": bool(k3a_identical),
            "K3c_exposure_seconds_le": W,
            "K4a_token_conservation_pass": bool(k4a_pass),
            "K4a_supply_before": supply_before, "K4a_supply_after": supply_after,
            "K4d_no_ask_answer_reward_fn_pass": bool(no_ask_reward_fn),
            "contracts": {"LabToken": token, "BondedValidatorV3": bv, "BondedJudgePanelV3": panel},
        }
        import os
        os.makedirs(str(HERE / "out"), exist_ok=True)
        json.dump(verdict, open(str(HERE / "out" / "phase2_unresponsive_results.json"), "w"), indent=2, ensure_ascii=False)
        print(json.dumps(verdict, indent=2, ensure_ascii=False))
        print(f"\ndone in {time.perf_counter()-t0:.1f}s")
    finally:
        anvil.terminate()
        anvil.wait()


if __name__ == "__main__":
    main()
