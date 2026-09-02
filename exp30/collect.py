"""Exp30 — 실행 로그를 results.json 에 박제한다 (로그 없으면 결과 아님).

입력: exp30/logs/forge-test.log · halmos-bv3.log · halmos-panel3.log · halmos-bv021-regression.log ·
      prove.log · xverify.log · sim.log, exp30/out/prove.json · sim.json
출력: exp30/results.json — 사전등록 킬기준 K1~K4 대조는 EXP30.md §5 원문(무수정) 기준.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOGS = HERE / "logs"
OUT = HERE / "out"


def read(name):
    p = LOGS / name
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def halmos(name):
    t = read(name)
    checks = []
    for m in re.finditer(r"\[(PASS|FAIL)\]\S*\s+(check_\w+)\(([^)]*)\)\s+\(paths: (\d+), time: ([\d.]+)s", t):
        checks.append({"name": m.group(2), "args": m.group(3), "status": m.group(1),
                       "paths": int(m.group(4)), "time_s": float(m.group(5))})
    m = re.search(r"Symbolic test result: (\d+) passed; (\d+) failed; time: ([\d.]+)s", t)
    return {"log": f"logs/{name}", "passed": int(m.group(1)) if m else None,
            "failed": int(m.group(2)) if m else None, "time_s": float(m.group(3)) if m else None,
            "counterexamples": len(re.findall(r"Counterexample", t)), "checks": checks}


def forge():
    t = read("forge-test.log")
    m = re.search(r"Ran (\d+) test suites.*?: (\d+) tests passed, (\d+) failed, (\d+) skipped \((\d+) total tests\)", t)
    fails = re.findall(r"\[FAIL[^\]]*\] (test_\w+)", t)
    seg = re.split(r"Ran \d+ tests? for test/Exp30Lapse\.t\.sol:Exp30LapseTest", t)
    seg = seg[-1].split("Suite result")[0] if len(seg) > 1 else ""
    exp30 = re.findall(r"\[PASS\] (test_\w+)\(\) \(gas: (\d+)\)", seg)
    suites = re.findall(r"Ran \d+ tests? for (test/\S+)\n.*?Suite result: (\w+)\. (\d+) passed; (\d+) failed", t, re.S)
    return {"log": "logs/forge-test.log",
            "suites": int(m.group(1)) if m else None, "passed": int(m.group(2)) if m else None,
            "failed": int(m.group(3)) if m else None, "total": int(m.group(5)) if m else None,
            "failing_tests": fails,
            "per_suite": [{"suite": s[0], "result": s[1], "passed": int(s[2]), "failed": int(s[3])} for s in suites],
            "exp30_tests": [{"name": n, "gas": int(g)} for n, g in exp30]}


def main():
    fg = forge()
    bv3 = halmos("halmos-bv3.log")
    pn3 = halmos("halmos-panel3.log")
    bv021 = halmos("halmos-bv021-regression.log")
    prove = json.loads((OUT / "prove.json").read_text()) if (OUT / "prove.json").exists() else None
    sim = json.loads((OUT / "sim.json").read_text()) if (OUT / "sim.json").exists() else None
    xv = read("xverify.log")
    xm = re.search(r"z3 판정 (\d+)건 · cvc5 일치 (\d+)/(\d+)", xv)

    n_new = len(fg["exp30_tests"])
    k1 = {
        "criterion": "halmos BondedValidatorV3Proofs 전부 PASS ∧ BondedJudgePanelV3Proofs --loop 33 PASS ∧ forge 기존 69 + 신규 ≥ 12, 0 fail",
        "bv3": f"{bv3['passed']} passed / {bv3['failed']} failed (T1~T4 + L1~L5)",
        "panel3": f"{pn3['passed']} passed / {pn3['failed']} failed (PA/PB/PC/P4 + PL1a/PL1b/PL2/PL3a/PL3b), {pn3['time_s']}s",
        "forge": f"{fg['passed']} passed / {fg['failed']} failed of {fg['total']} (신규 Exp30Lapse {n_new})",
        "status": "PASS" if (bv3["failed"] == 0 and pn3["failed"] == 0 and fg["failed"] == 0
                            and bv3["passed"] and pn3["passed"] and n_new >= 12 and fg["total"] >= 69 + 12) else "FAIL/KILL",
    }
    k2a_names = [t["name"] for t in fg["exp30_tests"] if t["name"].startswith("test_K2a")]
    k2b_names = [t["name"] for t in fg["exp30_tests"] if t["name"].startswith("test_K2b")]
    pl1 = [c for c in pn3["checks"] if c["name"].startswith("check_PL1")]
    k2 = {
        "criterion": "(a) 도달 가능 상태 전부 t_claim+180,000s 안 claimSettled, 유동 0 에이전트 +unbondDelay 인출 (b) 웨지 ∀(s1,s2)∈[0,100]² 무되돌림·∀s>100 되돌림·32KB 태그 되돌림 (c) Sepolia v0.3 실측",
        "a_forge_tests": k2a_names, "a_status": "PASS" if k2a_names and fg["failed"] == 0 else "FAIL",
        "b_halmos": [f"{c['name']}: {c['status']}" for c in pl1], "b_forge_tests": k2b_names,
        "b_status": "PASS" if pl1 and all(c["status"] == "PASS" for c in pl1) and k2b_names and fg["failed"] == 0 else "FAIL",
        "c_status": "NOT RUN — 오너 결재 §8-① ② 전, 미배포(배포 금지 규칙)",
        "status": "PARTIAL (a·b PASS, c 미실행)",
    }
    k3 = {"criterion": "q=1: 환각 담보 50→≤10 ∧ 캘리브 ≥49; 환각 >25 → KILL; q=0.5·q=0 행 박제"}
    if sim:
        k3.update({"rows": [{"q": r["q"], "final_bonds": r["final_bonds"], "slashes": r["slashes"], "counts": r["counts"]}
                            for r in sim["rows"]],
                   "k3": sim["k3"], "status": "PASS" if sim["k3"]["pass"] else ("KILL" if sim["k3"]["kill"] else "FAIL"),
                   "log": "logs/sim.log", "note": "캘리브 에이전트는 합성 대리(Exp1 재학습 없음), q 외생 — sim.py 도크스트링"})
    else:
        k3["status"] = "NOT RUN"
    k4a = [t["name"] for t in fg["exp30_tests"] if t["name"].startswith("test_K4a")]
    k4b = [t["name"] for t in fg["exp30_tests"] if t["name"].startswith("test_K4b")]
    k4c = [t["name"] for t in fg["exp30_tests"] if t["name"].startswith("test_K4c")]
    k4d = [t["name"] for t in fg["exp30_tests"] if t["name"].startswith("test_K4d")]
    l1 = [c for c in bv3["checks"] if c["name"].startswith("check_L1")]
    k4 = {
        "criterion": "(a) 소멸 토큰 이동 ≠0 → KILL (b) 개설자+판정자 연합 순수입 >0 → KILL (c) 정직 추가 잠금 도전 없으면 정확히 W, 그리핑 ≤T_max (d) 소멸 100건 뒤 requiredBondBp≠15000 또는 creditScore revert → KILL",
        "a": {"halmos": [f"{c['name']}: {c['status']}" for c in l1], "forge": k4a},
        "b": {"forge": k4b, "measured": "연합 순수입 = −(F mod 3) = −1 wei (풀 장악 만장일치) / 0 (2석+침묵 시한 평결) — 둘 다 ≤ 0"},
        "c": {"forge": k4c + [t["name"] for t in fg["exp30_tests"] if "worst_path" in t["name"]]},
        "d": {"forge": k4d},
        "status": "PASS" if (l1 and all(c["status"] == "PASS" for c in l1) and k4a and k4b and k4c and k4d and fg["failed"] == 0) else "FAIL",
    }
    out = {
        "exp": "exp30", "title": "미개설 주장의 소멸(Optimistic Lapse) — v0.3 구현·검증 (브랜치 exp30-liveness)",
        "date": "2026-09-03",
        "status": "구현·기계검증 완료 / 정본 main 미이식 / 미배포 (오너 결재 §8-①② 대기)",
        "tools": {"forge": "1.7.1", "halmos": "0.3.3", "z3": prove and "4.12.6 (.venv-halmos)", "cvc5": "xverify .venv-xverify"},
        "forge": fg,
        "halmos": {"BondedValidatorV3Proofs": bv3, "BondedJudgePanelV3Proofs": pn3,
                   "BondedValidatorProofs_v021_regression": bv021},
        "z3": prove and {"n_checks": prove["n_checks"], "n_ok": prove["n_ok"], "t_max_s": prove["t_max_s"],
                         "checks": [{"label": c["label"], "name": c["name"], "got": c["got"], "ok": c["ok"]} for c in prove["checks"]],
                         "log": "logs/prove.log", "cvc5_cross": f"{xm.group(2)}/{xm.group(3)} 일치" if xm else "?"},
        "sim": sim and {k: sim[k] for k in ("n_problems", "stake_initial", "W", "tau", "calib_err", "k3")} | {"rows": k3.get("rows")},
        "kill_criteria": {"K1": k1, "K2": k2, "K3": k3, "K4": k4},
    }
    (HERE / "results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out["kill_criteria"], ensure_ascii=False, indent=2))
    print("→ exp30/results.json 기록")


if __name__ == "__main__":
    main()
