# Bonded Validation — One-Pager (v1, 2026-08-26)

**Thesis.** As agents grow more capable, any security that depends on out-thinking them fails.
Durable guarantees must be *intelligence-invariant*: enforced by mathematics and consensus,
not vigilance. Applied to AI speech: **every agent utterance should be signed (identity),
bonded (economic liability at utterance time), and proven (verifiable judgment)**.

**The gap.** ERC-8004 (Trustless Agents; mainnet Jan 2026, 12+ chains) standardizes agent
identity, reputation, and a validation registry — and explicitly scopes out staking and
slashing: *"Incentives and slashing related to validation are managed by the specific
validation protocol and are outside the scope of this registry."* Emerging designs bond the
**validator** (staked re-execution). Nothing identified bonds the **speaker** per utterance.

**The protocol (v0, working).**

```
Agent wallet ──register()──▶ 8004 IdentityRegistry (agentId)
Agent ──requestValidation(agentId, hash)──▶ BondedValidator
        └─ reverts unless free bond ≥ minBondPerClaim  ← no bond, no speech
BondedValidator ──validationRequest()──▶ 8004 ValidationRegistry
Judge ──submitVerdict(hash, score 0-100, tag)──▶ BondedValidator
        ├─ score < 50 ⇒ slash bond          ← wrong speech costs
        ├─ tag "abstain" ⇒ bond released     ← honest ignorance is free
        └─ score ⇒ ValidationRegistry        ← reputation raw material
Withdrawal: delay window + no pending claims ← no hit-and-run
```

**Measured results (all reproducible, NumPy + Foundry only, laptop-scale):**

| Result | Evidence |
|---|---|
| Neuro-symbolic beats end-to-end on NL logic | 24k-param extractor + symbolic verifier: 98.4% vs 65.6% (same data, 910 tests, pre-registered kill criteria) |
| Errors are localizable | 100% of observed errors sat in the lowest 7.3% of model confidence |
| Abstention is buyable correctness | τ=0.9 → 0 observed wrong / 910, 92.7% coverage |
| Hallucination gets a price | 300 bonded utterances on Anvil: hallucinating agent 50→0; abstaining verifier-backed agent 50→50 lossless |
| Contract safety | 93/93 Foundry tests (2026-09-03; v0 core cases: bondless speech reverts, abstain is loss-free, double-settle blocked, withdrawal delay blocks hit-and-run |

**Why small models.** Deterministic verification, future zkML proofs, and formal verification
are only tractable for small components. We optimize under the constraint
*provable + local + contained*, not raw capability.

**Deliverables (6 months, $25k):**
1. Hardened open-source reference implementation + specified protocol interface (MIT/Apache)
2. Public testnet deployment against canonical 8004 registries + reproducible benchmark harness
3. Research report: abstention economics for bonded agents (slash ratio ⇄ abstention threshold)

**Known limitations (stated, not hidden).** Trusted judge in v0 (decentralizing judgment is
the research core going forward); toy-scale synthetic benchmarks; ERC-8004 still a Draft (re-checked 2026-09-03) —
registries treated as adapters.

**Track record of intellectual honesty.** Our previous target (account-layer policy
enforcement as a new ERC) was killed by our own two independent adversarial reviews after
finding ERC-7710/7780 + caveat enforcers occupy the slot. The full research trail — including
the kill — is in version control.
