# Deployments

## Sepolia testnet — v0.4 (2026-09-04)

Self-audit against EVM/Solidity foundations (not a peer-comparison pass — a "does our own
base-layer reasoning hold" pass) found two issues, both fixed here, no other logic changed:

- **RT-0031 (high): judge votes had no secrecy.** `voteVerdict` recorded score/tag
  immediately on submission — only *panel selection* (who becomes a judge) was
  commit-reveal protected (since Exp9), not the vote content itself. A late-voting judge
  could see earlier votes before choosing their own, undermining the Schelling-point
  independence Kleros/UMA rely on. Fix: `voteVerdict` split into `commitVerdict` (hash
  only) + `revealVerdict` (real values, checked against the commit) — the same
  commit-reveal pattern already used for panel selection, reused rather than reinvented.
  Settlement/fee/slash logic is unchanged; only the vote-aggregation point moved from
  submission to reveal.
- **RT-0032 (med): `stake()`/`registerJudge()`/`stakeMore()` called the external
  `transferFrom` before updating internal state** (checks-effects-interactions order
  violation). The current LabToken has no callback hooks so this was not exploitable
  today, but the pattern opens a reentrancy window the moment a hook-bearing token is
  used. Fix: state updates moved before the external call (safe — a failed transfer
  reverts the whole transaction, including the earlier state writes).

A third issue (RT-0033: judge-pool weighted-selection capture cost when `VETERAN_WEIGHT`
concentrates in a colluding minority) was investigated and quantified but is **not** a
code fix — see `exp3/RT0033_ANALYSIS.md` for the exact-probability calculation and the
resulting deployment guidance (minimum judge-pool-size threshold, `VETERAN_WEIGHT`
reconsideration). Not applied to this deployment.

| Contract | Address |
|---|---|
| BondedValidatorV4 (judge = panel below) | [`0x10b179CfF290052720Fa9D5426C703f1501C2C69`](https://sepolia.etherscan.io/address/0x10b179CfF290052720Fa9D5426C703f1501C2C69) |
| BondedJudgePanelV4 (commit-reveal votes + commit-reveal panel selection) | [`0x15B749fA8ac62c4DE1B0311DF264359AC30287b3`](https://sepolia.etherscan.io/address/0x15B749fA8ac62c4DE1B0311DF264359AC30287b3) |

- Deployed from `main` (post-merge of `judge-vote-secrecy`, forge test 99/99) with the
  same toolchain as v0.3 (forge 1.7.1 / solc 0.8.28 / optimizer 200). Deploy txs: validator
  `0x4f94a03a73f0e223a942f9ce45fe61a491543beeafd591f8e877fb39501c790b` (nonce 16), panel
  `0x81e14caa4e2b6de13dd122544f1f78c0549c62b3824f62b1788bda729d274612` (nonce 17). Panel
  address CREATE-predicted at nonce 17 and passed as the validator's `judge` — matched
  exactly, no owner key holds any privileged role.
- Both Sourcify-verified (exact match, confirmed via `GET /v2/contract/11155111/<addr>`).
- Constructor params unchanged from v0.3: validator `minBondPerClaim = 1e18`,
  `unbondDelay = 3600s`, `challengeWindow (W) = 86400s`; panel `perCaseBond = 10e18`,
  `judgeFee = 1e18`, `voteTimeout = 3600s`, `disputeTimeout = 86400s`,
  `veteranThreshold = 3`, `SEED_WINDOW = 256 blocks`. Reuses the v0 LabToken /
  IdentityRegistry / ValidationRegistry (same addresses as v0.2 – v0.3, below).
- Independent post-deploy check (cast, this session): `judge()` on the validator ==
  panel address, `bonded()` on the panel == validator address, `token()` matches on both
  and equals the v0 LabToken, `challengeWindow`/`minBondPerClaim`/`perCaseBond`/
  `judgeFee` all match the intended constants.
- v0.3 stays live for comparison (addresses below) — not deprecated, RT-0031/0032 do not
  affect the correctness of v0.3's own machine proofs (T1–T4, L1–L5, PA–P4, PL1–PL3),
  they only affect a game-theoretic assumption (vote independence) and a reentrancy
  posture that Halmos's symbolic model doesn't currently encode (no adversarial token).
- Findings register: RT-0031, RT-0032 → `verified` (this deployment is the approval-ref).
  RT-0033 → `triaged` (calculation done, no code change scheduled).

## Sepolia testnet — v0.3 (2026-09-03)

Exp30 closed v0.2.1's liveness gap: a bonded claim could only be released by the
judge's verdict, and a verdict only followed a paid `openCase` — so a claim nobody
bothered to open locked its bond forever (`withdraw` 'claims pending'). v0.3 adds a
challenge window W: the panel marks a claim `engage`d when it opens a case inside W
(and `disengage`s it if no panel could be drawn by the commit deadline — a panel-less
commit is not a challenge), and once W has elapsed with no engagement **anyone** can
`settleUnchallenged` — lossless, permissionless, no reward, no token movement, recorded
as (50, "unchallenged"), which is *not* a validation and must be excluded from validation
counts. Also fixes two v0.2.1 wedges (a score > 100 vote jammed settlement forever;
unbounded tag bytes).

| Contract | Address |
|---|---|
| BondedValidatorV3 v0.3 (judge = panel below) | [`0xd881d52F10220687297651DeC4d55C1644d3a2A7`](https://sepolia.etherscan.io/address/0xd881d52F10220687297651DeC4d55C1644d3a2A7) |
| BondedJudgePanelV3 (commit-reveal lottery + engage/disengage) | [`0xfDf23d7B16462795659Acd4b2d40d81E842Aa18E`](https://sepolia.etherscan.io/address/0xfDf23d7B16462795659Acd4b2d40d81E842Aa18E) |

- Deployed from `main` `5f156d1` (K1 PASS, exp30/EXP30.md §15) with forge 1.7.1 /
  solc 0.8.28 / optimizer 200 (same toolchain as v0.2.1). Deploy txs: validator
  `0xd36c6db949ca47be78acfe1f6e34836e34fe32f0e667988a59876822715d5731` (nonce 8), panel
  `0xd7829f6dc8e808acb81524be6f08689e3003ad16b7ec851b189112f400be8d72` (nonce 9). The panel
  address was CREATE-predicted at nonce 9 and passed as the validator's judge — no owner key
  holds any privileged role. Reuses the v0 LabToken / IdentityRegistry / ValidationRegistry.
- Both Sourcify-verified (exact match, creation + runtime; 2026-09-02T21:41:51Z / :52Z).
- Constructor params: validator `minBondPerClaim = 1e18`, `unbondDelay = 3600s`,
  **`challengeWindow (W) = 86400s`**; panel `perCaseBond = 10e18`, `judgeFee = 1e18`,
  `voteTimeout = 3600s`, `disputeTimeout = 86400s`, `veteranThreshold = 3`,
  `SEED_WINDOW = 256 blocks`. All immutable.
- **How W was fixed.** Lower-bound rule W ≥ k·D + voteTimeout with k = 2 and D = the worst
  observed L1 inclusion stall: Sepolia Pectra incident 2025-03-05, ≈ 6.5 h = 23,400 s
  (normal inclusion 12–36 s; probabilistic censorship at the 2023 peak relay share clears
  99.99 % within 348 s). 2·23,400 + 3,600 = 50,400 s ≤ 86,400 s, so the provisional
  24 h value stands (margin 36,000 s). This bound holds for Ethereum L1 only: forced
  inclusion is 86,400 s on Arbitrum One / Arbitrum Sepolia (→ W ≥ 176,400 s) and 43,200 s
  on OP-Stack chains (→ W ≥ 90,000 s), so **this parameterisation must not be deployed to an
  L2** — W is immutable; an L2 needs a fresh deployment with its own W. Measurements and
  sources: exp30/EXP30.md §16.1.
- Known limits (v0.3): (i) deterrence is conditional on the challenge probability q — v0.3
  prices non-engagement, it does not create challengers (Exp30 §12.6: at q = 0.5 the
  hallucinator's residual bond stays above the kill line); (ii) when composed with
  ZkVerdictGate, W becomes the proof deadline — a prover that misses W lapses losslessly
  instead of proving; (iii) judge-silence exhaustion — a panel that stays silent through
  its timeouts can walk a claim to a lossless lapse; attendance penalties / a pool-size
  floor are open work (§14.8); (iv) the v0.2.1 lottery caveat (proposer bias, no VRF) is
  inherited; (v) ReputationLens is not Halmos-proved; (vi) Sepolia is scheduled for
  retirement (EOL planned 2026-09-30), so these addresses carry an expiry.
- **K2(c) live measurement started** 2026-09-02T21:44:24Z: agentId 1 (`agent://exp30-k2c`,
  first registration on the v0 IdentityRegistry), stake 1e18, claim
  `0xa4f55aa9d15b3847884b887662e1b9562f3c96abb2453abeef6a9fcec9579740` bonded at
  `claimedAt = 1788385464` (tx `0x249d2bce2f09a122e371bcee34225b4e8e3a60d218078fcb119f333fb6093a42`,
  block 11622286) and left unopened. Lapse-eligible from **1788471864 =
  2026-09-03T21:44:24Z**; `settleUnchallenged` is to be called by a third-party EOA after
  that time in a separate run (exp30/EXP30.md §16.3–16.4).

## Sepolia testnet — v0.2.1 (2026-08-26)

Exp9 fixed the lottery's weak point: v0.2 drew panels with prevrandao inside the
opening transaction, letting an opener grind request hashes for a favorable panel.
v0.2.1 splits commit (openCase records the block number — the seed does not exist
yet) from reveal (drawPanel/drawExpanded next block, seeded by that block's hash),
with recommit after the 256-block hash window and a lossless timeout refund for
abandoned commits (fee returned to the opener). Proposer-level bias remains — an
acknowledged limitation; external VRF is future work.

| Contract | Address |
|---|---|
| BondedValidator v0.2.1 (judge = panel below) | [`0xE9bA0f2904955D57546911Ef57a75ffd5a03F0f0`](https://sepolia.etherscan.io/address/0xE9bA0f2904955D57546911Ef57a75ffd5a03F0f0) |
| BondedJudgePanelV2 (commit-reveal lottery) | [`0x666F90ae34d7119756CF6E41f99F6A49b0FC5775`](https://sepolia.etherscan.io/address/0x666F90ae34d7119756CF6E41f99F6A49b0FC5775) |

- Same economic rules as v0.2 (bonded judges, expanded trials, no winner bounty,
  no arbiter). Reuses the v0 LabToken / registries. Both Sourcify-verified (exact match).
- Panel params: `perCaseBond = 10e18`, `judgeFee = 1e18`, `voteTimeout = 3600s`,
  `disputeTimeout = 86400s`, `veteranThreshold = 3`, `SEED_WINDOW = 256 blocks`.

## Sepolia testnet — v0.2 (2026-08-26)

Exp8 attack simulations (K1–K4 all passed) promoted the design to v0.2: bonded judges,
weighted-lottery panels, expanded trials with minority slashing, **no winner bounty**
(slashed funds are half-burned, half paid to the frozen agent as compensation; judges
earn only a fixed outcome-independent fee), and the owner arbiter (training wheels)
removed — the only backstop is the lossless timeout refund.

| Contract | Address |
|---|---|
| BondedValidator v0.2 (judge = panel below) | [`0x8213B2ac495E5e5d4be6C8f642dedf1DeDF9811c`](https://sepolia.etherscan.io/address/0x8213B2ac495E5e5d4be6C8f642dedf1DeDF9811c) |
| BondedJudgePanel v0.2 | [`0xf66d53726F7677ffD3D033b3eF74Ef2598232421`](https://sepolia.etherscan.io/address/0xf66d53726F7677ffD3D033b3eF74Ef2598232421) |

- Reuses the v0 LabToken / IdentityRegistry / ValidationRegistry below.
- Constructor params: validator `minBondPerClaim = 1e18 IISLAB`, `unbondDelay = 3600s`;
  panel `perCaseBond = 10e18`, `judgeFee = 1e18`, `voteTimeout = 3600s`,
  `disputeTimeout = 86400s`, `veteranThreshold = 3`.
- The panel address was CREATE-predicted (deployer nonce 5) and passed as the
  validator's judge at nonce 4 — no owner key holds any privileged role.
- Both Sourcify-verified (exact match, creation + runtime).
- Known prototype limits (stated in source): prevrandao-seeded lottery (proposer bias —
  VRF is future work); minority-slash justification restricted to deterministic claims.

## Sepolia testnet — v0 (2026-08-26)

| Contract | Address |
|---|---|
| BondedValidator v0 | [`0x8cB0e4Ce4cA043eb357Fd5841C94e329c44EcCF9`](https://sepolia.etherscan.io/address/0x8cB0e4Ce4cA043eb357Fd5841C94e329c44EcCF9) |
| IdentityRegistry (minimal ERC-8004) | [`0x784B1238EB74Efe1AF8bD8cf358B613f799D8f28`](https://sepolia.etherscan.io/address/0x784B1238EB74Efe1AF8bD8cf358B613f799D8f28) |
| ValidationRegistry (minimal ERC-8004) | [`0x6e44ADBa5CCc034a372A00c4c9eaBC7deE5e5aB5`](https://sepolia.etherscan.io/address/0x6e44ADBa5CCc034a372A00c4c9eaBC7deE5e5aB5) |
| LabToken (valueless test token) | [`0x236781293F7387292F1cc0a674c607b2aCF35fec`](https://sepolia.etherscan.io/address/0x236781293F7387292F1cc0a674c607b2aCF35fec) |

- Constructor params: `minBondPerClaim = 1e18 IISLAB`, `unbondDelay = 3600s`, judge = deployer EOA (v0 trusted-judge caveat applies).
- Sources verified on Sourcify (all four).
- Registries here are our minimal local implementations for demonstration; integrating against
  canonical ERC-8004 registry deployments is a stated next-step deliverable.
- LabToken is an experiment-only token: no value, no sale, no listing.
