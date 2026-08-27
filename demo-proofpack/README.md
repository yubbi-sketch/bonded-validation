# Sample Proof Pack — Stateful ERC-4626 Dilution Invariant

> **One-line summary.** A one-line rounding-direction bug in a vault's deposit path passes
> clean-ratio unit tests, but symbolic execution finds a deterministic counterexample against a
> *stateful* dilution invariant — and after a one-line fix, the absence of the bug is **proved**
> over the full bounded input space (something fuzzing cannot do, even in principle).

This is what a customer engagement deliverable looks like: property → counterexample → fix →
absence proof → **honest limits**, all reproducible from this directory.

---

## 1. Scope & disclaimer (read first)

- `VaultBuggy.sol` / `VaultFixed.sol` are **representative demo contracts**, written for this
  pack. They target no specific project. The vulnerability *class* — deposit-path rounding
  direction violating EIP-4626's "rounding must favor the vault" rule — is public and appears
  repeatedly in audit reports. Seasoned reviewers check for it; clean-ratio unit tests miss it.
- This pack verifies **one property along one state transition**. It does not audit the vault.

## 2. The property (stateful, not a frozen rate)

> **No-dilution-on-deposit.** For an initialized vault (`totalSupply = S > 0`,
> `totalAssets = T > 0`, existing holder owns all `S` shares) and any deposit `a > 0`:
> the holder's redeemable backing after `deposit(a)` must satisfy
> `backingAfter ≥ backingBefore`.

A fair deposit is self-funded — new shares are backed by new assets — so it can never reduce
what existing holders can redeem. `deposit()` **mutates** `totalSupply`/`totalAssets` and mints
shares, so the check runs across a real state transition, not a pure conversion function.

**The bug (one line).** `convertToShares` rounds **up** (`mulDivUp`), crediting the depositor
more shares than their assets are worth. Combined with the (correct) floor on the redeem path,
each ragged-ratio deposit shaves value from existing holders.

## 3. Results (all logs reproduced below, versions pinned)

| Check | Tool | Result |
|---|---|---|
| Buggy, clean-ratio unit test (S=100, T=200, a=2) | forge | **passes** — why reviews miss it: at exact multiples `ceil == floor` |
| Buggy, randomized fuzz | forge fuzz | **caught** (e.g. `[2, 1586, 64]`) — we do not claim fuzzers miss this bug |
| Buggy, symbolic (bytecode level) | Halmos 0.3.3 | **deterministic counterexample in 3.0s** — `shares0=0xe0ee…2880, assets0=0xbff8…00d1, deposit=0x644d…8f45`; arithmetic re-check: holder backing drops by exactly 1 wei |
| Buggy, integer-level | z3 4.12.6 | **SAT** — minimal witness `S=1, T=3, a=1` |
| Fixed, randomized fuzz | forge fuzz | passes — but a fuzzer can only report "no failure found", never absence |
| **Fixed, integer-level absence proof** | z3 4.12.6 | **UNSAT in 0.05s** over the whole bound `S,T,a < 2^64` — no violating input exists |
| Fixed, symbolic (bytecode level) | Halmos | **timeout (60s+, honestly reported)** — 256-bit nonlinear division UNSAT is a known solver weak spot; see division of labor below |

**Division of labor (stated, not hidden).** Halmos carries the *counterexample* side at true
bytecode level. The *absence* side is carried by the integer-level z3 proof, which matches EVM
semantics exactly within the bound: Solidity 0.8 checked math reverts on overflow, and below
`2^64` every product stays under `2^128`, so integer `div` = EVM `div`. We do **not** print
"VERIFIED" from a timed-out bytecode query.

**Why this is the pitch.** The fuzzer catches the bug too (we say so). What fuzzing cannot do —
in principle — is prove the *fixed* contract has **no** violating input in the bound. The
0.05s UNSAT is that proof.

## 4. Reproduce it yourself (3 commands)

```bash
forge clean && forge build
forge test -vv                     # unit + fuzz: buggy caught, fixed passes
halmos --function check_buggy_deposit_never_dilutes   # deterministic CEX, ~3s
python prove_fixed.py              # z3: FIXED unsat / BUGGY sat (S=1,T=3,a=1)
```

Pinned: Halmos 0.3.3 · z3 4.12.6 · solc 0.8.28 · forge (nightly, see CI log). Repo tree:
`src/VaultBuggy.sol`, `src/VaultFixed.sol`, `test/VaultDilution.t.sol`, `prove_fixed.py`.

## 5. The fix (one line)

```diff
 function convertToShares(uint256 assets) public view returns (uint256) {
-    return mulDivUp(assets, totalSupply, totalAssets);   // BUG: favors depositor
+    return mulDivDown(assets, totalSupply, totalAssets); // FIX: favors the vault
 }
```

Algebraic sketch (machine-checked by `prove_fixed.py`): with `m = ⌊aS/T⌋`, `m ≤ aS/T` implies
`S(T+a)/(S+m) ≥ T`, hence `⌊S(T+a)/(S+m)⌋ ≥ T = backingBefore`. The ceil variant exceeds
`aS/T` whenever `T ∤ aS`, which is exactly the violating family.

## 6. Honest limits — read this box before quoting any result

1. **Bounded, not unbounded.** All claims are for `S, T, a < 2^64` (chosen to exclude
   multiplication overflow and keep solving tractable). `2^64 ≈ 18 tokens` at 18 decimals —
   large production vault balances exceed it. The algebraic argument extends beyond the bound,
   but the *machine-checked* statement is the bounded one.
2. **One property, one path.** Single `deposit` transition. No multi-transaction interleaving,
   reentrancy, first-depositor/inflation-donation attacks, mint-vs-deposit asymmetry, or
   access control. Property completeness is not claimed.
3. **Harm size is honest.** This is dust-level dilution per operation (the counterexample loses
   the holder exactly 1 wei), accruing across deposits — not a single-transaction drain.
4. **Empty vault excluded.** `S=0`/`T=0` (virtual-shares initialization) is out of scope.
5. **Bytecode-level UNSAT timed out.** We report it as such; the absence proof is
   integer-level (semantics-matching within the bound), not bytecode-level.
6. **Known class, known tools.** The rounding-direction class is on audit checklists, and
   ERC-4626 rounding appears in public Halmos examples. This pack's point is not novelty —
   it is what a *deliverable* looks like: stateful invariant, deterministic CEX, absence proof,
   and limits stated next to every claim.

## 7. What a real engagement adds

The hard (and priced) part of formal verification is not this demo: it is multi-transaction
interleavings, reentrancy, donation/first-depositor invariants, spec-completeness review, and
solver engineering at production scale. This pack shows the shape of the deliverable; an
engagement scopes the properties that matter for *your* contract.
