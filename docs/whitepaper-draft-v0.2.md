# Bonded Validation: Speaker-Bonded Accountability for AI Agents, with Machine-Checked Settlement Rules

**Whitepaper draft v0.2 — 2026-08-27**
*IIS Lab — an independent, currently pseudonymous research effort. Contact: github.com/yubbi-sketch (repo issues) · yubbi85@gmail.com.*
Repository: github.com/yubbi-sketch/bonded-validation (MIT) · Contracts on Sepolia, Sourcify-verified (§7)
No token launch, no sale: the experiment token is valueless by construction and testnet-only.

## Abstract

Most staking designs for AI agent trust bond the *validator*; this work bonds the
**speaker**: an agent cannot make a claim at all unless its own collateral is at
risk behind that claim. We build this as a settlement layer over the ERC-8004
agent registries and study it two ways, which we keep explicitly separate.

**Machine-checked settlement rules (unconditional over stated state spaces).**
Symbolic execution of the deployed bytecode (Halmos) proves, over all inputs in
the stated spaces: abstention is lossless — an agent that says "I don't know"
never loses its bond; slashing is exact — forfeiture happens precisely on a
verified failing verdict and in a precisely bounded amount; settled claims cannot
settle twice; and, at the judge-panel layer, only voters against the final
verdict are ever slashed while every judge's protocol income equals a fixed,
outcome-independent fee.

**Conditional economic security (theorems over a stated model).** Judges are
themselves bonded and disciplined by expanded trials. In a model with five
explicit assumptions we prove (z3, by unsatisfiability): bribery has non-positive
expected profit whenever the judge/agent bond ratio satisfies B_j/B_a ≥
p/(m(1−p)) — at deployed parameters, for capture probabilities up to 30/31 ≈
96.8% — and the expected-cost lower bound is invariant to the bribe payment
schedule, including p+ε-style conditional promises. Conversely, adding a
winner's reward funded from forfeitures admits budget-feasible parameters where
the identical mechanism becomes expected-profitable to attack: within this
model, a winner's bounty functions as a bribery subsidy. This is our sharpest
point of departure from redistributive designs (UMA, Kleros).

We also report nine experiments (six with pre-registered kill criteria) on a
synthetic multi-hop logic benchmark, including scripted 300-utterance runs on a
local Anvil chain in which a hallucinating agent's bond is exhausted while a
verifier-backed agent with calibrated abstention finishes lossless, and a
feasibility census suggesting our 24k-parameter extractor is small enough for
zero-knowledge re-execution proofs (≈2^19 estimated constraint rows by a stated
heuristic; proving-time measurement is future work).

## 1. Introduction

Security that depends on out-thinking the attacker fails when the attacker
thinks better. Our research program asks for guarantees that do not depend on
out-thinking anyone: properties that hold, under stated conditions, whatever the
adversary's intelligence. This paper develops the economic layer for one root
proposition — **every AI utterance signed, bonded, proven** — and proposes its
interface as an open, MIT-licensed ERC draft filling the collateral/slashing
slot that ERC-8004 deliberately delegates upward.

Contributions:

1. **A speaker-bond protocol** on ERC-8004: claims require locked collateral,
   abstention is a first-class lossless act, withdrawal is delayed, and
   reputation is derived statelessly with abstention counted separately from
   error (§3).
2. **Bonded judging without a superior court**: weighted-lottery panels,
   expanded trials slashing only the minority against the final verdict, a
   commit-reveal lottery closing free grinding, and lossless-timeout backstops
   replacing any owner arbiter (§3).
3. **Machine-checked settlement rules**: eight symbolic-execution theorems over
   the compiled contracts, including the no-bounty property as a bytecode-level
   invariant (§5.1).
4. **The no-bounty theorems**: conditional non-profitability of bribery with an
   explicit bond-ratio threshold, payment-schedule invariance, and a
   budget-feasible counterexample showing that winner rewards can flip the same
   mechanism from expected-lossy to expected-profitable to attack (§5.2).
5. **A measured path to proof-carrying judgment**: quantization-survival and
   circuit-size censuses for replacing honest-majority re-execution with zkML
   proofs (§6).

Method commitments: kill criteria are registered before experiments run (where
this holds and where it does not is stated in §4); limitations are collected in
§8, including one — an intermediate-supervision confound in our headline
benchmark — that materially reframes what the benchmark shows. We have killed
our own work before on these grounds: our original standards ambition (an
account-hierarchy ERC) was terminated when two independent reviews found the
slot already occupied, and the program pivoted to the present gap.

## 2. Related Work

**Agent trust stacks.** ERC-8004 ("Trustless Agents", in Review) provides
identity, reputation, and validation registries and delegates collateral and
slashing to higher layers — the slot this work fills. A recent comparative study
of inter-agent trust models (arXiv:2511.03434) recommends this shape: bonds
proportional to harm, objective slashing. Among emerging staked-claims projects:
**VeriBond** (ETHGlobal) has agents post stake behind claims with deterministic
on-chain resolution, but to our knowledge offers no lossless-abstention
primitive and no machine-checked settlement rules; **KYA Protocol** builds
8004-compliant staked validation networks on Base; **ECO/CPO-DAG** and
**AgentBound** (arXiv preprints) propose claim-bond accountability layers. These
are early, mostly non-archival artifacts; we cite them for fairness of
positioning rather than as settled literature. Our claimed novelty is not the
staking idea but the pairing of the mechanism with machine-checked proofs and
with abstention as a protected act.

**Optimistic oracles and decentralized courts.** UMA settles disputes
loser-pays, distributing forfeitures to the prevailing side, with escalation to
a token-holder vote as final backstop; Kleros disciplines jurors through
redistributive Schelling-game staking with fee-funded appeals. Our Theorem 3
result concerns the winner-reward channel in a one-shot panel under our stated
model; it does not model UMA's escalation game or Kleros's appeal rounds, and we
present it as a design principle for our mechanism class, not as a break of
those deployed systems. What it does establish: within a budget-feasible bounty
(paid only from forfeited bonds), there exist parameters where the bounty
variant is expected-profitable to bribe while the no-bounty variant is not.

**Bribery theory.** The p+ε attack (Buterin, crediting Miller; analyzed for
Schelling-game systems by George et al.) captures coordination games via
conditional payments; the known defense is deposits that force the attacker to
fund minority losses. Our judges do not play a coordination game — they
re-execute deterministic verification — and our acceptance constraint is that
deposit defense, formalized; Theorem 2′ shows the resulting cost bound is
invariant to the payment schedule, closing the conditional-promise loophole
within the model.

**zkML.** Proof systems over quantized inference (ezkl on halo2 and peers) are
approaching practicality for small models; we measure rather than assume that
our extractor is a candidate (§6).

## 3. Protocol

### 3.0 Threat model

Adversaries may: register agents and judges freely (in our minimal registries,
identity creation costs only gas — sybil pressure is borne entirely by bond
economics, §5.2 and Exp8 K2); choose and time their claims; open cases; offer
bribes to judges under any payment schedule, conditional or not; run judges and
agents as the same party (agent–judge collusion is priced, not prevented: a
colluding judge risks the same per-case bond, and the theorems in §5.2 make no
honesty assumption about any specific judge); and observe all pending
transactions (front-running the lottery is addressed by commit-reveal; proposer
bias is acknowledged, not bounded — §8.3). Out of scope: attacks on Ethereum
itself; token-value volatility (bonds are denominated in one token); griefing
financed for purely external motives (A5 — the cost lower bounds still apply,
profitability bounds do not); and non-deterministic claim classes (§8.1).

### 3.1 Bonded utterances (BondedValidator)

An agent registered in the ERC-8004 identity registry stakes collateral. A claim
(`requestValidation`) requires free bond ≥ `minBondPerClaim`, locked until
settlement and recorded through the 8004 validation registry. Settlement writes
a score (0–100) and tag: score < 50 with tag ≠ "abstain" forfeits the claim
bond; tag "abstain" is lossless regardless of score; withdrawal is delayed
(`unbondDelay`). Reputation is derived, not stored: a stateless lens computes
credit scores counting abstention separately from error, and prices collateral
by history — multipliers are design parameters set to 1.5× (newcomer) and 0.5×
(established), so that a track record halves the capital cost of speech by
construction.

### 3.2 Bonded judges and expanded trials (BondedJudgePanel v0.2 / v0.2.1)

Judging is itself a bonded utterance: judges register an 8004 identity, post
collateral, and have a per-case bond locked on assignment. A case opens with a
fixed outcome-independent fee; an initial panel of three is drawn by weighted
lottery (newcomers: 1.5× entry bond, 1/5 lottery weight). Unanimity settles. A
dissent escalates to a fresh five-judge expanded trial; the majority (≥3)
verdict is final, and every voter against it — initial or expanded — forfeits
the per-case bond.

**No winner's bounty.** Forfeited judge bonds are half-burned and half-paid to
the agent whose bond the dispute froze. Judges earn only the fixed fee,
identically on both sides of any verdict (§5 for why).

**Backstops without a superior court.** The v0.1 owner-arbiter is removed. The
backstop is a lossless timeout refund (score 50, tag "disputed": no agent slash,
no judge slash, non-participation recorded). Two matching initial votes after
the vote timeout constitute a genuine verdict — a case our own proof harness
initially mis-specified and the prover corrected (§5.3).

**Commit-reveal lottery (v0.2.1).** Case opening commits a block number; the
panel is drawn in a later block seeded by that block's hash, so the seed does
not exist when the opener chooses the request hash — eliminating free grinding.
Proposer-level bias remains (§8.3).

### 3.3 Parameters (Sepolia)

`minBondPerClaim` 1 token; judge `perCaseBond` 10; `judgeFee` 1; vote timeout
3600s; dispute timeout 86400s; veteran threshold 3; seed window 256 blocks. The
token (IISLAB) is a valueless experiment token: no sale, no listing, no plans
for either.

## 4. Empirical Results

Scope statement: Exp1, 2, 6, 7, 8, 10 carry pre-registered kill criteria in
their experiment files; Exp3 and Exp5 are scripted fixed-seed runs without
pre-registered criteria; Exp9 is contract-property verification (Foundry tests,
`BondedJudgePanelV2.t.sol`), not an experiment. All are re-runnable from the
repository. The benchmark throughout is a **synthetic multi-hop logic dataset**;
no claims about general LLM outputs are made. "Live runs" (Exp3/Exp5) execute
against a **local Anvil chain**; Sepolia deployments (§7) are the same contracts
but were not the venue of these runs.

| # | Question | Result |
|---|---|---|
| Exp1 | Does a decomposed pipeline beat end-to-end? | Pipeline 98.4% vs 65.6%/65.5% overall; +17.3pp on pre-registered trap categories (kill: <+10pp). Hallucination localizes to extraction (slot accuracy 0.995). **Confound (see §8.1): the extractor received gold intermediate supervision and a larger training budget that the end-to-end baselines did not** — the honest reading is that decomposition *enables cheap intermediate supervision and verification*, not that it wins like-for-like. |
| Exp2 | Is "I don't know" economically rational? | All 6 errors fall in the lowest-confidence 7.3% of the test set (66/910). Zero observed errors for every threshold τ ≥ 0.85 (coverage 95.2%); at the deployed τ = 0.9, coverage 92.7%. Under bonded scoring (+1/−5), abstention dominates bluffing. Observed, not guaranteed. |
| Exp3 | Does hallucination get a price? | 300 bonded utterances on Anvil (3 agents × 100 claims): coin-flipping agent 50 → 8 tokens; verifier-backed agent 50 → 49. Structural demonstration on a valueless token — behavioral deterrence is not measured (§8.5). |
| Exp5 | Does it run on the 8004 interfaces? | With abstention enabled: verifier-backed agent lossless 50 → 50 (16 abstentions, 84 correct); hallucinator 50 → 0; on-chain reputation 100/84/50. |
| Exp6 | Does honesty pay in reputation? | Abstention-neutral scoring restores the abstaining agent's credit 84 → 100 with abstention rate reported separately; risk-priced collateral applies the 0.5× design multiplier to proven agents. |
| Exp7 | Can one corrupt judge steal? | Single corrupt judge: 14/100 unjust seizures. 3-judge unanimous re-execution: 0, with all 14 disputes recorded on-chain. |
| Exp8 | Does judge bonding survive attack (in simulation)? | Monte Carlo, 20k trials/cell: bribery expected profit ≤ 0 across 5–50% bribed fractions in the no-bounty design; the winner-bounty control turns profitable from ~30%. Sybil capture of **5%** of the pool costs ~300× an honest bond (the cost of larger captures was not measured). ε = 0 → exactly 0 unjust slashes; ε = 1% → 0.6%. |
| Exp9 | Can openers grind the lottery? | Contract-property verification: drawing in the commit block reverts ("seed not born"); expired seeds force recommit; abandoned commits refund losslessly with the fee returned to the opener. |
| Exp10 | Is the extractor ZK-feasible? | Fixed-point quantization: accuracy change 0.00pp at scales 2^10–2^14 and −0.05pp (slightly *higher*) at 2^8 (n = 4,372); op census 78,976 MACs, 92 lookups → ≈2^19 rows **by a stated heuristic (4 rows/MAC + 2/lookup)**. No prover was run; proving time is unmeasured (§6). |

## 5. Formal Results

### 5.1 Contract-level theorems (symbolic execution, Halmos)

Proved over compiled bytecode, for all inputs **in the following state spaces** —
single claim, single settlement, symbolic scores (full uint8), tags bounded to
0–1024 bytes; panel proofs use a concrete 9-judge pool with a deterministic
draw (the lottery's distributional properties are probabilistic and outside SMT
scope) and symbolic votes:

- **T1 Abstention neutrality** — ∀ score, tag "abstain" leaves the bond unchanged.
- **T2 Slash exactness** — forfeiture iff (score < 50 ∧ ¬abstain), exactly
  `minBondPerClaim`; over- and arbitrary slashing unsatisfiable.
- **T3 No double settlement.**  **T4 Settlement conservation.**
- Panel refinement (implementation ≡ independently written spec):
  **PA** unanimity — none slashed, fee split three ways; **PB** majority (1,127
  paths) — only voters against the final verdict slashed, every judge's income
  exactly the fixed fee share, agent slashed iff verdict < 50; **PC** 2/2/1
  split — lossless refund, none slashed; **P4** timeout — judge bonds untouched
  in all 0–2-vote configurations; agent affected only by a genuine two-vote
  verdict.

The verdict space in PB/PC is partitioned by class (unanimous / majority /
no-majority), with the majority's *position* fixed without loss of generality —
an assumption argued by symmetry, **not machine-checked**; the unpartitioned
8-vote refinement exceeded practical SMT budget (>1 CPU-hour) and remains open.

### 5.2 Economic theorems (SMT, z3 — proofs by unsatisfiability)

Model: quorum m ≥ 3; judge per-case bond B_j; agent claim bond B_a; capture
probability p ∈ [0,1), exogenous (its relation to the number bribed is governed
by the lottery and measured only in simulation, Exp8). Assumptions, all
load-bearing:

- **A1** Judges maximize expected profit; honest re-execution carries zero slash
  risk. This idealizes the deterministic claim class — Exp8 measured 0.6% unjust
  slash at ε = 1% nondeterminism, and any positive honest risk lowers the bribe
  acceptance threshold, weakening the bound in a stated direction.
- **A2** No-bounty mechanism: forfeitures flow only to burn and agent damages;
  judge income is exactly the fixed fee (this assumption is discharged at the
  bytecode level by PB).
- **A3** Bribe acceptance: a bribed judge facing failure probability (1−p)
  accepts only if compensated for expected bond loss.
- **A4** The attacker's in-protocol gain is bounded by B_a (escaping one claim
  slash). Larger *external* stakes riding on a certified falsehood are excluded
  by **A5** — for those, our results bound the attack's *cost* from below but
  say nothing about profitability.

**Theorem 2 (conditional non-profitability).** Expected attacker profit
Π ≤ p·B_a − m(1−p)·B_j; hence Π ≤ 0 whenever B_j/B_a ≥ p/(m(1−p)). The
condition is necessary in general — removing it admits counterexamples, which
is itself machine-checked.

**Theorem 2′ (payment-schedule invariance).** The expected-cost lower bound
m(1−p)·B_j is identical under unconditional payment, pay-only-on-failure
(b_f ≥ B_j), and pay-only-on-success (b_s ≥ (1−p)B_j/p) — so p+ε-style
conditional promises do not evade it.

**Corollary (deployed parameters).** With B_j = 10·B_a, m = 3: bribery is
expected-lossy for all p ≤ 30/31 ≈ 96.8%. Tightness holds in the knife-edge
case of zero-margin bribe acceptance (b = (1−p)B_j); any real acceptance
premium strictly improves the threshold. Separately measured: capturing even 5%
of the judge pool by sybils costs ~300× an honest bond (Exp8 K2); the cost of
96.8% capture was not measured and we do not extrapolate.

**Theorem 3 (budget-feasible bounty counterexample).** Add a winner's reward
w > 0 funded only from forfeitures (w ≤ (2/3)·B_j for a 3-of-5 panel). The
acceptance constraint relaxes to b ≥ (1−p)B_j − p·w, and there exist parameters
(z3 witness: B_a = 3B_j, w = B_j/2, p = 1/2) where the bounty design is
expected-profitable to attack while the identical no-bounty design is
expected-lossy. Within this model, a winner's reward functions as a bribery
subsidy.

### 5.3 Method notes from the proving effort

The prover falsified our own specification once: we asserted "timeout is always
lossless" and symbolic execution produced the counterexample of two matching
votes with a failing score — a genuine verdict by design. Tests had not caught
this. We report it as evidence for the method and as calibration for the
reader: what is mechanized here is the settlement rules over stated state
spaces plus SMT algebra over a hand-written economic model — not an
unconditional proof of the mechanism.

## 6. Toward Proof-Carrying Judgment (zkML)

The remaining trust assumption — a majority of drawn judges honestly
re-executing — is an artifact of off-chain re-execution. Exp10 measures the
candidate path: the extractor survives fixed-point quantization without
accuracy loss (SSM gate constants fold at compile time; runtime nonlinearities
reduce to rsqrt and tanh lookups), and censuses at ≈2^19 estimated rows by a
stated heuristic. What remains before any performance claim: an ONNX/ezkl port,
measured proving and verification times, and overflow-safe accumulator design.
The protocol slot is a `proofHash` accompanying each verdict vote.

## 7. Deployments, Reproducibility, and Next Steps

Sepolia (all Sourcify exact-match): BondedValidator v0.2.1
[`0xE9bA0f2904955D57546911Ef57a75ffd5a03F0f0`](https://sepolia.etherscan.io/address/0xE9bA0f2904955D57546911Ef57a75ffd5a03F0f0),
BondedJudgePanelV2
[`0x666F90ae34d7119756CF6E41f99F6A49b0FC5775`](https://sepolia.etherscan.io/address/0x666F90ae34d7119756CF6E41f99F6A49b0FC5775);
earlier versions (v0, v0.2) and the minimal 8004 registries are tabulated in
`docs/deployments.md`. Reproduction: fixed seeds and one-command re-runs per
experiment; `halmos --contract BondedValidatorProofs`, `halmos --contract
BondedJudgePanelV2Proofs --loop 33`, `python exp13/prove.py`. The repository
state described by this draft is pinned by git tag `wp-v0.2`.

**Next steps** (each a scoped deliverable; the first three are what a small
research grant would fund):
1. zkML measurement — ONNX/ezkl port of the extractor with measured prove/verify
   times and an accumulator-width design (deliverable: report + circuit).
2. Canonical registry integration — target the mainnet ERC-8004 deployments in
   place of our minimal registries (deliverable: adapter + Sepolia rerun).
3. Third-party reproduction and audit — external re-run of experiments and
   proofs (deliverable: independent report; we will fund fixes, not rebuttals).
4. Lottery hardening — VRF or multi-party seed vs our zero-external-dependency
   stance, decided in the open (deliverable: ADR + implementation if adopted).

## 8. Limitations

1. **Benchmark and supervision confound.** The dataset is synthetic multi-hop
   logic. The extractor was trained with gold intermediate (slot-level)
   supervision and more epochs than the end-to-end baselines; Exp1 therefore
   shows that decomposition *makes intermediate supervision and symbolic
   verification available*, not that it beats end-to-end training
   like-for-like. Slashing justification is restricted to deterministic claim
   classes; ε-sensitivity was measured (0.6% unjust slash at ε = 1%), not
   eliminated.
2. **Conditional economics.** Theorem 2 is conditional on the bond ratio,
   capture probability, and assumptions A1–A5; p → 1 defeats it; judges are
   risk-neutral and one-shot; reputation effects and repeated play are
   unmodeled. External-stake attacks (A5) are cost-bounded, not
   profitability-bounded.
3. **Lottery bias.** Commit-reveal removes free grinding, not proposer bias;
   its exploitation economics are unbounded here. External VRF trades against
   our zero-external-dependency principle and is future work.
4. **Identity is free.** In our minimal registries, creating identities costs
   gas only; all sybil resistance is economic (entry bonds, newcomer weights).
   Agent–judge collusion is priced, not prevented.
5. **Valueless token.** All "economic" outcomes are accounting outcomes of
   scripted simulations on a token with no market value: they demonstrate
   mechanism structure, not measured deterrence of any real actor.
6. **Trusted history and adoption.** v0 ran with a trusted judge;
   decentralization arrived in stages and its terminal form (zk re-execution)
   is unbuilt. There is no external reproduction or third-party audit yet; this
   draft is intended to invite both.

## 9. Conclusion

The agent economy is standardizing identity (ERC-8004) and payments (x402),
with commerce proposals emerging (EIP-8183). We argue its accountability layer
should be built so that its safety claims are theorems with stated conditions,
checked by machines. This draft delivers a speaker-bonded settlement layer
whose rules — lossless abstention, exact slashing, bonded judgment, no winner's
bounty — are machine-checked at the bytecode level, and whose bribery
resistance is a conditional theorem with its conditions in the statement.

## References (draft)

- ERC-8004: Trustless Agents (Review). Ethereum Magicians thread 25098.
- Inter-Agent Trust Models: A2A, AP2, ERC-8004 and Beyond. arXiv:2511.03434.
- Buterin, V. "The P + epsilon Attack" (crediting A. Miller). George, W. et al.,
  "An Analysis of p+ε Attacks on Various Models of Schelling Game Based
  Systems," Cryptoeconomic Systems 1(2).
- UMA protocol documentation (Optimistic Oracle; DVM escalation). Kleros: Short
  Paper v1.0.7 (juror incentives; appeals).
- a16z crypto: "Symbolic testing with Halmos"; "Formal verification of Pectra
  system contracts with Halmos."
- ezkl / halo2 documentation (zkML toolchain).
- x402 payment protocol; EIP-8183 (agentic commerce, early proposal).
- VeriBond (ETHGlobal showcase); KYA Protocol (agentecon.ai); ECO/CPO-DAG
  (arXiv:2607.06804); AgentBound (arXiv:2606.30970) — non-archival, cited for
  positioning.
- This repository: experiments Exp1–Exp13, machine proofs, deployment records
  (tag `wp-v0.2`).

---

## 부록 A — 국문 요약 (오너·내부용; EF 제출본에서는 제외)

AI가 아무리 똑똑해져도 안 뚫리는 보안은 지능이 아니라 수학에 근거해야 한다.
이 백서는 "모든 AI 발화는 서명되고, 담보 잡히고, 증명된다"의 경제층이다.
대부분의 스테이킹 설계가 검증자에게 담보를 요구할 때, 우리는 **말하는 자**에게
요구한다: 담보 없이는 주장 자체가 성립하지 않고, 틀리면 정확히 그만큼만
몰수되며, 모르면 기권해 무손실이다. 판정자도 담보를 걸고, 몰수분은 승자가
아니라 소각·배상으로 흐른다 — 승자 상금은 (우리 모델 안에서, 예산 실현 가능한
형태로도) 매수 보조금이 됨을 z3 반례로 보였다. 정산 규칙은 바이트코드 수준에서
기계 증명됐고(8정리), 매수 저항은 가정 5개를 명시한 조건부 정리다(임계
30/31, 지급 스케줄 불변). 한계도 본문 §8에 전부 있다: 토이 벤치마크와 감독
confound, 무가치 토큰, 제안자 편향, 외부 재현 부재. 다음 단계는 zkML 실측,
정식 8004 레지스트리 연동, 제3자 재현·감사다.
