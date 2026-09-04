# We red-teamed our own live contracts

*2026-09-04*

Most of what we publish here is a proof or a benchmark. This one is closer to an audit
finding — the kind we'd want a third party to write about us, except we found it first
and it's on our own live testnet contracts.

We went back through `BondedValidatorV3` / `BondedJudgePanelV3` with a specific
question: not "does this match its own spec" (Halmos already checks that) but "does it
correctly assume how the chain underneath it actually behaves." Two real issues came out
of that pass. Both are fixed and deployed. One issue turned out to be a calculation, not
a bug, and we're leaving it open on purpose.

## Fixed: judge votes had no secrecy

`BondedJudgePanelV3`'s panel *selection* is commit-reveal protected — who becomes a
judge for a given case can't be predicted or ground for in advance, closing a
request-hash-grinding attack we found earlier (Exp9). But the votes themselves were not:
`voteVerdict` recorded a judge's score and tag immediately on submission. A judge voting
third could see the first two votes before deciding their own. Kleros's and UMA's own
designs both depend on jurors/stakers voting without seeing each other's answers first —
that's what a Schelling-point mechanism actually requires. We had copied the *shape* of
that game theory without copying the part that makes it hold.

**Fix:** `BondedJudgePanelV4` splits `voteVerdict` into `commitVerdict` (a hash of your
vote) and `revealVerdict` (the real values, checked against your own commit) — the exact
commit-reveal pattern we already had for panel selection, applied to the votes
themselves. Settlement, fee distribution, and slashing logic are unchanged; only the
point where votes become visible moved from submission to reveal, and a `revealVerdict`
call reverts (`"not reveal phase"`) until every panelist has committed.

## Fixed: state updates happened after the external call

`stake()`, `registerJudge()`, and `stakeMore()` all called `token.transferFrom(...)`
*before* updating internal balances — a checks-effects-interactions ordering violation.
Our test token has no callback hooks, so this wasn't exploitable today, but the pattern
opens a reentrancy window the moment a hook-bearing token is used instead. Fix: move the
state write before the external call — safe, because a failed transfer reverts the whole
transaction, including the earlier writes.

## Investigated, not fixed: judge-pool capture cost

Our judge lottery weights veteran judges 5× a newcomer's draw odds. We asked: how cheap
is it for a colluding minority of veterans to capture a full panel, without any
block-hash grinding — just by opening several independent cases (paying `judgeFee` each
time) and using whichever one happens to draw in their favor? We computed the exact
capture probability (weighted sampling without replacement, full permutation
enumeration, not a Monte Carlo estimate) across a few pool sizes:

| Pool size | Colluding share | P(capture) | Cost for 90% success |
|---|---|---|---|
| 10 | 30% of veterans | 5.0% | 45 attempts (~405× `judgeFee`) |
| 30 | same absolute collusion | 0.27% | 837 attempts (~7,500×) |
| 100 | same | 0.014% | 16,440 attempts (~148,000×) |

This isn't a code defect — it's a deployment-parameter question. A small judge pool with
concentrated veteran weight is cheap to capture; a pool past roughly 30 diverse
participants is not. We're recording it as a deployment rule (minimum pool size before
this mechanism should be trusted, and a case for lowering the veteran weight
multiplier) rather than shipping a fix for a threat model that depends on facts about
the deployment, not the contract.

## Where this lives

Findings are numbered and tracked the same way regardless of who finds them — us or
someone else (`docs/responsible-disclosure.md`). This round: RT-0031 (vote secrecy,
high), RT-0032 (reentrancy ordering, medium) — both `verified`, deployed as
`BondedValidatorV4` `0x10b179CfF290052720Fa9D5426C703f1501C2C69` and
`BondedJudgePanelV4` `0x15B749fA8ac62c4DE1B0311DF264359AC30287b3`, Sourcify-verified.
RT-0033 (judge-pool capture cost, low) — `triaged`, calculation published, no code
change scheduled.

**Sources:** `docs/deployments.md` (v0.4 section), `exp3/RT0033_ANALYSIS.md` (the exact
capture-probability calculation and reproduction command), regression suite 99/99
passing after the merge (`exp3/contracts/test/`).
