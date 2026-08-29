# Bonded Assertion — 담보 발화 규격 v0.1

> 2026-08-30 · Sejong Project / JEONGEUM · 3점 세트 ② (형 착공 도장 2026-08-30 07:04)
> 지위: 우리 제품이 실제로 쓰는 공개 포맷. 표준 제정 주장 아님(사용자 1 = 우리 자신부터).
> 참조 구현: `vending/certificate.py` (발급·서명·검증 실작동, 위조 거부 실측).

## 0. 한 줄
**주장(Assertion) + 담보(Bond) + 판정(Verdict)** — 서명된 레코드 3종을 해시로 엮은 것.
"AI 또는 검증자의 말에 책임을 묶는 최소 단위"이며, 체인은 선택 사항이다(chain-optional).

## 1. 왜 이 셋인가
- 주장만 있으면 말이고, 담보가 붙어야 책임이며, 판정이 있어야 담보가 작동한다.
- 판정은 **기계 재실행 가능한 것만** 허용 — 판정 불가 주장은 담보 대상이 아니라 **기권**(abstain) 대상.
- 정직 3라벨 고정: `counterexample` / `no-counterexample-in-bound` / `no-result`.
  `VERIFIED`라는 라벨은 존재하지 않는다 — 경계 안의 부재만 말할 수 있다.

## 2. 레코드 정의

### 2.1 Assertion (주장)
```json
{
  "type": "assertion/v0.1",
  "id": "sha256 of canonical body",
  "speaker": "서명자 식별자 (키 지문)",
  "property": "판정 가능한 성질 서술 (자연어 + 검사 id)",
  "check_id": "등록된 판정기 id (예: erc4626-dilution)",
  "bound": "판정이 유효한 경계 (예: S,T,a < 2^64)",
  "target": "대상 식별 (컨트랙트 주소/커밋 해시 등)",
  "asserted_at": "ISO8601",
  "sig": "ssh-ed25519 over canonical JSON"
}
```
- `check_id`가 등록된 판정기에 없으면 이 주장은 **담보 불가** → 시스템은 기권으로만 기록한다.

### 2.2 BondReceipt (담보 영수증)
```json
{
  "type": "bond/v0.1",
  "assertion_id": "위 주장의 id",
  "bond_kind": "fee-capped-refund | escrow-credit | onchain-stake",
  "amount": "액수와 단위",
  "clause": "발동 조건 문장 (사람이 읽는 계약 문구)",
  "misjudgment_definition": "오판의 기계 판정 가능한 정의 — 필수",
  "sig": "담보 제공자 서명"
}
```
- v0.1 기본형은 `fee-capped-refund`: **받은 요금 한도 내 환불.** 손실 규모 배상은 이 규격의 범위 밖(보험업 면허 영역 — 실측: Sherlock Euler $4.5M 지급 후 준비금 90% 소실).
- `misjudgment_definition`이 없는 담보는 무효 — 분쟁이 사람 해석으로 가는 순간 담보 경제가 죽는다.

### 2.3 VerdictRecord (판정)
```json
{
  "type": "verdict/v0.1",
  "assertion_id": "판정 대상",
  "label": "counterexample | no-counterexample-in-bound | no-result",
  "judge": "판정기 식별 (도구+버전, 또는 판정자 키)",
  "evidence_sha256": "판정 로그 해시",
  "reproduce": ["제3자가 그대로 돌릴 명령들 — 필수"],
  "judged_at": "ISO8601",
  "sig": "판정자 서명"
}
```
- `reproduce`가 비면 판정이 아니라 의견이다 — 필수 필드.
- `no-result`는 과금·담보 발동 대상이 아니다 (기권 무손실 원칙의 판정기 버전).

## 3. 의미론 (기계증명과의 연결)
- 소각·배상·무상금 규칙은 z3 증명 4종을 따른다: 태운 담보를 판정자 상금으로 주지 않는다(매수 유인 제거, 19/19) · 기권 무손실(14/14) · 가치 결속 조건(9/9) · 정지 권한 없음—권한 소멸로(38/38).
- 재실행 명령 문화: 본 연구의 모든 실험(exp1~27)과 동일 규율 — 증거 없는 판정 금지.

## 4. 체인 선택 (chain-optional)
- 양자 계약(우리↔고객)에서는 서명 레코드+계약서로 완결 — 체인 불필요.
- 다자·무계약 환경(서로 모르는 조직/AI 간, 공개 검증 필요)에서만 온체인 앵커/스테이크로 승격.
  참조: Sepolia BondedValidator v0.2.1 (`docs/deployments.md`) — 같은 의미론의 온체인 구현.

## 5. v0.1의 정직한 한계
- 판정기 목록이 현재 1개(erc4626-dilution)다. 목록 확장이 곧 제품 확장이다.
- 증명은 명세(property)까지만 보장한다 — 명세가 실제 위험과 어긋나면 증명이 참이어도 사고는 난다. 명세 선정 근거를 증명서에 남기는 것으로 완화하되, 소멸시키지 못한다.
- 사람 심판(비결정적 주장)은 범위 밖 — 심판 인센티브 연구(다음 실험) 이후 v0.2에서 다룬다.
