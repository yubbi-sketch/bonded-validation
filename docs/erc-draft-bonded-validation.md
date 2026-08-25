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
3. **No hit-and-run** — withdrawal MUST be impossible while any claim is unsettled,
   and MUST respect a delay window after `requestUnbond`.
4. **Registry truth** — every settlement MUST be reflected in the ERC-8004
   Validation Registry so reputation systems can consume it.

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

## Reference Implementation

`exp3/contracts/src/BondedValidator.sol` (MIT), 16/16 Foundry tests, live demo in `exp5/`.
