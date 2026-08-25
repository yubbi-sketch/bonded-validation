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

## What's here

| Path | Contents |
|---|---|
| `exp3/contracts/src/BondedValidator.sol` | Speaker-bond validation protocol v0 (+ minimal ERC-8004 registry implementations for local testing) |
| `exp3/contracts/src/BondManager.sol` | Predecessor: standalone bond/slash manager |
| `exp1/` | Neuro-symbolic pipeline: 24k-param extractor + symbolic logic verifier vs end-to-end baselines (pure NumPy, zero deps, own autograd) |
| `exp2/` | Calibrated abstention: risk–coverage sweeps and bond economics |
| `exp5/` | Live demo: 300 bonded utterances on Anvil against 8004-style registries |
| `docs/` | Protocol design notes |
| `grants/` | EF ESP application materials |

## Measured results (all reproducible on a laptop)

- **Neuro-symbolic beats end-to-end** on natural-language multi-hop logic:
  98.4% vs 65.6% at comparable parameter budgets (910 tests, pre-registered kill criteria).
- **Errors are localizable:** 100% of observed pipeline errors sat in the lowest
  7.3% of model confidence.
- **Abstention buys correctness:** confidence threshold τ=0.9 → 0 observed wrong
  answers / 910 at 92.7% coverage (observed, not a guarantee).
- **Hallucination gets a price:** over 300 bonded utterances, a hallucinating agent
  went bankrupt (50 → 0 tokens); a verifier-backed agent with abstention finished
  lossless (50 → 50). Contract suite: 16/16 Foundry tests.

## Reproduce

```bash
# AI experiments (Python 3 + NumPy only)
cd exp1 && python3 autograd.py && python3 train.py
cd ../exp2 && python3 run_exp2.py

# Contracts (Foundry)
cd ../exp3/contracts && forge test

# Live bonded-utterance demo (starts a local Anvil)
cd ../../exp5 && python3 run_exp5.py
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
