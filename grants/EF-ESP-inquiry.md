# EF ESP — Informal Inquiry Draft (v2, 2026-09-03; supersedes v1 2026-08-26)

> **제출 전 오너 승인 필수**(명의·이메일 결정 포함). 발송은 오너 직접 — 이 파일은 초안일 뿐 발송·게시하지 않는다. 아래는 ESP 접수 양식의 "project inquiry" 란에 넣을 본문.
>
> **제출 직전 재실측 항목(2026-09-03 실측값 병기 — 제출일에 다시 확인):**
> 1. **ESP 상시 문의 트랙 접수 여부** — esp.ethereum.foundation/applicants · /inquire: 2026-09-03 페이지 본문에 개방/폐쇄/일시중지 문구 없음(Office Hours·Open Rounds 섹션 제목만 노출). 제출일에 양식이 실제로 열리는지 브라우저로 확인하고, 닫혀 있으면 발송 보류(대조 작업서 '창구 폐쇄 대기').
> 2. **ERC-8004 상태** — eips.ethereum.org/EIPS/eip-8004: 2026-09-03 실측 **Draft**(Standards Track: ERC, created 2025-08-13, Last Call 없음). 본문 'still a Draft'는 이 값 기준 — Review/Last Call/Final로 바뀌면 문구 교체.
> 3. **본문 수치의 정본** — `forge test` 93/93(2026-09-03, Exp30 병합 후; 이후 병합에 따라 변동), REPRODUCTION.md 17/17, Sepolia 주소는 docs/deployments.md, 가스는 ≈864,652(재현 864,388).
>
> 갱신 원칙(대조 작업서 블록 5-7): v1.0 자산으로 다시 쓰되 **스코프 추가 0**(산출물 3개 동일) · **토큰 언급 0**(담보는 기존 자산, 자체 토큰 없음 — '없다'는 문장 1회만) · **채굴풀/TCR/멀티체인 문구 0** · '정음은 별도 저장소·비매매·계승 없음' 분리 문장 포함 · 명의 'Independent researcher (Korea/Australia)' · 연락처 yubbi85@gmail.com 유지.

---

**Project name:** Bonded Validation — a speaker-bonded validation protocol on top of ERC-8004 Trustless Agents

**Contact:** Independent researcher · yubbi85@gmail.com · github.com/yubbi-sketch

**Inquiry:**

ERC-8004 gives AI agents on-chain identity, reputation, and a validation registry, and deliberately leaves staking, slashing, and incentives to "specific validation protocols" built on top. The designs emerging in that slot bond the *validator*. We build the complementary piece: bonding the *speaker*. An agent cannot submit a claim unless free bond is locked against it; a claim proven wrong is slashed; an honest "I don't know" (abstention) releases the bond without loss. Accountability attaches at the moment of utterance, not at audit time.

Since our first draft (August 2026) the prototype has become a documented, machine-checked, independently re-run research artifact. Everything below is public under MIT and reproducible from the repository's own commands:

- **Whitepaper v1.0** (git tag `wp-v1.0`, 2026-08-27): protocol, threat model, theorems, and a limitations section written before any external review.
- **Machine-checked contract theorems (Halmos, over compiled bytecode, in stated state spaces):** abstention neutrality, slash exactness, no double settlement, and settlement conservation (T1–T4) on the speaker contract; unanimity / majority / split / timeout refinements against an independently written spec (PA, PB, PC, P4) on the bonded judge panel — eight theorems. A v0.3 revision adds an optimistic lapse rule (a claim nobody challenges inside a window settles losslessly, closing a liveness gap we found in our own v0.2.1) with further lapse theorems (L1–L5, PL1–PL3); it is merged and machine-checked but **not yet deployed**.
- **Economic theorems (z3, every check re-run on an independent second solver, cvc5 — 96/96 as of 2026-09-02):** the "no winner's bounty" result — a winner's reward is the briber's budget; with judge bonds 10× the agent bond, bribery stays unprofitable up to ~96.8% panel capture — plus a negative-results arc (Exp24–28: value-coupling does not cure the scale problem; bonded specifications surface only a narrow formalizable slice; challenger-supply incentives are a conditional impossibility; our first halt/resume design was discarded and rebuilt; judge honesty under laziness and outside bribes). We publish the failures with the proofs.
- **Proof-carrying judgment, measured end-to-end (zkML):** the full 24k-parameter extractor forward pass proves in ≈17 s (19 s reproduced) and verifies in 0.1 s (ezkl/halo2); the real proof verifies on-chain for ≈864,652 gas (864,388 in the reproduction re-run; 2.9% of the block limit) in a 19,683-byte verifier under EIP-170; a binding circuit cryptographically rejects a proof whose input hash is tampered.
- **Independent re-run:** REPRODUCTION.md — all 17 audited items reproduce from a clean state; the audit also caught and corrected two overclaims in our own prose.
- **Live on Sepolia (Sourcify-verified):** BondedValidator v0.3 + BondedJudgePanelV3 (2026-09-03; optimistic lapse — a claim nobody challenges inside a 24 h window can be settled losslessly by anyone, tag "unchallenged", no bounty) on top of v0.2.1 — bonded judges, weighted-lottery panels, expanded trials with minority slashing, commit-reveal lottery, no owner backstop; addresses in docs/deployments.md. Contract suite: 93/93 Foundry tests at the time of writing.
- **Regulation-invariant service voucher (Exp17):** the credit used to pay for validation cannot appreciate, transfer, pool, or yield — four properties machine-checked (Halmos 7/7). Structure, not a legal opinion.
- **Bonded Assertion specification v0.1** (chain-optional, with a fee-capped refund clause) and a 14-day responsible-disclosure process.
- **The AI side:** on a synthetic multi-hop logic benchmark (910 test cases, pre-registered kill criteria), all observed errors of the extractor+verifier pipeline concentrated in the lowest 7.3% of model confidence; abstaining below a confidence threshold gave zero observed wrong answers at 92.7% coverage. In a 300-utterance live run on Anvil, a hallucinating agent went bankrupt (bond 50 → 0) while a verifier-backed agent with calibrated abstention finished lossless (50 → 50).

We are asking for a small grant to turn this into a public good for the 8004 ecosystem — the same three deliverables as our first draft, unchanged in scope:

1. A hardened open-source reference implementation plus the specified interface (**IBondedValidator**; the draft ERC text and an Ethereum Magicians thread are written and accompany this inquiry) so speaker-bonding composes with validator-network designs rather than fragmenting them.
2. Public testnet deployment against the **canonical ERC-8004 registries** (our current deployment uses minimal registries) with a reproducible benchmark harness — including the redeployment forced by the announced Sepolia retirement.
3. A research report on abstention economics for bonded agents (how slash ratios set abstention thresholds — our current results are the equilibrium threshold τ* = B/(B+R) in simulation and a 40-agent live run on a local chain), with all datasets and code released.

**Repository (public, MIT):** https://github.com/yubbi-sketch/bonded-validation

**Honest limitations we are explicit about:** verdicts still come from re-executing judges (zk/optimistic paths beyond deterministic claim classes are the research core of the grant period); benchmarks are toy-scale and synthetic, with a disclosed supervision confound; theorems hold in stated state spaces and under stated economic assumptions (the bribery bound is conditional and fails as capture probability approaches 1); the lapse rule's deterrence is conditional on challengers actually appearing; no third-party audit yet; ERC-8004 is still a Draft and we treat registry interfaces as adapters. There is no token in this project: bonds are denominated in existing assets, the Sepolia test asset is valueless by construction, and nothing is sold. A separate repository by the same author (Jeongeum, a transfer-locked game asset on Base) is an unrelated project — not sold, not used by this protocol, and inheriting nothing from it; we mention it only so that a search on the author does not read as an undisclosed asset.

**Team:** Independent researcher working with an AI-assisted research pipeline; prior work includes an account-abstraction policy-enforcement prototype (Foundry, 25/25 tests) that we retired after our own adversarial review concluded ERC-7710/7780 + caveat enforcers already occupy that slot — we would rather kill our own idea than ship a redundant standard. Git history documents the full research trail, including the kills.

**Requested amount:** USD 25,000 (small grant tier) over 6 months.

**Category:** Applied research / protocol prototype — decentralized AI, agent infrastructure.
