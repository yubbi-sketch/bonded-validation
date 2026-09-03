# Ethereum Magicians 스레드 초안 (제출은 오너 승인 후)

> 게시판: ethereum-magicians.org → ERCs 카테고리
> 제목: **Speaker Bond Protocol (SBP): a speaker-bond interface on top of ERC-8004**
> 갱신 2026-09-03: '~30% 흑자' 문장 철회 반영(REPRODUCTION.md 정정 1 — 시뮬은 전 구간 음수, 수익 영역은 Exp13 정리 3 해석적) · 백서 링크 wp-v1.0 · '인류 최초'류 표현 0건 확인(grep 최초/first/unprecedented/world) · '노트북 재현' 서술 → REPRODUCTION 17/17 로 정리.

---

ERC-8004 deliberately leaves staking/slashing to validation protocols built on top.
Designs emerging in that slot (e.g. validator networks, staked re-execution) bond the
**validator**. We'd like feedback on the complementary layer: bonding the **speaker**.

Core idea: an agent cannot submit a claim to the Validation Registry unless free bond
is locked against it. Wrong claims (score below threshold) are slashed; claims tagged
"abstain" settle bond-neutral. Accountability attaches at utterance time — unbonded
speech is impossible by construction, and honest ignorance is free.

Why abstention neutrality matters (measured; independently re-run 17/17 in
REPRODUCTION.md): on a synthetic
natural-language logic benchmark, 100% of our pipeline's observed errors sat in the
lowest 7.3% of model confidence; abstaining below a confidence threshold gave zero
observed wrong answers at 92.7% coverage. In a 300-utterance live run against local
8004-style registries, a coin-flipping agent went bankrupt (50→0) while the
calibrated-abstention agent finished lossless (50→50).

Draft interface (IBondedValidator): requestValidation gated on free bond;
submitVerdict writes scores to the Validation Registry and settles bonds; abstention
neutrality, no-hit-and-run withdrawal delay, and registry-truth as normative
invariants. Judgment mechanism deliberately unspecified (re-execution consensus for
deterministic claim classes; zk/optimistic beyond).

Repo (MIT, reference implementation + tests + benchmark harness): https://github.com/yubbi-sketch/bonded-validation
Live on Sepolia (Sourcify-verified): BondedValidator v0.3 `0xd881d52F10220687297651DeC4d55C1644d3a2A7` (optimistic-lapse liveness fix — an unchallenged claim settles losslessly after a 24h window, no bounty) — see docs/deployments.md
Draft spec: https://github.com/yubbi-sketch/bonded-validation/blob/main/docs/erc-draft-bonded-validation.md

Questions for the group:
1. Does a speaker-bond interface belong as a separate ERC, or as an extension
   profile of an existing validation-network interface (e.g. the VNI direction)?
2. Should abstentions be visible in the Reputation Registry as a distinct signal
   rather than folded into average score?
3. Is per-claim fixed bonding too rigid — should bond scale with claim class?

We are aware of prior art in validator-side bonding and would welcome corrections
if a speaker-side interface already exists.

---

## Update draft — v0.2 / v0.2.1 (2026-08-26, post after thread approval)

Since the original post, the judge role itself is now bonded and decentralized
one step further:

- **Bonded judges (v0.2)** — judging is itself a bonded utterance: judges register
  an 8004 identity and post collateral; each case locks a per-case bond. Initial
  panels of 3 are drawn by weighted lottery (newcomers pay a 1.5× entry premium and
  carry 1/5 lottery weight); a dissent escalates to a fresh 5-judge expanded trial,
  and voters against the final majority verdict are slashed.
- **No winner's bounty** — our Monte Carlo attack simulations (20k trials/cell)
  showed a UMA-style winner's reward subsidises the briber at every capture
  fraction tested (expected profit rises toward zero but does not cross positive
  in-sim); that a budget-feasible bounty *can* turn profitable is established
  analytically (Theorem 3, z3 — Exp13), not by the simulation. So slashed funds
  are half-burned and half paid to the agent whose bond
  was frozen; judges earn only a fixed outcome-independent fee. Sybil capture of 5%
  of the pool costs ~300× an honest judge's bond under the newcomer premium.
- **Training wheels removed** — the owner-arbiter escape hatch from v0.1 is gone;
  the only backstop is a lossless timeout refund (tag `disputed`, no slash).
- **Commit-reveal lottery (v0.2.1)** — case opening commits a block number; the
  panel is drawn next block from that block's hash, so no one can grind request
  hashes for a favorable panel. (Proposer-level bias remains — external VRF is
  acknowledged future work.)
- **zkML recon** — our 24k-parameter extractor survives fixed-point quantization
  with zero accuracy loss down to scale 2^8, and censuses at ~79k MACs ≈ 2^19
  estimated halo2 rows: replacing "3-of-5 honest re-executors" with a zk proof of
  correct re-execution looks tractable for deterministic claim classes.

Whitepaper v1.0 (protocol, threat model, machine-checked theorems, stated
limitations; git tag `wp-v1.0`): https://github.com/yubbi-sketch/bonded-validation/blob/wp-v1.0/docs/whitepaper-draft.md

Sepolia (all Sourcify-verified): BondedValidator v0.2.1
`0xE9bA0f2904955D57546911Ef57a75ffd5a03F0f0` · BondedJudgePanelV2
`0x666F90ae34d7119756CF6E41f99F6A49b0FC5775` — full table in docs/deployments.md.
