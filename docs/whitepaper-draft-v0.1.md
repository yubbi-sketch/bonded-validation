# Bonded Validation: Machine-Proved Economic Accountability for AI Agent Utterances

**Whitepaper draft v0.1 — 2026-08-27**
*IIS Lab (Intelligence-Invariant Security research program)*
Repository: github.com/yubbi-sketch/bonded-validation · Contracts live on Sepolia (Sourcify-verified)

> **국문 요약 (한 문단).** AI가 아무리 똑똑해져도 안 뚫리는 보안은 지능이 아니라
> 수학에 근거해야 한다. 이 백서는 그 첫 조각으로 "모든 AI 발화는 서명되고,
> 담보 잡히고, 증명된다"는 지붕 명제의 경제층을 제시한다: ERC-8004 신원 위에서
> 에이전트는 담보 없이 말할 수 없고, 틀리면 몰수되며, 모르면 기권해 무손실이다.
> 판정자도 담보를 걸고, 몰수분은 승자가 아니라 소각·배상으로 흐른다("승자 상금은
> 매수 자금이다" — 본문 정리 3). 이 규칙들은 시뮬레이션 관측이 아니라 기계 증명된
> 정리다(Halmos 심볼릭 실행 + z3). 전 실험은 재현 가능하고 킬 기준 사전 등록제로
> 수행됐다.

---

## Abstract

As AI agents begin to transact with each other — identity via ERC-8004, commerce
via EIP-8183, payments via x402 — the missing layer is *accountability for what
agents say*. We present Bonded Validation, a protocol in which every agent claim
must be collateralized before it is uttered, is settled against verification, and
carries three normative rules we prove rather than assume: **(1) abstention is
lossless** — an agent that says "I don't know" never loses its bond; **(2) slashing
is exact** — forfeiture happens precisely on verified error, in a precisely bounded
amount; **(3) no winner's bounty** — slashed funds are burned and paid as damages,
never distributed to prevailing judges, because a winner's reward is structurally a
bribery budget. Judges themselves are bonded, drawn by commit-reveal lottery, and
disciplined by expanded trials in which only the minority against the final verdict
is slashed. We report (a) empirical results across ten pre-registered experiments,
including a live 300-utterance run in which a hallucinating agent goes bankrupt
while a verifier-backed agent with calibrated abstention finishes lossless; (b)
machine-checked proofs — symbolic execution over the deployed bytecode (Halmos)
establishing the settlement rules over all inputs, and SMT theorems (z3)
establishing conditions under which bribery has non-positive expected profit, with
a tight capture-probability threshold of 30/31 ≈ 96.8% at our deployed parameters;
and (c) a feasibility census showing our 24k-parameter extractor survives
fixed-point quantization with zero accuracy loss at ≈2^19 estimated circuit rows,
opening a path from "3-of-5 honest judges" to zero-knowledge re-execution proofs.

## 1. Introduction

Security that depends on out-thinking the attacker fails the moment the attacker
thinks better. Our research program (intelligence-invariant security) asks what
remains secure when the adversary's intelligence is unbounded — and answers:
systems whose guarantees are economic and mathematical, not cognitive.

This paper develops the economic layer for one root proposition: **every AI
utterance is signed, bonded, and proven.** Signed — the utterance is bound to an
on-chain identity (ERC-8004). Bonded — the speaker cannot make the claim without
collateral at risk. Proven — settlement follows verification, with abstention as
a first-class, lossless act.

Three design commitments distinguish this work:

- **Decomposition over scale.** We do not compete on frontier capability. A small
  extractor (24,384 parameters) feeding a symbolic verifier outperforms end-to-end
  networks on multi-hop logic (98.4% vs 65.6% overall; +17.3pp on pre-registered
  trap categories), and — critically — localizes hallucination into a stage that
  can be measured, priced, and eventually proven in zero knowledge (§6).
- **Economics over trust.** Judges are not oracles we trust but stakers we
  discipline. Every rule that disciplines them is stated as a theorem and machine
  checked, including the rule that surprised us: rewarding the winning side of a
  dispute is not a defense but an attack subsidy (§5).
- **Honesty as method.** Every experiment pre-registers kill criteria before
  running. Every limitation we know of is stated in §8. Where our proofs are
  conditional or bounded, the conditions and bounds are in the theorem statements,
  not the footnotes.

## 2. Related Work

**Agent trust stacks.** ERC-8004 ("Trustless Agents") provides identity,
reputation, and validation registries, deliberately delegating collateral and
slashing to higher-level protocols — the slot this work fills. Recent comparative
work on inter-agent trust models (A2A, AP2, ERC-8004; arXiv:2511.03434) recommends
exactly this shape: bonds proportional to harm, objective slashing, insurance
layers. Emerging projects (VeriBond; KYA Protocol; ECO/CPO-DAG; AgentBound) share
the staked-claims direction. To our knowledge, none pairs the mechanism with
machine-checked proofs of its settlement rules and bribery bounds — that is this
paper's contribution, not the staking idea itself.

**Optimistic oracles and decentralized courts.** UMA settles disputes with
loser-pays and distributes forfeitures to the prevailing side; Kleros disciplines
jurors via redistributive Schelling-game staking. Our Theorem 3 shows the
winner-reward channel is itself the bribery budget: under a winner's bounty there
exist parameters where verdict-flipping is expected-profitable while the identical
no-bounty mechanism is expected-lossy. This formalizes and generalizes the
structural weakness first quantified in our attack simulations.

**Bribery theory.** The p+ε attack (Buterin/Miller) captures Schelling games at
near-zero cost via conditional payments; the known defense is security deposits
that force the attacker to fund minority losses. Our judges do not play a Schelling
game — they re-execute deterministic verification, so "truth" is checkable — and
our acceptance constraint (Assumption A3, §5) is precisely the deposit defense,
formalized and machine-checked.

**zkML.** Proof systems over quantized neural inference (e.g., ezkl on halo2) are
approaching practicality for small models. We measure, rather than assume, that our
extractor is inside that envelope (§6).

## 3. Protocol

### 3.1 Bonded utterances (BondedValidator)

An agent registered in the ERC-8004 identity registry stakes collateral. A claim
(`requestValidation`) requires free bond ≥ `minBondPerClaim`, which is locked until
settlement and recorded through the 8004 validation registry. Settlement
(`submitVerdict`) writes a score (0–100) and tag:

- score < 50 and tag ≠ "abstain" → the claim bond is forfeited;
- tag = "abstain" → lossless, regardless of score (abstention neutrality);
- withdrawal is delayed (`unbondDelay`) so an agent cannot hit-and-run.

Reputation is derived, not stored: a stateless lens computes credit scores that
count abstention separately from error, and prices collateral by history
(newcomers 1.5×, proven agents 0.5×) — honesty literally halves the capital cost
of speech.

### 3.2 Bonded judges and expanded trials (BondedJudgePanel v0.2/v0.2.1)

Judging is itself a bonded utterance. Judges register an 8004 identity and post
collateral; each case locks a per-case bond. A case opens with a fixed
outcome-independent fee; an initial panel of three is drawn by weighted lottery
(newcomers carry a 1.5× entry premium and 1/5 lottery weight). Unanimity settles.
A dissent escalates to a fresh five-judge expanded trial; the majority (≥3)
verdict is final, and every voter against it — initial or expanded — forfeits the
per-case bond.

**No winner's bounty.** Forfeited judge bonds are half-burned and half-paid to the
agent whose bond was frozen by the dispute. Judges earn only the fixed fee,
identically on both sides of any verdict. §5 proves why this is the load-bearing
design decision.

**Backstops without a superior court.** v0.1's owner-arbiter (training wheels) is
removed. The only backstop is a lossless timeout refund: unresolved cases settle
at score 50 with tag "disputed" — no agent slash, no judge slash, non-participation
recorded on-chain. Two matching initial votes after the vote timeout constitute a
genuine verdict (a property our proof harness initially mis-specified and the
prover corrected — §5.3).

**Commit-reveal lottery (v0.2.1).** Opening a case commits a block number; the
panel is drawn in a later block, seeded by that block's hash. The seed does not
exist when the opener chooses the request hash, eliminating free grinding.
Proposer-level bias remains and is stated as a limitation (§8).

### 3.3 Parameters (Sepolia deployment)

`minBondPerClaim` 1 token; judge `perCaseBond` 10 tokens; `judgeFee` 1; vote
timeout 3600s; dispute timeout 86400s; veteran threshold 3; seed window 256
blocks. All contracts Sourcify-verified; addresses in the repository's
deployments table. The experiment token is valueless by construction.

## 4. Empirical Results

All experiments are re-runnable from the repository with fixed seeds; every kill
criterion below was registered before execution.

| # | Question | Result |
|---|---|---|
| Exp1 | Does decomposition beat end-to-end? | Pipeline 98.4% vs 65.6%/65.5%; +17.3pp on trap categories (kill: <+10pp). Hallucination localized to extraction (slot acc 0.995). |
| Exp2 | Is "I don't know" economically rational? | Errors concentrate in lowest 7.3% confidence; τ=0.9 → 0 observed errors / 910, 92.7% coverage. Under (+1/−5) scoring, abstention beats bluffing. |
| Exp3 | Does hallucination get a price? | 300 live utterances: hallucinating agent 50→8 tokens (v0: →0), verifier-backed 50→49. |
| Exp5 | Does it run on the standard? | 8004-integrated: abstaining extractor lossless 50→50; hallucinator bankrupt 50→0; on-chain reputation 100/84/50. |
| Exp6 | Does honesty pay? | Abstention-neutral reputation restores 84→100 (abstention rate reported separately); risk-priced collateral 0.5× for proven agents. |
| Exp7 | Can one corrupt judge steal? | 3-judge unanimous re-execution: unjust seizures 14→0; every dissent on-chain. |
| Exp8 | Does judge bonding survive attack? | Monte Carlo (20k/cell): bribery expected profit ≤0 in the no-bounty design across 5–50% capture; **winner-bounty control flips profitable at ~30%**; 5% sybil capture costs ~300× an honest bond; ε=0 → exactly 0 unjust slashes. |
| Exp9 | Can openers grind the lottery? | Commit-reveal: draw impossible in the commit block (seed unborn); expiry → recommit; abandoned commits refund losslessly. |
| Exp10 | Is the extractor ZK-feasible? | Fixed-point quantization loss 0.00pp down to scale 2^8 (n=4,372); 78,976 MACs ≈ 2^19 estimated halo2 rows (laptop range). |

## 5. Formal Results

### 5.1 Contract-level theorems (symbolic execution, Halmos)

Over the compiled bytecode, for **all** inputs in the stated state spaces:

- **T1 Abstention neutrality.** ∀ score: tag "abstain" leaves the bond unchanged.
- **T2 Slash exactness.** Forfeiture occurs iff (score<50 ∧ ¬abstain), in exactly
  `minBondPerClaim` — over-slashing and arbitrary slashing are unsatisfiable.
- **T3 No double settlement.** A settled claim cannot settle again.
- **T4 Settlement conservation.** Settlement releases exactly one claim's lock and
  never increases any bond.

Panel layer (refinement proofs — implementation ≡ an independently written spec):

- **PA Unanimity:** ∀ score — nobody slashed, fee split three ways.
- **PB Majority (1,127 paths):** only voters against the final verdict are
  slashed; **every judge's income equals the fixed fee share** (the no-bounty
  property as a machine-checked invariant); the agent is slashed iff the verdict
  scores below threshold.
- **PC No-majority (2/2/1):** lossless refund; nobody slashed.
- **P4 Timeout:** judge bonds are untouched by timeout resolution in all 0–2-vote
  configurations; the agent is affected only by a genuine two-vote verdict.

### 5.2 Economic theorems (SMT, z3 — proofs by unsatisfiability)

Model: panel quorum m ≥ 3, judge bond B_j, agent bond B_a, capture probability
p ∈ [0,1), acceptance constraint b ≥ (1−p)·B_j (the deposit defense against
conditional p+ε-style bribes).

- **Theorem 2 (conditional non-profitability).** Attacker expected profit
  Π ≤ p·B_a − m(1−p)·B_j; hence Π ≤ 0 whenever **B_j/B_a ≥ p / (m(1−p))**.
  The condition is necessary in general (removing it admits counterexamples —
  also machine-checked, so the theorem's conditionality is itself verified).
- **Corollary (deployed parameters).** With B_j = 10·B_a and m = 3, bribery is
  expected-lossy for all capture probabilities p ≤ 30/31 ≈ 96.8%, and the
  threshold is tight. Reaching such capture via sybils costs ~300× an honest bond
  (Exp8 K2).
- **Theorem 3 (bounty counterexample).** With a winner's reward w > 0 the
  acceptance constraint relaxes to b ≥ (1−p)B_j − p·w, and there exist parameters
  where the bounty design is expected-profitable while the identical no-bounty
  design is expected-lossy (z3 witness: B_j=B_a, w=0.875·B_j, p=0.5).
  **A winner's bounty is a bribery subsidy.**

### 5.3 What proving bought us

The prover falsified our own specification once: we asserted "timeout is always
lossless," and symbolic execution produced the counterexample of two matching
votes with a failing score — which is a genuine verdict by design, correctly
slashing the agent. Tests had not caught this; exhaustive path exploration did.
We report this as evidence for the method, and as a caution: the full 8-vote
symbolic refinement was intractable in one query (>1 CPU-hour, killed), so PB/PC
partition the verdict space with a stated without-loss-of-generality assumption
on majority position; complete unpartitioned refinement remains open.

## 6. Toward Proof-Carrying Judgment (zkML)

The remaining trust assumption — "3 of 5 judges honest" — is an artifact of
re-execution being off-chain. Exp10 measures the path to replacing it: our
extractor survives fixed-point quantization losslessly (the SSM gate constants
fold at circuit compile time; runtime nonlinearities reduce to rsqrt and tanh
lookups), and censuses at ≈2^19 estimated constraint rows — well inside
laptop-provable territory for halo2-based toolchains. The design slot is a
`proofHash` accompanying each verdict vote; verification moves the judge question
from *who* judged to *whether the computation was done*. This is the program's
next experimental stage, alongside overflow-safe accumulator design and an ONNX
port for end-to-end proving-time measurement.

## 7. Deployments and Reproducibility

Sepolia (all Sourcify exact-match): BondedValidator v0 / v0.2 / v0.2.1;
BondedJudgePanel; BondedJudgePanelV2; minimal 8004 registries; valueless
LabToken. Every experiment: fixed seeds, one-command re-runs, pre-registered kill
criteria in the experiment headers. Proof re-runs: `halmos --contract
BondedValidatorProofs` / `--contract BondedJudgePanelV2Proofs --loop 33`;
`python exp13/prove.py`.

## 8. Limitations (stated, not footnoted)

1. **Toy scale.** The extractor's domain is a synthetic multi-hop logic benchmark;
   claims about general LLM outputs are not made. Slashing justification is
   restricted to deterministic claim classes (re-execution agreement); ε-model
   sensitivity was measured (0.6% unjust slash at ε=1%), not eliminated.
2. **Conditional economics.** Theorem 2 is conditional on the bond ratio and
   capture probability; p→1 defeats it. Defense-in-depth is the ratio (Corollary),
   sybil cost (Exp8 K2), and on-chain dispute records — not impossibility.
   Judges are modeled risk-neutral, one-shot; reputation and repeated play are
   not yet in the model.
3. **Lottery bias.** Commit-reveal removes free grinding, not proposer-level
   bias; external VRF trades against our zero-external-dependency principle and
   remains future work.
4. **Trusted-judge history.** v0 ran with a trusted judge; decentralization
   arrived in stages (Exp7→v0.2.1) and its terminal form (zk re-execution) is
   unbuilt.
5. **Registries.** We deploy minimal local 8004 registries; integration against
   canonical mainnet deployments is a stated next step.
6. **Adoption.** No external reproduction or third-party audit yet; this draft
   precedes, and is intended to invite, both.

## 9. Conclusion

The agent economy is standardizing identity, commerce, and payments. We argue its
missing layer — accountability for agent speech — must be built the way this
paper builds it: mechanisms whose safety claims are theorems, checked by machines,
with the conditions stated. "Every AI utterance signed, bonded, proven" is a roof
proposition; this work delivers its economic floor — bonded speech, lossless
abstention, exact slashing, bonded judgment, and the proved principle that
winners must not be paid.

## References (draft)

- ERC-8004: Trustless Agents. Ethereum Magicians thread 25098.
- Inter-Agent Trust Models: A2A, AP2, ERC-8004 and Beyond. arXiv:2511.03434.
- Buterin, V. The P + epsilon Attack (crediting A. Miller); George, W. et al.,
  An Analysis of p+ε Attacks on Schelling-Game Systems.
- UMA Optimistic Oracle documentation; Kleros: Short Paper v1.0.7.
- a16z crypto: Symbolic testing with Halmos; Formal verification of Pectra
  system contracts with Halmos.
- ezkl / halo2 zkML toolchain documentation.
- x402 payment protocol; EIP-8183 (agentic commerce).
- This repository: experiments Exp1–Exp13, proofs, and deployment records.
