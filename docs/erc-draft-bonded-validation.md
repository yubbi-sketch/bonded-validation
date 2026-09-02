# [DRAFT] ERC-XXXX: Bonded Validation Interface for Trustless Agents

> Status: pre-draft for Ethereum Magicians discussion (not yet submitted to ethereum/ERCs)
> Requires: ERC-8004 · 2026-08-26 · Authors: IIS Lab

## Abstract

A minimal interface for **speaker-bonded validation protocols** on top of the
ERC-8004 Validation Registry. An agent MUST lock free bond before a claim can be
submitted for validation; a claim judged below a threshold is slashed; a claim
tagged as an **abstention** settles bond-neutral. The interface standardizes bond
accounting and settlement semantics while leaving judgment mechanisms
(re-execution, zkML, TEE, committee) to implementations.

## Motivation

ERC-8004 explicitly scopes out incentives and slashing: *"managed by the specific
validation protocol and outside the scope of this registry."* Emerging validation
protocols bond the validator (staked re-execution). No identified interface bonds
the **speaker** per utterance. Speaker bonds create accountability at utterance
time: unbonded speech is impossible by construction, wrong speech is costly, and
honest ignorance ("I don't know") is free — which measurably suppresses bluffing
(see reference results: a hallucinating agent bankrupts in ~100 utterances while a
calibrated-abstention agent is lossless).

## Specification

```solidity
interface IBondedValidator {
    /// Locks `minBondPerClaim()` of the agent's free bond and forwards a
    /// validation request to the ERC-8004 Validation Registry with this
    /// contract as validator. MUST revert if free bond is insufficient
    /// or msg.sender is not the agent's registered wallet.
    function requestValidation(uint256 agentId, string calldata requestURI,
                               bytes32 requestHash) external;

    /// Settles a claim. MUST write the score to the Validation Registry.
    /// If `tag` equals "abstain", bond MUST be released without loss
    /// regardless of score. Otherwise, score < threshold() MUST slash
    /// exactly the locked amount. MUST revert on double settlement.
    function submitVerdict(bytes32 requestHash, uint8 score,
                           string calldata responseURI, bytes32 evidenceHash,
                           string calldata tag) external;

    function stake(uint256 agentId, uint256 amount) external;
    function requestUnbond(uint256 agentId) external;   // starts delay window
    function withdraw(uint256 agentId) external;        // MUST revert while claims pending
    function freeBond(uint256 agentId) external view returns (uint256);
    function minBondPerClaim() external view returns (uint256);
    function threshold() external view returns (uint8);
}
```

Events: `Staked`, `ClaimBonded`, `ClaimSettled(agentId, requestHash, score, slashed, abstained)`,
`UnbondRequested`, `Withdrawn`.

### Invariants (normative)

1. **No bond, no speech** — `requestValidation` MUST NOT succeed without locked bond.
2. **Abstention neutrality** — an abstained claim MUST NOT reduce bond.
3. **No hit-and-run, bounded lock** — withdrawal MUST be impossible while any
   claim is unsettled, and MUST respect a delay window after `requestUnbond`;
   **and** every claim MUST be settleable within a bounded time by permissionless
   calls alone — either judged inside a challenge window, or, if no one engages it
   within that window, released lossless as *unchallenged* (v0.3, Exp30). A
   design in which an unengaged claim can stay locked forever violates this
   invariant (the v0.2.1 reference did; see Optimistic lapse below).
4. **Registry truth** — every settlement MUST be reflected in the ERC-8004
   Validation Registry so reputation systems can consume it.
5. **Reserved tags are not verification** — consumers MUST exclude the tags
   `"abstain"`, `"disputed"` and `"unchallenged"` from any count of *verified*
   claims. `"unchallenged"` means *nobody paid to judge this inside the window*;
   it is neither correct nor wrong, and an implementation MUST NOT let a judge
   vote a reserved tag.

### Optimistic lapse (v0.3 extension, Exp30)

```solidity
interface IBondedValidatorLapse is IBondedValidator {
    function challengeWindow() external view returns (uint256);       // W, immutable, 0 < W ≤ 365 days
    function claimedAt(bytes32 requestHash) external view returns (uint64);
    function engaged(bytes32 requestHash) external view returns (bool);
    /// Judge only. MUST revert unless block.timestamp < claimedAt + W. Marks the
    /// claim as engaged: lapse is blocked, only submitVerdict can close it.
    function engage(bytes32 requestHash) external;
    /// Judge only. Clears the mark when a case was opened but no panel was
    /// ever drawn (a commit that never became a challenge). Never settles.
    function disengage(bytes32 requestHash) external;
    /// Anyone. MUST revert while the window is open or the claim is engaged.
    /// Otherwise settles with score == threshold(), tag "unchallenged":
    /// bond and slashedTotal unchanged, atRisk released, zero token movement.
    function settleUnchallenged(bytes32 requestHash) external;
}
```

Normative: at every timestamp exactly one of `engage` / `settleUnchallenged` is
enabled for an unengaged, unsettled claim (`<` vs `≥` on the same boundary — no
race at the edge). `submitVerdict` MUST revert on an unengaged claim after the
window closes. No reward, reimbursement or bounty of any kind may be attached to
lapse or to opening a case (`R_c = 0`): a positive challenger payoff makes the
opener+judge coalition's income outcome-dependent, which is the winner's-bounty
bribery subsidy of Theorem 3 relocated to the opener (Exp30, z3 S6). Deterrence
under this extension is conditional on the probability `q` that a false claim is
engaged inside `W`; the expected penalty falls from `B_a` to `q·B_a` (z3 R1).
Implementations MUST disclose `W` and SHOULD set
`W ≥ k·(forced-inclusion delay of the target chain) + voteTimeout`, `k ≥ 2`.

## Rationale

- Bonding the speaker complements (does not replace) validator-bonded designs;
  the two compose as separate layers.
- Abstention neutrality is load-bearing: measured on a logic benchmark, all
  observed errors concentrated in the lowest-confidence tail, so a rational agent
  under this interface abstains exactly where it is likely to be wrong.
- Judgment is deliberately unspecified: deterministic claim classes can use
  re-execution consensus; probabilistic classes need zk/optimistic paths.

## Security Considerations

- The judge/threshold mechanism is the trust root of an implementation and MUST be
  disclosed. v0 reference uses a designated judge; production deployments SHOULD
  decentralize judgment before securing high-stakes claims.
- Reputation consumers SHOULD read abstentions separately (tag filter) so that
  abstaining is not penalized as low score.
- Griefing via dust claims is bounded by `minBondPerClaim`.
- **Commitment binding:** `requestHash` MUST be a commitment to the full claim —
  at minimum (claim content, agent response, model/version identifier, evidence
  reference). An index-style or opaque hash binds nothing and reduces "proven
  speech" to "numbered speech". (This was caught by external review of our own
  early demo runs — the reference drivers now commit full content.)

## Reference Implementation

`exp3/contracts/src/BondedValidator.sol` (MIT), 16/16 Foundry tests, live demo in `exp5/`.
Optimistic-lapse extension: `exp3/contracts/src/BondedValidatorV3.sol` +
`BondedJudgePanelV3.sol` (branch `exp30-liveness`, not yet deployed) — Halmos
`BondedValidatorV3Proofs` (T1–T4 + L1–L5) and `BondedJudgePanelV3Proofs` (PA–P4 + PL1–PL3).
