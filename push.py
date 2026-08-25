#!/usr/bin/env python3
"""연구 게이트 푸시 — 실험이 게이트를 통과하거나 킬 판정이 날 때만 오너 폰으로.

기존 자비스 텔레그램 인프라의 Keychain 항목(telegram-bot-token·telegram-chat-id)을
그대로 읽는다 — 새 키 0개. 공유 브리지 데몬은 건드리지 않는 독립 헬퍼.

사용:
    python3 push.py "Exp2 K1 통과 +17.3%p"                # 텍스트만
    python3 push.py "Exp2 결과" out/accuracy.png          # 텍스트 + 차트 사진
"""
import json
import mimetypes
import subprocess
import sys
import urllib.request
import uuid


def kc(account):
    r = subprocess.run(["security", "find-generic-password", "-a", account,
                        "-s", "jarvis-local", "-w"], capture_output=True, text=True)
    return r.stdout.strip()


def chat_ids():
    raw = kc("telegram-chat-id")
    return [x for x in raw.replace(",", " ").split() if x.strip().lstrip("-").isdigit()]


def send_text(token, cid, text):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": int(cid), "text": text[:3800]}).encode(),
        headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def send_photo(token, cid, text, photo_path):
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(photo_path)[0] or "image/png"
    with open(photo_path, "rb") as f:
        img = f.read()
    parts = b""
    for name, val in (("chat_id", cid), ("caption", text[:1000])):
        parts += (f"--{boundary}\r\nContent-Disposition: form-data; "
                  f'name="{name}"\r\n\r\n{val}\r\n').encode()
    parts += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; "
              f'filename="chart.png"\r\nContent-Type: {ctype}\r\n\r\n').encode()
    parts += img + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendPhoto", data=parts,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def push(text, photo=None):
    token = kc("telegram-bot-token")
    if not token:
        raise SystemExit("telegram-bot-token 없음(Keychain)")
    ids = chat_ids()
    if not ids:
        raise SystemExit("telegram-chat-id 없음(Keychain)")
    text = f"🔬 IIS 연구\n{text}"
    for cid in ids:
        if photo:
            send_photo(token, cid, text, photo)
        else:
            send_text(token, cid, text)
    print(f"pushed to {len(ids)} chat(s)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    push(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
