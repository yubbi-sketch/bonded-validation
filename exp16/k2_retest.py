"""K2 재시험 — 의미론적 변조: 증명은 그대로, 주장(인스턴스)만 바꿔서 검증 시도.
   변조 1: 입력 해시(인스턴스[0]) 교체 = '다른 문장에 대한 증명'이라고 주장
   변조 2: 출력 로짓 1개 교체 = '다른 평결'이라고 주장
   둘 다 로컬 verify와 온체인 검증에서 기각돼야 K2 통과."""
import asyncio, inspect, json, subprocess, time
import ezkl

async def A(v):
    return await v if inspect.isawaitable(v) else v

def tamper(src, dst, idx):
    p = json.load(open(src))
    inst = p["instances"][0]
    v = inst[idx]
    if isinstance(v, list):  # limb 배열 형태
        v[0] = (v[0] + 1) % 2**32 if isinstance(v[0], int) else v[0]
        inst[idx] = v
    elif isinstance(v, str):
        # hex 필드 원소 — 마지막 니블 뒤집기
        last = v[-1]
        inst[idx] = v[:-1] + ("0" if last != "0" else "1")
    else:
        inst[idx] = v + 1
    json.dump(p, open(dst, "w"))

async def main():
    OUT="out"; rpc="http://127.0.0.1:8562"
    results={}
    for name, idx in [("input_hash", 0), ("output_logit", 5)]:
        t=f"{OUT}/proof_tamper_{name}.json"
        tamper(f"{OUT}/proof.json", t, idx)
        try:
            ok = await A(ezkl.verify(t, f"{OUT}/settings.json", f"{OUT}/vk.key"))
        except Exception as e:
            ok = f"rejected({str(e)[:60]})"
        results[f"local_{name}"] = ok
    # 온체인
    anvil = subprocess.Popen(["anvil","--port","8562","--silent"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    try:
        await A(ezkl.deploy_evm(f"{OUT}/addr2.txt", rpc, f"{OUT}/Halo2Verifier.sol", "verifier", 1,
                "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"))
        addr=open(f"{OUT}/addr2.txt").read().strip()
        ok0 = await A(ezkl.verify_evm(addr, rpc, f"{OUT}/proof.json"))
        results["onchain_original"] = bool(ok0)
        for name in ["input_hash","output_logit"]:
            try:
                ok = await A(ezkl.verify_evm(addr, rpc, f"{OUT}/proof_tamper_{name}.json"))
                results[f"onchain_{name}"] = bool(ok)
            except Exception as e:
                results[f"onchain_{name}"] = f"rejected({str(e)[:80]})"
    finally:
        anvil.terminate()
    print(json.dumps(results, indent=2, ensure_ascii=False))
    r=json.load(open(f"{OUT}/results.json"))
    r["K2_semantic_tamper"]=results
    rej = lambda v: v is False or (isinstance(v,str) and v.startswith("rejected"))
    r["K2_tamper_rejected"]= all(rej(results[k]) for k in
        ["local_input_hash","local_output_logit","onchain_input_hash","onchain_output_logit"])
    json.dump(r, open(f"{OUT}/results.json","w"), indent=2)
    print("K2 =", r["K2_tamper_rejected"])

asyncio.run(main())
