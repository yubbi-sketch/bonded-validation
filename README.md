# Bonded Validation — speaker-bonded accountability for AI agents

**Every agent utterance is signed, bonded, and proven.**

ERC-8004 (Trustless Agents) gives AI agents on-chain identity, reputation, and a
validation registry — and deliberately leaves staking, slashing, and incentives to
validation protocols built on top. Most emerging designs bond the *validator*
(staked re-execution). This project bonds the **speaker**: an agent cannot make a
claim unless free bond is locked against it; a claim proven wrong is slashed; an
honest "I don't know" (abstention) releases the bond without loss. Accountability
attaches at the moment of utterance, not at audit time.

> Research program: *intelligence-invariant security* — guarantees that hold no
> matter how capable the attacker (or the agent) becomes, because they rest on
> mathematics and consensus rather than vigilance.

## 📜 Whitepaper

**[Bonded Validation: Speaker-Bonded Accountability for AI Agents, with
Machine-Checked Settlement Rules](docs/whitepaper-draft-v0.2.md)** (draft v0.2) —
protocol, threat model, nine experiments, eight symbolic-execution theorems over
the deployed bytecode, and conditional bribery-resistance theorems (z3) including
the no-bounty result: within our model, a winner's reward — even one funded only
from forfeitures — functions as a bribery subsidy. Repository state pinned at tag
`wp-v0.2`. Reviews, refutations, and reproduction attempts are welcome via issues.

## What's here

| Path | Contents |
|---|---|
| `exp3/contracts/src/BondedValidator.sol` | Speaker-bond validation protocol v0 (+ minimal ERC-8004 registry implementations for local testing) |
| `exp3/contracts/src/BondManager.sol` | Predecessor: standalone bond/slash manager |
| `exp1/` | Neuro-symbolic pipeline: 24k-param extractor + symbolic logic verifier vs end-to-end baselines (pure NumPy, zero deps, own autograd) |
| `exp2/` | Calibrated abstention: risk–coverage sweeps and bond economics |
| `exp5/` | Live demo: 300 bonded utterances on Anvil against 8004-style registries |
| `swarm/` | Multi-LLM research orchestrator: planner/builder/critic/judge/scribe loop with transcripts |
| `docs/` | Protocol design notes, [ERC draft](docs/erc-draft-bonded-validation.md), [Sepolia deployments](docs/deployments.md) |
| `grants/` | EF ESP application materials |

## Measured results (all reproducible on a laptop)

- **Decomposition enables cheap intermediate supervision:** the extractor+verifier
  pipeline reaches 98.4% vs 65.6% end-to-end on natural-language multi-hop logic
  (910 tests, pre-registered kill criteria). Disclosed confound: the extractor
  received gold slot-level supervision and a larger training budget that the
  end-to-end baselines did not — see whitepaper §8.1.
- **Errors are localizable:** 100% of observed pipeline errors sat in the lowest
  7.3% of model confidence.
- **Abstention buys correctness:** confidence threshold τ=0.9 → 0 observed wrong
  answers / 910 at 92.7% coverage (observed, not a guarantee).
- **Hallucination gets a price:** over 300 bonded utterances, a hallucinating agent
  went bankrupt (50 → 0 tokens); a verifier-backed agent with abstention finished
  lossless (50 → 50). Contract suite: 16/16 Foundry tests.

## Live on Sepolia

**v0.2.1 (current):** commit-reveal lottery closes request-hash grinding.
BondedValidator v0.2.1 `0xE9bA0f2904955D57546911Ef57a75ffd5a03F0f0` ·
BondedJudgePanelV2 `0x666F90ae34d7119756CF6E41f99F6A49b0FC5775`.

**v0.2:** bonded judges with weighted-lottery panels, expanded trials with
minority slashing, and **no winner bounty** — Exp8 attack simulations showed a winner's
bounty becomes the attacker's bribe budget, so slashed funds are half-burned and half
paid to the frozen agent, while judges earn only a fixed outcome-independent fee. The
owner arbiter (training wheels) is removed. BondedValidator v0.2:
`0x8213B2ac495E5e5d4be6C8f642dedf1DeDF9811c` · BondedJudgePanel:
`0xf66d53726F7677ffD3D033b3eF74Ef2598232421`.

v0 remains live for comparison (`0x8cB0e4Ce4cA043eb357Fd5841C94e329c44EcCF9`). All
contracts Sourcify-verified — see [docs/deployments.md](docs/deployments.md).

## Reproduce

```bash
# AI experiments (Python 3 + NumPy only)
cd exp1 && python3 autograd.py && python3 train.py
cd ../exp2 && python3 run_exp2.py

# Contracts (Foundry)
cd ../exp3/contracts && forge test

# Live bonded-utterance demo (starts a local Anvil)
cd ../../exp5 && python3 run_exp5.py

# Multi-LLM research loop (mock works without API keys)
cd ../.. && python3 swarm/orchestrator.py --provider mock --problem exp8_judge_bond_attack_sim
```

## Honest limitations

- Verdicts in v0 come from a trusted judge; decentralizing judgment
  (re-execution consensus for deterministic claims; zk/optimistic paths beyond)
  is the research core going forward.
- Benchmarks are toy-scale and synthetic; no claim of real-world extrapolation yet.
- ERC-8004 is in Review; registry interfaces are treated as adapters.
- This research trail includes a killed project: our earlier account-layer policy
  ERC idea was retired after two independent adversarial reviews found
  ERC-7710/7780 + caveat enforcers already occupy that slot. The kill is documented
  in the git history — we would rather kill our own idea than ship a redundant standard.

## License

MIT — see [LICENSE](LICENSE).
