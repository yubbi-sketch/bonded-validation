# Exp12 — 패널 계층 기계 증명 (B 전환 2보)

`exp3/contracts/test/BondedJudgePanelV2Proofs.t.sol` — BondedJudgePanelV2의
정산 경제를 Halmos로 심볼릭 증명. 정련(refinement) 방식: 테스트 안의 참조
모델(_specFinal)이 사양이고, 구현 상태가 사양과 일치함을 SMT로 증명.

## 증명된 정리 (4/4)

| 정리 | 내용 | 경로/시간 |
|---|---|---|
| PA 만장일치 | ∀점수 — 아무도 몰수 없음, 수수료 3등분 | 5 / 0.6s |
| PB 과반 성립 | ∀점수 6개 심볼릭 — 소수파만 정확히 몰수, **상금 0**(무보상금 정리), 에이전트는 평결<50일 때만 | 1,127 / 256s |
| PC 과반 부재(2/2/1) | ∀상호상이 3값 — 무손실 환급, 아무도 몰수 안 됨 | 16 / 5.3s (loop 33 완전) |
| P4 타임아웃 | ∀0~2표 조합 — 판정자 담보 절대 불변, 에이전트는 "일치 2표 평결"만 적용 | 18 / 2.6s |

> 경로 수는 실행·Halmos 버전에 따라 다르다(위는 원 실행; REPRODUCTION.md 재현 감사에서 PB 1,086경로). 정리 통과 여부는 동일.

## 연구 기록 2건 (결과만큼 중요)

1. **전 uint8^8 공간 단일 정련은 SMT 미완**(58분 CPU 후 킬) → 평결 클래스
   3분할로 축소. 과반의 위치(e1~e3)는 WLOG 가정 — 기계 증명 범위 밖 명기.
   완전 정련은 미해결 문제로 등재.
2. **증명이 사양 버그를 잡았다**: P4 v1 사양 "타임아웃은 무조건 무손실"에
   반례(일치 2표 + 점수<50 → 에이전트 슬래시). 컨트랙트가 아니라 사양이
   틀렸다 — 2표 일치 정산은 설계상 정식 평결. 사양 수정 후 증명 통과.

## 검증 가능 설계 변경

`BondedJudgePanelV2._revealSeed`를 `virtual`로 — 증명 하네스가 결정론 시드로
오버라이드(Halmos는 CREATE 주소가 내부 스킴이고 blockhash 심볼릭이 폭발).
경제 로직은 무수정. Forge 스위트 59/59 유지.

## 재현

```bash
cd exp3/contracts && forge clean
../../.venv-halmos/bin/halmos --contract BondedJudgePanelV2Proofs --loop 33
```
