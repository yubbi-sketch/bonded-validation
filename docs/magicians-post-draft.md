# Ethereum Magicians 스레드 초안 (제출은 오너 승인 후)

> 게시판: ethereum-magicians.org → ERCs 카테고리
> 제목: **Bonded Validation: a speaker-bond interface on top of ERC-8004**

---

ERC-8004 deliberately leaves staking/slashing to validation protocols built on top.
Designs emerging in that slot (e.g. validator networks, staked re-execution) bond the
**validator**. We'd like feedback on the complementary layer: bonding the **speaker**.

Core idea: an agent cannot submit a claim to the Validation Registry unless free bond
is locked against it. Wrong claims (score below threshold) are slashed; claims tagged
"abstain" settle bond-neutral. Accountability attaches at utterance time — unbonded
speech is impossible by construction, and honest ignorance is free.

Why abstention neutrality matters (measured, laptop-reproducible): on a synthetic
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

Repo (MIT, reference implementation + tests + benchmark harness): [링크 — 공개 후 삽입]
Draft spec: [링크]

Questions for the group:
1. Does a speaker-bond interface belong as a separate ERC, or as an extension
   profile of an existing validation-network interface (e.g. the VNI direction)?
2. Should abstentions be visible in the Reputation Registry as a distinct signal
   rather than folded into average score?
3. Is per-claim fixed bonding too rigid — should bond scale with claim class?

We are aware of prior art in validator-side bonding and would welcome corrections
if a speaker-side interface already exists.
