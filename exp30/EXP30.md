# Exp30 — 미개설 주장의 소멸(Optimistic Lapse): 활성(liveness) 공백 폐쇄

> 지능 불변 보안 연구 · 2026-09-03 · 오너 결재 "Exp30부터 시작해"(2026-09-03)에서 착수
> 대조 작업서(2026-09-02)가 잡은 구멍 → 소스 정독·프로브(4/4) → 설계 3렌즈(최소변경·낙관적창·개설권한) → 적대검증(경제·메커니즘·EVM·Halmos) → **수석연구원 합성 판정(이 문서)**
> 지위: **A2A 심의 산출물·오너 결재 전.** 정본(`exp3/contracts/src`) 무수정·미커밋·미배포. 모든 코드는 스크래치 전용.
> 심의 도중 **두 번째 활성 공백**(v0.2.1 기존)이 발견됐다 — §1.2.

---

## 0. 첫 줄 (LOCK-0, 모든 산출물에 고정)

> 우리가 만드는 것은 "도전자 공급"이 아니라 **"영원히 잠기지 않는다는 상한"**이다.
> 아무도 도전하지 않으면 주장은 판정되지 않는다 — **검증된 것이 아니라 미검증인 채로 풀린다.**
> 그 대가로 억지력은 도전 확률 q 에 조건부가 된다. **우리는 q 를 만들지 않는다. q 의 가격표만 정직하게 붙인다.**
> 소멸(lapse)에는 권한자 0명·보상 0·토큰 이동 0 — Exp27 L0 의 직계다.

---

## 1. 배경 — 구멍 (전부 실측)

### 1.1 미개설 주장의 영구 잠금 (대조 작업서가 잡은 것)

| 위치 | 사실 |
|---|---|
| `BondedValidator.sol:70-81` `requestValidation` | `atRisk += minBondPerClaim` 로 잠그고 claimAgent/claimExists 만 기록. **주장 생성 시각·만료·취소 없음.** 해제는 오직 `submitVerdict`(judge 전용, :87). |
| `BondedValidator.sol:113-116` `withdraw` | `require(a.atRisk == 0, "claims pending")` — 미정산 주장 1건이면 unbondDelay 뒤에도 영구 차단(ERC 초안 불변식 3 '도망 금지'의 구현). 프로브: 1년 warp 후에도 차단. |
| `BondedJudgePanelV2.sol:164-175` `openCase` | Phase.None → Committed 의 유일한 진입점. 누구나 가능하나 `judgeFee`(Sepolia 1e18 IISLAB) transferFrom 이 관문. |
| `BondedJudgePanelV2.sol:365-390` `resolveTimeout` | Committed·Initial·ExpandedCommit·Expanded 네 단계만 시한 처리, `else revert("no open case")` — **Phase.None 에는 타임아웃 경로가 없다.** |
| `BondedJudgePanelV2.sol:397-419` `_finalize` | `bonded.submitVerdict` 의 유일한 호출처. 도달 경로 셋(_settleUnanimous·_settleExpanded·_refund) 모두 phase ≠ None 에서만. |
| `LabToken.sol:25-26` | mint 는 minter 전용 — Sepolia 에서 수수료 토큰 보유는 배포자 재량. '누구나 개설'이 사실상 배포자 종속. |
| `test/BondedJudgePanelV2Proofs.t.sol:102-105` | PA·PB·PC·P4 는 setUp 에서 openCase+drawPanel 을 마친 상태에서 출발 — **Phase.None 은 기존 기계증명 범위 밖**(공백을 증명이 못 본 이유). |

"영원히 잠긴다"의 정확한 뜻: 프로토콜 안에 미개설 주장을 움직이는 함수가 **0개**다. 절대 데드락은 아니다 — 누구든 judgeFee 를 내고 개설하면 풀 0명이어도 voteTimeout 뒤 무손실 환급된다(프로브 2·3). 진짜 공백은 ① 개설이 수수료 관문(1e18 = minBond 와 동액)에 걸리고 ② 제3자 개설 유인이 0이며 ③ 에이전트 유동 토큰이 0이면 자기구제 불가(프로브 4 — 담보는 BV 안에 있어 수수료로 못 씀) ④ 수수료 토큰 자체가 배포자 민팅 종속이라는 점이다. 또 자기개설은 스스로를 평결(슬래시 가능)에 노출시키는 '판정 신청'이지 '무손실 탈출'이 아니다.

### 1.2 심의 중 발견된 두 번째 공백 — 개설된 주장의 웨지 (v0.2.1 기존, 신규 발견)

**실측(2026-09-03, forge 1.7.1, 스크래치 `exp30-skeptic-evm`, 5/5 통과):**

- `voteVerdict` 는 `score` 를 uint8 그대로 받는다(범위 검사 없음, `BondedJudgePanelV2.sol:281-296`). 레지스트리 `validationResponse` 는 `require(response <= 100, "range")` (`Erc8004Registries.sol:66`).
- 초심 판정자 2인이 score 101 로 일치 투표 → 3번째는 같은 표를 던지면 그 tx 자체가 되돌려져 착지 불가 → 시한 경과 후 `resolveTimeout` → `_settleUnanimous` → `bonded.submitVerdict` → 레지스트리 'range' 되돌림. **영구.** 에이전트 전 담보('claims pending')·패널 3인 perCaseBond('cases pending') 모두 영구 잠금. 구제는 3번째 판정자가 **다른 표**를 던져 확대재판으로 가는 것뿐(특정 1인의 선의).
- `test_PREEXISTING_v021_same_wedge` — 정본 `BondedValidator + BondedJudgePanelV2` 에서 동일 재현.
- **Halmos 가 못 본 이유(실측):** `halmos --contract Exp30SkepticProofs` → `check_L1_timeout_after_two_votes_never_reverts(uint8,uint8)` **FAIL, 반례 s1=s2=0x80(128).** Halmos 는 require 되돌림 경로를 조용히 버리므로 P4 는 이 영역에서 공허(vacuous)했다.
- **태그 가스(측정, 증명 아님):** `_finalize` 가스는 같은 태그를 저장한 `voteVerdict` 보다 **항상 크다** — 64B: 123,292 vs 197,997 / 4KB: 2.98M vs 3.08M / 16KB: 11.68M vs 11.82M / 32KB: 23.31M vs 23.55M. 따라서 "투표는 블록에 들어가지만 정산은 블록 가스한도를 넘는" 태그 길이 구간이 존재한다(정확한 블록 한도는 **미확인**). 수리: 태그 길이 상한.

이 웨지는 Exp30 의 "T_max 안에 반드시 정산" 주장을 그대로 두면 거짓으로 만든다. **v0.3 에 반드시 함께 수리한다**(§4 R6). 발견 대장 등재 대상(`findings.py`, RT-#### — 이 문서는 대장을 쓰지 않는다).

---

## 2. 웹 갭 판정 (착수 게이트: GO — 축소)

| 시스템 | 확인한 사실 | 등급 |
|---|---|---|
| **UMA Optimistic Oracle v3** (`OptimisticOracleV3.sol`, raw GitHub) | `disputeAssertion`: `require(assertion.expirationTime > getCurrentTime(), "Assertion is expired")` / `settleAssertion`: `require(assertion.expirationTime <= getCurrentTime(), "Assertion not expired")` — **창 경계가 시간으로 상호배타.** 무분쟁 정산 시 asserter 에 bond 전액 반환. 분쟁 시 `burnedBondPercentage·bond` 는 Store, **잔여 `bond·2 − oracleFee` 는 승자**(= loser-pays 승자보상). `defaultLiveness` 최소값 검증 없음. | 인용됨 — 2026-09-03 본 판정에서 재확인 |
| **OP Stack fault proofs** (docs.optimism.io/stack/fault-proofs/challenger) | "Claims that are found to be incorrect have their bonds paid to the account that posted the left-most uncountered child claim" — **승자보상.** 지급 후 7일 DelayedWETH 지연(같은 수취인에 지급될 때마다 리셋). | 인용됨 — 2026-09-03 |
| **ERC-8004 draft** | `getValidationStatus` 가 `lastUpdate` 반환; canonical `validationRequest` 는 agentId owner/operator 만 호출 가능. | 인용됨(설계 에이전트 2026-09-03) — **본 판정에서 재확인 안 함** |
| **Kleros** | 스크래치에 2019 Short Paper 본문만 존재. 배심 보상·패자 부담 구조 대조 **안 함.** | **미실측** |
| **L2 강제포함 지연**(Exp27 C3) | 체인별 값 | **미실측** — W 확정의 선행 조건 |

**판정.** 실측한 낙관적 선례(UMA·OP)는 전부 **패자 담보를 승자에게 주어 도전자 공급을 산다.** 우리는 정리 3(승자 보상금 = 매수 보조금, `exp13/prove.py` T3)이 그 길을 막는다. 따라서 **비어 있는 곳 = "승자보상 없는 낙관적 창"** 이고, 그것은 우리의 갭이자 **우리의 약점**(도전자 공급을 못 산다)이다. 착수 범위를 **활성 상한 하나**로 축소한다: 도전자 공급은 목표가 아니라 가격표다(§7-1).

---

## 3. 세 설계와 반박 — 판정표

| | 최소변경 (Exp30-min) | 낙관적창 (Exp30-OW) | 개설권한 (Exp30-A, `exp30-openlens`) |
|---|---|---|---|
| 소멸 위치 | **패널**(`expireUnchallenged`), 시각은 레지스트리 `vals[h].lastUpdate` | **검증자**(`claimedAt` 저장, `challenge` 플래그) | **검증자**(`claimedAt`, `engage(h, opener)`) |
| 창 밖 판정 | openCase 만 차단 | `submitVerdict` 는 `challenged ∥ windowOpen` | `submitVerdict` 는 `engaged ∥ windowOpen` |
| 도전자 상환 R_c | **0** | reimbCap(0.5e18) **결과무관**, 누적 forfeitPool 조달 | **슬래시 시에만** 그 사건 몰수분에서 R_c ≤ minBond(제안 1e18), 개설자 ≠ 에이전트 지갑 |
| 개설자-판정자 분리 | 없음 | opener ∉ voters 면 상환 | 개설자는 그 사건 패널 추첨 제외 |
| 자체 실측 | Forge 30/30·Halmos L1~L6 6/6·PanelV2Proofs 4/4(257.5s, 로그 확인) | Forge 8/8·Halmos E1~E7 7/7·T1~T4 회귀 4/4 | Forge 8/8·Halmos T1~T4+T5~T9 |
| 경제 반박 | **BROKEN**(survives=false): 억지력 (1−q)·B_a 감소·문턱 1/q 배 하락(z3 R1·R2)·분산피해형 거짓말은 q=0(R3)·**판정 수요 소멸→풀 붕괴→q→0 자기강화**(설계서 미언급)·레지스트리 세탁·검열 예산 유한화·레지스트리 결합 회귀 | (경제 반박 미배정) | **BROKEN**: 장악 풀에서 정답 주장 그리핑 사건당 **+R_c 순수익**(B5 실측, v0.2.1 은 0)·시빌 판정자 수수료 환류로 실효 슬래시 (2/3)B_a(B1 실측)·2석+침묵 시한 평결 그리핑 +R_c(B3 실측)·**S6 UNSAT: [연합수입 결과무관 Δ=0] ∧ [도전자 EV ≥ 0] ∧ F>0 동시 불가**·S7 장악비용 회수 가능(N ≥ C/R_c) |
| 메커니즘 반박 | **SURVIVES**(정리 안 깨짐) + 흠 7: claimWindow 무검증(0/오버플로)·렌즈 언더플로 무료 도달·예약태그 미강제·Settled 이벤트 없음·'T_max+unbondDelay' 과대기술·개설불가 기간도 창 소모·레지스트리 선점 그리핑 | 5 공격 실측(본 판정 재실행 5/5): **A 풀<3 자기개설로 창 우회(W→3,600s)·도전자 봉쇄**, B reimbCap>fee 배포 가능·파밍, D reimburse 널리파이어 없음, E 자기개설 슬래시분 절반 회수, F 1표 환급경로도 상환→풀 드레인 | **웨지(§1.2)**: 개설된 주장이 score>100 로 영구 잠금 — 'W+93,600s 상한' 거짓 |
| 판정 | R_c=0 는 **채택**, 패널측·레지스트리 결합은 **기각** | 검증자측 구조는 **채택**, 결과무관 상환은 **기각** | 검증자측·engage 는 **채택**, R_c>0·패널 제외는 **기각** |

### 3.1 선택 이유 — 합성 **Exp30-L (Lapse)**

**(a) 소멸은 검증자(BondedValidator v0.3)에 둔다.** 이유: ① judge 가 immutable 이라 v0.3 은 어차피 BV 재배포다 — "BV 0줄 변경"(min)은 절약이 아니다(T1~T4 재증명 0.96s). ② 검증자측이면 judge 가 ZkVerdictGate 인 구성(Exp20)도 같은 백스톱을 얻는다(min 의 A9 미커버 해소). ③ 레지스트리 `lastUpdate` 결합(min)은 canonical 8004 의미론에서 **양쪽 경로 동시 되돌림 = 새 영구 잠금** 위험(경제 반박 #5·메커니즘 반박 S5). `claimedAt` 2줄이 정답.

**(b) 도전자 상환 R_c = 0.** 이것이 이번 판정의 핵심이다.
- **S6(z3, 스크래치 `exp30-skeptic/refute.py`): [Δ = 0] ∧ [w·R_c − F ≥ 0] ∧ F > 0 은 UNSAT.** 즉 F>0 인 한, 도전자에게 양의 기대이익을 주면 개설자+판정자 연합의 수입이 결과 의존(Δ = R_c)이 된다. 결과 의존 수입은 정리 3 의 매수 보조금 구조를 판정자에서 개설자로 옮긴 것이고(B6′: 비용 하한 m(1−p)B_j → m(1−p)B_j − p·R_c), 자유 신원(백서 §9-4) 아래 '개설자 ≠ 판정자' 분리는 강제 불가(B1·B3·B5 전부 시빌).
- **B5 실측: 장악 풀(ρ=1)에서 정답 주장 그리핑이 사건당 +R_c.** v0.2.1 은 장악해도 프로토콜 내 수익 0(비용만, B5 UNSAT). R_c>0 은 **장악을 자기조달형으로** 만든다(S7: 정직 주장 N ≥ C/R_c 건이면 장악비용 C 회수). Exp8 이 실측한 것은 5% 장악 비용(정직 담보 300배)뿐이며 96.8% 장악 비용은 미측정 — 그 미측정 영역에 양의 수익을 붙일 수 없다.
- **R_c ≤ F 이면 어차피 공급 0.** S1: 도전자 EV = w·R_c − F − gas < 0 (w=1 이어도). Exp26 F-HORN 그대로. 즉 R_c ∈ (0, F] 는 공급을 못 사면서 공격면만 연다. R_c > F 는 (W)·시빌 조건을 깬다(E2′·B1′·OW 반박 B). **따라서 R_c = 0 이 지배적**: 같은(0) 공급, 엄격히 작은 공격면, 정리 3·Exp26 (W)·Exp27(보상 0) 동시 정합.
- 경제 반박이 제안한 치료 (1)(상환 R>0)은 위 이유로 기각, (2)(온체인 requiredBond 강제)는 활성과 무관한 별도 실험으로 분리(§7-2, Exp31 후보), (3)(레지스트리 MUST-exclude)·(4)(W 하한 규칙)·(5)(claimedAt 을 BV 에) 는 **채택**.

**(c) 무패널 커밋은 도전이 아니다 — Committed 시한은 정산이 아니라 리셋.** OW 반박 A(본 판정 재실행 통과): 풀 < 3 이면 거짓말쟁이가 자기 주장을 즉시 개설 → 'pool too small' → 3,600s 뒤 `_refund` → 50/'disputed' 무손실 + 수수료 반환(비용 gas) → 남은 창 동안 **진짜 도전자 영구 봉쇄('claim settled')**. 명목 W=86,400 이 실효 3,600 으로 준다. 세 설계 모두 이 우회를 상속했다. 수리: Committed 에서 패널 미추첨인 채 voteTimeout 이 지나면 **사건을 None 으로 되돌리고(disengage) 수수료를 반환**한다 — 주장은 정산되지 않고 창은 계속 흐르며, 창이 닫혀 있으면 즉시 소멸 가능. 그리핑 연장은 여전히 유계(§4 R11: T_max 불변).

**(d) v0.2.1 기존 웨지 동시 수리.** `voteVerdict` 에 `score ≤ 100`·태그 길이 ≤ 1024B(Halmos 태그 bound 와 동일)·예약 태그 금지. 없으면 어떤 T_max 도 거짓이다.

**(e) 메커니즘 반박의 방어선 채택:** 생성자 W 범위 검사, 렌즈 언더플로 가드 + "unchallenged" 중립화, 문서의 'T_max + unbondDelay' 정정.

**기각한 것과 이유:** 개설자 패널 제외(Exp30-A) — R_c=0 이면 이득 동기가 없고 시빌로 우회되며 `_draw` 변경은 PB 재증명 비용만 늘린다(개설자 겸 판정자의 F/3 환류는 §7-12 한계로 등재). 패널측 소멸(min) — (a). 결과무관 상환(OW) — (b) + 반박 B·D·E·F. 검증자측 `expireClaim` 없는 "발화자 자기개설 허용"안 — 이미 현행에서 가능하고 유동 토큰 0 이면 불가라 구멍을 못 닫는다.

---

## 4. 최종 규칙 (구현 대상 — 오너 결재 §8-① 전까지 정본 이식 금지)

기호: B_a = minBondPerClaim(1e18), F = judgeFee(1e18), W = challengeWindow, t_claim = claimedAt[h].

**R1 주장 시각.** `requestValidation` 이 `claimedAt[h] = uint64(block.timestamp)` 를 추가 기록한다. 그 외 v0.2.1 과 동일(atRisk += B_a, 레지스트리 validationRequest 동일 tx).

**R2 개설 표식(engage).** `engage(h)` — **judge 만**, `claimExists ∧ ¬claimSettled ∧ ¬engaged ∧ block.timestamp < t_claim + W`. 효과 `engaged[h] = true`. 패널 `openCase` 가 수수료 transferFrom 직후 호출한다(1줄). 창 밖 openCase 는 여기서 되돌려진다("window closed").

**R3 표식 해제(disengage).** `disengage(h)` — **judge 만**, `engaged ∧ ¬claimSettled`. 효과 `engaged[h] = false`. 패널이 **Committed 시한(committedAt + voteTimeout) 에 패널 미추첨**일 때만 호출한다: 사건 `delete cases[h]`(Phase.None 복귀), 수수료 opener 반환, `disengage`. 주장은 정산되지 않는다. 창이 열려 있으면 재개설 가능, 닫혀 있으면 R4.

**R4 소멸(settleUnchallenged).** **누구든**(권한·토큰 불요, gas 만), `claimExists ∧ ¬claimSettled ∧ ¬engaged ∧ block.timestamp ≥ t_claim + W`. 효과: `claimSettled = true`, `atRisk −= B_a`, `bonded`·`slashedTotal` 불변, **토큰 이동 0**, 레지스트리 `validationResponse(h, 50, "", 0, "unchallenged")`, 이벤트 `ClaimSettled(…, 50, slashed=false, abstained=false)` + `ClaimLapsed(h)`. 50 = THRESHOLD 이므로 T2 에 의해 슬래시 불가.

**R5 창 밖 판정 봉쇄.** `submitVerdict` 는 기존 조건에 `engaged[h] ∨ block.timestamp < t_claim + W` 를 추가한다. 창 안에서는 judge 가 개설 없이도 직접 정산 가능(ZkVerdictGate.attest·Exp11 하네스 경로 보존). 창이 닫힌 뒤엔 engaged 주장만 판정 가능 → **모든 시각에 {engage, settleUnchallenged} 중 정확히 하나만 활성**(UMA 와 같은 `<`/`≥` 분할, 경계 경합 없음).

**R6 패널 v0.3 (BondedJudgePanelV3 = V2 파생, 정산 로직 무수정).**
- `openCase`: 수수료 예치 직후 `bonded.engage(h)`.
- `resolveTimeout` Committed 분기: `_refund` 대신 `_resetCommit`(수수료 반환·delete·`bonded.disengage`). Initial/ExpandedCommit/Expanded 분기는 v0.2.1 그대로(패널이 실제로 추첨된 뒤의 시한 환급은 '실제 분쟁' — 50/"disputed" 유지).
- `voteVerdict`: `require(score <= 100, "score range")` · `require(bytes(tag).length <= 1024, "tag too long")` · `require(tag ∉ {"unchallenged","disputed"}, "reserved tag")`.
- 수수료 규칙 불변: 투표자 ≥ 1 이면 judgeFee/nVoters 균등, 0 이면 개설자 반환. **상환 없음·보상 없음(R_c = 0).**

**R7 판정자 보존.** 소멸은 패널 상태(bondedAmt·atRisk·settledCount·slashedTotal·잔고)를 건드리지 않는다.

**R8 렌즈.** `ReputationLens.creditScore`: d = byTag("disputed") + byTag("unchallenged") 로 중립화(미검증 ≠ 검증, 규격 v0.1 §1 'VERIFIED 없음' 정합); `avg·count < 50·d` 이면 (0, answered) 반환(언더플로 가드). 신참 할증(answered < 10 → 15000bp) 우회 불가.

**R9 생성자 검사.** BV v0.3: `require(challengeWindow_ > 0 && challengeWindow_ <= 365 days)`. (uint64 덧셈 안전.)

**R10 파라미터(잠정, 사전등록).** W = 86,400s. 나머지 v0.2.1 동일(minBond 1e18·unbondDelay 3600·perCaseBond 10e18·judgeFee 1e18·voteTimeout 3600·disputeTimeout 86400·veteranThreshold 3). **W 하한 규칙:** W ≥ k·(대상 체인 강제포함 지연) + voteTimeout, k ≥ 2, L1/L2 별도 값 — 강제포함 지연 실측 전에는 W 를 확정하지 않는다(§8-②).

**R11 정산 시간 상한.** 무허가 호출 열만으로 어떤 주장이든 `t_claim + T_max` 안에 `claimSettled`, **T_max = W + 2·voteTimeout + disputeTimeout = 180,000s(50h)**. 경로: 미개설 → W 소멸 / 개설·풀<3 → ≤ W+voteTimeout 리셋 → 소멸 / 개설·추첨(최악: 리셋 직전 추첨) → +voteTimeout 초심 시한 → 확대 → +disputeTimeout. 인출은 `requestUnbond` 선무장 시 T_max 정각, 아니면 T_max + unbondDelay.

**R12 의미론.** "unchallenged" 는 검증이 아니다. ERC 초안 규범: 소비자는 태그 {"abstain","disputed","unchallenged"} 를 검증 건수에서 **MUST exclude**; 불변식 3 은 "정산 전 인출 불가 + 정산은 유계 시간 안에 반드시 도달 가능(창 안 도전 또는 창 경과 후 무손실 소멸)" 로 개정.

상태기계(주장 h): `None --engage(창 안)--> Engaged --disengage(무패널 시한)--> None` · `None --lapse(창 밖)--> Settled` · `Engaged --verdict--> Settled` · `None --verdict(창 안, judge 직접)--> Settled`.

---

## 5. 킬기준 K1~K4 (사전등록 — 실행 전 박제, 결과 보고 후 수정 금지)

**K1 형식 증명 완전 통과(기계).** 정본 이식 후:
(a) `halmos --contract BondedValidatorV3Proofs` — T1~T4 회귀(단언 무수정) + L1~L5 전부 PASS;
(b) `halmos --contract BondedJudgePanelV3Proofs --loop 33` — PA/PB/PC/P4 회귀 + PL1·PL2·PL3 PASS;
(c) `forge test` — 기존 69 + 신규 ≥ 12, **0 fail.**
하나라도 FAIL·counterexample·timeout → **KILL(재설계).** 파라미터 조정으로 회피 금지.
사전 실측(스크래치, 2026-09-03): 웨지 반례 존재(§1.2, 수리 전) — 수리 후 PL1 통과가 K1 의 첫 관문.

**K2 활성 상한(실측).**
(a) Forge: 도달 가능한 모든 상태(미개설·창 마지막 초 개설·풀 0·풀 2·리셋 후 재개설·초심 2표·확대 2/2/1·확대 시한)에서 무허가 호출만으로 `t_claim + 180,000s` 안 `claimSettled`; 유동 토큰 0 에이전트가 + unbondDelay 안 `withdraw`. 초과 경로 1개 → **KILL.**
(b) 웨지: `∀ (s1,s2) ∈ [0,100]²` 2표 후 시한 해소 무되돌림(Halmos PL1) ∧ `∀ s > 100` 투표 자체 되돌림 ∧ 32KB 태그 투표 되돌림. 반례 → **KILL.**
(c) Sepolia v0.3(오너 결재 후 배포): 실주장 1건 미개설 → W 경과 → 제3자 EOA `settleUnchallenged` 성공(tx 해시·ClaimLapsed); 실주장 1건 W−60s 개설·풀 0 → voteTimeout 후 리셋 → 소멸. 실패 → **KILL.**

**K3 억지력 보존 — 조건부, Exp3 방식 재시뮬(anvil, `exp30/sim.py`).** 환각 에이전트 vs 캘리브 기권 에이전트 각 100발화, 정직 판정자 3인, 도전자 1명이 **모든 주장을 개설(q = 1)**: 합격 = 환각 담보 50 → ≤ 10(Exp3 기록 50→8), 캘리브 ≥ 49. **환각 담보 > 25 잔존 → KILL.** 같은 표에 q = 0.5·q = 0 행을 **숨기지 않고 박제**(예상: q = 0 → 환각 손실 0 = 조건부 억지력의 실측 증거).

**K4 공격면 상한(실측·증명).**
(a) 소멸 1회의 토큰 이동 ≠ 0 → **KILL**(L1 + Forge).
(b) 개설자+판정자 연합의 프로토콜 내 순수입이 어떤 결과에서도 > 0 (정답 주장 그리핑·장악 슬래시·시한 평결 포함) → **KILL.** 합격 기준: 연합 순수입 ≤ 0 (수수료 환류 상한 F, R_c = 0). (B5·B3 형 Forge 재실측.)
(c) 정직 에이전트 추가 잠금: 도전 없으면 정확히 W; 그리핑 포함 ≤ T_max. 초과 경로 → **KILL.**
(d) 소멸 N ≤ 100건 뒤 `ReputationLens.requiredBondBp` ≠ 15000 또는 `creditScore` 되돌림 → **KILL.**

---

## 6. 증명할 불변식

**검증자 v0.3 (Halmos, `BondedValidatorV3Proofs`, 단일 주장·W 구체값·dt 심볼릭 uint64):**
- **L1 소멸 무손실·완전성**: ∀dt ≥ W, ¬engaged ∧ claimExists ∧ ¬claimSettled ⟹ `settleUnchallenged` 성공 ∧ bonded′ = bonded ∧ slashedTotal′ = slashedTotal ∧ atRisk − atRisk′ = B_a ∧ balance(BV)′ = balance(BV) ∧ claimSettled′ ∧ registry = (responded, 50, "unchallenged").
- **L2 조기 소멸 불가**: ∀dt < W ⟹ `settleUnchallenged` 되돌림 ∧ atRisk′ = atRisk.
- **L3 상호배타·완전성**: ∀dt: enabled(engage) XOR enabled(lapse) — (dt < W ⟹ engage 성공·lapse 실패) ∧ (dt ≥ W ⟹ engage 실패·lapse 성공·`submitVerdict` 실패).
- **L4 표식 봉쇄·해제**: engaged ⟹ ∀dt lapse 되돌림; disengage 후 ⟹ 미표식과 동일 거동(창 밖이면 lapse 성공).
- **L5 단일 정산(T3 확장)**: lapse → verdict 실패·lapse 재호출 실패·engage 실패; verdict → lapse 실패·engage 실패.
- **T1~T4 회귀**: 창 안·미표식 상태에서 judge 직접 정산의 기존 단언 4건 무수정 PASS.

**패널 v0.3 (Halmos, `BondedJudgePanelV3Proofs`, PanelHarness 결정론 시드·9인 풀·심볼릭 표):**
- **PL1 시한 활성**: ∀ s1,s2 ≤ 100: 초심 2표 후 `resolveTimeout` 이 되돌리지 않는다(`assert(ok)`, Halmos 의 되돌림 무시를 우회하는 저수준 call). ∀ s > 100: `voteVerdict` 되돌림.
- **PL2 커밋 시한 리셋**: Committed ∧ 무추첨 ∧ t ≥ committedAt + voteTimeout ⟹ phase′ = None ∧ opener 잔고 +F ∧ ¬engaged′ ∧ ¬claimSettled′.
- **PL3 예약 태그·판정자 보존**: `voteVerdict("unchallenged"|"disputed")` 되돌림; lapse 전후 ∀j ∈ pool: (bondedAmt, atRisk, settledCount, slashedTotal, balance) 불변.
- **PA/PB/PC/P4 회귀**(--loop 33, ≈4분).

**경제 (z3, `exp30/prove.py` — 스크래치 `refute.py`·`attack.py`·`prove.py` 의 유효 검사 승격, 자명식 J2 류 제거):**
- **Q1** q·ρ·B_a ≥ G ⟹ Π_lie ≤ 0 (UNSAT) / **Q1′** q < q* 반례 SAT(조건부 명시).
- **S6** [Δ=0] ∧ [w·R_c − F ≥ 0] ∧ F>0 UNSAT — R_c = 0 선택의 근거.
- **B5** R_c = 0 ⟹ 장악 사건당 수익 ≤ 0 (UNSAT) / R_c > 0 ⟹ +R_c (SAT 증인).
- **R1** ∀q<1: 억지 감소분 = (1−q)·B_a (UNSAT) — 한계로 박제.
- **W1** R_c = 0 ⟹ wash 공동이득 ≤ 0 (UNSAT). cvc5 교차(`xverify.py`) 등록.

**Forge 실측(증명 아님):** T_max(R11)·K3·K4 전항.

---

## 7. 정직하게 못 하는 것 (전량 등재)

1. **슬래싱 의미가 바뀐다.** '모든 주장은 판정된다' → '창 안에 도전받지 않으면 판정 없이 풀린다'. 억지력은 q ≥ q* = G/(ρ·B_a) 에 조건부이고, v0.2.1 대비 감소분은 정확히 (1−q)·B_a(z3 R1). 분산피해형 거짓말(피해자 1인당 이득 < F + gas)은 균형에서 q = 0 이라 실효 억지 0(R3) — **거짓말쟁이가 거짓말 유형을 고른다.** 이것이 마스터플랜 불변원칙상 A2A 심의 + 오너 결재 사유이며, 이 문서가 그 심의다.
2. **판정 수요.** v0.2.1 의 판정자 수입은 발화자가 자기 담보를 풀려고 낸 judgeFee 였다 — 사실상 **활성 버그가 강제한 100% 검증세.** 소멸이 도입되면 그 강제 수입은 사라지고, 판정 수요는 검증 가치를 실제로 지불하는 소비자·평판을 원하는 에이전트에서만 온다. 온체인 `requiredBond` 강제(경제 반박 치료 2)는 T2 의 '정확히 minBondPerClaim' 을 주장별 담보로 바꾸는 별도 실험(Exp31 후보) — Exp30 범위 밖. **풀 붕괴 → q → 0 자기강화**는 모델 밖이며 K3 는 이를 재현하지 않는다(q 를 외생으로 준다).
3. **규모붕괴(Exp24 정리24-L) 상속.** G ≫ B_a 이면 q* → 1. 소멸 창은 이를 치료하지 않는다.
4. **레지스트리 오염.** canonical `getSummary` 무필터 소비자는 소멸 N건을 '응답 50점 N건'으로 본다(비용: 주장당 B_a 를 W 동안 잠금, 수수료 0). 'disputed'(v0.2.1) 와 같은 급이며 R12 MUST-exclude 는 우리 통제 밖 소비자에겐 권고다. 대안(레지스트리 미기록)은 ERC 불변식 4 위반이라 택하지 않았다.
5. **웨지 수리의 한계.** score/태그 웨지는 닫았으나 `_finalize` 의 `token.transfer`(판정자·개설자 지급)가 되돌리는 토큰(훅·블랙리스트·수수료 토큰)이면 같은 급 웨지가 남는다. LabToken 은 무해; 실토큰은 미검증.
6. **태그 가스.** 정산 > 투표가 항상 성립함을 실측했고 1024B 상한으로 봉쇄하나, 블록 가스한도 정확값·32KB 이상 구간은 미측정.
7. **증명 범위.** 단일 주장·W 구체값·판정자 9명 결정론 시드·dt 만 심볼릭. 다중 주장 교차·재진입·canonical ERC-8004 어댑터·ZkVerdictGate 구성·`disengage` 후 재개설 반복은 Forge 실측만.
8. **웹 실측.** UMA·OP 는 본 판정에서 재확인; ERC-8004 draft 는 설계 에이전트 인용 그대로; Kleros·L2 강제포함 지연 미실측 → **W = 86,400 은 잠정**(R10 하한 규칙과 함께 사전등록, 확정은 §8-②).
9. **Sepolia v0.2.1 바이트코드 ↔ HEAD 소스 동일성 미대조**(기존 한계 승계). v0.2.1 라이브는 패치 불가 — 기존 미정산 주장은 구 컨트랙트에 남는다.
10. **선무장 인출.** `requestUnbond` 를 주장 전에 걸어두면 소멸 정각에 인출 가능 — 정본 기존 성질, 문서만 정정(R11).
11. **개설 불가 기간도 창을 소모한다**(패널 미배포·수수료 토큰 미유통). 컨트랙트는 '도전 가능했으나 안 함'과 '도전 자체 불가'를 구분 못 한다.
12. **개설자 겸 판정자의 수수료 환류** F/3(가중치 5 면 더 자주) — 그리핑 할인, 현행과 동일. R_c = 0 이라 이득은 못 만든다.
13. **판정자 풀 < 3 이 W 내내면** 소멸 = 거짓말 무손실. 판정자 활성은 이 실험이 다루지 않는다.
14. **2석 + 침묵 1석 시한 평결(B3)로 정답 주장을 슬래시하는 그리핑은 여전히 가능**(P4 '2표 일치 = 정식 평결' 규칙, 풀 3명 조건). R_c = 0 이라 무수익이지만 무비용도 아니다(F 환류 후 0). 풀 크기 하한은 별도 심의.
15. **K3 미실행·정본 미이식·미배포.** 스크래치 실측은 세 설계 각각의 프로토타입 위에서였고, 합성본 Exp30-L 자체의 Forge/Halmos 는 아직 없다(§9 1~5 가 만든다).

---

## 8. 오너 결정 필요 (되돌릴 수 없는 것만)

① **슬래싱 규칙 변경 결재** — "창 W 안에 도전받지 않은 주장은 판정 없이 무손실로 소멸한다(50/'unchallenged', 검증 아님)". 마스터플랜 불변원칙(슬래싱 규칙 변경 = A2A 심의 + 오너 결재). 이 문서가 심의 결과이며, 결재 전에는 정본 이식·배포 없음.

② **v0.3 Sepolia 재배포 승인 + 불변 파라미터 확정** — BV v0.3 + PanelV3 쌍(judge immutable 이라 신규 배포만 가능). `challengeWindow` = 86,400s(잠정; R10 하한 규칙·L2 지연 실측 후 최종값 제시) 외 v0.2.1 동일. 배포 후엔 바꿀 수 없다.

(구 v0.2.1 라이브의 미정산 주장 처리 — 방치 또는 배포자 토큰으로 자기개설 — 는 되돌릴 수 있는 운영 선택이라 결재 항목이 아니다.)

---

## 9. 구현 계획 (순서, 전부 스크래치 → 결재 후 정본)

1. `exp30/prove.py`(z3: Q1/Q1′·S6·B5·R1·W1, [THM]/[WIT] 라벨) + `exp30/results.json` 생성; `xverify.py` cvc5 교차 등록.
2. `exp3/contracts/src/BondedValidatorV3.sol` — 스크래치 `exp30-openlens/src/BondedValidatorV3.sol` 에서 `openerRefund`·`deadPool`·`OpenerRefunded` 제거, `disengage` 추가, 생성자 R9, 이벤트 `ClaimLapsed`.
3. `exp3/contracts/src/BondedJudgePanelV3.sol` — V2 파생: `openCase`→`engage`, Committed 시한→`_resetCommit`(+`disengage`), `voteVerdict` R6 세 검사. 정산 로직·추첨 무수정.
4. `exp3/contracts/src/ReputationLens.sol` — R8(언더플로 가드·unchallenged 중립). 기존 V2 소비자에도 적용.
5. 테스트: `test/Exp30Lapse.t.sol`(스크래치 Exp30LivenessV3·Exp30Skeptic(A/B3/B5 형)·Wedge·Boundary·T_max·렌즈 통합, Sepolia 파라미터) · `test/BondedValidatorV3Proofs.t.sol`(T1~T4 + L1~L5) · `test/BondedJudgePanelV3Proofs.t.sol`(PA~P4 + PL1~PL3). 실행 로그를 `exp30/results.json` 에 박제 — **로그 없으면 결과 아님.**
6. `exp30/sim.py` — K3 (anvil, q ∈ {1, 0.5, 0}).
7. 문서: `docs/erc-draft-bonded-validation.md` 불변식 3 개정·R12 MUST-exclude · `docs/whitepaper-draft.md` §3.2(백스톱 2개)·§3.3(W)·§5.1(L·PL)·§9(조건부 억지력·웨지) · `REPRODUCTION.md` halmos 명령 · 발견 대장(`findings.py`): score>100 웨지·태그 가스.
8. 오너 결재 §8-① → 정본 이식·커밋(스크래치 원본 경로 명기) → §8-② → Sepolia v0.3 배포 → `docs/deployments.md` → K2(c).
9. K3 실행 → 표 박제 → 킬기준 대조 보고(사전등록본 무수정).

---

## 10. 재현 (본 판정이 직접 돌린 것, 2026-09-03, forge 1.7.1 · halmos 0.3.3)

```bash
# 정본 회귀 (무수정 확인: git status 는 vending/* 3건만)
cd ~/iis-lab/exp3/contracts && forge test                 # 69 passed / 0 failed (9 suites)

S=/private/tmp/claude-501/-Users-yubbi-jarvis-ui/d668d6bd-3a4e-45d4-a99e-7638b71c1380/scratchpad
# 웨지(§1.2) — v0.2.1 기존 + V3 재현 + 범위검사 수리 + 경계 상보
cd $S/exp30-skeptic-evm && forge test --match-contract Exp30SkepticWedge      # 5 passed
forge test --match-contract Exp30SkepticTagGas -vvvv | grep 'Gas('             # finalize > vote, 4/4 크기
# Halmos 가 웨지를 못 본 이유
cd $S/exp30-skeptic-halmos && ~/iis-lab/.venv-halmos/bin/halmos --contract Exp30SkepticProofs
#   → [FAIL] check_L1_timeout_after_two_votes_never_reverts, 반례 s1=s2=0x80
# 낙관적창 반박 5건 + 낙관적창 자체 8건
cd $S/exp30-skeptic && forge test                                              # 13 passed
# 개설권한 자체 8건
cd $S/exp30-openlens && forge test                                             # 8 passed
# 최소변경 패널 재증명 로그(본 판정은 재실행 안 함, 로그만 확인)
tail -5 $S/exp30min/panelproofs.log                                            # 4 passed / 257.50s
```

측정 에이전트 보고(본 판정 미재실행): Halmos `BondedValidatorProofs` 4/4 (0.96s) · 스크래치 `Exp30GapProbe` 4/4 · 최소변경 `Exp30Proofs` 6/6 · 낙관적창 `Exp30OptWinProofs` 7/7.

**아크 요약:** Exp26(도전자 공급 이중모순) → Exp27(정지 권한은 만들 수 없음, 소멸만 남김) → **Exp30(영구 잠금은 소멸로 닫히지만 도전자 공급은 여전히 살 수 없음 — S6 로 기계 확정, 그래서 R_c = 0).** 이번에도 "동기가 된 것(억지력을 유지한 채 활성)"은 절반만 됐고, 그 절반의 경계를 정확히 그었다.

---

## 11. 구현·검증 결과 (2026-09-03 · 브랜치 `exp30-liveness` · 오너 결재 §8-① 전)

> 지위: **브랜치 위 구현 초안 + 기계검증 완료.** `main` 미수정·미배포. §5 킬기준 원문은 손대지 않았고 아래는 그 대조다.
> 실행 로그는 전부 `exp30/logs/` 에, 집계는 `exp30/results.json`(`exp30/collect.py` 가 로그에서 생성) — 로그 없으면 결과 아님.

### 11.1 만든 것

| 파일 | 내용 |
|---|---|
| `exp3/contracts/src/BondedValidatorV3.sol` | R1 `claimedAt` · R2 `engage`(judge) · R3 `disengage`(judge) · R4 `settleUnchallenged`(누구든, 50/"unchallenged", 토큰 이동 0) · R5 `submitVerdict` 에 `engaged ∨ windowOpen` · R9 생성자 `0 < W ≤ 365 days`. `_settle` 본문은 v0.2.1 `submitVerdict` 그대로. 스크래치 원본 `scratchpad/exp30-openlens/src/BondedValidatorV3.sol` 에서 `openerRefund`·`deadPool`·`OpenerRefunded` 제거(R_c = 0). |
| `exp3/contracts/src/BondedJudgePanelV3.sol` | V2 파생(정산·추첨 무수정, diff 로 확인): `openCase`→`bonded.engage`; Committed 시한→`_resetCommit`(`delete cases[h]`·수수료 opener 반환·`bonded.disengage`·`CommitReset` 이벤트); `voteVerdict` 에 `score ≤ 100`·`tag ≤ 1024B`·예약태그 금지. |
| `exp3/contracts/src/ReputationLens.sol` (수정) | R8 — `d = byTag("disputed") + byTag("unchallenged")` 중립화 + `avg·count < 50·d` 언더플로 가드. 기존 렌즈 테스트 5/5 유지. |
| `exp3/contracts/test/Exp30Lapse.t.sol` | Forge 21건 — K2(a) 8 상태·K2(b) 웨지·K4(a)(b)(c)(d)·R2/R3/R5/R8/R9·L5 구체·낙관적창 반박 A 재현. Sepolia 파라미터 + W = 86,400. |
| `exp3/contracts/test/BondedValidatorV3Proofs.t.sol` | Halmos — T1~T4 (Exp11 단언 무수정) + L1·L2·L3·L4·L5a·L5b. |
| `exp3/contracts/test/BondedJudgePanelV3Proofs.t.sol` | Halmos — PA/PB/PC/P4 (Exp12 본문 무수정, assume 도 없음) + PL1a·PL1b·PL2·PL3a·PL3b. |
| `exp30/prove.py` · `xverify.py`(exp30 등록) | z3 Q1/Q1′/Q1″·S1·S6/S6′/S6″·B5/B5′/B5″·R1/R1′/R1″·W1/W1′/W1″ — [THM] 11 · [WIT] 6. |
| `exp30/sim.py` | K3 anvil 재시뮬 q ∈ {1, 0.5, 0}. |
| `exp30/collect.py` → `exp30/results.json` | 로그 → 킬기준 대조표. |
| 문서 | `docs/erc-draft-bonded-validation.md`(불변식 3 개정·불변식 5 예약태그 MUST-exclude·lapse 인터페이스) · `docs/whitepaper-draft.md` §3.2(백스톱 2·웨지)·§3.3(W)·§5.1(L·PL)·§9-8(조건부 억지력) · `REPRODUCTION.md`(halmos 명령 + `forge clean` 주의). |

### 11.2 킬기준 대조 (사전등록본 §5 무수정)

| 기준 | 결과 | 근거(로그) |
|---|---|---|
| **K1** 형식 증명 완전 통과 | **PASS** | `halmos --contract BondedValidatorV3Proofs` **10/10** (1.77s) · `halmos --contract BondedJudgePanelV3Proofs --loop 33` **9/9** (239.07s, PB 1,052 paths) · `forge test` **90/90** (기존 69 + 신규 21, 0 fail) · v0.2.1 `BondedValidatorProofs` 회귀 4/4. 반례·timeout 0. `logs/halmos-bv3.log`·`halmos-panel3.log`·`forge-test.log` |
| **K2(a)** 활성 상한 | **PASS** | 미개설(정확히 W, 유동 0 에이전트 +3,600s 인출)·창 마지막 초 개설 풀0·풀2·리셋→재개설→리셋·초심 2표·확대 2/2/1·확대 커밋 시한·**최악 경로**(W−1 개설 → 커밋시한 1초 전 추첨 → 초심 분쟁 시한 → 확대 추첨 → 확대 시한) = **t_claim + 179,998s = T_max − 2** 에 정산, 인출 +3,600s. 초과 경로 0. |
| **K2(b)** 웨지 | **PASS** | Halmos PL1a ∀s: 투표 착지 ⟺ s ≤ 100 · PL1b ∀(s1,s2) ≤ 100 초심 2표 뒤 `resolveTimeout` 저수준 call `ok` (스크래치 반례 0x80 폐쇄) · Forge 101/255/32KB/1025B/"unchallenged"/"disputed" 전부 되돌림, 1024B·100 두 표 뒤 시한 정산. |
| **K2(c)** Sepolia 실측 | **미실행** | 오너 결재 §8-①② 전·배포 금지 규칙. |
| **K3** 억지력 조건부 | **PASS (q=1)** | 환각 50 → **2** (≤ 10) · 캘리브 50 → **50** (≥ 49). 박제: q=0.5 → 환각 **31**, q=0 → 환각 **50(손실 0)** = 조건부 억지력의 실측. `logs/sim.log`·`out/sim.json` |
| **K4(a)** 소멸 토큰 이동 | **PASS** | L1(Halmos ∀dt≥W: balance(BV) 불변) + Forge 7 잔고·totalSupply 불변. |
| **K4(b)** 연합 순수입 ≤ 0 | **PASS** | 풀 장악(ρ=1) 정답 그리핑: 순수입 **−1 wei** (= −(F mod 3), 수수료 3등분 잔여가 패널에 남음 — v0.2.1 성질) · 2석+침묵 시한 평결: **0**. 몰수분 1e18 은 BV 안에 남고 누구에게도 가지 않음. |
| **K4(c)** 정직 추가 잠금 | **PASS** | 도전 없음 + 선무장 인출 = **정확히 W**; 그리핑 최악 = T_max − 2. |
| **K4(d)** 소멸 100건 뒤 렌즈 | **PASS** | `requiredBondBp` = 15000 · `creditScore` = (0, 0) 무되돌림 · 언더플로 가드 실측(오답 1 + 소멸 3 → (0, 1)). |
| 경제 z3 | **17/17** | cvc5 교차 **17/17 일치** (`logs/prove.log`·`xverify.log`). |

K3 표(`sim.py`, N=100, stake 50, 정직 판정자 3, 도전자 1):

| q | 환각 담보 (50→) | 캘리브 담보 (50→) | 개설 | 소멸 | 환각 오답 | 캘리브 답/기권/오답 |
|---|---|---|---|---|---|---|
| 1.0 | 2 | 50 | 200 | 0 | 48 | 16/84/0 |
| 0.5 | 31 | 50 | 104 | 96 | 48 | 16/84/0 |
| 0.0 | 50 | 50 | 0 | 200 | 48 | 16/84/0 |

### 11.3 정직한 한계·이탈 (구현 단계에서 새로 생긴 것)

1. **Halmos 캐시 함정(재현성 마찰).** `forge test` 뒤에 halmos 를 돌리면 forge 캐시가 `--ast` 플래그 변화를 무시해 "No files changed" → 모든 아티팩트가 `KeyError: 'ast'` 로 건너뛰어진다. `forge clean` 후 halmos 실행이 필요 — `REPRODUCTION.md` 에 명기.
2. **PA/PB/PC/P4 의 s > 100 영역.** 본문·단언 무수정으로 회귀했으나, v0.3 은 그 표를 `voteVerdict` 에서 되돌리므로 그 영역은 Halmos 가 버리는 되돌림 경로다(v0.2.1 에서도 레지스트리 'range' 로 되돌려져 공허했음). 그 영역의 성질은 PL1a 가 명시적으로 증명한다.
3. **렌즈 내림 편향(기존).** 레지스트리 평균이 내림이라 `creditScore` 는 정확값보다 최대 (count−1)/answered 낮다(실측 91 vs 정확 92.3). v0.2.1 렌즈 성질, Exp30 범위 밖.
4. **수수료 잔여.** `judgeFee / nVoters` 의 나머지(F mod n)는 패널 컨트랙트에 영구 잔류(v0.2.1 성질). K4(b) "≤ 0" 은 성립하나 "= 0" 은 아니다.
5. **K3 의 캘리브 에이전트는 합성 대리.** τ = 0.85 를 균등 확신에 적용해 100 발화 중 16 건만 답하고(84 기권) 오류 0 — Exp1 추출기 재학습 없음. 환각 에이전트 오답 48/100 → q=1 에서 48 슬래시. q 는 외생.
6. **anvil 영수증 경합.** `eth_sendTransaction` 직후 `eth_getTransactionReceipt` 가 드물게 null(약 1/3,000 tx) — `send()` 가 최대 2s 폴링하도록 수리. 결과 불변.
7. **ZkVerdictGate 구성 미재검증.** 게이트는 `BondedValidator` 타입을 import 하며 v0.3 과 `submitVerdict` 시그니처가 같아 주소 캐스팅으로 동작하겠으나, 실제 결합 테스트는 안 했다. judge = EOA 직접 판정 경로(R5)는 Forge 로 실측.
8. **ReputationLens 는 제자리 수정.** v0.2.1 소비자에게도 적용되며 기존 5 테스트 통과 — 그러나 `disputed` 만 있던 배포본과 의미가 달라지므로(unchallenged 추가) 정본 이식 시 명기 필요.
9. **발견 대장 미등재.** score>100 웨지·태그 가스는 `findings.py`(jarvis-ui 저장소) 등재 대상이나 이 브랜치 범위 밖이라 쓰지 않았다 — 상위(팀장) 처리 대기.
10. **커밋 제외.** `exp3/contracts/cache/solidity-files-cache.json`(빌드 캐시, 추적 파일)과 `vending/*`(선행 작업의 미커밋 변경)은 이 브랜치 커밋에 넣지 않았다.
11. **미실행:** K2(c) Sepolia, W 최종값(L2 강제포함 지연 실측), 오너 결재 ①②.

### 11.4 재현

```bash
cd ~/iis-lab && git checkout exp30-liveness
cd exp3/contracts && forge test                                            # 90 passed
forge clean && ../../.venv-halmos/bin/halmos --contract BondedValidatorV3Proofs        # 10 passed
../../.venv-halmos/bin/halmos --contract BondedJudgePanelV3Proofs --loop 33            # 9 passed (~4 min)
cd ../.. && .venv-halmos/bin/python exp30/prove.py && .venv-xverify/bin/python xverify.py exp30
.venv-halmos/bin/python exp30/sim.py && .venv-halmos/bin/python exp30/collect.py
```

---

## 12. 결과 (서기 합성 — 심의·구현·독립검증·반박검토·웹갭 종합 · 2026-09-03)

> 지위: 브랜치 `exp30-liveness`(코드 d76872d · 기록 b7bfc43, base 83012fa = main) 위 구현 초안. **main 무수정 · Sepolia 미배포**(`git diff --name-only 83012fa..b7bfc43` 에 BondedValidator.sol·BondedJudgePanelV2.sol·ZkVerdictGate.sol·Erc8004Registries.sol 없음 — 서기 재확인). §5 사전등록 킬기준 원문은 이 절에서도 수정하지 않았다 — 아래는 결과만이다.
> 헤더 5행("정본 무수정·미커밋·미배포, 모든 코드는 스크래치 전용")과 §7-15("합성본의 Forge/Halmos 는 아직 없다")는 **심의 시점(§0~§10)의 서술**이다. §11·§12 시점의 정확한 지위는 "브랜치 커밋 있음 · main 무수정 · 미배포"다. 심의 기록 보존을 위해 원문은 그대로 두고 여기서 바로잡는다.

### 12.1 한 줄 (비개발자용)

**구멍:** 발화자가 담보를 걸고 말했는데 아무도 "판정해 달라"고 사건을 열지 않으면 그 담보가 **영원히** 안 풀리는 문제(소스에서 확인, §1.1). 심의 중에 두 번째 구멍(사건이 열려도 점수 101 두 표면 영구 정지, §1.2)도 찾았다.
**막은 법:** 도전 창 W(잠정 24시간)를 두고, 창 안에 아무도 사건을 열지 않으면 **누구든 손해 없이 담보를 풀 수 있게** 했다(권한자 0·보상 0·토큰 이동 0). 대신 "풀렸다" ≠ "검증됐다"임을 태그 `"unchallenged"` 로 분명히 남긴다. 두 번째 구멍은 점수·태그 범위 검사로 막았다.
**대가:** 억지력이 "누군가 창 안에 도전할 확률 q"에 조건부가 된다 — 숨기지 않고 표로 박제했다(q=1 환각 담보 50→2, q=0.5 → 31, q=0 → 50).
**기계 검증:** Halmos 10/10 + 9/9 + 회귀 4/4, Forge 90/90, z3 17/17(cvc5 교차 17/17) — 반례·실패 0. 독립 재실행 동일. 반박 검토 통과(survives).
**남은 것:** 형 결재 ①②(아래 12.7) 전이라 정본 이식·Sepolia 배포·K2(c) 미실행. 새로 발견된 정정 사항 — 문서 정밀도 6건, 렌즈 편향 1건(중), 판정자 소진 게임 1건(중하) — 을 결재 전에 반영할 것을 권고한다.

### 12.2 무엇이 구멍이었나 (전부 소스 실측)

- **구멍 1(대조 작업서 지적, 맞았음).** `BondedValidator.requestValidation` 이 `atRisk` 를 잠그고, 해제는 `submitVerdict`(judge 전용)뿐. judge = `BondedJudgePanelV2` 는 `openCase`(judgeFee 1e18 예치)로 열린 사건만 `_finalize` → `submitVerdict`. `resolveTimeout` 은 Phase.None 에 `revert("no open case")`. `withdraw` 는 `atRisk == 0` 요구 ⇒ 미개설 주장 1건이면 담보 전액 영구 잠금(1년 warp 후에도, 프로브 4/4).
- **구멍 2(심의 중 신규, v0.2.1 기존).** `voteVerdict` 가 score>100 을 받고 레지스트리가 `require(≤100,"range")` 로 되돌려, 초심 2인이 101 로 일치 투표하면 시한 정산이 영구 revert(Forge 5/5, Halmos 반례 s1=s2=0x80 — P4 는 revert 무시라 공허). 태그 길이 무제한도 '투표는 되고 정산은 블록 가스 초과' 구간 존재(측정, 블록 한도 정확값 미확인).
- **웹 갭(착수 전 실측).** UMA OOv3·Kleros Curate·Escrow·EigenLayer·Arbitrum BoLD/OP 5계열 전부 [담보 잠금 → 고정 창 → 창 만료 시 누구나 무허가 정산 → 침묵은 무손실 반환] 골격. **우리가 업계 기본값(세 번째 단계)을 빠뜨린 쪽**이며 해법 골격은 발명이 아니라 수입이다. 반면 '발화자 담보 + 무보상 판정 + 무손실 기권' 조합은 5계열 어디에도 없어 차별성은 유지 — 그 대가로 우리는 승자보상(정리 3 금지)으로 도전자 공급을 살 수 없다(약점, §2). ERC-8004 자체는 만료 조항이 없어 책임은 온전히 우리 층.

### 12.3 어떤 규칙으로 막았나 (§4 R1~R12 요약 · 구현 위치)

| 규칙 | 뜻(쉬운 말) | 구현 |
|---|---|---|
| R1 | 주장할 때 시각을 적는다 | `BondedValidatorV3.sol:100` `claimedAt` |
| R2 `engage` | 사건이 열리면 '개설됨' 표식 — judge 만, 창 안에서만(창 밖 개설은 여기서 거부) | `:112-119`; `BondedJudgePanelV3.openCase` 가 수수료 예치 직후 호출 |
| R3 `disengage` | 패널이 추첨되지 못한 채 시한이 지나면 표식 해제 + 사건 리셋 + 수수료 반환 — **정산이 아니라 되돌림**(창은 계속 흐름) | `:124-129`; PanelV3 `_resetCommit` |
| R4 `settleUnchallenged` | 창이 닫혔고 개설 표식이 없으면 **누구든** 무손실로 담보 해제(50/`"unchallenged"`, 토큰 이동 0) | `:144-151` |
| R5 | 창 밖 판정 봉쇄 → 매 시각 {engage, lapse} 중 정확히 하나만 가능 | `:137` `engaged ∨ windowOpen` |
| R6 | 두 번째 구멍 수리: score ≤ 100 · 태그 ≤ 1024B · 예약태그 금지 | PanelV3 `voteVerdict` 3 require |
| R7 / R8 | 소멸은 판정자 상태를 안 건드림 / 렌즈가 소멸을 중립 처리 + 언더플로 가드 | `ReputationLens.sol:35-45` |
| R9 / R10 / R11 | 생성자 0 < W ≤ 365d / W = 86,400s 잠정 / T_max = W + 2·voteTimeout + disputeTimeout = 180,000s | `:63` / §8-② / Forge |
| R12 | `"unchallenged"` 는 검증이 아니다 — 소비자 MUST exclude | `docs/erc-draft-bonded-validation.md` 불변식 3·5 |

**채택하지 않은 것과 이유:** 도전자 상환 R_c > 0 — z3 S6 UNSAT([연합수입 결과무관] ∧ [도전자 EV ≥ 0] ∧ F > 0 동시 불가): F > 0 인 한 도전자 이익은 개설자+판정자 연합 수입을 결과의존으로 만들어 정리 3 의 보조금을 개설자로 옮기고, Forge B5 실측으로 장악 풀에서 정답 주장 그리핑이 사건당 +R_c(장악 자기조달). R_c ≤ F 면 어차피 공급 0(S1). ⇒ R_c = 0 이 지배적. 패널측 소멸(레지스트리 `lastUpdate` 결합 → 양쪽 경로 동시 revert 위험)·개설자 패널 제외(시빌 우회)도 기각.

### 12.4 기계로 증명된 것 (정리 이름 · 통과 수 · 로그)

| 도구 | 대상 | 결과 | 로그 |
|---|---|---|---|
| Halmos 0.3.3 | `BondedValidatorV3Proofs`: **T1** 기권 무손실 · **T2** 슬래시 정확 · **T3** 이중정산 불가 · **T4** 보존(단언 무수정) + **L1** 소멸 무손실·완전성 · **L2** 조기 소멸 불가 · **L3** engage XOR lapse · **L4** 표식 봉쇄·해제 복원 · **L5a/L5b** 단일 정산 | **10/10**, 반례 0, 1.77s(검증팀 재실행 1.76s) | `logs/halmos-bv3.log` |
| Halmos `--loop 33` | `BondedJudgePanelV3Proofs`: **PA/PB/PC/P4** 회귀(본문 무수정) + **PL1a** 투표 착지 ⟺ s ≤ 100 · **PL1b** ∀(s1,s2) ≤ 100 시한 정산 무되돌림(스크래치 반례 0x80 폐쇄) · **PL2** 커밋 시한 리셋 · **PL3a** 예약태그 revert · **PL3b** 소멸 전후 판정자 9명 5-튜플·패널 잔고 불변 | **9/9**, 239s(재실행 245s·248s; 경로 수는 실행 간 변동 PB 1,052/1,066/1,049) | `logs/halmos-panel3.log` |
| Halmos | v0.2.1 `BondedValidatorProofs` 회귀 T1~T4 | **4/4** | `logs/halmos-bv021-regression.log` |
| Forge 1.7.1 | 10 suites: 기존 69 + `Exp30Lapse` 21(K2a 8상태·K2b 웨지·K4a~d·R2/R3/R5/R8/R9·L5·낙관적창 반박 A) | **90/90**, 0 fail | `logs/forge-test.log` |
| z3 4.12.6 | [THM] Q1·Q1-v021·S1·S6·B5·B5″·R1·R1′·R1″·W1·W1′ (11) + [WIT] Q1′·Q1″·S6′·S6″·B5′·W1″ (6) | **17/17** | `logs/prove.log` |
| cvc5 1.3.4 | 위 17건 독립 솔버 교차 | **17/17 일치** | `logs/xverify.log` |
| anvil | K3 `sim.py` N=100, q ∈ {1, 0.5, 0} | 표 §11.2 | `logs/sim.log` |

- **독립 재실행(검증팀, 같은 브랜치):** 위 전부 동일 판정. `prove.json`·`sim.json` 바이트 동일. 정본 4파일 무수정 diff 확인. PanelV3 의 `_draw/_pickOne/_settleUnanimous/_settleExpanded/_finalize/_refund` 무수정 diff 확인. PA~P4·T1~T4 단언 본문 무수정 diff 확인. R1~R12 ↔ 구현 라인 대조 일치.
- **반박팀 재실행:** forge 90/90 · halmos BV3 10/10 · Panel3 9/9 동일.
- **서기 재실측(이 절 작성 시):** 검증팀 독립 스크래치 `scratchpad/exp30-verify/test/Exp30Verify.t.sol` **4/4 PASS** 재현(적대 선점 최악 경로 T_max−1 · 확대 부분투표 · recommit 무연장 · 두 주장 교차 회계); 정본 4파일 무수정 확인; `BondedValidatorV3.sol` 전문·`ReputationLens.sol` 전문·PanelV3 핵심 구간·`Erc8004Registries.getSummaryExcluding`·`ZkVerdictGate.attest` 정독.

**증명이 말해 주는 것과 말해 주지 않는 것.** 말해 주는 것: 단일 주장에 대해 소멸은 토큰을 옮기지 않고(L1), 창 안에서는 불가능하며(L2), 개설과 소멸은 어느 시각에도 동시에 열리지 않고(L3), 정산은 한 번뿐이며(L5·T3), 기존 정리 T1~T4 는 그대로다. 말해 주지 않는 것: 다중 주장 교차·재진입·ZkVerdictGate 실결합·실토큰 훅·W 의 적정값(§7-7·§12.6-C).

### 12.5 킬기준 대조 결과 (§5 원문 무수정 · 검증팀 재채점 반영)

| 기준 | 결과 | 정직한 라벨 |
|---|---|---|
| **K1** 형식 증명 | **PASS** | 사전등록 원문의 조건은 '정본 이식 후'인데 현재는 브랜치 위 실행이다(코드 동일·main 무수정이라 실질 문제 아님). **main 이식 후 재실행 필수** |
| **K2(a)** 활성 상한 | **PASS** | 구현 보고의 최악 경로 T_max−2(179,998s)는 진짜 최악이 아니었다 — `drawPanel`·`drawExpanded` 에 시한 상한이 없어 시한 '정각'에 선점하면 **T_max−1(179,999s)**(검증팀 실측·서기 재현). 상한 180,000s 안이라 판정 불변. §11.2 K2(a)·K4(c) 와 백서 §5.1 의 '정확히 T_max−2' 는 '≤ T_max−1(적대 선점 포함)' 로 정정 대상 |
| **K2(b)** 웨지 | **PASS** | PL1a·PL1b + Forge 101/255/32KB/1025B/예약태그 revert, 1024B·100 두 표 뒤 시한 정산 |
| **K2(c)** Sepolia | **미실행** | 오너 결재 ①② 뒤 배포 — 배포 금지 규칙 준수(정당한 미실행) |
| **K3** 억지력 | **PASS (q=1 조건부)** | 환각 50→2(≤10) · 캘리브 50→50(≥49). **q=0.5 는 31 > 25 킬선 초과, q=0 은 손실 0** — 사전등록이 q=1 에만 킬을 걸어 판정은 PASS 가 맞지만, 억지력의 q 민감도가 크다(절반 도전이면 이미 킬선 초과). 또 q=1 행은 소멸 0건이라 v0.3 새 메커니즘엔 무정보(v0.2.1 동치 재현). 캘리브 대리는 16/100 만 답해 '≥49' 가 거의 자동 |
| **K4(a)** 토큰 이동 | **PASS** | L1 + Forge 잔고 7종·totalSupply 불변 |
| **K4(b)** 연합 순수입 | **PASS** | −1 wei(F mod 3 잔여가 패널에 잔류, v0.2.1 성질) / 0 — ≤0 이지 =0 아님 |
| **K4(c)** 정직 잠금 | **PASS** | 도전 없음 정확히 W(선무장 인출); 그리핑 ≤ T_max−1 |
| **K4(d)** 렌즈 | **PASS** | 단, answered=0 퇴화 사례만 검사했다 — 반박팀이 answered>0 사례에서 편향을 발견(12.6-A①). 사전등록 원문은 유지하고 사후 사례를 별도 표기 |

**총평:** 킬 발동 0 · 재설계 사유 0 · 미실행 1(K2c). 코드 결함·증명 실패·반례 없음.

### 12.6 실패·미해결·새로 발견된 것 (전량, 숨김 없음)

**A. 반박팀 검토(survives = true) — 정리 위반 없음, 결재 전 반영 권고**

① **[중] ReputationLens R8 '중립화'가 소멸 다수 이력에서 수치적으로 거짓.** 레지스트리 평균이 내림(`getSummaryExcluding` 의 정수 나눗셈, 서기 확인)이라 `avg·count` 복원 오차 ≤ count−1 이 answered 로 나뉘어, d ≫ answered 면 편향이 무계. 산술: 정답 100점 10건 + 소멸 990건 → sum 50,500 / 1,000 = 50(내림) → 50·1,000 − 50·990 = 500 → /10 = **50**(정확값 100), `requiredBondBp` 10000(정확 5000). 100점 1건 + 소멸 100건 → 50; 49점 10건 + 소멸 100건 → 39. 방향은 항상 하향·자해형(남의 agentId 로 소멸을 만들 수 없음 — `onlyAgentWallet`)이라 착취 경로는 아니다. 현재 `requiredBond` 는 view 전용이라 온체인 손실 0. 그러나 v0.3 이 만드는 저-q 체제에서 렌즈가 무정보가 되고, 평판을 지키려는 정직 에이전트에게 자기개설(F 지불) 유인 = 검증세의 뒷문 복귀. §11.3-3 의 식 '최대 (count−1)/answered' 는 맞으나 예시(91 vs 92.3)가 무계성을 숨긴다. **Exp31(온체인 requiredBond 강제) 착수 전 게이트.**
② **[중하] 판정자 용량 소진에 의한 유도 소멸(§7-13 의 능동형).** `requiredFreeBond = perCaseBond`(10e18, 신참 1.5x)이고 판정자 입장 담보가 15e18 이면 1인당 동시 1건. 공격자가 참 주장 3건을 결의(decoy)로 열어 9인 전원 `atRisk` → 도전자의 거짓 주장 개설이 `'pool too small'` → 리셋 → 24라운드 반복 → 창 종료 → 거짓 주장 무손실 소멸, 공격자 토큰 순비용 0(0표 사건 수수료는 개설자 반환). **전제:** 추첨된 판정자 전원이 voteTimeout 내내 침묵(불참 비용 0 — `NonParticipation` 이벤트뿐, 서기 확인). 판정자 1인이라도 즉시 투표하면 무산(반박팀 실측: 슬래시 1e18). 실제 매개변수는 풀 크기가 아니라 **'판정자 지연·불참 비용 0'**. 완화 후보(불참 페널티·판정자 용량 ≥ 2건)는 슬래싱 규칙 변경이라 별도 A2A 심의 사항 — 이번 결재에 끼워 넣지 않는다.
③ **[하]** `_resetCommit` 의 수수료 반환 `transfer` 가 되돌리는 토큰(훅·블랙리스트)이면 사건 Committed·주장 engaged 로 영구 고착 — Exp30 이 닫은 활성 공백의 재개. §7-5 는 `_finalize` 만 지목했다. LabToken 은 되돌릴 수 없어 현 배포 범위에선 발생 불가.
④ **[하]** K3 는 v0.3 새 메커니즘에 사실상 무정보(q=1 = 소멸 0건 = v0.2.1 동치). 킬기준 우회는 아니나 'PASS' 를 v0.3 억지력의 증거로 읽으면 과대해석.
⑤ **[하]** `BondedValidatorV3.submitVerdict` 는 예약 태그(`"unchallenged"`/`"disputed"`)를 거부하지 않는다 — 봉쇄는 패널 층(`_reservedTag`)에만. judge = EOA/ZkVerdictGate 구성에선 임의 점수 + 예약 태그 기록 가능(호출자는 judge 뿐, 무권한 경로 없음). ERC 초안 불변식 5 는 패널 층에서만 참.

**B. 검증팀 불일치 — 서술 정밀도·미기재 설계 결과(재설계 사유 아님)**

- 최악 경로 '정확히 T_max−2' → '≤ T_max−1(적대 선점 포함)' 정정: §11.2 K2(a)·K4(c), `docs/whitepaper-draft.md:287` ("exactly `T_max − 2 s`").
- `REPRODUCTION.md:91-93`·§11.3-1 의 'KeyError: ast 캐시 함정(2026-09-03 실측)'이 동일 도구 버전(forge 1.7.1·halmos 0.3.3)에서 문서 순서 그대로 **재현되지 않음**(halmos 가 재컴파일해 10/10). `forge clean` 권고는 무해하나 '실측' 표기는 조건 없이는 과대.
- Halmos 경로 수는 실행 간 변동(PB 1,052/1,066/1,049 · PC 16/17) — `results.json` 이 고정값처럼 박제, 주석 필요.
- EXP30.md 헤더 5행·§7-15 stale(이 절 머리에서 바로잡음).
- K1 라벨 '정본 이식 후' 조건 미충족(브랜치 실행) — 12.5 에 명기.
- **ZkVerdictGate 구성의 의미 변화(구현 보고 미기재).** R5 때문에 judge = ZkVerdictGate(Exp20) 구성에서는 `engage` 경로가 없어 증명 제출(`attest`)이 창 W 안에서만 가능하고, W 경과 후엔 주장이 50/`"unchallenged"` 로 소멸되며 늦은 증명은 `'window closed'` 로 거부된다(`BondedValidatorV3.sol:137` + `ZkVerdictGate.sol:71`, 서기 확인). 검증 누락이 아니라 **'증명 마감 = W' 라는 설계 결과** — 결재 ② W 확정의 판단 재료. 게이트는 `BondedValidator` 타입을 import(주소 캐스팅으로 동작 가능, 미테스트).
- ERC 초안 사소: `threshold()` 선언 vs 실제 `THRESHOLD()` public constant 이름 불일치(기존 승계).
- '최초 실행 신규 테스트 5건 실패 → 테스트만 수정' 은 커밋 이력에 중간 상태가 없어 검증 불가(최종 상태만 검증됨).

**C. 여전히 미실행·미확정·모델 밖**

- K2(c) Sepolia 실측 · W 최종값(L1/L2 강제포함 지연 실측 → R10 하한 규칙 W ≥ k·지연 + voteTimeout, k ≥ 2) · Kleros 보상 구조 대조 · ERC-8004 draft 재확인.
- 증명 범위(§7-7): 단일 주장·W 구체값·9인 결정론 시드·dt 만 심볼릭. 다중 주장 교차(검증팀 스크래치 1건뿐)·재진입·ZkVerdictGate 실결합·canonical 8004 어댑터·실토큰 훅 — Forge 실측만 또는 미검증.
- 발견 대장(`findings.py` RT-####) 미등재 2건: score>100 웨지·태그 가스 — 상위 처리 대기.
- 문서 개정(ERC·백서·REPRODUCTION)은 브랜치 초안이며 EF 제출본 갱신 아님.
- §7-14 '무비용도 아니다' 는 실측(0 / −1 wei)과 문구 모순 — 정정 대상.
- 판정 수요 붕괴 → q → 0 자기강화, 규모붕괴(G ≫ B_a ⇒ q* → 1), 분산피해형 거짓말(균형 q = 0) — §7-1~3 그대로, 치료 아님.
- 소진 공격(A②)의 '판정자 침묵' 전제 하 현실 발생확률은 미측정.

### 12.7 형이 결정할 것 (되돌릴 수 없는 것만)

**① 슬래싱 규칙 변경 결재** — "창 W 안에 도전받지 않은 주장은 판정 없이 무손실로 소멸한다(50/`'unchallenged'`, 검증 아님)". 마스터플랜 불변원칙(슬래싱 규칙 변경 = A2A 심의 + 오너 결재). 이 문서가 심의 결과이며, 결재 전 정본 이식·배포 없음은 준수됐다. **결재 시 알아야 할 대가:** 억지력이 q 조건부(q = 0.5 에서 환각 담보 31 잔존 — 사전등록 킬선 25 초과), 판정자의 강제 수입(활성 버그가 만든 100% 검증세) 소멸, 분산피해형 거짓말 무억지, 판정자 침묵 조건에서 유도 소멸 가능(A②).

**② v0.3 Sepolia 재배포 승인 + 불변 파라미터 확정** — `BondedValidatorV3` + `BondedJudgePanelV3` 쌍(judge immutable 이라 신규 배포만 가능). `challengeWindow = 86,400s` 잠정(강제포함 지연 실측 후 하한 규칙으로 최종값 제시), 나머지 v0.2.1 동일(minBond 1e18·unbondDelay 3600·perCaseBond 10e18·judgeFee 1e18·voteTimeout 3600·disputeTimeout 86400). **배포 후 변경 불가.** ZkVerdictGate 구성에서는 W 가 곧 증명 마감이 됨을 감안할 것.

(결재 항목 아님·서기 권고) ①② 전에 되돌릴 수 있는 정정 묶음(12.8)을 브랜치에서 먼저 마치는 편이 결재 문서의 정직성을 높인다. 구 v0.2.1 라이브의 미정산 주장 처리는 §8 그대로 운영 선택.

### 12.8 다음 한 수

결재 전, 브랜치에서 **되돌릴 수 있는 정정 묶음 1회**: (a) `ReputationLens.creditScore` 를 내림 평균 복원 대신 정확 합계(레지스트리 순회 또는 다중태그 제외 합계 함수)로 수리 + Forge 회귀 2건(100점 10 + 소멸 990 → (100, 10)·5000bp / 49점 10 + 소멸 100 → 49) + Halmos·Forge 전량 재실행; (b) 문서 정정 — T_max−1·캐시 함정 조건·경로 수 변동·§7-5(`_resetCommit`)·§7-13(능동형·지연 매개변수)·§7-14 문구·ZkVerdictGate W 마감·K1 라벨·헤더 지위; (c) 발견 대장 RT 등재 2건. 그 다음 **① 결재 → main 이식 → K1 재실행 → ② W 확정(강제포함 지연 실측) → Sepolia 배포 → K2(c) 실측**. 불참 페널티·판정자 용량 하한은 별도 심의로 분리.

---

## 13. 결재 전 정정 묶음 (a) — 렌즈 내림 편향 수리 (2026-09-03 · 브랜치 `exp30-liveness` · §12.8 (a) 실행 · 결재 ①② 전)

> 지위: 되돌릴 수 있는 정정. 정본(`Erc8004Registries.sol`·`BondedValidator.sol`·`BondedJudgePanelV2.sol`·`ZkVerdictGate.sol`) 무수정 · main 무수정 · 미배포. §5 킬기준 원문은 바이트 단위로 손대지 않았다(§12 이전 절 전부 무수정 — 이 절만 추가).

### 13.1 무엇을 어떻게 고쳤나

- **대상:** `exp3/contracts/src/ReputationLens.sol` — `creditScore`·`abstainRateBp` (둘 다 view, 상태 없음).
- **원인(§12.6-A①):** 레지스트리 `getSummaryExcluding` 은 내림 평균 avg = ⌊S/count⌋ 만 돌려주므로 렌즈가 `avg·count` 로 합계 S 를 복원했다. 복원 오차 ≤ count−1 이 answered 로 나뉘어 중립 건수 d ≫ answered 이면 편향이 무계 — 정답 100점 10건 + 소멸 990건 → 50(정확 100), `requiredBondBp` 10000(정확 5000).
- **수리(수식):** 렌즈가 레지스트리를 직접 순회해 정확 합계를 만든다.
  `_tally(agentId)`: `reqs = valReg.getAgentValidations(agentId)`; 각 `h ∈ reqs` 에 대해 `(…, response, tag, responded) = valReg.getValidationStatus(h)`; `responded` 인 것만, `tag = "abstain"` 이면 `abstains++`, `tag ∈ {"disputed", "unchallenged"}` 이면 건너뜀, 그 외 `answered++`, `sum += response`.
  `creditScore = answered == 0 ? (0, 0) : (⌊sum / answered⌋, answered)` · `abstainRateBp = ⌊abstains·10000 / (answered + abstains)⌋`.
  내림은 마지막 나눗셈 한 번(< 1점)뿐. 이전의 `avg·count < 50·d` 언더플로 가드는 정확 합계에선 발생 불가라 제거.
- **R8 '소멸은 평판 중립' 보존 방식:** "50점을 걷어냄"(점수 의존)이 아니라 **"답한 이력에 없음"**(태그 의존)으로 실현. 소멸 990건이 있어도 answered = 10 이라 신참 할증(answered < 10 → 15000bp) 우회 불가(K4(d) `test_K4d_100_lapses_lens_stable` 그대로 통과), 예약 태그에 50 이외 점수가 기록되는 judge = EOA 경로(§12.6-A⑤)에서도 렌즈는 흔들리지 않는다. `"disputed"`(JudgePanelV2 시한환급) 중립도 같은 방식으로 유지(`JudgePanelV2.t.sol` 2건 통과).
- **왜 '순회'이고 '다중태그 제외 합계 함수'가 아닌가:** 후자는 정본 레지스트리(Sepolia 배포본) 수정 + 재배포 = 결재 범위 확대. 순회는 렌즈 단독 변경(렌즈는 상태 없는 view 계약이라 재배포로 교체 가능)이며 되돌릴 수 있다.

### 13.2 회귀 테스트 2건 (Forge · `exp3/contracts/test/Exp30Lapse.t.sol` · 실제 `BondedValidatorV3.settleUnchallenged` 소멸 경로, judge = this)

| 테스트 | 시나리오 | 수리 전(내림 복원) | 수리 후 |
|---|---|---|---|
| `test_R8fix_exact_sum_100x10_plus_990_lapses` | 정답 100점 10건 → 소멸 990건 (n = 1,000) | (50, 10) · 10000bp | **(100, 10) · 5000bp** · `requiredBond` 5e17 · abstainBp 0 · 담보 10e18 무손실(atRisk 0·slashed 0) — PASS |
| `test_R8fix_exact_sum_49x10_plus_100_lapses` | 소멸 50 → 49점 10건 → 소멸 50 (순서 무관 확인, n = 110; 49 < THRESHOLD 라 10건 슬래시, 담보 10e18 추가 예치) | 39 · 11100bp | **49** · 10100bp · slashed 10e18 정확 — PASS |

### 13.3 실행 결과 (수리 후 전량 재실행 · forge 1.7.1 · halmos 0.3.3 · `forge clean` 후 halmos)

| 도구 | 대상 | 결과 | 로그 |
|---|---|---|---|
| Forge | 10 suites, 92 tests (기존 90 + 신규 2) | **91 passed · 1 failed** · 44ms | `logs/forge-test-lensfix.log` |
| Halmos | `BondedValidatorV3Proofs` T1~T4 + L1~L5 | **10/10** · 1.78s (wall 5.4s 컴파일 포함) | `logs/halmos-bv3-lensfix.log` |
| Halmos `--loop 33` | `BondedJudgePanelV3Proofs` PA/PB/PC/P4 + PL1~PL3 | **9/9** · 244.65s (wall 4:09; PB 경로 수 1,074 — 실행 간 변동) | `logs/halmos-panel3-lensfix.log` |
| Halmos | v0.2.1 `BondedValidatorProofs` 회귀 T1~T4 | **4/4** · 1.04s | `logs/halmos-bv021-regression-lensfix.log` |

- **실패 1건 = 기존 테스트, 지시대로 미수정.** `test_R8_lens_neutralizes_unchallenged_and_guards_underflow` 2단계 단언 `answered == 13 && score == 91` — 이 91 은 내림 편향값을 기대값으로 박제한 것(같은 테스트 주석에 '정확값 92.3' 명기). 수리 후 렌즈는 ⌊(12·100 + 1·0) / 13⌋ = **92** 를 돌려줘 단언이 깨진다(실측 revert 사유 `neutralization wrong`; 1단계 언더플로 시나리오 오답 1·소멸 3 → (0, 1)·15000bp 는 통과 지점을 지남). 수정안(상위 결정): `91 → 92`, bp `5000 + (100 − 92)·100 = 5800`. 그 외 90건(기존 `ReputationLens.t.sol` 5/5 · `JudgePanelV2.t.sol` disputed 중립 · K4(d) 포함) 전부 통과.
- Halmos 는 렌즈를 import 하는 대상이 없어 '동일'이 기대값이며 실측도 동일(경로 수는 실행 간 변동 — §12.6-B).

### 13.4 가스 (`logs/lens-gas-probe.log` · 임시 프로브 `_GasProbe.t.sol`, 미커밋 · revm gasleft() 차분, 테스트 → 렌즈 외부호출 포함)

| 시나리오 | `creditScore` 콜드(별도 tx) 전 → 후 | 웜 전 → 후 | `abstainRateBp` 웜 전 → 후 |
|---|---|---|---|
| n = 1,000 (100점 10 + 소멸 990) | 11,977,830 → **15,957,620 (+33%)** | 3,968,826 → 3,948,616 (−0.5%) | 5,150,867 → 3,948,743 (−23%) |
| n = 110 (49점 10 + 소멸 100) | 1,330,760 → 1,743,700 (+31%) | 441,756 → 414,696 | 573,597 → 414,862 |
| n = 20 (100점 12 + 기권 8) | 234,508 → 328,707 (+40%) | 81,504 → 79,703 | 108,033 → 79,872 |

이유: 이전 구현은 레지스트리 안에서 3회 순회(제외 평균 1 + 태그 건수 2, 건당 3슬롯), 새 구현은 렌즈에서 1회 순회이나 건당 외부호출 1 + 5슬롯(`getValidationStatus` 가 validator·agentId 도 읽음). 콜드에선 슬롯 수가, 웜에선 순회 횟수가 지배한다. **두 구현 모두 이력 길이에 선형** — n = 1,000 이면 콜드 12~16M gas 로 어느 쪽도 온체인 호출(Exp31 `requiredBond` 강제)엔 못 쓴다; 오프체인 `eth_call` 용도(현재)는 영향 없음.
**대안(한 줄):** 정산 시점(`_settle`/`validationResponse`)에 에이전트별 (sum, answered, abstains) 누적 캐시를 O(1) 로 갱신하고 렌즈가 그것만 읽으면 호출당 상수 gas — 정본 수정이라 Exp31 심의 항목.

### 13.5 정직한 한계

1. 전량 녹색이 아니다 — 기존 실패 1건(13.3)을 남긴 채 커밋(지시). `results.json`·§12.4 의 Forge 90/90 은 §12 시점 기록으로 그대로 둠.
2. 순회 렌즈에 ∀ 증명은 없다(Halmos 대상 아님) — Forge 실측 신규 2 + 기존 5 + K4(d) + JudgePanelV2 2 뿐.
3. 가스는 forge revm 측정치 — 실제 노드 `eth_call` 절대치와 다를 수 있다(상대 비교용). 콜드 여부는 forge 가 setUp 과 테스트를 별도 tx 로 돌린다는 전제(콜드 ≫ 웜 실측으로 확인).
4. `getSummaryExcluding` 의 내림은 레지스트리 정본 성질 그대로 — 렌즈만 우회했다. 다른 소비자가 그 함수로 평균을 쓰면 같은 편향이 남는다(ERC 초안 R12 MUST-exclude 는 권고).
5. §11.3-3·§11.3-8·§12.6-A① 의 '수리 전' 서술과 `REPRODUCTION.md:88` '90 passed' 는 문서 정정 묶음 (b) 에서 함께 손볼 것(이 커밋은 코드·테스트·이 절·로그만).
6. 렌즈 의미 변화: 예약 태그 건은 점수와 무관하게 제외 — 이전엔 정확히 50점일 때만 중립이었다. 소비자 문서(ERC 초안 R12)엔 미반영.

### 13.6 재현

```bash
cd ~/iis-lab && git checkout exp30-liveness && cd exp3/contracts
forge test                                                        # 92 tests: 91 passed, 1 failed (기존 R8 단언 91 vs 정확값 92)
forge clean && ../../.venv-halmos/bin/halmos --contract BondedValidatorV3Proofs      # 10 passed
../../.venv-halmos/bin/halmos --contract BondedJudgePanelV3Proofs --loop 33          # 9 passed (~4 min)
../../.venv-halmos/bin/halmos --contract BondedValidatorProofs                       # 4 passed
```
