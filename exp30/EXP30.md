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

---

## 14. 결재 전 정정 묶음 (b)(c) — 문서 정정·한계 보강·발견 대장 등재 (2026-09-03 · 브랜치 `exp30-liveness` · §12.8 (b)(c) 실행 · 결재 ①② 전)

> 지위: 되돌릴 수 있는 정정 — **문서·로그·대장만, 코드 무수정.** §5 킬기준 원문은 바이트 단위로 무수정(sha256 대조 14.5), §12 이전 절도 전부 무수정 — 정정은 원문 자리에 덮어쓰지 않고 **이 절의 정정표로만** 한다(사전등록·심의 이력 보존; 독자는 §11·§12 를 이 표와 함께 읽어야 한다). §13 은 (a) 렌즈 수리 기록이며 이 절은 그 뒤에 붙는다. main 무수정·미배포·미푸시.

### 14.1 정정표 (§12.6-B·C 의 서술 정정 — 원문은 그대로, 여기서 정정)

| # | 대상(원문 위치) | 원문 | 정정 | 근거 |
|---|---|---|---|---|
| 1 | §11.2 K2(a)·K4(c) · `docs/whitepaper-draft.md:287` | 최악 경로 = "정확히 T_max−2(179,998s)"(커밋시한 1초 전 추첨) | **≤ T_max−1(179,999s).** `drawPanel`/`drawExpanded` 는 `phase` 검사만 있고 시한 상한이 없어(`BondedJudgePanelV3.sol:180-203`) 커밋 시한 **정각**에 `resolveTimeout`(Committed 분기, `≥`) 대신 추첨을 선점할 수 있다. 상한 180,000s 안이라 **판정 불변.** 백서 §5.1 은 이번 커밋에서 정정(영문, "strictly inside `T_max`" + 이전 초안 문구 병기) | 검증팀 실측·서기 재현(§12.5) · 소스 확인(이 절) · 본 브랜치에 이 경로의 Forge 테스트는 없음(검증팀 스크래치) |
| 2 | §11.3-1 · `REPRODUCTION.md:91-93` | "`forge test` 뒤 halmos → `KeyError: 'ast'` 캐시 함정(실측)" | **조건부 함정으로 정밀화.** 검증팀 재실행(같은 forge 1.7.1·halmos 0.3.3)에선 재현되지 않았고(halmos 가 재컴파일해 10/10), **이번 정정 실행에선 재현됐다** — `forge test` 직후 `forge clean` 없이 `halmos --contract BondedValidatorV3Proofs` → "No files changed, compilation skipped" → 아티팩트 **46건** `KeyError: 'ast'` 건너뜀 → "No tests with --match-contract" exit 1(`logs/halmos-bv3-nocleanprobe-docfix.log`). 관측된 재현 조건은 forge 가 "No files changed" 로 컴파일을 건너뛰는 상태이며, 검증팀 환경에서 왜 재컴파일이 일어났는지는 **미확인.** `forge clean` 선행은 권고가 아니라 **필수**로 유지, 표기는 '2회 재현·1회 미재현' | `REPRODUCTION.md` 이번 커밋에서 정정 |
| 3 | §11.2 K1 · §12.4 · `results.json` | Halmos PB 경로 수 1,052(고정값처럼 박제) | 경로 수는 **실행 간 변동**: PB 1,052(§11) · 1,066/1,049(검증팀) · 1,074((a) 수리 후) · **1,101(이번)**, PC 16/17. 판정(9/9·반례 0)은 불변. `results.json` 의 `paths` 는 그 실행의 값일 뿐 규격이 아니다 — 파일은 §12 시점 기록으로 두고 여기서 주석 | `logs/halmos-panel3*.log` 4종 |
| 4 | §7-7 · §11.3-7 (미기재 설계 결과) | ZkVerdictGate 구성은 "Forge 실측만" / "미재검증" | **W = 증명 마감.** R5(`BondedValidatorV3.sol:137` `engaged ∨ windowOpen`) 때문에 judge = ZkVerdictGate(Exp20) 구성에는 `engage` 경로가 없어 `attest`(`ZkVerdictGate.sol:71` → `bonded.submitVerdict`)는 창 W 안에서만 착지하고, W 경과 후 주장은 50/"unchallenged" 로 소멸·늦은 증명은 'window closed' 로 거부된다. 검증 누락이 아니라 **설계 결과**이며 **결재 ② W 확정의 판단 재료.** 게이트는 `BondedValidator` 타입 import(주소 캐스팅 동작 가능, 실결합 미테스트). 같은 구성에서 `BondedValidatorV3.submitVerdict` 는 예약 태그를 거부하지 않는다(§12.6-A⑤ — 봉쇄는 패널 층 `_reservedTag` 뿐, 호출자는 judge 뿐이라 무권한 경로 없음; ERC 초안 불변식 5 는 패널 층에서만 참) | §12.6-B · 소스 확인 |
| 5 | §7-14 | "R_c = 0 이라 무수익이지만 **무비용도 아니다**(F 환류 후 0)" | 실측(§11.2 K4(b))과 모순 — 장악 그리핑 순수입 **−1 wei**(F mod 3 패널 잔류), 2석+침묵 시한 평결 **0**. 정정 문구: "무수익이며 **토큰 순비용도 0**(F 환류 후 0; 장악 시 −1 wei = F mod 3 패널 잔류). 남는 비용은 가스와 perCaseBond 잠금의 기회비용뿐 — 억지력이 아니라 마찰이다." | `logs/forge-test*.log` K4(b) |
| 6 | §7-5 | `_finalize` 의 `token.transfer` 만 되돌림-토큰 웨지로 지목 | **`_resetCommit` 추가.** `BondedJudgePanelV3._resetCommit` 은 `require(token.transfer(opener, judgeFee), "fee return")` 를 `bonded.disengage` **앞**에서 실행한다 — 수수료 반환이 되돌리는 토큰(훅·블랙리스트·수수료 토큰)이면 사건 Committed·주장 engaged 로 영구 고착 = Exp30 이 닫은 활성 공백의 재개. LabToken 은 되돌릴 수 없어 현 배포 범위에선 발생 불가; 실토큰 미검증(§7-5 와 같은 급) | §12.6-A③ · 소스 확인 |
| 7 | §7-13 (보강) | "판정자 풀 < 3 이 W 내내면 소멸 = 거짓말 무손실"(수동형) | **능동형 추가**(§12.6-A②): `requiredFreeBond = perCaseBond` 라 입장 15e18 판정자는 동시 1건 — 공격자가 참 주장 3건을 결의(decoy)로 열어 9인 전원 atRisk → 거짓 주장 개설 'pool too small' → 리셋 반복(24라운드) → 창 종료 → 무손실 소멸, 공격자 토큰 순비용 0. 실제 매개변수는 풀 크기가 아니라 **판정자 지연·불참 비용 0**(추첨 판정자 전원 voteTimeout 내내 침묵 전제; 1인이라도 즉시 투표하면 무산 — 실측 슬래시 1e18). 완화(불참 페널티·용량 하한)는 슬래싱 규칙 변경 = 별도 심의, 발생확률 미측정 | §12.6-A② |
| 8 | §11.2 K3 · §12.5 K3 (한계 명기) | "PASS (q=1)" | **PASS 는 q=1 조건부이며 q 민감도가 크다는 것을 한계로 명기한다:** q=0.5 에서 환각 담보 50→**31 > 사전등록 킬선 25**, q=0 에서 50(손실 0). §5 가 q=1 에만 킬을 걸었으므로 판정은 PASS 가 맞으나, 이 PASS 를 v0.3 억지력의 증거로 읽으면 과대해석 — q=1 행은 소멸 0건이라 v0.3 새 메커니즘엔 무정보(v0.2.1 동치 재현), 캘리브 대리는 16/100 만 답해 '≥49' 가 거의 자동, q 는 외생이며 판정 수요 붕괴 → q → 0 자기강화는 모델 밖 | `logs/sim.log` · §12.6-A④ |
| 9 | §11.2 K1 · §12.5 K1 | "PASS" | 사전등록 원문 조건 '**정본 이식 후**'가 문자상 미충족 — 브랜치 `exp30-liveness` 위 실행(코드 동일·main 무수정이라 실질 문제 아님). **main 이식 후 재실행 필수**(halmos BV3 · Panel3 `--loop 33` · forge). 라벨: "PASS(브랜치 · 정본 이식 후 재실행 대기)" | §12.5 |
| 10 | §11.2 K1 · §11.4 · §12.4 · `REPRODUCTION.md:88` | Forge "90/90" | (a) 수리 후 **92 tests: 91 passed · 1 failed** — 실패 1건은 기존 `test_R8_lens_neutralizes_unchallenged_and_guards_underflow` 의 내림 편향값 91 단언(정확값 92, §13.3). §11.3-3('v0.2.1 렌즈 성질, 범위 밖')·§11.3-8·§12.6-A① 의 '수리 전' 서술은 §13 으로 대체됨. `REPRODUCTION.md:88` 이번 커밋에서 정정; §11·§12 원문은 시점 기록으로 유지 | `logs/forge-test-docfix.log` |
| 11 | 헤더 5행 · §7-15 | "정본 무수정·미커밋·미배포 / K3 미실행·합성본 Forge/Halmos 없음" | 브랜치 커밋 존재(d76872d·b7bfc43·23b0e95·f3867bd + 이번), K3 실행됨(§11.2), 합성본 Forge/Halmos 존재 — §12 머리에서 이미 바로잡음. 헤더·§7-15 는 심의 시점 기록으로 유지 | §12.6-B |

### 14.2 (a) 렌즈 수리 요약 (상세 §13 · 커밋 f3867bd)

`ReputationLens.creditScore`·`abstainRateBp` 가 레지스트리 내림 평균(`getSummaryExcluding` 의 ⌊S/count⌋)에서 합계를 복원하던 것을, 레지스트리 순회 정확 합계(`_tally`: `getAgentValidations` → 건별 `getValidationStatus`, responded 만 집계, "abstain" → abstains, "disputed"/"unchallenged" → 점수 무관 통째 제외)로 바꿨다 — 정본 레지스트리(Sepolia 배포본)는 무수정, 기존 view 인터페이스만 사용. R8 '소멸은 평판 중립' 은 '50점 걷어내기'(점수 의존)에서 **'답한 이력에 없음'**(태그 의존)으로 실현돼 신참 할증(answered < 10 → 15000bp) 우회 불가(K4(d) 유지)·judge = EOA 가 예약 태그에 50 이외 점수를 기록해도(§12.6-A⑤) 흔들리지 않는다. 회귀 2건 통과: 100점 10 + 소멸 990 → **(100, 10)·5000bp**(수리 전 (50, 10)·10000bp), 49점 10 + 소멸 100 → **49·10100bp**(수리 전 39·11100bp). 전량 재실행: Forge 92 중 91 통과·1 실패(기존 테스트의 편향값 91 단언, 정확값 92 — **미수정, 91→92·5800bp 수정 여부는 상위 결정**), Halmos BV3 10/10·Panel3 9/9·v0.2.1 회귀 4/4, 반례 0. 가스: 콜드 `creditScore` +31~40%(n=1,000: 11.98M → 15.96M), 웜 ≈ 동일, `abstainRateBp` 웜 −23% — **두 구현 모두 이력 길이에 O(n)** 이라 온체인 강제(Exp31 `requiredBond`)엔 어느 쪽도 부적합, 대안은 정산 시점 O(1) 누적 캐시(정본 수정 = Exp31 심의). 렌즈 의미 변화(예약 태그 건은 점수 무관 제외 — 이전엔 정확히 50점일 때만 중립)는 소비자 문서(ERC 초안 R12)에 **미반영** — 결재 후 정본 이식 시 함께.

### 14.3 (c) 발견 대장 등재 (`~/jarvis-ui/automations/findings.py` · RT 번호대 · 2026-09-03)

| ID | 제목(요약) | 상태 | 수리 참조 |
|---|---|---|---|
| **RT-0029** | `BondedJudgePanelV2.voteVerdict` 가 score>100 을 받아 초심 2인이 101 로 일치하면 정산이 레지스트리 'range' 되돌림으로 **영구 정지** — 에이전트 담보·판정자 perCaseBond 영구 잠금(v0.2.1 Sepolia 라이브). 증명됨(proven) — 정본 재현 `test_PREEXISTING_v021_same_wedge` 5/5, Halmos 반례 s1=s2=0x80 | triaged | d76872d `require(score <= 100, "score range")` + PL1a/PL1b |
| **RT-0030** | `voteVerdict` 태그 길이 무제한 — 정산(`_finalize`) 가스가 같은 태그의 투표 가스보다 항상 커 '투표는 착지하나 정산은 블록 한도 초과' 하는 태그 길이 구간 존재(32KB 실측 23.31M vs 23.55M). 측정이지 증명 아님(블록 한도 정확값·32KB 초과 미측정) | triaged | d76872d `MAX_TAG_BYTES = 1024` |

각 항목은 '어디서·왜 거기 있나·재현·수리·교훈' 으로 등재했고 심각도는 **med**(Sepolia 테스트넷·LabToken 이라 실자금 노출 0, 프로토콜 안에서는 활성 붕괴). 두 건 모두 정본 v0.2.1 라이브는 judge immutable 이라 패치 불가 → v0.3 재배포(결재 ②) 전까지 잔존하므로 'fixed' 가 아니라 **'triaged'** 로 두었다('fixed' 는 결재 ①② + main 이식 + 배포 뒤, 'verified' 는 K2(c) 실측 뒤). §1.2·§11.3-9·§12.6-C 의 '미등재' 는 이로써 해소.

### 14.4 이번 실행 (문서 정정 커밋 시점 재실행 · 코드 무수정이라 §13.3 과 동일이 기대값 · forge 1.7.1 · halmos 0.3.3)

| 순서 | 도구 | 결과 | 로그 |
|---|---|---|---|
| 1 | `forge test` | **92 tests: 91 passed · 1 failed**(§13.3 과 동일한 기존 R8 단언) | `logs/forge-test-docfix.log` |
| 2 | `halmos --contract BondedValidatorV3Proofs` **`forge clean` 없이**(캐시 함정 프로브) | **재현** — "No files changed, compilation skipped" → 46 아티팩트 `KeyError: 'ast'` → "No tests with --match-contract", exit 1 | `logs/halmos-bv3-nocleanprobe-docfix.log` |
| 3 | `forge clean` → `halmos --contract BondedValidatorV3Proofs` | **10/10** · 1.78s | `logs/halmos-bv3-docfix.log` |
| 4 | `halmos --contract BondedValidatorProofs`(v0.2.1 회귀) | **4/4** · 0.94s | `logs/halmos-bv021-regression-docfix.log` |
| 5 | `halmos --contract BondedJudgePanelV3Proofs --loop 33` | **9/9 · 0 failed** · 251.81s (PB 경로 1,101 · PC 17 — 실행 간 변동, 판정 불변) | `logs/halmos-panel3-docfix.log` |

### 14.5 §5 무수정 증빙

`sed -n '132,153p' exp30/EXP30.md | shasum -a 256` = `37a02f2b1af0d121a7213f7b4296e1f845886e87c473bed052f5253d69c2472b` — 이 절 추가 전(f3867bd)·§12 추가 시점(23b0e95)·이 절 추가 후 모두 동일(커밋 전 재대조). §12 이전 절은 `git diff f3867bd -- exp30/EXP30.md` 에 삽입 hunk 1개(이 절)뿐, 삭제 0행.

### 14.6 정직한 한계

1. **원문 자리 정정이 아니다.** §11.2·§11.3·§12.4·§12.5 의 stale 문구(T_max−2·90/90·'실측' 캐시 함정·PB 1,052)는 그대로 남아 있고, 이 정정표가 그것을 덮는다 — 사전등록·심의 이력 보존을 택한 대가.
2. **전량 녹색이 아니다.** 기존 실패 1건(§13.3)은 이번에도 미수정 — 91→92 결정은 상위.
3. **캐시 함정의 정확한 원인은 미확인.** '2회 재현·1회 미재현' 이라는 관측과 "No files changed" 조건만 있다. 검증팀 환경이 왜 재컴파일했는지 모른다.
4. **T_max−1 경로의 Forge 테스트는 이 브랜치에 없다**(검증팀 스크래치·서기 재현). 코드·테스트 무수정 원칙으로 추가하지 않았다 — 결재 후 정본 이식 시 K2(a) 테스트에 넣을 것.
5. **발견 대장은 다른 저장소(`~/jarvis-ui`, 브랜치 `feat/voice-jarvis` 작업 트리)** 에 있다 — 등재 커밋은 그 저장소에서 별도.
6. ERC 초안(`threshold()` vs `THRESHOLD()` 이름 불일치, R12 렌즈 의미 변화)·`results.json`(Forge 90/90·paths 고정값)·§11·§12 원문은 이번에도 손대지 않았다. ERC·백서·REPRODUCTION 은 브랜치 초안이며 EF 제출본 갱신 아님.
7. Halmos PB 경로 수는 이번에도 달랐다(14.1-3) — 판정 불변.
8. main 무수정·Sepolia 미배포·미푸시. 결재 ①② 는 여전히 열려 있다(§12.7).

### 14.7 재현

```bash
cd ~/iis-lab && git checkout exp30-liveness && cd exp3/contracts
forge test                                                        # 92: 91 passed, 1 failed (기존 R8 단언 91 vs 정확값 92)
../../.venv-halmos/bin/halmos --contract BondedValidatorV3Proofs # (forge clean 없이) → 캐시 함정 재현 여부 확인용: 재현되면 KeyError: 'ast'·0 tests
forge clean && ../../.venv-halmos/bin/halmos --contract BondedValidatorV3Proofs      # 10 passed
../../.venv-halmos/bin/halmos --contract BondedValidatorProofs                       # 4 passed
../../.venv-halmos/bin/halmos --contract BondedJudgePanelV3Proofs --loop 33          # 9 passed (~4 min)
cd ~/jarvis-ui && python3 automations/findings.py list --team redteam --open | grep -E 'RT-0029|RT-0030'
```

### 14.8 마감 — 남은 열림 4건 정리 (2026-09-03 · 브랜치 `exp30-liveness` · 결재 ①② 전)

> 지위: 되돌릴 수 있는 정정. 코드는 2파일(`ReputationLens._tally` validator 필터 1줄 보강 · `Exp30Lapse.t.sol` 기대값 정정 + 회귀 1건), 나머지는 문서·로그. §5 킬기준 원문은 바이트 단위로 무수정(sha256 14.8.5) · §12 이전 절과 §13·§14.1~14.7 원문도 무수정 — 정정은 이 소절의 정정표 추가 행으로만 한다. main 무수정·미배포·미푸시.

#### 14.8.1 정정표 추가 행 — R8 관련 (§14.1 의 12~14 행)

| # | 대상(원문 위치) | 원문 | 정정 | 근거 |
|---|---|---|---|---|
| 12 | §4 R8 (사전등록 규칙 원문) | "d = byTag(disputed) + byTag(unchallenged) 로 중립화 … `avg·count < 50·d` 이면 (0, answered) 반환(언더플로 가드)" | 구현은 §13 수리로 바뀌었다 — 레지스트리 순회 정확 합계 `_tally`, 예약 태그("disputed"/"unchallenged")는 점수 무관 통째 제외, **언더플로 가드 없음**(정확 합계라 발생 불가). 이번 마감으로 `_tally(agentId, validator)` 가 **`validator == address(bonded)` 인 응답만** 집계(14.8.2). R8 의 뜻('소멸은 평판 중립 · 신참 할증 우회 불가')은 그대로이고 실현 방식만 바뀜. §4 원문은 사전등록 기록으로 유지 | §13.1 · `ReputationLens.sol:45-62` |
| 13 | §12.3 R7/R8 행 | 구현 위치 `ReputationLens.sol:35-45` · "중립 처리 + 언더플로 가드" | 현재 `_tally` 는 **`ReputationLens.sol:45-62`**(이 커밋 기준; 필터 줄 `:55`), 가드 없음, validator 필터 있음. R7(소멸이 판정자 상태를 안 건드림)은 무관·불변 | 소스 |
| 14 | §11.1 표 R8 행 · §11.3-3 · §13.3 · §13.5-1 · §13.6 · §14.1-10 · §14.4 · §14.6-2 · §14.7 · `REPRODUCTION.md:88` | "92 tests: 91 passed · 1 failed(기존 R8 단언 91)" / "91→92 는 상위 결정" | **93 tests: 93 passed · 0 failed.** 기존 `test_R8_lens_neutralizes_unchallenged_and_guards_underflow` 2단계 기대값을 **91 → 92, bp 5800**(= 5000 + (100−92)·100)으로 정정 — 91 은 옛 렌즈의 내림 편향값(레지스트리 avg ⌊1400/17⌋ = 82 복원 → 91)을 박제한 것이지 규격이 아니었고, 같은 테스트 주석이 이미 '정확값 92.3' 을 적어 두었다(§13.3). 테스트 이름의 `guards_underflow` 는 §4 R8 원문 시점 이름 — 시나리오(오답 1 + 소멸 3 → (0, 1)·15000bp)는 회귀로 유지, 이름은 참조 보존을 위해 그대로. 회귀 1건 추가(14.8.2). `REPRODUCTION.md:88` 이번 커밋에서 정정; §13.6·§14.7 코드블록 주석은 시점 기록으로 유지 | `logs/forge-test-closeout.log` |

#### 14.8.2 (2) 렌즈 validator 필터 — 기존 구멍 수리 (코드 1줄 + 회귀 1건)

- **구멍(기존, Exp6 렌즈부터):** 정본 `ValidationRegistry.validationRequest(validatorAddress, agentId, …)` 는 **무허가**다 — 누구든 아무 agentId 에 자기 자신을 validator 로 등록하고 `validationResponse` 로 스스로 점수를 기록할 수 있다(레지스트리는 `msg.sender == v.validator` 만 검사). 렌즈 `_tally` 는 validator 를 보지 않았으므로 제3자가 100점 10건을 꽂으면 `creditScore = (100, 10)`, `requiredBondBp = 5000`(신참 할증 우회) 이 되고, "abstain" 을 꽂으면 기권률이 왜곡됐다. **담보 없는 응답이 담보 이력으로 둔갑** — 렌즈의 전제('담보 이력 = 신용')를 깨는 구멍이며 §13 수리 전에도 있었다. 가해자 비용은 gas 뿐(자기 agentId 든 남의 agentId 든 가능 — 남의 점수를 낮추는 방향도 됨: 0점 다수 꽂기).
- **수리:** `_tally(uint256 agentId, address validator)` — `getValidationStatus` 가 이미 돌려주는 validator 를 받아 `if (!responded || v != validator) continue;`(`ReputationLens.sol:55`). 호출자(`creditScore`·`abstainRateBp`)는 `address(bonded)` 를 넘긴다 — `BondedValidator.requestValidation` 이 `validationRequest(address(this), …)` 로 등록하므로 담보가 걸린 요청은 정확히 validator == bonded 인 것뿐. 외부호출 수 불변(추가 읽기 없음). 정본 레지스트리 무수정.
- **회귀(Forge, `Exp30Lapse.t.sol` `test_R8_lens_ignores_other_validator_responses`):** 제3자가 aidD 에 자기 자신을 validator 로 15건 등록·응답(100점 10 + "abstain" 5) → 레지스트리 순진 `getSummary` 는 (15, 66) 으로 **세지만** 렌즈는 (0, 0)·15000bp·기권률 0; 이어서 담보 주장 100점 1 + 담보 기권 1 → 렌즈 (100, 1)·15000bp·기권률 5000bp(1/2) — 제3자 15건 무시, 담보 회계 무손실. 필터 전 렌즈로는 1단계에서 `answered` 가 10 이 되어 실패한다 — 필터 줄만 지운 프로브 실행으로 확인(`[FAIL: foreign validator counted]`, 14.8.4-6).
- **그대로 통과해야 하는 것(전부 확인):** `ReputationLensTest` **5/5** · `JudgePanelV2Test` **7/7**(disputed 중립 2건 포함) · `exp6/run_exp6.py` 재실행 **K1·K2 PASS**, 렌즈 수치(honest 100/100건/5000bp · extractor 100/84건/기권 1600bp/5000bp · hallucinator 50/100건/10000bp)·담보 궤적·순진 평판 **수리 전(같은 날 HEAD bd9bc19 재실행)과 바이트 동일** — Exp6 는 validator 가 BV 하나뿐이라 필터가 결과를 바꿀 이유가 없고 실측도 그렇다(`logs/exp6-rerun-closeout.log`; `exp6/out/results.json` 은 gitignore).

#### 14.8.3 (3)(4) 문서 정정·한계

- **(3)** §4 R8·§12.3 라인 참조 stale → 14.8.1 행 12·13. 정정표에 R8 행이 없던 것 → 행 12~14 로 보충.
- **(4) 그리핑 단가 '5배' 추정은 미측정.** 논의 과정에서 나온 '그리핑 라운드당 비용이 정직 이용 대비 약 5배' 류의 단가 추정은 **어떤 실험도 재지 않았고, 이 브랜치 어디에도 실측·산식 근거가 없다**(§11.2 K4(b) 가 잰 것은 장악·시한 평결 그리핑의 **토큰 순수입**(−1 wei / 0)이지 그리핑 **단가**(가스 + perCaseBond·수수료 잠금 기회비용 + 결의(decoy) 수수료, §12.6-A② 24라운드 경로)가 아니다). 대외 자료·백서·ERC 초안에 그 배수를 인용하지 말 것. 재려면 Forge 에서 §12.6-A② 경로(결의 3건 + 거짓 주장 개설·리셋 × 24)의 가스·수수료·잠금 시간을 라운드별로 적산하는 프로브가 필요 — 별도 작업.

#### 14.8.4 이번 실행 (코드 변경 후 전량 재실행 · forge 1.7.1 · halmos 0.3.3 · `forge clean` 후 halmos)

| 순서 | 도구 | 결과 | 로그 |
|---|---|---|---|
| 1 | `forge test` (10 suites) | **93 tests: 93 passed · 0 failed**(기존 92 − 실패 1 정정 + 회귀 1 신규) — `Exp30LapseTest` 24/24 · `ReputationLensTest` 5/5 · `JudgePanelV2Test` 7/7 · 그 외 v0.2.1 57 | `logs/forge-test-closeout.log` |
| 2 | `python3 exp6/run_exp6.py` (anvil 8549 · forge create) 수리 전·후 각 1회 | **K1 PASS · K2 PASS**, 렌즈·담보·평판 수치 전후 동일 | `logs/exp6-rerun-closeout.log` |
| 3 | `forge clean` → `halmos --contract BondedValidatorV3Proofs` | **10 passed · 0 failed** · 1.82s | `logs/halmos-bv3-closeout.log` |
| 4 | `halmos --contract BondedJudgePanelV3Proofs --loop 33` | **9 passed · 0 failed** · 248.85s (PB 경로 1,077 · PC 17 — 실행 간 변동, 판정 불변) | `logs/halmos-panel3-closeout.log` |
| 5 | `halmos --contract BondedValidatorProofs`(v0.2.1 회귀) | **4 passed · 0 failed** · 1.01s | `logs/halmos-bv021-regression-closeout.log` |
| 6 | 프로브: `_tally` 의 `|| v != validator` 를 잠시 제거 → `forge test --mt test_R8_lens_ignores_other_validator_responses` → 소스 원복 | **[FAIL: foreign validator counted]** — 필터 없는 렌즈로는 회귀가 실제로 실패함을 실행으로 확인(소스는 원복, diff 동일) | `logs/lens-nofilter-probe-closeout.log` |

Halmos 대상 3종은 렌즈를 import 하지 않으므로 '§14.4 와 동일' 이 기대값이다(경로 수는 실행 간 변동 — §14.1-3). `cache/solidity-files-cache.json` 은 HEAD 로 복원(도구 부산물, 커밋 제외).

#### 14.8.5 §5 무수정 증빙

`sed -n '132,153p' exp30/EXP30.md | shasum -a 256` = `37a02f2b1af0d121a7213f7b4296e1f845886e87c473bed052f5253d69c2472b` — §14.5 와 동일(이 소절 추가 전·후 재대조). `git diff bd9bc19 -- exp30/EXP30.md` 는 파일 끝 삽입 hunk 1개, 삭제 0행.

#### 14.8.6 정직한 한계

1. **렌즈는 이제 `bonded` 하나의 이력만 본다.** 같은 레지스트리·같은 agentId 에 다른 BondedValidator(예: Sepolia v0.2.1 `BondedValidator` 와 v0.3 `BondedValidatorV3`)가 쌓은 담보 이력은 **합산되지 않는다** — v0.3 재배포(결재 ②) 후 새 렌즈는 이력 0 에서 시작하고 기존 에이전트는 다시 신참 할증(15000bp)을 받는다. 담보 없는 응답을 걷어내는 대가이며, 다중 BV 이력 승계(허용 validator 집합)는 렌즈 설계 변경 = 별도 심의. 지금은 필터가 없는 쪽이 더 큰 구멍(14.8.2)이라 단일 validator 를 택했다.
2. **가스 미재측정.** 필터는 이미 읽던 반환값 비교 1회라 외부호출·슬롯 수 불변이나, §13.4 프로브(`_GasProbe.t.sol`, 미커밋)를 다시 돌리지 않았다 — 수치는 §13.4 그대로 인용하되 '필터 전 측정' 임을 안다.
3. 필터 전 렌즈로 회귀가 실패하는 것은 프로브(14.8.4-6)로 확인했으나 프로브 소스는 커밋하지 않았다 — 재현은 `_tally` 의 `|| v != validator` 를 지우고 `forge test --mt ignores_other_validator`.
4. **'5배' 의 출처를 이 저장소에서 찾지 못했다**(`grep '5배'` 0건 — 검색된 것은 신참 할증 1.5× 뿐). 논의 메모의 추정치로 보이며, 14.8.3-(4) 는 '무근거 수치 인용 금지' 한계 명기이지 그 수치의 반박이나 확인이 아니다.
5. §11·§12·§13 원문과 §14.1~14.7 의 '91 passed · 1 failed'·'상위 결정 대기' 문구는 시점 기록으로 남는다(원문 자리 정정 아님 — §14.6-1 과 같은 원칙). `results.json`·ERC 초안·백서는 이번에도 무수정.
6. Halmos 는 렌즈를 증명하지 않는다(§13.5-2 그대로) — validator 필터의 ∀ 성질(모든 비-bonded 응답이 무시됨)은 코드 한 줄의 검토와 Forge 실측 1건뿐.
7. main 무수정·Sepolia 미배포·미푸시. 결재 ①② 는 여전히 열려 있다(§12.7). 이 마감으로 Exp30 브랜치의 열림 항목은 결재 대기만 남는다.

#### 14.8.7 재현

```bash
cd ~/iis-lab && git checkout exp30-liveness && cd exp3/contracts
forge test                                                        # 93 tests: 93 passed
forge test --mt test_R8_lens                                      # R8 4건(정정 1·회귀 3)
cd ../.. && python3 exp6/run_exp6.py                              # VERDICT K1·K2 True (anvil 8549, numpy·matplotlib 필요)
cd exp3/contracts && forge clean && ../../.venv-halmos/bin/halmos --contract BondedValidatorV3Proofs   # 10 passed
../../.venv-halmos/bin/halmos --contract BondedJudgePanelV3Proofs --loop 33                          # 9 passed (~4 min)
../../.venv-halmos/bin/halmos --contract BondedValidatorProofs                                       # 4 passed
git checkout -- exp3/contracts/cache/solidity-files-cache.json    # 도구 부산물 복원
```

## 15. 정본 이식·K1 재실행 (2026-09-03 · `main` · 오너 결재 ① 승인 후)

오너 결재(2026-09-03, "추천방향대로"): **① 소멸 규칙 채택 · ② v0.3 Sepolia 재배포(W 는 실측 후 하한 규칙으로 확정)** 승인. 이 소절은 ① 의 실행 — §4 R1~R12 의 정본 이식(브랜치 → `main`)과 §5 K1 원문("정본 이식 후 … 전부 PASS")의 재판정만 다룬다. ② 는 별도 작업(15.4-1).

### 15.1 이식 — `git merge exp30-liveness` → `main`

| 항목 | 값 |
|---|---|
| 브랜치 HEAD | `e49c67d` (base `83012fa`) |
| main HEAD(병합 전) | `8c6124e` (base 이후 REPRODUCTION.md 경로 정정 1커밋) |
| **병합 커밋** | **`426b555`** (`병합: exp30-liveness → main — Exp30 소멸(Optimistic Lapse) 규칙 정본 이식 (오너 결재 ① 2026-09-03)`) |
| 충돌 | **1파일 `REPRODUCTION.md`:88~90** — main 쪽 `.venv-halmos` 경로·`python3` 정정 vs 브랜치 쪽 `93 tests` 주석·Exp30 v0.3 재현 블록(`forge clean` 경고 포함). **양쪽 모두 보존**(halmos 줄은 `.venv-halmos`, forge test 줄은 브랜치 주석, Exp30 블록 전체 유지). 코드 충돌 **0** |
| 동일성 | `git diff --stat exp30-liveness 426b555 -- exp30/ exp3/ docs/ xverify.py` **빈 출력** — 계약·테스트·문서·로그 전부 브랜치와 바이트 동일 |
| §5 무수정 | `sed -n '132,153p' exp30/EXP30.md \| shasum -a 256` = `37a02f2b1af0d121a7213f7b4296e1f845886e87c473bed052f5253d69c2472b` — §14.5·§14.8.5 와 동일(이 소절 추가 전·후 재대조) |

### 15.2 K1 재실행 (`main` `426b555` · forge 1.7.1 · halmos 0.3.3 · `forge clean` 후 halmos · 2026-09-03 07:26~07:31 AEST = UTC 09-02 21:26~21:31)

| 순서 | 도구 | 결과 | 로그 |
|---|---|---|---|
| 1 | `forge test` (10 suites) | **93 tests: 93 passed · 0 failed · 0 skipped** — v0.2.1 기존 69(ServiceVoucher 4 · ZkVerdictGate 6 · JudgePanelV2 7 · BondedJudgePanelV2 9 · BondManager 8 · JudgePanel 7 · BondedJudgePanel 15 · ReputationLens 5 · BondedValidator 8) + `Exp30LapseTest` 24 | `logs/forge-test-main-k1.log` |
| 2 | `forge clean` → `halmos --contract BondedValidatorV3Proofs` | **10 passed · 0 failed** · 1.77s — T1~T4 + L1·L2·L3·L4·L5a·L5b (K1-(a)) | `logs/halmos-BondedValidatorV3Proofs-main-k1.log` |
| 3 | `halmos --contract BondedJudgePanelV3Proofs --loop 33` | **9 passed · 0 failed** · 257.88s — PA·PB·PC·P4 + PL1a·PL1b·PL2·PL3a·PL3b (K1-(b)); PB 경로 1,104(246.55s) · PC 17 | `logs/halmos-BondedJudgePanelV3Proofs-main-k1.log` |
| 4 | `halmos --contract BondedValidatorProofs` (v0.2.1 회귀) | **4 passed · 0 failed** · 2.24s — T1~T4 | `logs/halmos-BondedValidatorProofs-main-k1.log` |
| 5 | `halmos --contract ServiceVoucherProofs` (Exp17 회귀) | **7 passed · 0 failed** · 0.29s — K1×3·K2×2·K3×2 | `logs/halmos-ServiceVoucherProofs-main-k1.log` |
| 6 | `halmos --contract ZkVerdictGateProofs` (Exp20 회귀) | **5 passed · 0 failed** · 0.43s — K1·K2·K2b·K3·K4 | `logs/halmos-ZkVerdictGateProofs-main-k1.log` |

- 종료 코드 6건 전부 0 — `logs/main-k1-run-header.log`(HEAD·도구 버전·타임스탬프 박제).
- 컴파일: `forge test` 가 29 파일 컴파일 → `forge clean` → 첫 halmos(2번)가 `--ast` 로 29 파일 재컴파일, 이후 4회는 "No files changed"(halmos 자기 산출물 재사용) — `KeyError: 'ast'` **0건**, `No tests` 0건(REPRODUCTION.md 의 `forge clean` 경고가 이번에도 유효했음을 확인).
- 4~6 은 K1 원문(§5)에 없는 **추가 회귀**(팀장 요청) — 정본 v0.2.1 증명 3종이 V3 이식으로 깨지지 않았음을 본다.

### 15.3 K1 판정 (§5 원문 무수정 기준)

| K1 조항 | 원문 조건 | 실측 | 판정 |
|---|---|---|---|
| (a) | `halmos --contract BondedValidatorV3Proofs` — T1~T4 회귀(단언 무수정) + L1~L5 전부 PASS | 10/10, 반례 0 | **PASS** |
| (b) | `halmos --contract BondedJudgePanelV3Proofs --loop 33` — PA/PB/PC/P4 회귀 + PL1·PL2·PL3 PASS | 9/9, 반례 0, timeout 0 | **PASS** |
| (c) | `forge test` — 기존 69 + 신규 ≥ 12, 0 fail | 69 + 24, 0 fail | **PASS** |

**K1 = PASS.** FAIL·counterexample·timeout 0건, 파라미터 조정 0건. 브랜치 시점(§11.2·§12.5·§14.8.4)과 판정 동일 — 병합이 코드를 바꾸지 않았으므로 기대값 그대로다. K1 원문의 '정본 이식 후' 조건이 이제 충족됐다(브랜치 시점 판정은 '이식 전'이었음, §11.2).

### 15.4 정직한 한계

1. **이 소절은 K1 만이다.** K2(c)(Sepolia v0.3 실주장 소멸·리셋 후 소멸)는 결재 ② 의 실행 = **별도 작업**이며 이 소절 시점 **미배포**. K3·K4·z3/cvc5·Exp6 재실행(`prove.py`·`xverify.py`·`sim.py`·`run_exp6.py`)은 하지 않았다 — 병합이 계약·스크립트를 바이트 하나 바꾸지 않았으므로(15.1 동일성) 브랜치 시점 결과(§11.2·§12.4·§14.8.4)가 그대로 성립한다고 보지만, `main` 에서의 재실측은 아니다.
2. Halmos 경로 수는 실행 간 변동(PB 1,052/1,066/1,049/1,077 → 1,104; §14.1-3) — 판정 불변, 시간 257.88s 는 기록 중 최장.
3. `REPRODUCTION.md:88` 주석 "93 tests … on branch exp30-liveness" 는 병합으로 `main` 에도 해당하나 문구는 충돌 해결 원칙(양쪽 보존·재서술 금지)대로 그대로 둠.
4. 원격 **미푸시**(오너가 한다). `main` 은 로컬에서만 전진. 브랜치 `exp30-liveness` 는 삭제하지 않았다.
5. 렌즈(`ReputationLens`)는 여전히 Halmos 대상이 아니다(§13.5-2·§14.8.6-6) — K1 은 렌즈를 증명하지 않는다.
6. `exp3/contracts/cache/solidity-files-cache.json` 은 도구 부산물이라 HEAD 로 복원(커밋 제외). 이 소절과 로그 7건(`*-main-k1.log`)의 커밋은 `426b555` 바로 다음 `main` 커밋이다(`git log --oneline -2`).

### 15.5 재현

```bash
cd ~/iis-lab && git checkout main && git log --oneline -1 426b555      # 병합 커밋 확인
git diff --stat exp30-liveness 426b555 -- exp30/ exp3/ docs/ xverify.py # 빈 출력 = 브랜치와 동일
cd exp3/contracts && forge test                                          # 93 tests: 93 passed
forge clean && ../../.venv-halmos/bin/halmos --contract BondedValidatorV3Proofs               # 10 passed
../../.venv-halmos/bin/halmos --contract BondedJudgePanelV3Proofs --loop 33                  # 9 passed (~4 min)
../../.venv-halmos/bin/halmos --contract BondedValidatorProofs                               # 4 passed
../../.venv-halmos/bin/halmos --contract ServiceVoucherProofs                                # 7 passed
../../.venv-halmos/bin/halmos --contract ZkVerdictGateProofs                                 # 5 passed
git checkout -- exp3/contracts/cache/solidity-files-cache.json         # 도구 부산물 복원
```

## 16. K2(c) 진행 — v0.3 Sepolia 배포·실주장 1건 미개설 (2026-09-03 · `main` · 오너 결재 ② 실행)

오너 결재 ②("v0.3 Sepolia 재배포, W 는 실측 후 하한 규칙으로 확정")의 실행. §15 K1 PASS(`main` `5f156d1`)를 전제로 v0.3 쌍을 Sepolia 에 배포하고, §5 K2(c) 첫 문장("실주장 1건 미개설 → W 경과 → 제3자 EOA `settleUnchallenged` 성공")의 **전반부(주장 생성·미개설)만** 실행했다. W 경과 후의 `settleUnchallenged` 와 둘째 문장(W−60 s 개설·풀 0·리셋 후 소멸)은 별도 실행이다(16.4). 메인넷 배포 없음. LabToken 은 기존 무가치 토큰 재사용.

### 16.1 W 확정 — 하한 규칙 W ≥ k·D + voteTimeout (실측 2026-09-02 21:27~21:30 UTC · 팀 입력 데이터)

| 체인 | 포함 지연 D | 근거(요약) |
|---|---|---|
| Ethereum L1(Sepolia) 정상 | 24 s (1~3 슬롯) | 공개 RPC 실측: 최근 1,000 블록 평균 12.24 s/블록(누락 슬롯 ≈20), 200 블록 연속 최대 간격 24 s. Sepolia 는 허가형 검증자 집합 — 메인넷 MEV-Boost 검열 구조가 그대로 적용되지 않음 |
| Ethereum L1 검열 시나리오(메인넷 데이터, 확률적) | 348 s | L1 에 강제포함 프로토콜 없음(FOCIL/EIP-7805 Draft, 2026 미가동). 비검열 제안자 1명이면 포함 → P(n 슬롯 초과)=cⁿ: 2023 정점 c=0.72 → 99.99 % 29 슬롯 = 348 s (mevwatch 2026-09-02 24 h c=0.274 → 8 슬롯 96 s; c=0.95 가정 → 2,160 s) |
| **Ethereum L1 보수적 상한(라이브니스 사고)** | **23,400 s** | 머지 이후 최악의 L1 포함 정지: Sepolia Pectra 사고 2025-03-05 — 빈 블록만 3.5 h, 전 노드 수정까지 ≈6.5 h(EF 블로그·van der Wijden 회고). 메인넷 참고 2023-05 파이널리티 지연 25~64 min 은 블록 생산 지속. 원인은 Sepolia 전용 설정이라 메인넷 재현 불가 — 그래도 **D_L1 로 채택** |
| Arbitrum One / Arbitrum Sepolia | 86,400 s | SequencerInbox `maxTimeVariation = (7200, 64, 86400, 768)` 온체인 실측(2026-09-02), `forceInclusion` 은 블록 조건(7,200 L1 블록 ≈ 86,400~88,128 s), delayBuffer 는 시퀀서 오작동 뒤에만 창 단축. 시퀀서가 L2 `block.timestamp` 를 −86,400~+768 s 범위에서 배정 가능 → L2 에서 W 를 timestamp 로 재면 최대 24 h 왜곡(k ≥ 2 근거) |
| OP Mainnet (OP Stack) | 43,200 s | superchain-registry `op.toml` `seq_window_size = 3600` L1 블록 × 12 s(누락 슬롯 반영 ≈44,000 s); 표준 체인 요건 [3600, 3600] |
| Base (OP Stack) | 43,200 s | 같은 표준 파라미터 — **입력 데이터가 이 행에서 절단돼 수치만 수신, 근거 원문 미확인** |

계산: k = 2, D = D_L1 = 23,400 s, voteTimeout = 3,600 s → **W ≥ 50,400 s**. 잠정값 86,400 s(§4 R9 · §12.7)가 하한을 만족(여유 36,000 s = 10 h, D_L1 의 1.54 배)하므로 **W = 86,400 s 로 확정**. 규칙이 86,400 을 산출한 것이 아니라 잠정값이 하한 검사를 통과한 것이다 — 더 작은 W(예 50,400 s)도 규칙상 가능했으나 (i) 인간 도전자의 하루 주기, (ii) `disputeTimeout` 과 동일값의 단순성을 이유로 잠정값을 유지했다.
**L2 금지:** 같은 규칙으로 Arbitrum 은 W ≥ 176,400 s, OP Stack 은 W ≥ 90,000 s — 86,400 s 는 둘 다 미달. W 는 immutable 이므로 이 배포본을 L2 에 그대로 올리면 안 되고, L2 는 별도 W 로 새 배포가 필요하다(deployments.md v0.3 절에 동일 명기).

### 16.2 배포 (`main` `5f156d1` · forge 1.7.1 · solc 0.8.28 · optimizer 200 · 2026-09-02 21:40 UTC = 09-03 07:40 AEST · `logs/sepolia-v03-deploy.log`)

| 항목 | 값 |
|---|---|
| 배포자 | `0x47b3FB71726e9AA8b121C4bA5649f4Bff8dd9FD1` (docs/sepolia-deployer-address.txt · nonce 8 → 10) — 키는 Keychain, 값은 어디에도 기록하지 않음 |
| BondedValidatorV3 | **`0xd881d52F10220687297651DeC4d55C1644d3a2A7`** · tx `0xd36c6db949ca47be78acfe1f6e34836e34fe32f0e667988a59876822715d5731` (nonce 8) |
| BondedJudgePanelV3 | **`0xfDf23d7B16462795659Acd4b2d40d81E842Aa18E`** · tx `0xd7829f6dc8e808acb81524be6f08689e3003ad16b7ec851b189112f400be8d72` (nonce 9, CREATE 예측 주소 = 실제 주소) |
| 결합 확인 | `validator.judge() == panel` · `panel.bonded() == validator` · `panel.token() == LabToken` (배포 직후 읽기) |
| 재사용 | LabToken `0x236781293F7387292F1cc0a674c607b2aCF35fec` · IdentityRegistry `0x784B1238EB74Efe1AF8bD8cf358B613f799D8f28` · ValidationRegistry `0x6e44ADBa5CCc034a372A00c4c9eaBC7deE5e5aB5` (v0) |
| 생성자 | validator `(token, idReg, valReg, judge = panel, minBondPerClaim 1e18, unbondDelay 3600, challengeWindow 86400)` · panel `(validator, perCaseBond 10e18, judgeFee 1e18, voteTimeout 3600, disputeTimeout 86400, veteranThreshold 3)` · `SEED_WINDOW` 256 상수 — 배포 후 전부 읽기 대조 일치 |
| Sourcify | 둘 다 **exact_match**(creation · runtime, 2026-09-02T21:41:51Z / :52Z) — `logs/sepolia-v03-sourcify.log` |
| 특권 키 | 0 (v0.2 와 동일 — 오너 함수 없음) |
| 가스 단가 | 0.94 gwei 시점, 배포자 잔액 0.0386 → 0.0330 ETH(Sepolia) |

### 16.3 K2(c) 전반부 — 실주장 1건 미개설 (`logs/sepolia-v03-k2c-start.log`)

| 순서 | tx | 블록 | 내용 |
|---|---|---|---|
| 1 | `0xc4e14de63d73b85e7fcdb06d28ae4368fbe179005f102043a35c94d123b13a74` | 11622281 | `LabToken.mint(배포자, 1e18)` — minter = 배포자 |
| 2 | `0x0bab34db936a353459ca354df1d6022e37feb4fc01d9242f19ad02841342eb86` | 11622282 | `IdentityRegistry.register("agent://exp30-k2c")` → **agentId 1** (이 Sepolia 레지스트리의 첫 등록 — v0·v0.2 실측은 Anvil 이었음) |
| 3 | `0x634e98de43e5da1569b0d0837802f786d44503f6ffb9deea674564260f32e34f` | 11622283 | `approve(validator, 1e18)` |
| 4 | `0x5547dd8020b2552dbbf137dbd115f8573ba0301cd52008fc8ecb9328cc27841a` | 11622285 | `stake(1, 1e18)` |
| 5 | **`0x249d2bce2f09a122e371bcee34225b4e8e3a60d218078fcb119f333fb6093a42`** | **11622286** | `requestValidation(1, "agent://exp30-k2c/claim-1", h)` · **h = keccak256("exp30-k2c-claim-1-2026-09-03") = `0xa4f55aa9d15b3847884b887662e1b9562f3c96abb2453abeef6a9fcec9579740`** · gas 290,734 |

읽기 확인(21:44:49Z): `claimExists = true` · `engaged = false` · `claimSettled = false` · `windowOpen = true` · `claimAgent = 1` · `agents[1] = (bonded 1e18, atRisk 1e18, unlockAt 0, slashedTotal 0)` · `freeBond = 0` · `valReg.vals[h] = (validator = BV3, agentId 1, exists, !responded)`.

**claimedAt = 1788385464 = 2026-09-02T21:44:24Z** (블록 11622286 timestamp 와 동일).
**소멸 가능 시각 = claimedAt + W = 1788471864 = 2026-09-03T21:44:24Z** (AEST 09-04 07:44:24). 그 전에는 `settleUnchallenged(h)` 가 `'window open'` 으로 되돌려진다(R4 · `windowOpen` 엄격 부등호 — 경계 초 1788471864 자체는 '닫힘'); 그 시각 이상의 timestamp 를 가진 블록부터 누구든 호출 가능.

### 16.4 다음 실행 (별도 — 이 소절에서 하지 않은 것)

1. **2026-09-03T21:44:24Z 이후**: **제3자 EOA**(배포자·에이전트 지갑이 아닌 주소 — K2(c) 원문 '제3자 EOA')로 `settleUnchallenged(0xa4f5…9740)` → 기대: status 1 · `ClaimLapsed(h)` · `ClaimSettled(1, h, 50, false, false)` · valReg (50, "unchallenged") · `agents[1].atRisk = 0` · `bonded` 1e18 불변 · 토큰 이동 0(K4-a). **제3자 EOA 는 아직 없다** — 오너가 지정하거나 새 EOA 에 가스만 넣어야 하며, 이 작업에서는 만들지 않았다.
2. K2(c) 후반부: 실주장 2건째 → W−60 s 에 `openCase`(judgeFee 1e18 필요 · 판정자 풀 0) → voteTimeout 후 `resolveTimeout`(Committed 시한 → `_resetCommit`: 사건 삭제·수수료 반환·`disengage`) → 창 닫힘 후 소멸. 미착수.
3. 1·2 의 tx 해시·이벤트로 §5 K2(c) 판정 → §16 추가 소절.

### 16.5 정직한 한계

1. 이 소절은 K2(c) 의 **전반부(주장 생성)만** — 소멸 tx 는 아직 없다. K2 는 여전히 **PARTIAL**(§12.5 그대로).
2. 실주장의 에이전트 지갑 = 배포자 EOA(자기 등록·자기 스테이크). 실 에이전트가 아닌 배포자의 시연 주장이다. K2(c) 는 '소멸이 무허가·무손실로 성립하는가'를 재므로 주장자 신원은 판정과 무관하지만 명기한다.
3. W 하한 규칙의 D_L1 은 Sepolia 전용 사고 값이라 메인넷 대표값이 아니고, 메인넷 검열은 확률적(c 의존)이라 '상한'이 없다 — 하한 규칙은 관측치 위의 보수적 근사이지 증명이 아니다. Sepolia 정상 포함(24 s)만 놓고 보면 W 는 3,600 배 과잉이다.
4. W 는 immutable — Sepolia EOL(2026-09-30 예정) 이후 재배포 시 재실측·재확정 필요. L2 는 이 배포본 금지(16.1).
5. Base 행은 입력 절단으로 수치(43,200 s)만 받았다(16.1 표).
6. 판정자 풀 0 — 아직 아무 판정자도 v0.3 패널에 `registerJudge` 하지 않았다. 따라서 이 주장은 실제로 도전 확률 q ≈ 0 조건에서 소멸을 기다린다(§12.6 '억지력은 q 조건부' 한계의 실측 그 자체).
7. Sourcify 만 검증(v0.2.1 과 동일). Etherscan 은 API 키 없이 미제출.
8. 원격 미푸시(오너). `exp3/contracts/cache/solidity-files-cache.json` 은 도구 부산물이라 HEAD 복원.

### 16.6 재현

```bash
RPC=https://ethereum-sepolia-rpc.publicnode.com
BV3=0xd881d52F10220687297651DeC4d55C1644d3a2A7; PANEL=0xfDf23d7B16462795659Acd4b2d40d81E842Aa18E
H=0xa4f55aa9d15b3847884b887662e1b9562f3c96abb2453abeef6a9fcec9579740
cast call $BV3 "judge()(address)" --rpc-url $RPC                 # == $PANEL
cast call $PANEL "bonded()(address)" --rpc-url $RPC              # == $BV3
cast call $BV3 "challengeWindow()(uint256)" --rpc-url $RPC       # 86400
cast call $BV3 "claimedAt(bytes32)(uint64)" $H --rpc-url $RPC    # 1788385464
cast call $BV3 "windowOpen(bytes32)(bool)" $H --rpc-url $RPC     # true (timestamp < 1788471864) / false 이후
curl -s https://sourcify.dev/server/v2/contract/11155111/$BV3 | python3 -c "import sys,json;print(json.load(sys.stdin)['match'])"   # exact_match
# 소멸(1788471864 이후 · 제3자 EOA · 키는 명령줄에 남기지 말 것):
# cast send $BV3 "settleUnchallenged(bytes32)" $H --rpc-url $RPC --private-key "$(security find-generic-password -a <third-party-item> -w)"
```

### 16.7 K2(c) 후반 준비 완료 (2026-09-03 14:57 AEST)
- 제3자 EOA: `0xd9E90164623bFe77d7DfE008d21032943808bb79` (keys/exp30-k2c-thirdparty 키스토어, gitignore) — 배포자 `0x47b3…9FD1`과 다른 주소. 가스 충전 0.005 ETH: tx `0x49bad71823ec361114823839072173f6895edcb8123be6f75ec9b56866526c25` (status 1).
- 호출 스크립트 `exp30/k2c_settle.sh` (키 값 미출력, `dry` 모드는 cast call만). 드라이런 2026-09-03T04:56:50Z: chain ts 1788411408 < lapse_at 1788471864 → `window open` revert 확인(정상).
- 예약 실행: launchd `com.iislab.exp30-k2c-settle` 2026-09-04 07:50 AEST(= 소멸 가능 시각 +6분) → 로그 `exp30/logs/sepolia-v03-k2c-settle.log`. 실패 시 수동 재실행 `zsh exp30/k2c_settle.sh run`.
- 미착수: K2(c) 2건째(W−60s 개설·풀0·resolveTimeout 리셋→소멸)는 판정자 풀 0 상태를 만들어야 하므로 별도 실행 계획 필요.

### 16.8 K2(c) 1건째 결과 — 확정 (2026-09-03T21:50:04Z, 예약대로 자동 실행)

**독립 재확인(방금, 원본 실행 로그와 별개로 cast 직접 조회):**
- `claimSettled(H) == true`
- tx `0x29b03cec6b46ceabf56ecf9a0bb57b06995157a19e1e8311ba3e9b2cb54b4773` — status **1(success)**, block 11629268
- `from = 0xd9E90164623bFe77d7DfE008d21032943808bb79`(제3자 EOA, 배포자와 다른 주소) → `to = BondedValidatorV3`
- 로그 3건: `ClaimLapsed`(tag "unchallenged") + 정산 이벤트 2건. 실행 로그(`exp30/logs/sepolia-v03-k2c-settle.log`)의 드라이런(2026-09-03T04:56:50Z, chain ts 1788411408 < lapse_at 1788471864 → "window open" revert)과 실행(21:50:04Z, chain ts 1788472200 > lapse_at → 성공)이 예상대로 갈렸다.

**K2(c) 1건째 사전등록 판정: PASS.** "실주장 1건 미개설 → W 후 제3자 EOA settleUnchallenged 성공(tx 해시·ClaimLapsed)" — 스크립트가 아니라 launchd 자동 스케줄로 사람 개입 없이 재현. 무허가 정산이 설계대로 동작함을 실제 메인넷급 조건(Sepolia, 진짜 가스, 진짜 서명)에서 확인.

**미착수 그대로:** K2(c) 2건째(W−60s 개설·풀0·resolveTimeout 리셋→소멸)는 판정자 풀을 인위적으로 0으로 만들어야 해서 별도 스크립트 필요.
