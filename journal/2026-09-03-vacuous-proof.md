# Our machine proof was vacuous

*2026-09-03*

We machine-verify our contracts with [Halmos](https://github.com/a16z/halmos), a
symbolic execution tool that checks a property against every possible input in a stated
state space, not just the cases we thought to write as unit tests. Getting a `[PASS]`
from Halmos feels like a strong claim. This week we found out one of ours wasn't real.

## The property

`BondedJudgePanel` (v0.2.1, the version live on Sepolia before this fix) settles a claim
once the initial three-judge panel votes unanimously. We had a Halmos property,
`check_L1_timeout_after_two_votes_never_reverts`, asserting that once two judges agree
on a score, a timeout-triggered settlement can never revert — one of the liveness
guarantees our whitepaper's "T_max" bound depends on.

It reported `[PASS]`.

## What Halmos actually checked

`voteVerdict` accepts a judge's `score` as a raw `uint8` — no upper-bound check. The
downstream `ValidationRegistry.validationResponse` does check: `require(response <= 100,
"range")`. So if two judges happen to submit the same out-of-range score — say, 101 —
the third vote (or the timeout path) tries to write that score to the registry, and the
registry reverts. Permanently. The claim's bond, and the panel's `perCaseBond` for all
three judges, are locked with no code path out (`withdraw` reverts `'claims pending'` /
`'cases pending'` forever).

Symbolic execution tools reason over the possible traces of a call. When a call reverts,
Halmos treats that trace as not a counterexample to `"never reverts"` in the naive
framing we'd written — it discards the reverting branch instead of flagging it, so a
property phrased as "the low-level call always returns `ok`" can pass by construction
even when every real trace in the danger zone actually reverts. We re-ran the concrete
counterexample directly: `s1 = s2 = 0x80` (128). It reverts, every time. The Halmos run
that said otherwise wasn't lying about what it checked — it was vacuously true, because
we asked it the wrong question.

## The fix

v0.3 (`BondedJudgePanelV3`) rejects the vote at submission instead of at settlement:
`require(score <= MAX_SCORE, "score range")` inside `voteVerdict` itself, alongside a
tag-length cap (`MAX_TAG_BYTES = 1024`) closing an identical-shaped gas-griefing path we
found at the same time. The corrected property is `PL1a`/`PL1b` in
`BondedJudgePanelV3Proofs` — phrased so a revert *is* a counterexample, not a discarded
branch — and it's the first thing our K2(b) kill criterion checks before anything else
runs (`exp30/EXP30.md` §5).

## Why we're writing this down

The honest version of "we use formal methods" includes the times formal methods didn't
save us — because we phrased the property in a way that let the tool agree with us for
the wrong reason. `[PASS]` is a claim about a specific formalization, not about the
code. We'd rather publish the miss than let the green checkmark do more talking than the
counterexample.

**Sources:** `exp30/EXP30.md` §1.2 ("웨지"), the fix in `exp3/contracts/src/BondedJudgePanelV3.sol`
(`voteVerdict`), regression coverage in `exp3/contracts/test/Exp30Lapse.t.sol`
(K2(b)). Findings register: this class of issue is tracked the same way we track
everything we find in our own contracts — see the [self-red-team entry](2026-09-04-self-red-team.md)
for the pattern.
