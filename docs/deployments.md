# Deployments

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
