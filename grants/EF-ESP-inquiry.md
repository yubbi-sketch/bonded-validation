# EF ESP — Informal Inquiry Draft (v1, 2026-08-26)

> 제출 전 오너 승인 필수. 아래는 ESP 접수 양식의 "project inquiry" 란에 넣을 본문.

---

**Project name:** Bonded Validation — a speaker-bonded validation protocol for ERC-8004 Trustless Agents

**Inquiry:**

ERC-8004 gives AI agents on-chain identity, reputation, and a validation registry — but the spec deliberately leaves staking, slashing, and incentives to "specific validation protocols" built on top. The validation layer is the least occupied part of the stack today, and the designs emerging in it (validation network interfaces, staked re-execution validators) bond the *validator*. We are building the complementary missing piece: a protocol that bonds the *speaker*. An agent cannot make a claim unless free bond is locked against it; a claim proven wrong is slashed; an honest "I don't know" (abstention) releases the bond without loss. Accountability attaches at the moment of utterance, not at audit time.

We have a working open-source prototype and measured results, all reproducible on a laptop with zero external dependencies (NumPy + Foundry only):

- **BondedValidator v0** (Solidity, 8/8 Foundry tests): agents register in an ERC-8004 Identity registry; every claim flows through `validationRequest` with bond locked; verdict scores (0–100) land in the Validation registry as reputation raw material; the "abstain" tag settles bond-neutral. In a 300-utterance live run on Anvil, a hallucinating agent went bankrupt (50 → 0 tokens) while a verifier-backed agent with calibrated abstention finished lossless (50 → 50).
- **Deterministic verification + calibrated abstention** (the AI side): a 24k-parameter extractor translates natural-language claims into symbolic propositions checked by a logic verifier. On our synthetic multi-hop logic benchmark (910 test cases), all observed errors concentrated in the lowest 7.3% of model confidence; abstaining below a confidence threshold yielded zero observed wrong answers at 92.7% coverage. Small models matter here: they are the ones amenable to future zkML proof and formal verification.

We are asking for a small grant to turn this prototype into a public good for the 8004 ecosystem: (1) a hardened open-source reference implementation plus a **specified interface (IBondedValidator) proposed as an ERC draft** so speaker-bonding composes with validator-network designs rather than fragmenting them; (2) public testnet deployment against the canonical 8004 registries with a reproducible benchmark harness; (3) a research report on abstention economics for bonded agents (how slash ratios should set abstention thresholds), with all datasets and code released. Everything is already MIT licensed and public; the draft interface and Ethereum Magicians thread accompany this inquiry.

Honest limitations we are explicit about: current verdicts come from a trusted judge (decentralizing judgment via re-execution consensus for deterministic claims, and zk/optimistic paths for the rest, is the research core of the grant period); results to date are toy-scale and synthetic; ERC-8004 is still in Review and we treat registry interfaces as adapters.

**Team:** Independent researcher (Korea/Australia) working with an AI-assisted research pipeline; prior work includes an account-abstraction policy-enforcement prototype (Foundry, 25/25 tests) that we retired after our own adversarial review concluded ERC-7710/7780 + caveat enforcers already occupy that slot — we would rather kill our own idea than ship a redundant standard. Git history documents the full research trail.

**Requested amount:** USD 25,000 (small grant tier) over 6 months.

**Category:** Applied research / protocol prototype — decentralized AI, agent infrastructure.
