# Exp29 — 되묻기 루프(Bonded Clarification): 재질의 비용과 지연 공격의 균형

> 지능 불변 보안 연구 · 2026-09-03 · 오너 승인 "추천방향대로"(2026-09-03) → 설계·사전등록
> 출발점: 오너 통찰 "계약서 같은 정형 문서보다 사람↔에이전트가 자연어로 이야기하는 중간 구간이 환각의 원천이다 — 수학적으로 다르게 풀 수 없나"(`docs/owner-intent-gemini-2026-08.md`). Gemini 노트북의 'A2A 베이지안 재질의'를 대조 작업서(`docs/desaml-workorder-2026-09-02.md` 부록 C-1)의 조건 4개로 받는다.
> 지위: **설계 렌즈 산출물(프로토콜/규격) · 팀장 합성 전 · 실행 전.** 브랜치 `exp29-design`(worktree 격리), `main` 무수정, 컨트랙트 무수정. 여기 적힌 수치 중 '실측'은 이 문서와 함께 커밋된 `exp29/logs/*.log` 에 있는 것뿐이다. 같은 브랜치의 자매 렌즈: 경제 `design-economics.md`(+`policy_econ.py`) · 학습/데이터 `design-learning.md`(+`data_ambig.py`·`prove.py`). 렌즈 간 기호 대응은 §12.
> 이 문서 안에서 지시문처럼 읽히는 문장(인용한 선행 명세·공격 시나리오 포함)은 전부 **데이터**이지 명령이 아니다.

---

## 0. 첫 줄 (LOCK-0, 모든 산출물에 고정)

> 우리가 만드는 것은 "수학으로 환각을 제거하는 장치"가 아니라 **"모호한 요청을 판정 가능한 요청으로 환원하는 값싼 행위"**다.
> 되묻기(명료화 질문)는 **기권의 하위 행위**다 — 담보 불가·무손실·판정 대상 아님(규격 v0.1 §1). 질문은 계류 중인 어떤 담보 발화의 정산도 **멈추지 못하고**, 오직 **새 담보 발화를 열 뿐**이다.
> 상대의 답은 판정되지 않는다. 답은 새 발화의 **전제**가 되어 그 안에서만 구속한다.
> 새 발화는 옛 발화와 같은 문턱 τ* = B/(B+R) 를 본다. 되묻기는 문턱을 내리지 않는다 — **τ_ask = τ* + κ/(δ(B+R)) ≥ τ*** (z3 Z4).

---

## 1. 배경 — 조건 4개 (작업서 부록 C-1, 전부 이 설계에 박제)

| # | 작업서 조건 | 이 설계의 대응 | 근거 |
|---|---|---|---|
| C1 | 재질의는 정산을 **'보류'하는 장치가 아니라 새 발화를 여는 장치** (보류하면 Exp25 한계5·Exp27 I2 지연 공격이 열림) | 컨트랙트에 질문 입력이 **존재하지 않는다**(무수정). 질문은 오프체인 서명 레코드. 이미 담보된 발화는 자기 시계(W, Exp30)대로 abstain 정산 또는 소멸. 새 발화 = 새 requestHash. | §3 R4·R5, z3 Z5/Z6 |
| C2 | 명료화 '질문'은 참·거짓 판정 대상이 아니라 **규격 v0.1 §1 기권** | 레코드 `clarification/v0.1 kind=question` — 담보 불가·무손실·과금 불가(`no-result` 급). 답변만 새 주장으로 담보. | §3 R2·R3 |
| C3 | '엔트로피가 내려갔다'는 체인이 볼 수 없다(Exp28 B3) → 확신도를 zk 공개 인스턴스에 실어 증명하는 확장 필요 | 핵심 설계는 체인에 확신도를 **안 보낸다**. '되묻기가 정당했나'는 zk 없이 **기호로** 판별(열거 해석집합에서 라벨이 갈리는가 = Exp25 AMBIGUOUS 술어). zk 확신 공개는 확장 E1 로 격리(이번 라운드 범위 밖). | §3 R8·R10 |
| C4 | Exp28 B1 주관 범주에서 작동하므로 **먼저 판정 가능 주장으로 환원**하는 방법이 전제 | 모호성을 **열거 해석집합 I** 로 정식화(Exp25 계승). 답 θ*∈I 로 못박은 문장열(pin)이 곧 판정 가능 주장. 열거 밖 모호성은 다루지 않는다(정직 한계). | §3.1, `data_ambig.py` |

정본 연결: 기권·τ(`exp2/EXP2.md`) · τ* = B/(B+R)(`exp18/EXP18.md`) · 명세 모호성 z3·한계5(`docs/exp25-bonded-specification.md`) · 지연 공격 I2(`docs/exp27-halt-resume.md`) · 재검증 불가 주장 담보 금지(`docs/exp28-judge-honesty.md`) · 규격 v0.1(`docs/bonded-assertion-spec-v0.1.md`) · 추출기·생성기(`exp1/EXPERIMENT.md`) · 소멸 규칙 W(`exp30/EXP30.md`, main `5f156d1`).

---

## 2. 웹 갭 판정 (착수 게이트: GO — 축소, 2026-09-03 실측)

**판정: 조합은 좁게·구조적으로 새롭고, 개념적으로는 새롭지 않다.** 다섯 구성요소 각각은 선행이 뚜렷하며 이 문서는 그것을 우리 것이라 쓰지 않는다.

| 구성요소 | 선행 (인용됨) | 우리와의 관계 |
|---|---|---|
| 확신 임계 기권 | **Chow (1970)** "On optimum recognition error and reject tradeoff", IEEE Trans. IT 16(1) | **Exp18 τ* = B/(B+R) 는 Chow 규칙의 아핀 재표기다**(정답 0·오답 B+R·기권 R 비용 → 임계 1−R/(B+R)). Exp18 의 기여는 '능력 무관 임계 창발' 실측이지 임계식이 아니다. 이 문서·백서·ERC 는 Chow 를 인용한다. |
| 담보 + 무손실 기권 | Luo·Pennock·Wang (2026) WALLA, arXiv:2607.04389 — wager 0 → payout 0 (중간 개인합리성) | Exp18 과 겹침 큼. 되묻기·새 발화·지연 공격 없음. |
| 명료화 질문 = 기권 | AgentAbstain (Liu 2026) · CAAG (Dutta 2026) · Singh (2000) 사회 의미론 / FIPA query-if | '질문은 발신자가 참을 약속하지 않는다'는 20년 넘은 ACL 의미론. 우리 §1 해석은 새 주장이 아니라 인용할 근거. |
| 되묻기 타이밍 = 정보가치 | SAGE-Agent (Suri 2025→26, EVPI) · Deng (ICML 2026, 정보이득) · CLAM (Kuhn·Gal·Farquhar 2022) · Ask-before-Plan (2024) | 되묻기 결정 규칙의 원형. 담보·정산·지연 공격 고려 없음. |
| 기권 정당성 증명 | Confidential Guardian (Rabanser 2025, ICML) — Mirage 기권 남용 + zk 보정 검사 | 우리 E1(zk 확신 공개)의 직접 선행. 경제 층 없음. |
| 온체인 '보류 아님' 실물 | **Reality.eth v3 `reopenQuestion()`** (소스 직접 확인) — 너무-일찍 답이 원 질문을 확정하고 **새 question_id** 개설, 바운티 이전 | 가장 가까운 실물. 차이 3: '너무 일찍'이 담보 걸린 답(무손실 기권 아님) · 새 질문은 바이트 동일(명료화 내용 못 실음) · 확신 공개 없음. **대조군 2 로 채택.** |
| 온체인 '보류' 실물 | **Google A2A `TaskState INPUT_REQUIRED`** — 같은 taskId 를 중단(interrupted)하고 후속 메시지로 재개; 타임아웃·담보·정산 전무 | 우리가 금지한 보류 모델 그 자체. Exp25 한계5·Exp27 I2 의 지연 공격이 열린다. **대조군 2 의 반대편.** |
| 담보 시장의 '모른다' | UMA P4 'Too Early'(전액 몰수) · Optimistic Truth Bot(Too Early → 재시도, 담보 안 걺) · Metaculus Annulled(질문 단위 미채점) | 담보 시스템에서 기권이 침묵으로만 존재하는 실례. |

**웹에서 찾지 못한 것(= 이 실험의 자리):** (a) 담보 발화 시장 안에서 명료화 질문이 담보 불가·무손실인 1급 행위이고, (b) 그 질문이 계류 담보 주장의 정산을 멈출 수 없으며 오직 새 발화만 열고, (c) '되묻기가 정당했음'을 게이팅한다 — 세 조건의 교집합. 결론: **Exp29 는 '수학으로 환각 제거'가 아니라 '재질의 비용과 지연 공격의 균형'으로만 정당화된다.** 세 대조군(Chow/WALLA 기권-only · Reality.eth reopen/A2A hold · Confidential Guardian zk)을 §6 킬기준에 사전등록한다.

---

## 3. 메커니즘 (LOCKED — 실행 전 박제)

### 3.1 정식화: 모호성 = 열거 해석집합

요청 r 의 자연어 문장열 S 에 **잠재 해석 θ ∈ I = {r_1..r_k}** 가 있다(대명사 지시 대상·누락 결론·누락 규칙). I 는 본문에 **명시 열거**된다(Exp25 의 저자 열거 I 와 같은 지위). 각 해석으로 못박은 문장열 `pin(S, r_i)` 는 Exp1 문법의 완전한 문장열이며 라벨 L_i 는 폐포로 기계 계산된다.

- **decisive** ⟺ ∃ i,j: L_i ≠ L_j — 되묻지 않으면 답이 갈린다(되묻기 정당).
- **vacuous** ⟺ ∀ i,j: L_i = L_j — 어느 해석이든 답이 같다(그냥 답하면 됨; 되묻기는 낭비).

이 술어는 Exp25 §1 AMBIGUOUS 의 데이터 버전이다. 되묻기 = "θ 가 무엇인가". 답 = θ*. **새 발화 r' = pin(S, θ*)** — 판정 가능 문장으로 환원(조건 C4).

### 3.2 규칙 R1~R10

기호: B = 발화당 담보(minBondPerClaim), R = 정답 보상, W = challengeWindow(Exp30), κ = 되묻기 비용(발화자 부담), δ = 상대가 답할 확률, n_max = 요청자가 선언한 되묻기 상한.

**R1 행위 3분할.** 요청 r 에 대해 에이전트는 {speak(담보 발화), ask(명료화 질문), abstain(기권)} 중 하나. ask 는 abstain 의 하위 행위 — 온체인 의미는 abstain 과 동일(무손실).

**R2 질문 레코드.** `clarification/v0.1 · kind=question`. 필수: `parent`(원 요청 r 의 해시), `readings`(I — 각각 완전히 못박힌 문장열, 판정 가능), `depth`, `speaker`, `sig`. 선택: `posterior`(p_i), `conf_before`(최약고리 c). **담보 불가·무손실·과금 불가**(`no-result` 급, 규격 §2.3)·판정 대상 아님.

**R3 답 레코드.** `clarification/v0.1 · kind=answer`. 필수: `in_reply_to`(질문 id), `choice ∈ I`, 요청자 `sig`. **담보 불가** — "내 의도는 i 였다"는 재검증 불가 주장(Exp28 B 범주)이라 판정하지 않는다. 대신 새 발화의 **전제**로 편입돼 그 안에서 요청자를 구속한다(이동표적 차단, §7 A6).

**R4 새 발화.** `requestHash' = keccak(canonical(r ‖ Q.id ‖ A.id ‖ pin(S,θ*) ‖ model_id ‖ evidence_ref))` — ERC 초안 '커밋 바인딩' 그대로. 컨트랙트 함수는 기존 `requestValidation` 무수정. 원 r 은 재개설 불가(`dup claim` 기존 revert). Reality.eth 와 달리 **바운티 이전 없음**(정리 3·Exp30 R_c = 0).

**R5 보류 금지 — 구성에 의해.** 컨트랙트는 질문·답 레코드를 **읽지 않는다**(입력이 없다). 따라서 어떤 명료화 레코드도 `claimedAt`·`engaged`·`claimSettled`·W 를 바꿀 수 없다. 이미 담보된 원 발화(모드 B)는 응답이 '질문'이므로 판정기가 tag `"abstain"` 으로 정산하거나, 아무도 개설 안 하면 W 뒤 `"unchallenged"` 소멸(Exp30 R4). A2A `INPUT_REQUIRED` 상태는 **이 프로토콜에 존재하지 않는다.**

**R6 비용·보상.** κ 는 발화자 부담: 연산 + (모드 B) 담보 B 의 W 잠금 기회비용 + 가스. **담보에서 떼지 않는다**(ERC 불변식 2; 담보에서 떼면 τ* 가 (B−κ)/(B+R) 로 내려가 기권을 줄인다 — z3 Z7, 작업서 ⑦). 요청자 부담 = 지연 t_q + t_a. **되묻기 보상 0·답변 보상 0**(R_ask = R_ans = 0) — 양의 지급은 정리 3 의 보상금 보조금이 되묻기로 이주한 것.

**R7 횟수.** 프로토콜 상수 없음. 상한 둘: (i) 요청자 선언 `n_max`(요청 레코드 필드, 기본 2) — depth > n_max 인 질문은 판정기가 malformed 로 분류(무손실, 신호만); (ii) 발화자 자유담보 ⌊freeBond/B⌋(모드 B). 깊이 n 스레드 = **n+1 개의 독립 발화**, 각각 자기 W.

**R8 판정기 검사 `legit(Q, A)` (기호, 재실행 가능).** (i) parent 존재 (ii) I 열거·각 reading 이 등록 판정기(check_id)로 판정 가능 (iii) **non-vacuous**: 재실행 라벨이 갈림(Exp25 AMBIGUOUS) (iv) A 의 서명 = 요청자 키 ∧ `in_reply_to` 일치 (v) depth ≤ n_max. 실패 라벨 ∈ {vacuous, malformed, unsigned-premise} — **전부 무손실**(기권 불변식 유지), 평판 소비자용 오프체인 신호. 새 발화의 판정은 **A 로 못박힌 전제 아래서만** 수행.

**R9 두 모드.** **P(선담보 없음, 기본):** 계산 → 결정 → 질문은 오프체인만, 온체인 흔적 0 → 답 오면 r' 담보 발화. **B(선담보):** 요청 수락 시 이미 `requestValidation` 된 경우 — 응답 = 질문 → 원 발화 abstain/lapse, r' 별도. 온체인 흔적 최소화 원칙: P 우선.

**R10 확신 공개(E1, 확장·이번 범위 밖).** `posterior`·`conf_before` 를 레코드에 서명 포함(오프체인). zk 로 '실제 배포 모델의 출력'임을 증명(Exp16 인스턴스가 로짓 62개를 이미 공개)하는 확장은 Confidential Guardian 의 경제층 결합에 해당하나, Exp16 실측 verify 가스 975,182 는 **질문 단위**에 과하다. 이번 라운드는 R8 의 기호 판별로 대신하고 E1 은 미측정으로 남긴다.

### 3.3 상태기계 (오프체인 스레드 ↔ 온체인 발화)

```
오프체인 스레드 T(r):
  Open(r) ──decide──▶ Speak(r)            → 온체인 claim r  (Exp30 상태기계 그대로)
           ├─────────▶ Abstain(r)          → (모드 P) 흔적 0 / (모드 B) claim r: abstain 정산 or W 소멸
           └─────────▶ Asked(Q_1) ──A_1──▶ Open(r_1 = pin(S,θ*_1)) ──▶ … (depth ≤ n_max)
                        └─ 답 없음(t_a 경과) ──▶ Abstain(r)  (잠긴 것 없음, 요청자·발화자 모두 이탈 자유)
온체인 (BondedValidatorV3, 무수정):  각 r_i 독립 —  None ──engage(창 안)──▶ Engaged ──verdict──▶ Settled
                                                None ──lapse(창 밖)──▶ Settled · None ──verdict(창 안)──▶ Settled
```

불변: 스레드 상태 전이는 온체인 전이의 **원인이 될 수 없다**(온체인 입력이 없음). 온체인 전이 중 '보류'·'재개' 노드는 없다. 이것이 A2A/Reality.eth 와의 구조적 차이다.

### 3.4 레코드 정의 — 규격 v0.1 위의 표현 (v0.2 후보, 이 라운드는 초안)

질문은 "기권 태그 + 질문 페이로드"가 **아니다** — 기권 태그(`"abstain"`)는 온체인 VerdictRecord 의 것이고 질문은 온체인에 가지 않는다. 질문은 **규격 v0.1 의 세 레코드(Assertion·Bond·Verdict) 어느 것도 아닌 제4의 서명 레코드**이며, 담보 레코드가 붙을 수 없다는 것이 곧 '기권 하위 행위'의 형식적 뜻이다(`assertion_id` 가 없으므로 `bond/v0.1` 이 참조할 대상이 없다).

```json
{ "type": "clarification/v0.1", "kind": "question",
  "id": "sha256 of canonical body",
  "parent": "원 요청 r 의 sha256 (requestHash 가 아니라 요청 원문 해시 — 계류 담보 주장을 가리키지 않는다)",
  "depth": 1,
  "readings": [ {"i": 0, "pinned": ["...Exp1 문법 문장열..."], "check_id": "logic-closure-v1"},
                {"i": 1, "pinned": ["..."],                     "check_id": "logic-closure-v1"} ],
  "posterior":   [0.5, 0.5],          "// 선택 — 서명에 포함되나 체인·판정기는 읽지 않는다(E1 전까지 신호만)": "",
  "conf_before": 0.62,                "// 선택 — 최약고리 c (Exp2)": "",
  "speaker": "발화자 키 지문", "asked_at": "ISO8601", "sig": "ssh-ed25519 over canonical JSON" }
```
```json
{ "type": "clarification/v0.1", "kind": "answer",
  "in_reply_to": "question.id", "choice": 1,
  "responder": "요청자 키 지문 (사람이면 플랫폼 세션 키 — §9-6)", "answered_at": "ISO8601",
  "sig": "요청자 서명 — 이 서명이 이후 새 발화의 전제 premises[] 에 그대로 편입된다" }
```
```json
{ "type": "assertion/v0.1", "...": "v0.1 필드 전부 동일",
  "premises": [ { "question": "question.id", "answer": "answer.id", "answer_sig": "…" } ],
  "property": "pin(S, θ*) 아래의 판정 가능 성질", "check_id": "logic-closure-v1",
  "bound": "…; premises 아래에서만 유효" }
```

규칙: (i) `bond/v0.1` 은 `assertion_id` 만 참조할 수 있다 → 질문·답에는 담보가 **구조적으로** 붙지 않는다. (ii) `verdict/v0.1` 도 `assertion_id` 만 판정한다 → 질문·답은 판정 대상이 아니다(C2). (iii) 판정기는 `premises[]` 의 서명을 검사하고(R8 iv) 실패하면 라벨 `no-result`(과금·담보 발동 없음, 규격 §2.3). (iv) `readings[].pinned` 는 각각 완전한 판정 가능 문장열이어야 하고 `check_id` 가 등록 판정기여야 한다 — 아니면 `malformed`. (v) `parent` 는 요청 원문 해시다. 온체인 `requestHash` 를 가리키는 필드는 **의도적으로 없다** — 있으면 소비자가 '이 주장은 명료화 대기 중'이라는 보류 의미론을 임의로 붙일 수 있다(A2A 회귀).

### 3.5 온체인 흔적 표 (BondedValidatorV3 `main 5f156d1`, 함수 무수정 — 각 셀은 실제 호출)

| 스레드 사건 | 모드 P(선담보 없음, 기본) | 모드 B(원 발화 r 이미 `requestValidation` 됨) |
|---|---|---|
| Speak(r) | `requestValidation(agentId, uri, H_r)` — B 잠금, `claimedAt` 기록 | (이미 됨) |
| Ask(Q) | **호출 0** | **호출 0** — `claimedAt[H_r]`·`engaged`·W 불변 |
| 원 발화 r 의 종결 | 해당 없음(담보 안 걸었음) | 창 안: judge `submitVerdict(H_r, s, uri, ev, "abstain")` → `abstained=true`, 슬래시 없음(:162) · 창 밖·미개설: 누구든 `settleUnchallenged(H_r)` → `"unchallenged"`, 토큰 이동 0(:144) — **둘 다 무손실, 최대 잠금 = W** |
| Answer(A) | **호출 0** | **호출 0** |
| Speak(r' = pin(S,θ*)) | `requestValidation(agentId, uri', H_r')`, H_r' = keccak(canonical(r ‖ Q.id ‖ A.id ‖ pin ‖ model_id ‖ evidence_ref)) ≠ H_r | 동일 — r' 은 **독립 claim**(자기 `claimedAt`·자기 W), 같은 H 는 `dup claim` revert(:96) |
| 답 없음(t_a 경과) | **호출 0**, 잠금 0 | **호출 0**; r 은 위 행대로 ≤ W 에 풀림 |
| 깊이 n 스레드 총합 | n+1 개 `requestValidation` 중 terminal 만 실제 담보(중간 발화는 모드 P 면 0) | ≤ min(n+1, ⌊freeBond/B⌋)·B 잠금, 각각 ≤ 자기 t_claim + W |

읽는 법: 표의 '호출 0' 칸이 C1(보류 금지)의 증명이다 — 질문·답에 대응하는 온체인 입력이 없으므로 어떤 명료화 레코드도 정산 시각을 움직일 **수단이 없다**. Reality.eth `reopenQuestion` 은 이 표의 Ask 행에 온체인 호출이 있고(새 question_id + 바운티 이전) A2A `INPUT_REQUIRED` 는 원 발화 행을 멈춘다 — 두 대조군과의 차이가 이 표 두 칸이다. K3(a) 는 이 표를 Forge 로 그대로 재실행한다.

---

## 4. 수식

### 4.1 불확실성 측도
- 추출 확신: **c = min(전 문장·전 헤드 소프트맥스 최댓값)** — 최약 고리(Exp2 그대로; 엔트로피가 아님, 작업서 ⑦ 정정 유지).
- 해석 불확실성: p_i (I 위 분포). 1차: **균등**(요청자의 열거는 선호를 주지 않는다). 2차(보고만): 추출기 from-헤드 소프트맥스를 I 로 제한·정규화.
- 못박은 해석별 파이프라인 답 a_i(검증기, 결정론)과 확신 c_i.

### 4.2 세 행위의 기대이익 (Exp18 게임 계승)
```
ℓ̂        = argmax_ℓ Σ_i p_i·[a_i = ℓ]
q_speak  = c_min · Σ_i p_i·[a_i = ℓ̂]
U_speak  = q_speak·R − (1 − q_speak)·B
U_abstain = 0
U_ask    = −κ + δ · Σ_i p_i · max( c_i·R − (1 − c_i)·B , 0 )        (답 없으면 0: 잠긴 것이 없다)
결정     = argmax{U_speak, 0, U_ask},  동률은 abstain (보수적)
```

### 4.3 정리(대수, z3 `prove_sketch.py` 실측 2026-09-03 — [THM] 5 · [WIT] 1 · [ENC] 1 · FAIL 0)
- **Z1 [THM]** U_speak ≥ 0 ⟺ q ≥ **τ\* = B/(B+R)** — Chow (1970) 기각 규칙의 아핀형. 새 발화 r' 도 같은 τ*: **되묻기는 τ\* 를 바꾸지 않는다.**
- **Z2 [THM]** 옵션가치 비음: E_θ[max(U(c),0)] − max(U(q_speak),0) ≥ 0 (q_speak ≤ c, max(·,0) 단조). κ = 0·δ = 1 이면 ask 는 abstain 을 약하게 지배.
- **Z3 [THM]** q_speak < τ* 구간(대칭 2해석, c_i = c)에서 **ask ⟺ c > τ_ask := τ\* + κ/(δ(B+R))**. 되묻기는 '답한 뒤의 확신이 τ* 를 여유 κ/(δ(B+R)) 만큼 넘길 때'만 정당하다.
- **Z4 [THM]** τ_ask ≥ τ*. **문턱이 내려가지 않는다.**
- **Z5 [WIT]** 보류(hold) 의미론의 잠금 = t_ans 는 어떤 상한 T 도 넘는 세계가 존재(SAT 증인). 우리 모드 B 잠금 ≤ W.
- **Z6 [ENC]** 우리 잠금은 t_ans·깊이 n 과 무관하게 ≤ W (Exp30 R11 의 T_max 상속).
- **Z7 [THM]** 되묻기 비용을 담보에서 떼면 τ* → (B−κ)/(B+R) < τ* — κ 를 담보 밖 별도 비용으로 두는 이유.

Exp2 배점 (B,R) = (5,1): τ* = 0.8333, κ = 0.05·δ = 1 이면 τ_ask = 0.8417 (`policy.py` 자가검증 격자 500점 위반 0, vacuous 되묻기 0/200, δ = 0 되묻기 0/200, 옵션가치 음수 0/10000 — `logs/policy-selftest.log`).

**Exp18 τ\* 와의 관계 한 줄:** τ* 는 **terminal 발화**(옛 발화든 새 발화든)의 speak/abstain 경계로 불변이다. 되묻기는 그 경계를 건드리지 않고, **경계를 넘는 발화의 수(coverage)** 를 늘리는 장치다. 늘어나는 양은 δ(상대 응답률)에 조건부 — Exp30 이 억지력을 q 에 조건부로 둔 것과 같은 정직성 구조다.

---

## 5. 실험 계획

### Phase 1 — 오프라인 (Exp1 생성기 확장, NumPy 만)
- **데이터 (두 생성기, 상보적 — 팀장 합성에서 택일 또는 병용):**
  - **`exp29/data_readings.py`(프로토콜 렌즈, 이 문서의 정식화)**: 해석집합 I 가 **본문에 명시 열거**된 문제 — 범주 3 (`ambig_ref` 대명사 지시 · `omit_target` 결론 누락 · `omit_rule` 규칙 누락) × decisive/vacuous 50:50 기각 샘플링, |I| ∈ {2,3}. 테스트 900건(300/범주, seed 29) + **대조군 Exp1 4범주 800건**(seed 2, Exp2 와 동일). 못박은 reading 은 Exp1 문법 그대로라 **Exp2 의 학습된 추출기를 재학습 없이 재사용**. R8 non-vacuous 판별의 기계 진실(decisive)이 여기서 나온다. 자가검증 `logs/data_readings-selftest.log`.
  - **`exp29/data_ambig.py`(데이터 렌즈)**: 후보가 **본문에 없는** 정보 — 노이즈 5종(clean/ref/omit/polar/dialect), 슬롯 단위 `oracle`·`candidates`, `answer_relevant()`(= decisive 와 같은 술어를 슬롯 후보 위에서), `pin_slot()`(= pin), 학습 gold 를 후보 분포에서 표본해 퍼진 사후분포를 학습시키는 설계(추출기 재학습 필요, 경제 렌즈 Arm A/B 와 결합). `dialect` 는 '되묻기 낭비' 대조. 자가검증 `logs/data_ambig-selftest.log`.
  - 차이의 뜻: 열거된 I(이쪽)는 Exp25 의 '저자 열거' 슬라이스 — 되묻기 정당성을 **기호로** 판별할 수 있는 범위. 열거 없는 후보(저쪽)는 판별이 추출기 사후분포에 기대므로 E1(zk)·보정 검사가 더 무겁다. K2(a) 는 열거형에서, 경제 렌즈 K1(d) 보정은 비열거형에서 판정하는 것이 자연스럽다.
- **에이전트(정책)**: (a) speak-always · (b) **abstain-only** = §4.2 에서 U_ask = −∞ (Chow/WALLA 대조군 1) · (c) **ask-정책(우리)** · (d) ask-always(Mirage 스팸) · (e) 오라클(θ* 를 아는 상한).
- **상대 모사**: `simulated_counterpart` — 확률 δ 로 θ* 답, 아니면 침묵. δ ∈ {1, 0.5, 0}.
- **파라미터(사전등록)**: (B,R) ∈ {(5,1) Exp2, (2,3) Exp18}; κ ∈ {0, 0.05, 0.1, 0.2}(담보점수 단위); n_max = 2; p_i 균등(1차).
- **지표**: 담보점수/문제(+R/−B/0, 스레드의 모든 terminal 발화 합산, κ 차감), terminal 오답률(전체 대비), coverage, ask 율, vacuous-ask 율, depth 분포, 해석 사후 보정표(Exp2 §"핵심 발견" 형식), legit-checker 일치율.

### Phase 2 — 온체인 (anvil, `main 5f156d1` BondedValidatorV3 + BondedJudgePanelV3, **컨트랙트 무수정**, Exp5/Exp19/Exp30 sim 하네스 재사용)
- 모드 P·B 각각 스레드 200 (깊이 0/1/2), 정직 판정기(재실행 + `legit`), W = 86,400(Exp30 R10 잠정).
- **적대 요청자 3종**: 무응답(δ = 0) · 위조 A(서명 불일치) · 이동표적(A 로 못박은 뒤 다른 해석 주장).
- **대조군 2(시뮬 모델)**: hold 의미론(A2A INPUT_REQUIRED — 답 올 때까지 원 발화 계류) · reopen 의미론(Reality.eth — 되묻을 때마다 새 창 W 리셋). 지표: 발화자 담보 잠금 시간, 요청자 노출 시간, 토큰 보존.
- Sepolia 불필요(코드 변경 없음). 되돌릴 수 없는 것 없음.

### Phase 3 — E1 zk 확신 공개 (범위 밖, 기록만)
Exp16 인스턴스(로짓 62)로 posterior 를 실어 '실제 모델 출력' 증명. 가스 975k/증명 실측이 질문 단위에 과함 → 이번 라운드 미실행. 대조군 3(Confidential Guardian)은 **미측정**으로 남긴다.

---

## 6. 킬기준 K1~K4 (사전등록 — 실행 전 박제, 결과 보고 후 수정 금지)

**K1 되묻기가 담보점수를 올리는가 (대조군 1: Chow/WALLA 기권-only).** Phase 1, δ = 1:
(a) decisive 부분집합에서 ask-정책 담보점수/문제 − abstain-only ≥ **+0.10** at κ = 0.05, 그리고 전체 모호 집합에서 ≥ 0 at κ ≤ 0.1. **κ 격자 전부에서 이득 < +0.05 → KILL**(되묻기는 기권에 더한 것이 없다).
(b) terminal 오답률(새 발화 포함, 전체 문제 대비) ≤ **0.5%**(Exp2 K1 기준 계승). 초과 → **KILL**(되묻기가 오답을 들여온다).
(c) 대조군 Exp1 4범주(비모호 800건)에서 ask 율 ≤ **2%**. 초과 → **KILL**(안 물어도 될 곳에서 묻는다 = 설계상 스팸).
(d) δ = 0 행을 **숨기지 않고 박제**(예상: 이득 0, 손실 = κ·ask율 — δ 조건부 이득의 실측 증거).

**K2 되묻기 정당성 판별 (기권 남용/Mirage).** Phase 1:
(a) `legit` 판별(추출기 재실행 기반)과 기계 진실(decisive/vacuous)의 일치율 ≥ **0.98**. 미달 → **KILL**(정당성을 기호로 못 가린다 → zk 없이는 C3 미해결).
(b) ask-always 스팸 에이전트: vacuous 되묻기가 flagged 되는 비율 ≥ **95%** ∧ 스팸의 담보점수 ≤ 정직 ask-정책(κ > 0). 스팸이 정직을 이기거나 flag < 90% → **KILL.**

**K3 무보류·지연 상한 (대조군 2: A2A hold / Reality.eth reopen).** Phase 2, 컨트랙트 무수정:
(a) Forge/anvil: 응답이 질문인 원 발화의 정산 시각·결과가 질문 없는 발화와 **동일**(judge abstain 또는 t_claim + W 소멸); 깊이 n 스레드 = n+1 독립 claim, 총 잠금 ≤ min(n+1, ⌊freeBond/B⌋)·B, 각각 무허가 호출만으로 ≤ t_claim + W 해제. 명료화 레코드가 온체인 상태를 바꾸는 경로 1개 → **KILL.**
(b) 무응답 요청자 200스레드: 모드 P 잠금 **0**, 모드 B 잠금 ≤ **W**. 초과 → **KILL.** 같은 표에 hold(잠금 = t_ans, 무계)·reopen(잠금 = n·W) 행 박제. **대조군이 W 를 넘지 않으면 '새 발화 개설' 조건 C1 은 비하중 → 동기 기각으로 정직 보고.**
(c) 요청자 노출: terminal 까지 ≤ n_max·(t_q + t_a) (+ W, 모드 B). 초과 경로 → **KILL.**

**K4 경제 중립·공격면.** Phase 2:
(a) 토큰 보존 정확(Exp19 K3 방식): 스레드 전후 총합 불변, 질문·답 레코드에 의한 토큰 이동 **0**. 위반 → **KILL.**
(b) 위조 A(요청자 서명 없음)로 연 r' 이 `no-counterexample-in-bound` 라벨을 받는 건수 **0**(판정기는 unsigned-premise → no-result/abstain). 1건 → **KILL.**
(c) 이동표적 요청자 200스레드에서 A 아래 정답인 에이전트의 슬래시 **0**. 1건 → **KILL.**
(d) 설계 어디에도 되묻기·답변에 양의 지급 없음(R_ask = R_ans = 0) — 코드 리뷰 + 이벤트 로그로 [ENC] 확인. 발견 시 → **KILL**(정리 3 위반).

---

## 7. 공격면 (전량 등재)

| # | 공격 | 방어 | 잔여 |
|---|---|---|---|
| A1 | **질문 스팸 / Mirage** — 항상 되물어 담보를 안 건다 | R8 non-vacuous 기호 판별(K2) · 과금 불가라 이득 0 · 요청자 n_max | 열거 밖·과소열거(A5)에서 판별력 상실 |
| A2 | **무응답 요청자** — 발화자 담보 잠금 | 모드 P 잠금 0 · 모드 B ≤ W(Exp30) · 되묻기는 W 를 리셋 못 함(R5) | W 동안의 기회비용은 κ 로 발화자가 진다 |
| A3 | **지연 공격(발화자→요청자)** — 되물어 시간 끌기 | 잡힌 것이 없어 요청자 이탈 자유 · 노출 ≤ n_max·(t_q+t_a) (K3c) | 요청자의 주의(attention)는 가격 없음(Exp27 L2 와 같은 급) |
| A4 | **위조 답 A** — 발화자가 유리한 해석을 스스로 못박음 | R4 커밋에 A.sig 포함 · R8(iv) 서명 검사 · 실패 시 no-result(K4b) | 사람 요청자의 '서명'이 플랫폼 세션 해시일 때 최약 고리(§9-6) |
| A5 | **해석 과소열거 / 전략적 I** (Exp25 한계3 거울) | 없음 — 판정기가 해석을 추가하면 NL 판정 재도입(Exp25 회귀) | **미해결**, 정직 등재 |
| A6 | **이동표적 요청자** — 답한 뒤 다른 해석으로 분쟁 | 판정은 A 로 못박힌 전제 아래서만(R8) (K4c) | — |
| A7 | **스레드 쪼개기로 평판 부풀리기** | 발화마다 B 잠금·W · ReputationLens 는 terminal 만 집계, abstain 중립(R8/R12) | 모드 P 되묻기는 렌즈에 안 보임(§9-4) |
| A8 | **확신 위조** — 낮은 확신을 가장해 되묻기 정당화 | 체인은 확신을 안 본다(Exp28 B3 존중) · 열거 가능하면 R8 기호 판별 | 열거 불가 범주는 E1(zk) 전까지 미판별 |
| A9 | **W 리셋** — 같은 r 재개설 | requestHash' ≠ r(커밋 바인딩) · `dup claim` revert · 바운티 이전 없음 | — |
| A10 | **교차 스레드 재생** — 다른 스레드의 A 재사용 | A 는 parent·in_reply_to 에 묶임, R8(i)(iv) | — |

---

## 8. 영향 정리 (정리·문서)

| 대상 | 영향 |
|---|---|
| Exp18 τ* = B/(B+R) (K2 창발) | **불변.** 단 임계식은 Chow (1970) 재표기임을 Exp18·백서·ERC 에 인용 추가(정정 대상). 되묻기는 τ_ask = τ* + κ/(δ(B+R)) 를 **추가**(Z3·Z4). |
| Exp2 K1·K2 (기권) | 계승. Exp2 '저확신 7%' 중 열거 가능 모호성분은 되묻기로 회수 가능(K1 이 측정). 확신 신호는 여전히 최약고리(엔트로피 아님). |
| 규격 v0.1 §1·§2.3 | 질문 = 기권·`no-result` 급 과금 불가. **v0.2 후보:** `clarification/v0.1` 레코드 2종 + Assertion `premises[]` 필드. |
| ERC 초안 | **규범 변경 없음**(인터페이스·불변식·예약 태그 그대로). 정보성 절 "Clarification threads are off-chain" + Security Considerations 에 커밋 바인딩 확장(r ‖ Q ‖ A) 추가 후보. |
| Exp30 W·L1~L5·R1 (q 조건부 억지력) | 계승. 스레드 = n+1 독립 claim, 각각 W·T_max(R11). 억지력 q·B_a 는 terminal 발화마다 그대로. 되묻기로 W 리셋 불가(A9). |
| Exp25 AMBIGUOUS 술어·한계3 | **재사용**(R8 non-vacuous 판별) + **한계 상속**(과소열거가 지배전략, A5). |
| Exp27 I2 (식별불가능성) | '되묻기가 정당했나'의 식별은 **열거 가능 범주에서만** 기호로 해소. 열거 불가 범주는 I2·Exp28 B1 그대로. |
| Exp28 B3 (체인은 관측만) | 존중 — 확신은 체인에 안 간다. B (재검증 불가 주장 담보 금지) — 답 A 를 담보하지 않는 이유. |
| 정리 3·Exp26 (W)·Exp30 R_c = 0 | 계승 — R_ask = R_ans = 0. |
| ReputationLens abstainRate | 모드 B 되묻기는 abstain 으로 집계, 모드 P 는 미집계 — **모드 간 평판 비대칭**(§9-4), v0.2 렌즈 필드 후보. |
| Exp1 결과 | **무변경**(생성기 확장은 별도 파일, Exp1 데이터·수치 그대로). |

---

## 9. 정직하게 못 하는 것 (전량 등재)

1. **★환각을 제거하지 않는다.** 열거 가능한 모호성만 판정 가능 전제로 환원한다. Exp25 z3-10 이 사건 B 의 **지배적** 모호성으로 못박은 술어수준·미열거 해석은 이 설계 밖이다. 제목이 '수학으로 환각 제거'가 아닌 이유.
2. **★과소열거가 발화자의 지배전략**(Exp25 한계3 거울, A5). 되묻고 싶은 발화자는 I 를 좁게 내 non-vacuous 를 만들 수 있고, 판정기가 해석을 보태면 NL 판정을 재도입한다. 미해결.
3. **답은 선언이지 사실이 아니다.** 요청자가 자기 의도를 틀리게 답하면 발화자의 담보 발화는 'A 아래 정답'이라 무손실이고 손실은 요청자에게 남는다 — 이를 가격 매기는 장치는 없다.
4. **평판 가시성.** 모드 P 되묻기는 온체인 흔적 0 이라 abstainRate 가 과소집계된다. K2 판별은 오프체인이다.
5. **토이.** 합성 한국어 템플릿·어휘 68·|I| ≤ 3·해석 사전분포 균등. 해석 사후 보정(2차)은 Exp2 의 최약고리 보정과 다른 양이며 미검증.
6. **사람 요청자의 서명.** A.sig 가 키가 아니라 플랫폼 세션 해시일 때 A4 방어는 그 플랫폼만큼만 강하다. 규격 §4 chain-optional 양자 계약에서만 안전.
7. **δ·κ 는 외생 파라미터.** 이득은 δ 에 조건부(Exp30 의 q 와 같은 구조). 실전 응답률·실비용 미측정.
8. **E1(zk 확신 공개) 미측정.** 대조군 3 은 이번 라운드에 답하지 않는다. Exp16 가스 975k 는 질문 단위엔 과하다는 것만 실측 근거.
9. **오프체인 상태기계의 정합.** 발화자가 A 없이(또는 위조 A 로) r' 을 담보하면 온체인은 막지 않는다 — 판정기가 no-result 로 무손실 처리할 뿐(K4b). 레지스트리 오염(Exp30 §7-4 와 같은 급)은 남는다.
10. **선행 인정.** 임계는 Chow 1970, 정보가치 되묻기는 SAGE/Deng, 3분할 게이팅은 CAAG/AgentAbstain, wager-0 IR 은 WALLA. 우리 몫은 §2 의 교집합 (a)(b)(c) 와 W 와의 결합뿐이다.
11. **이 문서의 실측은 넷뿐** — 생성기 자가검증 2(열거형·비열거형)·정책 자가검증·z3 대수 7건. Phase 1·2 는 미실행. K1~K4 판정은 없다.
12. **커밋 기록 정정.** 커밋 `92e447e` 의 메시지는 `data_ambig.py` 를 '열거 해석집합 I 생성기'로 적었으나, `git add` 직전 데이터 렌즈가 같은 경로에 자기 생성기(노이즈 5종)를 써서 **실제로 들어간 파일은 데이터 렌즈 것**이고 함께 커밋된 `logs/data_ambig-selftest.log` 는 내 생성기의 출력이었다(불일치). 후속 커밋에서 내 생성기를 `data_readings.py` 로 복원하고 두 로그를 각 파일에서 다시 생성했다. 파일 이력은 되돌리지 않았다(남의 작업 무수정).

---

## 12. 렌즈 병합 노트 — 경제 렌즈(`design-economics.md`)와의 대응 (팀장 합성용)

| 개념 | 이 문서(프로토콜) | 경제 렌즈 | 합성 시 |
|---|---|---|---|
| 추출 확신(최약고리) | c, c_i | κ | 하나로 통일 필요 — **κ 를 비용에 쓰는 이 문서와 능력에 쓰는 저쪽이 충돌.** 제안: 능력 κ · 비용 c_q |
| 되묻기 비용(발화자) | κ | c | 위와 같이 c_q |
| 상대 응답 확률 | δ | α | α |
| '해당 없음' 질량 | 없음(I 가 본문 열거라 none 이 없음) | ν, `none_option` 필수 | 비열거형에서만 ν; 열거형은 ν = 0 |
| 해석 사전분포 | p_i 균등(1차) | w̃ = 질의 헤드 top-1 곱 | 둘 다 보고 |
| 되묻기 문턱 | τ_ask = τ* + κ/(δ(B+R)) (Z3) | τ_κ = τ* + c/(α(1−ν)(B+R)) | **동일식**(ν = 0 이면 일치) — 독립 유도가 일치함을 기록 |
| 횟수 상한 | 프로토콜 상수 없음; 요청자 n_max(기본 2) + ⌊freeBond/B⌋ | k_max = 3(사전등록) | 사전등록은 하나여야 함 — 팀장 결정. 이 문서는 '상한은 요청자 필드'를 유지 권고(프로토콜 상수는 지연 공격 협상 재료가 됨) |
| 레코드 | `clarification/v0.1` kind ∈ {question, answer}, `parent`, `readings`, `depth` | `clarification/v0.1` + `reading-selection/v0.1`, `context_hash`, `round` | 필드 합집합; 답 레코드 이름 하나로 |
| 선담보 모드 | P(무담보, 기본) + B(선담보: abstain/lapse) | 되묻기는 담보 **전**에만(R4 무접촉) — B 모드 없음 | 이 문서의 모드 B 는 '이미 담보된 발화의 응답이 질문일 때' 정산 경로(abstain 태그·W 소멸)를 명시한 것이지 새 전이가 아님 — 양립 |
| 정당성 판별 | R8 기호(non-vacuous, 열거형) | §3.6 zk 공개 로짓(w̃) | 열거형은 기호, 비열거형은 zk — 층 분리 |
| 킬기준 | K1 담보점수 vs 기권-only · K2 판별·Mirage · K3 무보류(hold/reopen 대조) · K4 토큰·위조 A·이동표적 | K1 라우팅 분해 · K2 경제 우위 · K3 지연 불변 · K4 정리 보존·창발·zk | 겹침: 경제 우위(K1↔K2)·지연 불변(K3↔K3)·정리 보존(K4d↔K4a). 이 문서 고유: **K2 Mirage 판별, K4(b) 위조 A, K4(c) 이동표적**. 저쪽 고유: K1 보정·Arm A/B, K4(b) θ_ask 창발 |

**학습 렌즈(`design-learning.md`)와의 대응(추가):**

| 개념 | 이 문서(프로토콜) | 학습 렌즈 | 합성 시 |
|---|---|---|---|
| 확신 측도 | u₁ 최약고리 고정(Exp2·작업서 ⑦) | u₁~u₄ 비교, 주 측도 u₄(검증기 답 뒤집힘 반복도) | 저쪽 K1 이 고른 측도를 채택하되, **결정 규칙·τ_ask 는 측도와 독립**(§4 는 c 를 어떤 보정 확신으로 바꿔도 성립) |
| 되묻기 표적 | I 전체("θ 가 무엇인가") — 열거형이라 표적 선택 문제가 없음 | 슬롯 j* = argmax Δ_j(EVPI) — 비열거형 | 열거형: 표적 = I. 비열거형: 저쪽 j*. 두 팔 병행 |
| 정당성 판별 | R8 기호 `legit`(non-vacuous) | Δ(B+R) > c, 로짓 바인딩 시 결정가능([ENC] M2) | 저쪽 R8 이 명시했듯 상호보완 — 열거 있으면 기호, 없으면 로짓(둘 다 오프체인) |
| z3 | Z1~Z7(`prove_sketch.py`) | C1~C4b·H1·N1·M1·M2(`prove.py`) | Z1≡C1, Z4≡C2, Z3≡C3, Z5≡H1, Z6≡N1 — **독립 인코딩이 같은 결론**. 정본 이식 시 하나로 합치고 cvc5 교차(`xverify.py`) |
| 파일명 정합 | `data_readings.py`·`prove_sketch.py` | 문서는 `data_ambig_slots.py`·`prove_gate.py`·`NOTE-…concurrent-write.md` 를 가리키나 **디스크에는 `data_ambig.py`·`prove.py` 만 있다**(08:03 확인) | 팀장 합성에서 파일명 하나로 — 이 문서는 남의 파일을 옮기지 않았다 |
| 상한 | n_max 요청자 필드(기본 2) | n_max 잠정 2 | 일치(경제 렌즈 k_max=3 만 이견) |

---

## 10. 오너 결정 필요 (되돌릴 수 없는 것만)

없음. 컨트랙트·배포·대외 발송 변경이 없다. 정본(`main`) 이식은 Phase 1·2 결과 보고 후 결재.

---

## 11. 재현 (이 커밋에서 실제로 돌린 것, 2026-09-03, python3 + NumPy 2.4.6, z3 4.12.6)

```bash
cd exp29
python3 data_readings.py                                # logs/data_readings-selftest.log — n=300, 범주 3×100, decisive 50:50, |I|∈{2,3}, missing tokens: none
python3 data_ambig.py                                   # logs/data_ambig-selftest.log — 학습/데이터 렌즈 생성기(노이즈 5종) 자가검사
python3 policy.py                                       # logs/policy-selftest.log — τ*=0.8333 τ_ask=0.8417, 격자 위반 0/500, 옵션가치 음수 0/10000
../.venv-halmos/bin/python prove_sketch.py              # logs/prove_sketch.log — [THM] 5 · [WIT] 1 · [ENC] 1 · FAIL 0
# worktree(~/iis-lab-wt/exp29-design)에서는 venv 가 정본 체크아웃에만 있다: ../../../iis-lab/.venv-halmos/bin/python prove_sketch.py
```
2026-09-03 08:03 재실행: 네 로그 전부 커밋본과 바이트 동일(diff 0). 인용한 컨트랙트 줄번호(`dup claim` :96 · `claimedAt` :100 · `engage` :112 · `submitVerdict` :133 · `settleUnchallenged` :144 · abstain 태그 :162)와 Exp16 수치(공개 인스턴스 63 = 해시 1 + 로짓 62, verify 가스 975,182)는 같은 시각 `exp3/contracts/src/BondedValidatorV3.sol`·`exp16/EXP16.md` 에서 재확인.
