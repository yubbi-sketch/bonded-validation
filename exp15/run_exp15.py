"""Exp15 — EVM halo2 검증자 생성·Anvil 배포·가스 실측 (EXP15.md 킬 기준)."""
import asyncio, inspect, json, os, subprocess, time

E14 = "../exp14/out"
OUT = "out"
os.makedirs(OUT, exist_ok=True)

import ezkl

async def A(v):
    return await v if inspect.isawaitable(v) else v

async def main():
    sol, abi = f"{OUT}/Halo2Verifier.sol", f"{OUT}/verifier.abi"
    t0=time.perf_counter()
    await A(ezkl.create_evm_verifier(f"{E14}/vk.key", f"{E14}/settings.json", sol, abi, None, False))
    print(f"[create_evm_verifier] {time.perf_counter()-t0:.1f}s, sol={os.path.getsize(sol)} bytes", flush=True)

    # Anvil 기동 (코드 크기 한도는 일단 기본 — 초과 시 K3 절차)
    anvil = subprocess.Popen(["anvil","--port","8560","--silent"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    rpc = "http://127.0.0.1:8560"
    try:
        t0=time.perf_counter()
        try:
            await A(ezkl.deploy_evm(f"{OUT}/addr.txt", rpc, sol, "verifier", 1,
                    "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"))
            oversize=False
        except Exception as e:
            print("기본 한도 배포 실패:", str(e)[:200], flush=True)
            anvil.terminate(); time.sleep(1)
            anvil = subprocess.Popen(["anvil","--port","8560","--silent","--disable-code-size-limit"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
            await A(ezkl.deploy_evm(f"{OUT}/addr.txt", rpc, sol, "verifier", 1,
                    "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"))
            oversize=True
        addr=open(f"{OUT}/addr.txt").read().strip()
        print(f"[deploy] {time.perf_counter()-t0:.1f}s addr={addr} oversize={oversize}", flush=True)
        code_size = (len(subprocess.run(["cast","code",addr,"--rpc-url",rpc],
                     capture_output=True,text=True).stdout.strip())-2)//2

        t0=time.perf_counter()
        ok = await A(ezkl.verify_evm(addr, rpc, f"{E14}/proof.json"))
        print(f"[verify_evm] {time.perf_counter()-t0:.1f}s ok={ok}", flush=True)

        # 가스 실측: 같은 calldata를 eth_estimateGas로
        await A(ezkl.encode_evm_calldata(f"{E14}/proof.json", f"{OUT}/calldata.bytes"))
        cd = "0x"+open(f"{OUT}/calldata.bytes","rb").read().hex()
        est = subprocess.run(["cast","estimate",addr,"--rpc-url",rpc,cd],
                             capture_output=True,text=True).stdout.strip()
        res={"verifier_sol_bytes":os.path.getsize(sol),
             "deployed_code_bytes":code_size,
             "eip170_limit":24576,
             "oversize_limit_disabled":oversize,
             "onchain_verify_ok":bool(ok),
             "verify_gas":int(est) if est.isdigit() else est,
             "calldata_bytes":len(cd)//2-1}
        json.dump(res,open(f"{OUT}/results.json","w"),indent=2)
        print(json.dumps(res,indent=2))
    finally:
        anvil.terminate()

asyncio.run(main())
