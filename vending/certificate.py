#!/usr/bin/env python3
"""담보 감사 증명서(Bonded Audit Certificate) 발급기 — 3점 세트 ①.

원칙 (형 도장 2026-08-30 착공 명령 + 전략 v2 실측 반영):
- 정직 3라벨만: counterexample / no-counterexample-in-bound / no-result. VERIFIED 남발 금지.
- 재실행 명령 동봉 — 고객이 우리 없이 전부 재현 가능해야 증명서다.
- 담보 = 받은 요금 한도 내 환불 (초과 배상 금지 — 무면허 보험 회피, Sherlock 자본 교훈).
- '오판'은 기계 판정 가능하게만 정의: 공표된 검사의 재실행 결과 불일치.
- 서명: Ed25519(ssh-keygen -Y), 페이로드는 정렬 JSON. 검증 명령도 증명서에 동봉.

  python3 certificate.py issue erc4626-dilution --variant fixed [--client NAME] [--fee USD]
  python3 certificate.py verify certs/BAC-xxxx.json
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

LAB = os.path.expanduser("~/iis-lab")
CERTS = os.path.join(LAB, "certs")
KEY = os.path.join(LAB, "keys", "cert-signing")
NAMESPACE = "jeongeum-bac"

sys.path.insert(0, os.path.join(LAB, "vending"))
from run_check import CATALOG, run_prover, CEX, NOCEX, NORES  # noqa: E402

HUMAN = {CEX: "반례 발견 — 성질 위반이 실재함",
         NOCEX: "경계 내 반례 없음 (≠ 전체 안전 — 아래 '검사하지 않은 것' 참조)",
         NORES: "결과 없음 (시간초과/미완 — 판정 불가, 과금 대상 아님)"}


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sign(payload: dict) -> str:
    """ssh-keygen -Y sign — 서명문(PEM 유사 블록)을 문자열로 반환."""
    import tempfile
    with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as f:
        f.write(canonical(payload)); path = f.name
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", KEY, "-n", NAMESPACE, path],
                   check=True, capture_output=True)
    sig = open(path + ".sig").read()
    os.unlink(path); os.unlink(path + ".sig")
    return sig


def cmd_issue(check_id: str, variant: str, client: str, fee: str):
    if check_id not in CATALOG:
        sys.exit(f"알 수 없는 검사: {check_id}")
    c = CATALOG[check_id]
    print(f"▶ 실제 검사 실행: {c['title']} · {variant} …")
    label, log_tail = run_prover(variant)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cert_id = "BAC-" + now.replace("-", "").replace(":", "")[:13] + "-" + hashlib.sha256(
        (check_id + variant + now).encode()).hexdigest()[:6].upper()

    payload = {
        "certificate": "Bonded Audit Certificate v0.1",
        "id": cert_id,
        "issued_at": now,
        "issuer": "Sejong Project / JEONGEUM (research outfit, not a licensed auditor)",
        "client": client,
        "assertion": {
            "check_id": check_id,
            "title": c["title"],
            "property": c["property"],
            "bound": c["bound"],
            "variant": variant,
            "variant_desc": c["variants"][variant],
        },
        "verdict": {"label": label, "human": HUMAN[label]},
        "not_checked": c["not_proven"],
        "reproduce": [
            "cd ~/iis-lab/vending && python3 run_check.py check %s --variant %s" % (check_id, variant),
            "cd ~/iis-lab/demo-proofpack && cat README.md  # 3-command reproduction pack",
        ],
        "bond": {
            "type": "fee-capped refund",
            "fee_usd": fee,
            "clause": "발급자가 오판했을 경우 수령한 요금 전액을 한도로 환불한다. 그 이상의 배상·보증·보험이 아니다.",
            "misjudgment_definition": "오판 = 본 증명서의 reproduce 명령을 제3자가 동일 환경 사양으로 재실행한 결과가 verdict.label과 불일치하는 것. 성질(property)·경계(bound) 밖의 사건은 오판이 아니다.",
        },
        "honesty": "이 증명서는 위 성질 하나를 위 경계 안에서만 판정한다. 보안 감사가 아니며, 컨트랙트 전체의 안전을 보증하지 않는다.",
        "evidence_log_sha256": hashlib.sha256(log_tail.encode()).hexdigest(),
    }
    signature = sign(payload)
    doc = {"payload": payload, "signature_ssh_ed25519": signature,
           "verify_cmd": "ssh-keygen -Y verify -f allowed_signers -I jeongeum -n %s -s cert.sig < payload.json" % NAMESPACE}

    os.makedirs(CERTS, exist_ok=True)
    jpath = os.path.join(CERTS, cert_id + ".json")
    with open(jpath, "w") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    md = f"""# 담보 감사 증명서 {cert_id}

**발급** {now} · Sejong Project / JEONGEUM
**수신** {client}

## 판정한 주장
- **성질**: {c['property']}
- **경계**: {c['bound']}
- **대상**: {c['title']} · `{variant}` ({c['variants'][variant]})

## 판정
**{HUMAN[label]}**  `[{label}]`

## 누구나 재현하는 법 (우리를 믿을 필요 없음)
```bash
{payload['reproduce'][0]}
```

## 담보 (이 증명서가 종이가 아닌 이유)
{payload['bond']['clause']}
- 요금: {fee}
- **오판의 정의(기계 판정 가능)**: {payload['bond']['misjudgment_definition']}

## 정직 고지
{payload['honesty']}
검사하지 않은 것: {c['not_proven']}

*서명: Ed25519 (`{jpath}` 의 signature — verify_cmd로 검증)*
"""
    mpath = os.path.join(CERTS, cert_id + ".md")
    open(mpath, "w").write(md)
    print(f"발급 완료: {mpath}\n          {jpath}")
    print(f"판정: {HUMAN[label]}")
    return cert_id


def cmd_verify(jpath: str):
    doc = json.load(open(jpath))
    import tempfile
    with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as f:
        f.write(canonical(doc["payload"])); p = f.name
    with tempfile.NamedTemporaryFile("w", suffix=".sig", delete=False) as f:
        f.write(doc["signature_ssh_ed25519"]); s = f.name
    with tempfile.NamedTemporaryFile("w", suffix=".allowed", delete=False) as f:
        f.write("jeongeum " + open(KEY + ".pub").read()); a = f.name
    r = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", a, "-I", "jeongeum",
                        "-n", NAMESPACE, "-s", s], stdin=open(p), capture_output=True, text=True)
    for x in (p, s, a):
        os.unlink(x)
    print("서명 검증:", "유효 ✓" if r.returncode == 0 else f"실패 ✗ ({r.stderr.strip()})")
    return r.returncode


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    if a[0] == "issue":
        check_id = a[1] if len(a) > 1 else "erc4626-dilution"
        variant = a[a.index("--variant") + 1] if "--variant" in a else "fixed"
        client = a[a.index("--client") + 1] if "--client" in a else "(견본 — 미판매)"
        fee = a[a.index("--fee") + 1] if "--fee" in a else "$0 (견본)"
        cmd_issue(check_id, variant, client, fee)
    elif a[0] == "verify":
        sys.exit(cmd_verify(a[1]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
