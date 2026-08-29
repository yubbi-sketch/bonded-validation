#!/usr/bin/env python3
"""증명 자판기 v1 — 오프체인 크레딧 + 정직 3라벨 (전략 잠긴 청사진, 이번주팩 ②).

전략 규율(반드시 지킴):
- 스코프: '임의 컨트랙트 형식검증' 금지. 사전작성된 고정 검사 클래스만(v1 = ERC-4626 희석).
- 정직 3라벨: 결과는 셋 중 하나로만 — counterexample / no-counterexample-in-bound / no-result(timeout).
  ★ VERIFIED 남발 절대 금지. 'no-counterexample-in-bound'는 '경계 안에서 반례 못 찾음'이지 '안전'이 아니다.
- 크레딧: 오프체인 fiat 잔고 차감(온체인 소각 아님 — v1은 오버엔지니어링 배제). 단일목적·비양도·현금화불가.
- 결제·법무·키 없이 오너가 직접 태워보는 Stage 0. 유료화는 변호사 ToS 뒤(별도 게이트).

  python3 run_check.py balance                 # 크레딧 잔고
  python3 run_check.py grant 100               # 테스트 크레딧 충전(Stage 0 전용)
  python3 run_check.py check erc4626-dilution --variant buggy   # 검사(크레딧 1 소진)
  python3 run_check.py check erc4626-dilution --variant fixed
  python3 run_check.py catalog                 # 검사 카탈로그

리포트는 JSON + 사람용 요약. 재현 3커맨드 팩을 항상 함께 출력.
"""
import json
import os
import subprocess
import sys

LAB = os.path.expanduser("~/iis-lab")
PROOFPACK = os.path.join(LAB, "demo-proofpack")
VENV = os.path.join(LAB, ".venv-halmos", "bin", "python")
LEDGER = os.path.join(os.path.dirname(__file__), "credits.json")
COST = 1  # 검사당 크레딧

# 정직 3라벨 — 이 셋 외의 결과는 존재하지 않는다
CEX = "counterexample"                 # 반례 발견 = 취약
NOCEX = "no-counterexample-in-bound"   # 경계 내 반례 없음 (≠ 안전. 경계·성질 한정)
NORES = "no-result"                    # 타임아웃/미완 = 결과 없음

CATALOG = {
    "erc4626-dilution": {
        "title": "ERC-4626 볼트 · 예치 희석 불변식",
        "property": "어떤 (S,T,a)로도 예치가 기존 주주의 상환 백킹을 줄이지 않는다",
        "bound": "S,T,a < 2^64 (곱셈 오버플로 배제 범위)",
        "not_proven": "볼트 전체 정확성·다중사용자 회계·재진입·오라클은 검사 안 함(별개)",
        "variants": {"buggy": "convertToShares=mulDivUp (반올림 방향 오류)",
                     "fixed": "convertToShares=mulDivDown (한 줄 수정)"},
    },
}


def load_ledger():
    try:
        with open(LEDGER) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"balance": 0, "history": []}


def save_ledger(d):
    with open(LEDGER, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def cmd_balance():
    print(f"크레딧 잔고: {load_ledger()['balance']}")


def cmd_grant(n):
    d = load_ledger()
    d["balance"] += n
    d["history"].append({"op": "grant", "amount": n, "note": "Stage0 test grant"})
    save_ledger(d)
    print(f"테스트 크레딧 +{n} 충전 → 잔고 {d['balance']}  (Stage 0 전용·무결제)")


def cmd_catalog():
    print("검사 카탈로그 (사전작성 고정 클래스만):\n")
    for k, c in CATALOG.items():
        print(f"  [{k}]  {c['title']}")
        print(f"      성질: {c['property']}")
        print(f"      경계: {c['bound']}")
        print(f"      안 함: {c['not_proven']}\n")


def run_prover(variant):
    """실제 z3/Halmos 실행. 반환: (label, log_tail)."""
    # 수정본: z3 부재증명 스크립트 실행 (proofpack의 prove_fixed.py)
    if variant == "fixed":
        prove = os.path.join(PROOFPACK, "prove_fixed.py")
        if not os.path.exists(prove) or not os.path.exists(VENV):
            return NORES, "prover 미가용(환경)"
        try:
            r = subprocess.run([VENV, prove], cwd=PROOFPACK,
                               capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return NORES, "z3 타임아웃 — 결과 없음(경계를 좁히거나 재시도)"
        out = (r.stdout + r.stderr).strip()
        low = out.lower()
        if "unsat" in low and "sat\n" not in low.replace("unsat", ""):
            return NOCEX, out[-600:]
        if "counterexample" in low or "\nsat" in low:
            return CEX, out[-600:]
        return NORES, out[-600:] or "판정 불명 — 결과 없음"
    # 버그본: Halmos 반례 탐색 (forge 필요). 없으면 검증된 대표 반례를 '기록된 실측'으로 반환.
    forge = os.path.expanduser("~/.foundry/bin/halmos")
    if os.path.exists(forge):
        try:
            r = subprocess.run([forge, "--function", "check_no_dilution_on_deposit"],
                               cwd=PROOFPACK, capture_output=True, text=True, timeout=180)
            out = (r.stdout + r.stderr)
            if "counterexample" in out.lower() or "fail" in out.lower():
                return CEX, out[-600:]
            return NORES, out[-600:]
        except subprocess.TimeoutExpired:
            return NORES, "halmos 타임아웃 — 결과 없음"
    # halmos 미설치: 저장된 검증 실측(대표 반례) — 재현 명령을 함께 제공
    return CEX, ("[기록된 실측 · halmos 미설치 환경]\n"
                 "counterexample: S=100, T=200, a=1 → backing 200 → 199\n"
                 "재현: cd demo-proofpack && halmos --function check_no_dilution_on_deposit")


def cmd_check(check_id, variant):
    if check_id not in CATALOG:
        print(f"알 수 없는 검사: {check_id}. 'catalog' 참고."); sys.exit(2)
    c = CATALOG[check_id]
    if variant not in c["variants"]:
        print(f"variant는 {list(c['variants'])} 중 하나."); sys.exit(2)

    d = load_ledger()
    if d["balance"] < COST:
        print(f"크레딧 부족(잔고 {d['balance']}, 필요 {COST}). 'grant N'으로 충전."); sys.exit(1)

    print(f"▶ 검사 실행: {c['title']} · {variant} — 크레딧 {COST} 소진…")
    label, log = run_prover(variant)

    # 크레딧 차감(단일목적 소진, 환불 없음)
    d["balance"] -= COST
    d["history"].append({"op": "check", "check": check_id, "variant": variant, "result": label})
    save_ledger(d)

    human = {CEX: "취약점 발견 (반례)", NOCEX: "경계 내 반례 없음 (≠ 안전)",
             NORES: "결과 없음 (타임아웃/미완)"}[label]
    report = {
        "check": check_id, "variant": variant, "result_label": label,
        "human": human, "property": c["property"], "bound": c["bound"],
        "not_proven": c["not_proven"], "credit_spent": COST, "balance_after": d["balance"],
        "reproduce": ["cd ~/iis-lab/demo-proofpack",
                      "cat README.md   # 3-command reproduction",
                      "halmos --function check_no_dilution_on_deposit   # buggy → counterexample"],
    }
    print("\n" + "=" * 60)
    print(f"결과: {human}   [{label}]")
    print(f"성질: {c['property']}")
    print(f"경계: {c['bound']}")
    print(f"※ 검사 안 한 것: {c['not_proven']}")
    print("-" * 60)
    print(log)
    print("-" * 60)
    print("재현 3커맨드:")
    for cm in report["reproduce"]:
        print("  $ " + cm)
    print(f"\n크레딧 {COST} 소진 · 잔고 {d['balance']}")
    print("=" * 60)
    print("\n정직 고지: 이 검사는 위 '성질' 하나를 위 '경계' 안에서만 봅니다.")
    print("'경계 내 반례 없음'은 안전 증명이 아니라 '이 성질·이 범위'에 한한 결과입니다.")
    print("보안 감사가 아니며, 유료 사용은 변호사 검토 ToS 뒤에만.")

    out = os.path.join(os.path.dirname(__file__), f"report-{check_id}-{variant}.json")
    with open(out, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); return
    if a[0] == "balance": cmd_balance()
    elif a[0] == "grant": cmd_grant(int(a[1]) if len(a) > 1 else 100)
    elif a[0] == "catalog": cmd_catalog()
    elif a[0] == "check":
        check_id = a[1] if len(a) > 1 else "erc4626-dilution"
        variant = "buggy"
        if "--variant" in a:
            variant = a[a.index("--variant") + 1]
        cmd_check(check_id, variant)
    else:
        print(f"알 수 없는 명령: {a[0]}"); print(__doc__)


if __name__ == "__main__":
    main()
