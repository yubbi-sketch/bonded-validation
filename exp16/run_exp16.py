"""Exp16 — 바인딩 회로 (EXP16.md 킬 기준): hashed/public 입력·fixed 파라미터·public 출력."""
import asyncio, inspect, json, os, subprocess, time

import ezkl

OUT = "out"
TIMES = {}

def tic(n): TIMES[n] = -time.perf_counter()
def toc(n):
    TIMES[n] += time.perf_counter(); print(f"  [{n}] {TIMES[n]:.1f}s", flush=True)

async def A(v):
    return await v if inspect.isawaitable(v) else v

async def main():
    model, settings, compiled = f"{OUT}/net.onnx", f"{OUT}/settings.json", f"{OUT}/net.ezkl"
    vk, pk, witness, proof = f"{OUT}/vk.key", f"{OUT}/pk.key", f"{OUT}/witness.json", f"{OUT}/proof.json"
    data = f"{OUT}/input.json"

    ra = ezkl.PyRunArgs()
    ra.input_visibility = "hashed/public"   # 입력 poseidon 해시 = 공개 인스턴스
    ra.param_visibility = "fixed"           # 모델 박제 — vk가 곧 모델 커밋
    ra.output_visibility = "public"         # 출력 = 공개 인스턴스

    tic("gen_settings"); assert await A(ezkl.gen_settings(model, settings, py_run_args=ra)); toc("gen_settings")
    tic("calibrate"); await A(ezkl.calibrate_settings(data, model, settings, "resources")); toc("calibrate")
    print("   logrows:", json.load(open(settings))["run_args"]["logrows"], flush=True)
    tic("compile"); assert await A(ezkl.compile_circuit(model, compiled, settings)); toc("compile")
    tic("get_srs"); await A(ezkl.get_srs(settings)); toc("get_srs")
    tic("setup"); assert await A(ezkl.setup(compiled, vk, pk)); toc("setup")
    tic("witness"); await A(ezkl.gen_witness(data, compiled, witness)); toc("witness")
    tic("prove"); await A(ezkl.prove(witness, compiled, pk, proof)); toc("prove")
    tic("verify_local"); ok = await A(ezkl.verify(proof, settings, vk)); toc("verify_local")
    assert ok

    pj = json.load(open(proof))
    inst = pj.get("instances")
    n_inst = sum(len(x) for x in inst) if inst else 0
    print(f"   공개 인스턴스 {n_inst}개 (입력해시+출력 62+α 기대)", flush=True)

    sol, abi = f"{OUT}/Halo2Verifier.sol", f"{OUT}/verifier.abi"
    tic("evm_verifier"); await A(ezkl.create_evm_verifier(vk, settings, sol, abi, None, False)); toc("evm_verifier")
    anvil = subprocess.Popen(["anvil","--port","8561","--silent"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    rpc = "http://127.0.0.1:8561"
    try:
        await A(ezkl.deploy_evm(f"{OUT}/addr.txt", rpc, sol, "verifier", 1,
                "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"))
        addr = open(f"{OUT}/addr.txt").read().strip()
        code_size = (len(subprocess.run(["cast","code",addr,"--rpc-url",rpc],
                     capture_output=True,text=True).stdout.strip())-2)//2
        ok_chain = await A(ezkl.verify_evm(addr, rpc, proof))
        await A(ezkl.encode_evm_calldata(proof, f"{OUT}/calldata.bytes"))
        cd_raw = open(f"{OUT}/calldata.bytes","rb").read()
        cd = "0x"+cd_raw.hex()
        est = subprocess.run(["cast","estimate",addr,"--rpc-url",rpc,cd],
                             capture_output=True,text=True).stdout.strip()

        # K2 변조 시험: calldata 마지막 32바이트(인스턴스 영역) 1워드 변조
        tam = bytearray(cd_raw); tam[-1] ^= 0x01
        cd_bad = "0x"+bytes(tam).hex()
        bad = subprocess.run(["cast","call",addr,"--rpc-url",rpc,cd_bad],
                             capture_output=True,text=True)
        tamper_rejected = (bad.returncode != 0) or ("revert" in (bad.stdout+bad.stderr).lower()) \
                          or (bad.stdout.strip() in ("0x","0x0000000000000000000000000000000000000000000000000000000000000000"))
        res = {"times_sec": {k: round(v,1) for k,v in TIMES.items()},
               "logrows": json.load(open(settings))["run_args"]["logrows"],
               "n_public_instances": n_inst,
               "deployed_code_bytes": code_size,
               "onchain_verify_ok": bool(ok_chain),
               "verify_gas": int(est) if est.isdigit() else est,
               "calldata_bytes": len(cd_raw),
               "K2_tamper_rejected": bool(tamper_rejected),
               "tamper_raw": (bad.stdout+bad.stderr).strip()[:120]}
        json.dump(res, open(f"{OUT}/results.json","w"), indent=2)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    finally:
        anvil.terminate()

asyncio.run(main())
