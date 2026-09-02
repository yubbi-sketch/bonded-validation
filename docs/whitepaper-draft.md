# Bonded Validation: Speaker-Bonded Accountability for AI Agents, Machine-Checked and On-Chain

**Whitepaper v1.0 + addendum §6.1 — 2026-08-27**
*Addendum (post-v1.0): §6.1 adds the post-quantum proof-layer path (Exp21–23) and the
implemented ZkVerdictGate (Exp20). The §4 experiment table still reflects the v1.0
set; Exp20–23 are described in §6 and in `docs/{quantum-resistance,stark-migration}.md`.*
*IIS Lab — an independent, currently pseudonymous research effort. Contact: github.com/yubbi-sketch (repo issues) · yubbi85@gmail.com.*
Repository: github.com/yubbi-sketch/bonded-validation (MIT) · Contracts on Sepolia, Sourcify-verified (§8)
No token launch, no sale: the experiment token is valueless by construction and testnet-only.

## Abstract

Most staking designs for AI agent trust bond the *validator*; this work bonds the
**speaker**: an agent cannot make a claim at all unless its own collateral is at
risk behind that claim. We build this as a settlement layer over the ERC-8004
agent registries and study it along three axes we keep explicitly separate.

**(1) Machine-checked settlement rules (unconditional over stated state spaces).**
Symbolic execution of the deployed bytecode (Halmos) proves, over all inputs in
the stated spaces: abstention is lossless; slashing is exact (precisely on a
verified failing verdict, in a precisely bounded amount); settled claims cannot
settle twice; and, at the judge-panel layer, only voters against the final
verdict are slashed while every judge's protocol income equals a fixed,
outcome-independent fee.

**(2) Conditional economic security (theorems over a stated model).** Judges are
themselves bonded and disciplined by expanded trials. Under five explicit
assumptions we prove (z3, by unsatisfiability): bribery has non-positive
expected profit whenever the judge/agent bond ratio satisfies B_j/B_a ≥
p/(m(1−p)) — at deployed parameters, for capture probabilities up to 30/31 ≈
96.8% — and the expected-cost lower bound is invariant to the bribe payment
schedule, including p+ε-style conditional promises. Conversely, a winner's
reward funded from forfeitures admits budget-feasible parameters that flip the
identical mechanism from expected-lossy to expected-profitable to attack: within
this model, **a winner's bounty is a bribery subsidy** — our sharpest departure
from redistributive designs (UMA, Kleros).

**(3) The proven incentives, made real.** We close the loop empirically: a
zero-knowledge re-execution proof of the full extractor forward pass, measured
end-to-end (ezkl/halo2: 17.2 s to prove, 0.1 s to verify, and **864,652 gas** to
verify on-chain, in a 19,683-byte verifier under EIP-170); a binding circuit that
ties each proof to its input hash, model, and outputs so a proof cannot be
replayed against a different *input* (case-level requestHash binding is future
work, §6); and a **living economy** in which self-interested adaptive agents
*converge*, unscripted, to the honest equilibrium the theorems predict (Exp18,
simulation), which forty fixed-strategy wallets then *reproduce on-chain* on the
deployed contract — a majority (6/9) of unconfident gamblers go bankrupt while
calibrated agents grow, token conservation exact (Exp19).

We report **sixteen experiments (twelve with pre-registered kill criteria; Exp9
and Exp13 are formal verifications; one criterion — Exp18 K1 — we report as
failed rather than bend)** on a synthetic multi-hop logic benchmark. Every
limitation we know of is in §9.

## 1. Introduction

Security that depends on out-thinking the attacker fails when the attacker thinks
better. Our program asks for guarantees that do not depend on out-thinking
anyone — properties that hold, under stated conditions, whatever the adversary's
intelligence. This is the **intelligence-invariant** stance, and this paper is
its economic layer for one root proposition: **every AI utterance signed, bonded,
proven.** We propose the interface as an open, MIT-licensed ERC draft filling the
collateral/slashing slot ERC-8004 deliberately delegates upward.

Contributions:

1. **A speaker-bond protocol** on ERC-8004: claims require locked collateral,
   abstention is a first-class lossless act, withdrawal is delayed, reputation is
   derived statelessly with abstention counted separately from error (§3).
2. **Bonded judging without a superior court**: weighted-lottery panels,
   expanded trials slashing only the minority against the final verdict, a
   commit-reveal lottery closing free grinding, lossless-timeout backstops
   replacing any owner arbiter (§3).
3. **Machine-checked settlement rules**: eight symbolic-execution theorems over
   the compiled contracts, including the no-bounty property as a bytecode-level
   invariant (§5.1).
4. **The no-bounty theorems**: conditional non-profitability with an explicit
   bond-ratio threshold, payment-schedule invariance, and a budget-feasible
   counterexample where winner rewards make attack profitable (§5.2).
5. **Proof-carrying judgment, measured**: a full zk proof of the extractor,
   on-chain verification gas, and an input/model/output-binding circuit (§6).
6. **A living on-chain economy**: emergent convergence of self-interested
   autonomous agents to the theorem-predicted honest equilibrium, in simulation
   and on the deployed contract (§7).

Method commitments: kill criteria are registered before experiments run (§4);
limitations are collected in §9, including an intermediate-supervision confound
that reframes our headline benchmark. We have killed our own work on these
grounds before — our original account-hierarchy ERC ambition was terminated when
two independent reviews found the slot occupied, and the program pivoted here.

## 2. Related Work

**Agent trust stacks.** ERC-8004 ("Trustless Agents", in Review) provides
identity, reputation, and validation registries and delegates collateral and
slashing upward — the slot this work fills. A comparative study of inter-agent
trust models (arXiv:2511.03434) recommends this shape: bonds proportional to
harm, objective slashing. Among emerging staked-claims projects, **VeriBond**
(ETHGlobal) posts stake behind claims with deterministic on-chain resolution but,
to our knowledge, offers no lossless-abstention primitive and no machine-checked
settlement rules; **KYA Protocol** builds 8004-compliant staked validation on
Base; **ECO/CPO-DAG** and **AgentBound** (arXiv preprints) propose claim-bond
accountability layers. These are early, mostly non-archival; we cite them for
positioning. Our claimed novelty is not staking but pairing the mechanism with
machine-checked proofs, with abstention as a protected act, and with an on-chain
demonstration that self-interest converges to the proven equilibrium.

**Optimistic oracles and decentralized courts.** UMA settles loser-pays,
distributing forfeitures to the prevailing side, with escalation to a
token-holder vote; Kleros disciplines jurors through redistributive
Schelling-game staking with fee-funded appeals. Our Theorem 3 concerns the
winner-reward channel in a one-shot panel under our stated model; it does not
model UMA's escalation game or Kleros's appeals, and we present it as a design
principle for our mechanism class, not a break of those systems. It establishes:
within a budget-feasible bounty (paid only from forfeited bonds), there exist
parameters where the bounty variant is bribe-profitable while the no-bounty
variant is not.

**Bribery theory.** The p+ε attack (Buterin, crediting Miller; George et al. for
Schelling systems) captures coordination games via conditional payments; the
known defense is deposits forcing the attacker to fund minority losses. Our
judges do not play a coordination game — they re-execute deterministic
verification — and our acceptance constraint is that deposit defense, formalized;
Theorem 2′ shows the cost bound is schedule-invariant, closing the
conditional-promise loophole within the model.

**zkML.** Proof systems over quantized inference (ezkl on halo2 and peers) are
approaching practicality for small models; we **measure** rather than assume that
our extractor is a candidate (§6), including on-chain verification cost.

## 3. Protocol

### 3.0 Threat model

Adversaries may: register agents and judges freely (identity costs only gas —
sybil pressure is borne entirely by bond economics, §5.2 and Exp8 K2); choose and
time claims; open cases; offer bribes under any payment schedule; run judges and
agents as the same party (collusion is priced, not prevented — the theorems make
no honesty assumption about any specific judge); and observe pending transactions
(front-running the lottery is addressed by commit-reveal; proposer bias is
acknowledged, not bounded — §9.3). Out of scope: attacks on Ethereum itself;
token-value volatility; griefing financed for purely external motives (A5 — cost
lower bounds still apply, profitability bounds do not); and non-deterministic
claim classes (§9.1).

### 3.1 Bonded utterances (BondedValidator)

An agent registered in the 8004 identity registry stakes collateral. A claim
(`requestValidation`) requires free bond ≥ `minBondPerClaim`, locked until
settlement and recorded through the 8004 validation registry. Settlement writes a
score (0–100) and tag: score < 50 with tag ≠ "abstain" forfeits the claim bond;
tag "abstain" is lossless regardless of score; withdrawal is delayed. Reputation
is derived, not stored: a stateless lens counts abstention separately from error
and prices collateral by history — multipliers 1.5× (newcomer) / 0.5×
(established), so a track record halves the capital cost of speech by construction.

### 3.2 Bonded judges and expanded trials (BondedJudgePanel v0.2 / v0.2.1)

Judging is itself a bonded utterance: judges register an 8004 identity, post
collateral, and have a per-case bond locked on assignment. A case opens with a
fixed outcome-independent fee; an initial panel of three is drawn by weighted
lottery (newcomers: 1.5× entry bond, 1/5 lottery weight). Unanimity settles. A
dissent escalates to a fresh five-judge expanded trial; the majority (≥3) verdict
is final, and every voter against it — initial or expanded — forfeits the
per-case bond.

**No winner's bounty.** Forfeited judge bonds are half-burned and half-paid to
the agent whose bond the dispute froze. Judges earn only the fixed fee,
identically on both sides of any verdict (§5).

**Backstops without a superior court.** The v0.1 owner-arbiter is removed; the
backstop is a lossless timeout refund (score 50, tag "disputed"). Two matching
initial votes after the vote timeout constitute a genuine verdict — a case our
own proof harness initially mis-specified and the prover corrected (§5.3).

**Commit-reveal lottery (v0.2.1).** Case opening commits a block number; the panel
is drawn in a later block seeded by that block's hash, so the seed does not exist
when the opener chooses the request hash — eliminating free grinding.
Proposer-level bias remains (§9.3).

**Second backstop — optimistic lapse (v0.3, Exp30; branch, not yet deployed).**
v0.2.1 had a liveness gap: a claim locks bond at `requestValidation`, but the only
release path was a verdict, and a verdict requires someone to *pay the fee to open
a case*. An unopened claim stayed locked forever (a one-year warp still returned
"claims pending"). v0.3 records `claimedAt` and a challenge window `W`: inside the
window the panel's `openCase` marks the claim *engaged* (judge-only); once the
window closes an **unengaged** claim can be released by anyone, with zero token
movement, as score 50 / tag "unchallenged" — *not* a verification, an unverified
release. `engage` (`<`) and lapse (`≥`) partition every timestamp, so there is no
race at the edge. A commit that never drew a panel (pool < 3) is **reset**, not
settled — fee returned, mark cleared, window still running — which closes the
self-open bypass that would otherwise shrink an effective window to one vote
timeout. No reimbursement or bounty is attached to opening a case: `R_c = 0` is
forced by an impossibility (§5.2, S6) — a positive challenger payoff makes the
opener+judge coalition's income outcome-dependent, i.e. the Theorem 3 subsidy
relocated to the opener. The price is that deterrence becomes conditional on the
probability `q` that a false claim is engaged inside `W` (§9.8). Every claim is
now settleable by permissionless calls within
`T_max = W + 2·voteTimeout + disputeTimeout` (Forge-measured, §5.1).

**A pre-existing wedge, fixed in the same version.** `voteVerdict` accepted any
`uint8` score while the registry requires `≤ 100`: two matching initial votes of
101 made every settlement path revert forever ("range"), locking the agent's
whole stake and three judges' case bonds. Halmos had not seen it because a
reverting path is discarded, not reported (P4 was vacuous there). v0.3 bounds
score (≤ 100), tag length (≤ 1024 B — settlement gas exceeds voting gas at every
measured tag size, so an unbounded tag can make a vote land while its settlement
cannot) and forbids judges from voting the reserved tags "unchallenged" /
"disputed". PL1 now proves the timeout path *does not revert* for all score pairs.

### 3.3 Parameters (Sepolia)

`minBondPerClaim` 1 token; judge `perCaseBond` 10; `judgeFee` 1; vote timeout
3600 s; dispute timeout 86400 s; veteran threshold 3; seed window 256 blocks. The
token (IISLAB) is valueless: no sale, no listing, no plans for either.
v0.3 adds `challengeWindow W = 86,400 s` (**provisional**, pre-registered with the
lower-bound rule `W ≥ k·(forced-inclusion delay) + voteTimeout`, `k ≥ 2`; the
final value waits on measured L1/L2 inclusion delays), giving `T_max = 180,000 s`.

## 4. Empirical Results

Scope: Exp1, 2, 6, 7, 8, 10, 14, 15, 16, 17, 18, 19 carry pre-registered kill
criteria; Exp3 and Exp5 are scripted fixed-seed runs without them; Exp9 is
contract-property verification and Exp13 is z3 economic-theorem verification
(§5.2). **Exp18's K1 failed as pre-registered and we report it as a failure.** Benchmark: a **synthetic multi-hop logic
dataset** — no claims about general LLM outputs. "Live/on-chain" runs execute
against a **local Anvil chain**; Sepolia deployments (§8) are the same contracts.

| # | Question | Result |
|---|---|---|
| Exp1 | Decomposed pipeline vs end-to-end? | 98.4% vs 65.6%/65.5%; +17.3 pp on pre-registered trap categories (kill <+10 pp); hallucination localizes to extraction (slot 0.995). **Confound (§9.1): the extractor got gold intermediate supervision and more epochs** — the honest reading is decomposition *enables cheap intermediate supervision*, not like-for-like superiority. |
| Exp2 | Is "I don't know" rational? | All 6 errors in the lowest-confidence 7.3% (66/910). Zero observed errors for τ ≥ 0.85 (coverage 95.2%); at τ = 0.9, 92.7%. Under (+1/−5) bonded scoring, abstention dominates bluffing. Observed, not guaranteed. |
| Exp3 | Does hallucination get a price? | 300 bonded utterances on Anvil: coin-flipper 50 → 8; verifier-backed 50 → 49. Structural demo on a valueless token (§9.5). |
| Exp5 | Runs on 8004 interfaces? | Abstaining verifier-backed agent lossless 50 → 50 (16 abstain, 84 correct); hallucinator 50 → 0; on-chain reputation 100/84/50. |
| Exp6 | Does honesty pay in reputation? | Abstention-neutral scoring restores 84 → 100 (abstention rate separate); 0.5× collateral for proven agents. |
| Exp7 | Can one corrupt judge steal? | Single corrupt judge 14/100 unjust seizures; 3-judge unanimous re-execution 0, all 14 disputes on-chain. |
| Exp8 | Judge bonding survives attack (sim)? | Monte Carlo 20k/cell: bribery E[profit] ≤ 0 across 5–50% capture (no-bounty); the winner-bounty control raises E[profit] toward zero at *every* fraction (subsidizing the attack) — least-negative −0.29 at 50% — but does **not** cross positive in this sim; the *profitable* bounty regime is established analytically (Theorem 3, Exp13), not by this Monte Carlo (**correction from wp-v1.0, which mis-stated a ~30% positive crossover** — see REPRODUCTION.md). Sybil capture of **5%** costs ~300× an honest bond (larger captures unmeasured). ε = 0 → 0 unjust slashes; **ε = 1% → 0.048 wrongful slashes/panel (≈0.96%/judge)** (< 2% limit). |
| Exp9 | Can openers grind the lottery? | Contract-property: drawing in the commit block reverts; expired seeds force recommit; abandoned commits refund losslessly, fee returned to opener. |
| Exp10 | Extractor ZK-feasible? | Quantization: 0.00 pp change at scales 2^10–2^14, −0.05 pp at 2^8 (n = 4,372); census 78,976 MACs → ≈2^19 rows by a stated heuristic. Prover not yet run (see Exp14). |
| Exp13 | Is "no bounty" provable, not just simulated? | The Exp8 result formalized: seven z3 checks — bond-ratio threshold, payment-schedule invariance, and a budget-feasible bounty counterexample — all pass (§5.2). Formal verification, not a kill-criteria experiment. |
| Exp14 | Does the extractor actually prove? | Full forward pass proven+verified (ezkl/halo2): logrows 18, **prove 17.2 s, verify 0.1 s**, proof 40 KB, peak 5.3 GB; circuit argmax = float on 20/20. K1–K3 passed. Single-sentence only. |
| Exp15 | zk verdict on-chain — how much? | ezkl EVM verifier on Anvil verifies the real proof: **864,652 gas** (2.9% of block limit), code **19,683 B < EIP-170 24,576** (no limit lift needed). Optimistic use → cost only on dispute. |
| Exp16 | Can a proof be replayed? | Binding circuit (input Poseidon hash + outputs as 63 public instances, model = verifier vk): tampering the claimed **input hash** is **cryptographically rejected** on-chain (output-instance tampering is likewise expected but was demonstrated only via the input-hash case; case↔requestHash binding is off-chain, future work). Gas 975,182; code 24,257 B (**319 B under EIP-170** — a hard margin, §9.3). |
| Exp17 | Can the service token become an investment? | Regulation-invariant voucher: the four properties (no appreciation / transfer / pooling / yield) are **machine-checked** (Halmos 7/7) as invariants over its six external state-changing functions (buy/refund proven for amt < 1e30, not all uint256; coverage rests on manual surface enumeration). Structure, not a legal opinion (§7.2, §9.6). |
| Exp18 | Do the proven incentives yield the honest equilibrium? | Agent-based sim: self-interested adaptive agents hill-climb, unscripted, so the **population mean** threshold reaches **τ* = B/(B+R) = 0.4** (mean learned θ = 0.447, σ = 0.215 — individuals stay dispersed); a winner-bounty control revives the gambler (Theorem 3, behaviorally). **K1 (gambler extinct) failed as pre-registered** — "always answer" pays if competent; the mechanism punishes *unconfident* answering, shown by K2 and by incompetent gamblers reaching 100% bankruptcy. |
| Exp19 | Does the equilibrium hold on the real contract? | On-chain pilot, 40 autonomous wallets × 25 rounds on the deployed BondedValidator: rational agents net 20 → 39.1 (1/26 bankrupt); unconfident gamblers 20 → 14.9 (**6/9 bankrupt**); abstainers 20.0 flat. **Token conservation exact.** |

## 5. Formal Results

### 5.1 Contract-level theorems (symbolic execution, Halmos)

Proved over compiled bytecode, for all inputs **in stated state spaces** — single
claim/settlement, symbolic scores (full uint8), tags 0–1024 bytes; panel proofs
use a concrete 9-judge pool with a deterministic draw (lottery distribution is
outside SMT scope) and symbolic votes:

- **T1 Abstention neutrality**; **T2 Slash exactness** (forfeiture iff score < 50
  ∧ ¬abstain, exactly `minBondPerClaim`; over-/arbitrary slashing unsatisfiable);
  **T3 No double settlement**; **T4 Settlement conservation**.
- Panel refinement (implementation ≡ independently written spec): **PA** unanimity
  (none slashed, fee split three ways); **PB** majority, 1,127 paths (only voters
  against the final verdict slashed, every judge's income exactly the fixed fee,
  agent slashed iff verdict < 50 — **the no-bounty invariant, machine-checked**);
  **PC** 2/2/1 split (lossless refund); **P4** timeout (judge bonds untouched in
  all 0–2-vote configurations).

PB/PC partition the verdict space by class, with the majority's *position* fixed
without loss of generality — argued by symmetry, **not machine-checked**; the
unpartitioned 8-vote refinement exceeded practical SMT budget and remains open.

v0.3 (Exp30, `BondedValidatorV3Proofs` 10/10 · `BondedJudgePanelV3Proofs`, symbolic
`dt` over `uint64`, concrete `W`): **T1–T4 regress unmodified** on the new
contract; **L1** lapse is lossless and complete (∀ dt ≥ W: bond, slashedTotal and
contract balance unchanged, atRisk released by exactly `minBondPerClaim`, registry
= (50, "unchallenged")); **L2** no early lapse (∀ dt < W); **L3** enabled(engage)
XOR enabled(lapse) at every dt, and the verdict path is closed with the window;
**L4** an engaged claim never lapses, and after `disengage` it behaves exactly as
unengaged; **L5** single settlement across both paths. Panel: **PA/PB/PC/P4
regress unmodified**; **PL1** ∀ (s1, s2) ≤ 100 the timeout after two votes does
not revert (asserted on the raw call — the region where P4 had been vacuous) and
∀ s > 100 the vote itself reverts; **PL2** a commit timeout with no panel is a
reset (phase None, fee back to the opener, mark cleared, claim unsettled); **PL3**
reserved tags are refused and lapse leaves every judge's (bond, atRisk,
settledCount, slashedTotal, balance) unchanged. Forge (measurement, not proof):
settlement within `T_max` on every reachable state, including the worst path
(open at the last second, draw at the exact commit-timeout second — `drawPanel`
and `drawExpanded` carry no upper deadline, so an adversary can pre-empt the
reset at the boundary — disputed initial timeout, expanded timeout) at
`T_max − 1 s`, strictly inside `T_max`. An earlier draft of this paragraph said
"exactly `T_max − 2 s`" from a draw one second *before* the timeout; independent
re-verification (2026-09-03) found the tighter boundary path. The bound is
unchanged; the stated worst path was.

### 5.2 Economic theorems (SMT, z3 — proofs by unsatisfiability)

Model: quorum m ≥ 3; judge per-case bond B_j; agent claim bond B_a; capture
probability p ∈ [0,1), exogenous. Five load-bearing assumptions: **A1** rational
judges, honest re-execution zero-slash-risk (idealizes the deterministic class —
Exp8 measured ≈0.96% wrongful slash per judge at ε = 1% (0.048/panel); any positive risk weakens the bound in
a stated direction); **A2** no-bounty (forfeitures flow only to burn + agent
damages; judge income exactly the fee — discharged at bytecode by PB); **A3**
bribe acceptance (a bribed judge accepts only if compensated for expected bond
loss); **A4** attacker in-protocol gain ≤ B_a; **A5** external motives out of
scope (cost-bounded, not profitability-bounded).

**Theorem 2 (conditional non-profitability).** Π ≤ p·B_a − m(1−p)·B_j; hence
Π ≤ 0 whenever B_j/B_a ≥ p/(m(1−p)). The condition is necessary in general —
removing it admits counterexamples, itself machine-checked.

**Theorem 2′ (payment-schedule invariance).** The expected-cost lower bound
m(1−p)·B_j is identical under unconditional, pay-on-failure, and pay-on-success
schedules — so p+ε conditional promises do not evade it.

**Corollary (deployed parameters).** B_j = 10·B_a, m = 3 ⇒ bribery expected-lossy
for all p ≤ 30/31 ≈ 96.8%; tightness holds only at zero-margin acceptance, any
real premium improves it. Separately: 5% sybil capture costs ~300× an honest bond
(Exp8 K2); 96.8% capture cost unmeasured, not extrapolated.

**Theorem 3 (budget-feasible bounty counterexample).** A winner's reward w > 0
funded only from forfeitures (w ≤ (2/3)·B_j for 3-of-5) relaxes acceptance to
b ≥ (1−p)B_j − p·w, and there exist parameters (z3 witness B_a = 3B_j, w = B_j/2,
p = 1/2) where the bounty design is bribe-profitable while the identical
no-bounty design is not. **Within this model, a winner's reward is a bribery
subsidy.** (Seven z3 checks pass; see `exp13/prove.py`.)

### 5.3 Method notes

The prover falsified our own spec once: we asserted "timeout is always lossless"
and symbolic execution produced the counterexample of two matching votes with a
failing score — a genuine verdict by design that tests had not caught. What is
mechanized here is the settlement rules over stated state spaces plus SMT algebra
over a hand-written economic model — not an unconditional proof of the mechanism.

## 6. Proof-Carrying Judgment, Measured (zkML)

The remaining trust assumption — a majority of drawn judges honestly re-executing
— is an artifact of off-chain re-execution. We measured the replacement path
end-to-end:

- **Proving (Exp14).** The full extractor forward pass proves in **17.2 s** and
  verifies in **0.1 s** on a laptop (ezkl/halo2, logrows 18, 40 KB proof, 5.3 GB
  peak), circuit argmax matching float on 20/20 held-out sentences. Quantization
  is lossless (SSM gate constants fold at compile time; runtime nonlinearities
  reduce to rsqrt/tanh lookups).
- **On-chain verification (Exp15).** ezkl's EVM verifier verifies the real proof
  on-chain for **864,652 gas** — 2.9% of the block limit, well inside the range
  for dispute-time verification — in a **19,683-byte** contract, under EIP-170
  without lifting the size limit. Under an optimistic design, proofs are produced
  only on dispute, so steady-state cost is zero.
- **Binding (Exp16).** A binding circuit exposes the input Poseidon hash and the
  outputs as 63 public instances, with the model commitment being the verifier's
  baked-in vk; a proof whose input-hash instance is altered is **cryptographically
  rejected** on-chain (output-instance tampering is likewise expected, shown via
  the input-hash case). Cost rises to 975,182 gas and 24,257 bytes — **319 bytes
  under EIP-170**, a hard margin we flag: the further binding needed for a full
  protocol integration (requestHash in the instance — the case↔input mapping is
  still off-chain — and symbolic-stage coverage) must fit or move to
  L2/aggregation.

The protocol slot is a `proofHash` on each verdict vote. We deliberated the rule
changes this enables (a proven vote immune from slashing, overriding the majority
for deterministic claims) with an adversarial and a mechanism-design pass. The
verdict: the immunity rule is safe only with full end-to-end binding and on-chain
score determination; the override and conflict-slashing rules must be redesigned
(permissionless attestation, truth-gated cost-capped reimbursement that provably
does not become a Theorem-3 bounty, non-retroactive same-phase slashing) before
they are safe. Implementation is gated on that binding and on a charter decision,
and is deferred — we present the design, not a deployed rule change.

The safe subset of that design **is** implemented: a `ZkVerdictGate` (Exp20)
that sits as the validator's judge, forces `instances[0] == requestHash`
(closing the wrong-input attack) and `instances[1] == score` (closing the
partial-pipeline attack), settles the deterministic case, and reimburses the
prover a capped, outcome-independent amount (not a Theorem-3 bounty). Its
decision logic — binding, score determination, single-settlement, capped
reimbursement — is machine-checked (Halmos). It deliberately omits panel
override and conflict-slashing, which the deliberation killed as unsafe until
binding is complete; the gate settles directly, so no conflicting vote exists to
mis-slash.

### 6.1 Post-quantum: the proof layer's transparent path (Exp21–23)

The verifier above (halo2-KZG) is **pairing-based, hence not post-quantum**: a
quantum adversary with Shor's algorithm forges proofs. A dependency audit
(Exp21) classifies the whole stack — ECDSA and KZG are Shor-broken; keccak and
Poseidon are only Grover-weakened (256→128 bit, safe); and the economic core
(bonds, slashing, Theorems 2–3) is **hardness-assumption-free**, hence invariant
to a quantum adversary *as mathematics*. The composition caveat is stated
explicitly: those theorems presuppose an unforgeable signature/verdict layer, so
"quantum-invariant economic core" describes the model, not the deployed system's
survival — which holds only once the cryptographic shell is replaced.

We took two concrete steps on that shell. For **speech authentication**, a
hash-only signature (WOTS, the SLH-DSA/FIPS-205 leaf primitive; Exp21) — correct,
forgery-resistant, and one-time-safe on 200 utterances, resting only on
collision resistance (≈128-bit classical). For the **proof layer**, we
demonstrated the transparent replacement end-to-end: a hash-only FRI low-degree
proof (Exp22) over our scan recurrence — Fiat-Shamir-bound, with genuinely
β-dependent folding, rejecting high-degree, forged, and tampered inputs, using
SHA-256 with no pairing and no trusted setup. (This is educational-grade over a
31-bit field; an adversarial review caught and we fixed a broken first version.)

The **production migration decision** (Exp23) is risc0 zkVM as primary: port the
forward pass — validated as an exact integer computation whose argmax matches the
float model on 100/100 sentences — as a Rust guest and prove it with a STARK/FRI
receipt. **Critical caveat, stated because it undoes the whole point if missed:**
risc0's default pipeline wraps the STARK in a Groth16-on-BN254 SNARK (a pairing
*and* a trusted setup), so a post-quantum deployment **must keep the succinct
STARK receipt and refuse the Groth16 wrap**. Public benchmarks put our workload
at single-digit-to-tens-of-seconds proving, <1–2 GB GPU memory, tens-of-KB
succinct proof. The full production proof was **not run** here — it needs a Rust
toolchain absent from our environment — so this is a designed, primitive-
demonstrated, migration-decided path, not an executed one; Fiat-Shamir's quantum
knowledge-soundness also remains an open academic question. See
`docs/quantum-resistance.md` and `docs/stark-migration.md`.

## 7. The Proven Incentives, Made Real

### 7.1 A living on-chain economy (Exp18, Exp19)

Proving the incentive is right is one direction; the other is whether
self-interested agents actually reach the honest equilibrium. In an agent-based
simulation (Exp18), adaptive agents starting from random thresholds hill-climb, on
their own payoff alone, toward the optimal answer threshold **τ* = B/(B+R)**
(analytically 0.4); the population *mean* learned threshold reaches 0.447 (σ =
0.215 — individual thresholds remain dispersed, so the equilibrium is a
population-level result), regardless of competence. Turning on a
winner-bounty revives the always-gamble strategy (Theorem 3, behaviorally). Our
pre-registered K1 ("gamblers go extinct") **failed**: "always answer" pays for a
competent agent — the mechanism punishes *unconfident* answering, not answering,
which K2 (threshold emergence) and the 100% bankruptcy of incompetent gamblers
show precisely. We report the failure rather than restate the criterion.

Exp19 puts this on the deployed contract: forty autonomous wallets register 8004
identities, stake, and make bonded utterances over 25 rounds, an oracle settling
each (correct → reward transfer, wrong → slash). Rational agents grow 20 → 39.1
(1/26 bankrupt); unconfident gamblers bleed to 20 → 14.9 with **6/9 bankrupt**;
abstainers stay flat; **token conservation is exact**. The equilibrium the
theorems predict emerges, in money, on the real mechanism.

### 7.2 A companion result — regulation-invariant tokens (Exp17)

The same method — replace dependence on an adversary's freedom with a proven
structural invariant — extends beyond security to *legality*. A service token can
be built so it cannot become an investment instrument: a voucher whose four
properties (no appreciation, no transfer, no pooling, no yield) are machine-checked
(Halmos 7/7) as invariants over its six external state-changing functions (the
value-multiplying buy/refund paths proven for amt < 1e30, and coverage resting on
manual enumeration of that surface), so no execution path creates investment
substance. This is **structure, not a legal opinion** (§9.6):
it minimizes regime-dependence, it does not certify compliance in any
jurisdiction. We include it as evidence the invariant method generalizes; it is a
separate mechanism from the core protocol.

## 8. Deployments, Reproducibility, Next Steps

Sepolia (all Sourcify exact-match): BondedValidator v0.2.1
`0xE9bA0f2904955D57546911Ef57a75ffd5a03F0f0`, BondedJudgePanelV2
`0x666F90ae34d7119756CF6E41f99F6A49b0FC5775`; earlier versions and the minimal
8004 registries in `docs/deployments.md`. Reproduction: fixed seeds and
one-command re-runs per experiment; `halmos --contract BondedValidatorProofs` /
`BondedJudgePanelV2Proofs --loop 33` / `ServiceVoucherProofs`; `python
exp13/prove.py`; `python exp19/run_exp19.py`. Pinned by git tag `wp-v1.0`.

**Next steps** (the first three fundable by a small research grant): (1) proofHash
integration — requestHash-in-instance binding + on-chain score determination +
the redesigned rules of §6; (2) canonical registry integration in place of the
minimal registries; (3) third-party reproduction and audit (we fund fixes, not
rebuttals); (4) lottery hardening (VRF or multi-party seed vs zero-external-
dependency, decided in the open).

## 9. Limitations

1. **Benchmark and supervision confound.** Synthetic multi-hop logic; the
   extractor had gold intermediate supervision and more epochs than baselines —
   Exp1 shows decomposition *makes intermediate supervision available*, not
   like-for-like superiority. Slashing justification is deterministic-class only;
   ε-sensitivity measured (≈0.96%/judge at ε = 1%), not eliminated.
2. **Conditional economics.** Theorem 2 is conditional on bond ratio, capture
   probability, and A1–A5; p → 1 defeats it; judges are risk-neutral, one-shot;
   reputation and repeated play unmodeled; external-stake attacks (A5)
   cost-bounded only.
3. **Lottery bias and circuit margin.** Commit-reveal removes free grinding, not
   proposer bias (unbounded here; VRF is future work). The binding verifier sits
   319 bytes under EIP-170 — further binding may not fit L1 without aggregation.
4. **Identity is free.** Creating identities costs only gas; all sybil resistance
   is economic. Collusion is priced, not prevented.
5. **Valueless token; simulated agents; local chain; trusted oracle.** Every
   "economic" outcome is accounting on a valueless token; Exp18 agents are
   simulated optimizers, not humans; Exp19 runs on a local Anvil chain with a v0
   trusted oracle and a central reward pool. These demonstrate mechanism behavior
   at scale, not real-money deterrence.
6. **Regulation-invariance is structural, not legal.** Exp17 proves the token has
   no investment substance by construction — over six external functions, with
   buy/refund proven for amt < 1e30 (not all uint256) and coverage resting on a
   manual enumeration of the state-changing surface. It is not a legal opinion,
   and any real deployment needs licensed counsel; it minimizes regime-dependence,
   it does not guarantee any classification.
7. **Adoption.** No external reproduction or third-party audit yet; this version
   is intended to invite both.
8. **Conditional deterrence under optimistic lapse (v0.3).** With a challenge
   window, a false claim is punished only if someone pays to engage it inside `W`:
   the expected penalty is `q·B_a`, exactly `(1−q)·B_a` less than v0.2.1 (z3 R1),
   and a lie whose harm is dispersed (no single victim gains more than fee + gas
   by challenging) faces `q = 0` in equilibrium. We could not buy challenger
   supply: every optimistic precedent we measured (UMA OOv3, OP fault proofs) pays
   the loser's bond to the winner, which Theorem 3 forbids; and any challenger
   payoff `R_c > 0` with a positive fee makes coalition income outcome-dependent
   (S6, unsat). So v0.3 buys a *bound on lock time*, not deterrence; "unchallenged"
   is an unverified release and consumers must not count it as verification. A
   judging pool below three for the whole window turns lapse into a lossless exit
   for a liar; the registry sees each lapse as a 50-point response unless it
   filters the tag; a settlement whose fee transfer reverts (hook/blacklist
   tokens) would still wedge — LabToken cannot, real tokens are unverified.
   Proofs are single-claim with concrete `W`; `W = 86,400 s` is provisional.

## 10. Conclusion

The agent economy is standardizing identity (ERC-8004) and payments (x402), with
commerce proposals emerging (EIP-8183). Its accountability layer, we argue, should
be built so its safety claims are theorems with stated conditions, checked by
machines — and then shown to hold in money on the real mechanism. This paper
delivers a speaker-bonded settlement layer whose rules are machine-checked at the
bytecode level, whose bribery resistance is a conditional theorem with its
conditions in the statement, whose zk re-execution path is measured on-chain, and
whose predicted honest equilibrium emerges among autonomous agents on the deployed
contract. Every AI utterance signed, bonded, proven — and now, demonstrably,
priced.

## References

- ERC-8004: Trustless Agents (Review). Ethereum Magicians thread 25098.
- Inter-Agent Trust Models: A2A, AP2, ERC-8004 and Beyond. arXiv:2511.03434.
- Buterin, V. "The P + epsilon Attack" (crediting A. Miller). George, W. et al.,
  "An Analysis of p+ε Attacks on … Schelling Game Based Systems," Cryptoeconomic
  Systems 1(2).
- UMA (Optimistic Oracle; DVM escalation). Kleros: Short Paper v1.0.7.
- a16z crypto: "Symbolic testing with Halmos"; "Formal verification of Pectra
  system contracts with Halmos." ezkl / halo2 documentation.
- EIP-5192 (minimal soulbound); ERC-5679 (mint/burn). x402; EIP-8183 (early).
- VeriBond (ETHGlobal); KYA Protocol (agentecon.ai); ECO/CPO-DAG (arXiv:2607.06804);
  AgentBound (arXiv:2606.30970) — non-archival, cited for positioning.
- This repository: experiments Exp1–Exp19, machine proofs, deployment records
  (tag `wp-v1.0`).

---

## 부록 A — 국문 요약 (오너·내부용; EF 제출본에서는 제외)

AI가 아무리 똑똑해져도 안 뚫리는 보안은 지능이 아니라 수학에 근거해야 한다. 이
백서는 "모든 AI 발화는 서명·담보·증명"의 경제층이다. 대부분이 검증자에게 담보를
요구할 때 우리는 **말하는 자**에게 요구한다 — 담보 없이는 주장이 성립 안 하고,
틀리면 정확히 그만큼만 몰수, 모르면 기권해 무손실. 판정자도 담보를 걸고, 몰수분은
승자가 아니라 소각·배상으로 흐른다(승자 상금 = 매수 자금, z3 반례). v1.0에서
새로 닫은 것: **zk 증명을 실제로 돌려 온체인 검증 가스까지 측정**(생성 17.2초·검증
0.1초·온체인 864,652 가스), **증명 재사용을 암호학적으로 봉쇄**(바인딩 회로), 그리고
**40개 자율 에이전트가 실제 컨트랙트 위에서 정리가 예측한 정직 균형으로 수렴**
(합리적 성장·무근거 발화자 파산·토큰 보존). 정직: Exp18 K1은 사전등록대로 실패로
기록(구부리지 않음), Exp17 규제 불변 바우처는 구조 증명이지 합법 보증 아님. 한계는
§9에 전부.
