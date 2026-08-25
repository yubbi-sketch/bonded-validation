# Bonded Validation — ERC-8004 위 담보·검증 프로토콜 설계서 v1

> 지능 불변 보안 연구 · 2026-08-26 · G1 킬 판정 후 피벗(오너 결정 A)
> 전신: Exp3 BondManager (~/iis-lab/exp3, Forge 8/8·Anvil 300건 실증)

## 1. 한 문장

**ERC-8004(Trustless Agents)가 일부러 비워둔 자리 — "담보·슬래싱은 상위 검증
프로토콜의 몫"(스펙 원문 명시) — 를 채우는 프로토콜.** AI 에이전트는 담보 없이
발화할 수 없고, 틀린 발화는 담보를 잃으며, 그 이력이 8004 평판·검증 레지스트리에
표준 형식으로 쌓인다.

## 2. 지형 (2026-08 실측)

- ERC-8004: Draft/Review. 신원(ERC-721)·평판·검증 3레지스트리. 메인넷·Base·Taiko 실험 진행.
- 검증 모델 담론: zkML 증명 / TEE / **스테이크드 재실행**(검증자가 담보) 3갈래.
- **빈자리**: 스펙이 명시적으로 위임 — "Incentives and slashing related to validation
  are managed by the specific validation protocol and are outside the scope."
- 지배적 구현: 미확인(사서석 지속 추적 임무). G1 교훈에 따라 이 갭 주장도
  **갱신 가능한 가설**로 취급 — Exp5 착수 전 재확인 게이트.

## 3. 차별점 — "검증자 담보"가 아니라 "발화자 담보"

세간의 스테이크드 재실행: 검증자가 자기 판정에 담보를 건다 (채점자 책임).
**우리: 에이전트 본인이 자기 발화에 담보를 건다 (발화자 책임).** 둘은 배타가 아니라
직교 — 우리 층이 깔리면 "말하는 순간 책임이 발생"하는 경제가 서고, 검증자 담보는
그 위의 채점 품질 층이다. 지붕 명제 그대로: 서명(8004 신원)·담보(본 프로토콜)·
증명(검증기, 향후 zkML).

추가 차별점 둘:
- **결정론적 검증 엔진**: Exp1 기호 검증기 — 판정 가능한 주장 범주(논리·규칙 준수)에서
  재실행 분쟁이 아예 없음(수학이라 만장일치).
- **기권 통합(Exp2 예정)**: "모름"은 담보 무손실 — 거짓 양성 제로 원칙의 경제 번역.
  억지 답변보다 기권이 항상 싸게 설계한다.

## 4. 아키텍처 매핑

| 우리 부품 | ERC-8004 접점 | 역할 |
|---|---|---|
| 에이전트 | Identity Registry `register()` → agentId | 발화 주체의 온체인 신원 |
| BondedValidator (신규, BondManager 계승) | Validation Registry의 validator 주소 | 담보 관리 + 판정 집행 |
| submitClaim | `validationRequest(validator, agentId, requestURI, requestHash)` 래핑 — **자유 담보 없으면 요청 자체 거부** | 담보 잡힌 발화 |
| 판정 | `validationResponse(requestHash, response 0~100, …)` 후크 → 임계 미달이면 슬래시 | 채점→과금 원자화 |
| 슬래시 이력 | Reputation Registry `giveFeedback()` (태그: slash) | 담보 이력의 평판화 |

### BondedValidator v0 (Exp5 프로토타입 범위)

```
상태: BondManager 전부 계승 (bonded/atRisk/unlockAt/slashedTotal, 지연창)
신규:
  requestValidation(agentId, requestURI, requestHash)
    — 담보 잠금 → registry.validationRequest 호출 (담보 없는 발화 원천 차단)
  onValidationResponse(requestHash, score)
    — score < THRESHOLD ⇒ 비례 슬래시 (0~100 점수 → 등급별 몰수율)
    — score ≥ THRESHOLD ⇒ 담보 해제 (+ 선택: 보상)
    — 기권 표시(태그 "abstain") ⇒ 무손실 해제 (Exp2 연동점)
  8004 레지스트리 주소는 생성자 주입 — Draft 인터페이스 변동 대비 어댑터 패턴
```

## 5. 정직성·리스크

1. **8004은 아직 Draft/Review** — 인터페이스가 바뀔 수 있다. 어댑터로 격리하고
   스펙 버전을 커밋에 고정 기록.
2. **판정 탈중앙화는 여전히 미해결** — v0의 판정자는 우리 검증기(단일)다. 로드맵:
   결정론 범주는 재실행 만장일치로, 비결정 범주는 zkML(P3)·검증자 담보층으로.
3. **갭 재확인 게이트**: Exp5 착수 전, 8004 위 발화자-담보 프로토콜 선행 사례
   유무를 1차 출처로 재검증 (G1 방식 그대로 — 확증 사냥 금지).

## 6. 로드맵 갱신

- **Exp2** 기권 메커니즘 (다음 실험 후보) — §3 기권 통합의 전제
- **Exp5** BondedValidator v0: 8004 3레지스트리 로컬 배포(공개 구현 또는 스펙 직접 구현)
  + BondManager 연동 + Exp3 시연 재실행(이번엔 8004 표준 이벤트로 기록)
- **Exp6** 평판 연동: 슬래시 이력 → giveFeedback, "담보 이력 = 신용 점수" 실증
- 그랜트 각도: EF가 8004 생태계 초기 프로토콜에 자금 지원 중인지 사서석 조사
