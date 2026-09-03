"""Exp29 K4(b) — legit(Q,A) 판정기 오프체인 구현 + 위조 서명 방어 실측 (EXP29.md R8·§3.4).

R8: legit(Q,A) 는 (i) parent 존재 (ii) 각 reading 이 등록 check_id 로 판정 가능
(iii) non-vacuous(라벨이 갈림) (iv) A 의 서명 = 요청자 키 ∧ in_reply_to 일치 (v) depth<=n_max.
실패 라벨 ∈ {vacuous, malformed, unsigned-premise} — 전부 무손실(담보·과금 발동 없음).

서명은 실제 ed25519 대신 HMAC-SHA256 대칭 서명으로 시뮬(대칭키=등록된 요청자 키 자체).
연구 목적은 서명 암호 강도가 아니라 "판정기 로직이 위조를 실제로 잡아내는가"이므로 충분하다.

재현: python3 legit_check.py [N]
"""
import hashlib
import hmac
import sys

sys.path.insert(0, ".")
from data_readings import gen_dataset_readings  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
N_MAX = 2


def sign(payload: str, key: str) -> str:
    return hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify(payload: str, sig: str, key: str) -> bool:
    return hmac.compare_digest(sign(payload, key), sig)


def make_question(ex, depth=1):
    body = f"{ex['cat']}:{ex['sents']}"
    qid = hashlib.sha256(body.encode()).hexdigest()
    return {
        "id": qid,
        "parent": hashlib.sha256(str(ex["sents"]).encode()).hexdigest(),
        "depth": depth,
        "readings": [{"i": i, "pinned": r, "check_id": "logic-closure-v1"} for i, r in enumerate(ex["readings"])],
    }


def make_answer(question, choice, responder_key, signer_key, in_reply_to=None):
    payload = f"{in_reply_to or question['id']}:{choice}"
    return {
        "in_reply_to": in_reply_to or question["id"],
        "choice": choice,
        "sig": sign(payload, signer_key),
        "_payload": payload,
    }


def legit(question, answer, ex, registered_requester_key, n_max=N_MAX):
    """R8 (i)-(v) 순서대로 재실행 검사. 반환: ('legit'|'vacuous'|'malformed'|'unsigned-premise', detail)."""
    # (i) parent 존재
    if not question.get("parent"):
        return "malformed", "no parent"
    # (v) depth <= n_max
    if question["depth"] > n_max:
        return "malformed", f"depth {question['depth']} > n_max {n_max}"
    # (ii) 각 reading 이 등록 check_id 로 판정 가능 + (iv) in_reply_to 일치·서명 검증
    if answer["in_reply_to"] != question["id"]:
        return "malformed", "in_reply_to mismatch"
    for r in question["readings"]:
        if r["check_id"] != "logic-closure-v1":
            return "malformed", f"unregistered check_id {r['check_id']}"
    if not verify(answer["_payload"], answer["sig"], registered_requester_key):
        return "unsigned-premise", "signature does not match registered requester key"
    # (iii) non-vacuous: 재실행 라벨이 갈리는가(기계 진실 = ex['decisive'])
    if not ex["decisive"]:
        return "vacuous", "labels agree across readings"
    return "legit", "ok"


def main():
    data = gen_dataset_readings(max(N, 300), seed=4229, decisive_share=0.7)  # decisive 위주 표본(legit 다수 확보)
    data = data[:N]

    real_key = "requester-real-key-0xabc"
    forger_key = "attacker-forged-key-0xdef"

    results = {"forged_accept": 0, "valid_reject": 0, "n": N, "labels": {}}
    for ex in data:
        q = make_question(ex, depth=1)
        theta = int(ex["theta"])

        # 정상 케이스: 진짜 요청자 키로 서명
        a_valid = make_answer(q, theta, real_key, real_key)
        label_valid, _ = legit(q, a_valid, ex, real_key)
        results["labels"].setdefault(("valid", label_valid), 0)
        results["labels"][("valid", label_valid)] += 1
        expected_valid = "legit" if ex["decisive"] else "vacuous"
        if label_valid != expected_valid:
            results["valid_reject"] += 1  # 정상인데 잘못 거부/오분류

        # 위조 케이스: 공격자 키로 서명(요청자 사칭)
        a_forged = make_answer(q, theta, real_key, forger_key)
        label_forged, _ = legit(q, a_forged, ex, real_key)
        results["labels"].setdefault(("forged", label_forged), 0)
        results["labels"][("forged", label_forged)] += 1
        if label_forged not in ("unsigned-premise",):
            results["forged_accept"] += 1  # 위조가 unsigned-premise 로 안 걸림 = 위험

        # in_reply_to 불일치(다른 질문에 답 붙이기 시도)
        a_wrongreply = make_answer(q, theta, real_key, real_key, in_reply_to="0x" + "1" * 64)
        label_wr, _ = legit(q, a_wrongreply, ex, real_key)
        results["labels"].setdefault(("wrong_reply_to", label_wr), 0)
        results["labels"][("wrong_reply_to", label_wr)] += 1

    print(f"N={N}")
    for k, v in sorted(results["labels"].items()):
        print(f"  {k}: {v}")
    print(f"\nK4(b) forged_accept (위조가 unsigned-premise 로 안 걸린 건수) = {results['forged_accept']}/{N}")
    print(f"K4(b) valid_reject (정상 답변이 잘못 분류된 건수) = {results['valid_reject']}/{N}")
    verdict = {
        "n": N,
        "forged_accept": results["forged_accept"],
        "valid_misclassified": results["valid_reject"],
        "K4b_pass": bool(results["forged_accept"] == 0),
    }
    import json
    import os
    os.makedirs("out", exist_ok=True)
    json.dump(verdict, open("out/k4b_legit_check_results.json", "w"), indent=2, ensure_ascii=False)
    print(json.dumps(verdict, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
