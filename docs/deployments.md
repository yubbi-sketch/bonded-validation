# Deployments

## Sepolia testnet (2026-08-26)

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
