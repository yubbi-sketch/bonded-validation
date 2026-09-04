# A claim nobody challenges must not lock forever

*2026-09-03*

v0.2.1 of our validator had a liveness gap we didn't notice until we went looking for
one: an agent locks bond when it submits a claim (`requestValidation`), and the only way
that bond is ever released is a judge's verdict — which only happens if someone pays to
open a case. If nobody opens a case, the bond is locked with no expiry. `withdraw`
reverts `'claims pending'` forever. We built a system whose stated purpose is bounded
settlement time, and it had an unbounded path.

## The rule we wrote down before designing anything

> What we're building is not "a supply of challengers" — it's "an upper bound on how
> long anything stays locked." If nobody challenges, the claim settles **unverified**,
> not verified. In exchange, deterrence becomes conditional on the probability a false
> claim actually gets challenged. We are not manufacturing that probability. We are only
> pricing it honestly.

That's LOCK-0 in our design doc, fixed before we wrote a line of Solidity, specifically
so we couldn't quietly redefine "settled" as "verified" once the design got harder.

## What we found when we checked who else had solved this

We read the actual contract source (not summaries) of the two closest prior systems
before designing anything:

- **UMA's Optimistic Oracle v3** — `disputeAssertion` and `settleAssertion` gate on
  mutually exclusive time comparisons (clean design, we copied the shape of this). But
  on an undisputed settlement, the full bond returns to the asserter; on a dispute, the
  loser's bond (minus a burn cut) goes to the *winner*.
- **OP Stack fault proofs** — same shape: "claims that are found to be incorrect have
  their bonds paid to the account that posted the left-most uncountered child claim."
  Winner-pays-loser, again.

Both systems fund a supply of challengers by paying them out of the loser's stake. We
can't do that. Our own economic theorem (Theorem 3, `exp13/prove.py`) says a winner's
reward is mathematically equivalent to a bribery subsidy — the same funds move whether
the winner is honest or paid to lie. So the gap we're filling is specifically
*"an optimistic window with no winner's bounty,"* which is also, honestly, our weak
point: we have no mechanism that manufactures challengers. We only guarantee the lock
can't outlast the window.

## What we built

`settleUnchallenged` — callable by anyone, no reward, no token movement — releases the
bond once the challenge window `W` has closed with no case opened, tagged
`"unchallenged"`. That tag is not a verdict. Consumers reading validation history must
exclude it, along with `"abstain"` and `"disputed"`, from anything they count as
*verified* (this is now a MUST in the ERC draft, R12). At every timestamp exactly one of
`engage` (a judge opening a real case inside the window) or `settleUnchallenged` (after
it) is available — a strict `<` / `≥` split on the same boundary, checked with Halmos so
there's no edge-second race between them.

## What this costs, honestly

Deterrence under this design is conditional on `q`, the probability a false claim
actually gets challenged inside `W`. At `q = 0.5` our own simulation shows a
hallucinating agent's residual bond stays above the line we'd set as a kill criterion
elsewhere in this research program — a real, disclosed weakness, not a hypothetical one.
We priced the gap. We didn't close it by assumption.

**Sources:** `exp30/EXP30.md` §0 (LOCK-0), §2 (web-gap judgment against UMA/OP source),
§12.6 (the `q` sensitivity result); live on Sepolia as `BondedValidatorV3`
`0xd881d52F10220687297651DeC4d55C1644d3a2A7` (`docs/deployments.md`).
