# Reproduction Audit — Bonded Validation (P8)

> 2026-08-27 · An independent re-run of **every** experiment from a clean state,
> following the repository's own documented commands, checking that the numbers in
> the whitepaper and README actually reproduce. Nine independent agents ran the
> full experiment set in parallel/serial with no source edits.

## Verdict

**All 17 audited items reproduce.** Numeric results (accuracy, verdicts, gas,
proof counts, on-chain balances) match to the digit or within run-to-run
variance. In doing so the audit also (a) found real **reproducibility friction**
an external person would hit, now fixed or documented, and (b) caught **two
overclaims** in prose, now corrected — the discipline working as intended.

## Environment

All experiments run under one Python environment with `numpy z3-solver onnx ezkl
matplotlib` (see `requirements.txt`), plus **Foundry** (`forge`/`anvil`/`cast`)
and **Halmos** for contracts. ezkl needs network for the one-time KZG SRS
download. Create it with:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Results

| Experiment | Claimed | Reproduced | Match |
|---|---|---|---|
| Exp1 decomposition | pipeline 0.9835 / e2e 0.6560·0.6549 / slot 0.9954 / +17.3pp | identical to the digit; params 43,008/17,088/24,384 match | ✅ |
| Exp2 abstention | n=910; τ≥0.85→0 wrong @95.2%; τ=0.9 @92.7% | calibration bins + verdict byte-identical | ✅ |
| Exp8 attack sim | K1~K4 pass; sybil 5%→300×; promote true | JSON byte-identical (sha256 match); 300.0× exact | ✅ * |
| Exp10 zkML recon | slot 0.9977; f12 drop 0.00pp; ≈2^19 rows; GO | 0.9977 / 0.00pp / 316,088 rows / go true | ✅ |
| Exp13 no-bounty z3 | 7 z3 checks OK | all 7 [OK], exit 0 | ✅ |
| Exp18 living economy | τ*=0.4; θ→0.447; K2·K3 pass; K1 fail | reproduced incl. K1 pre-registered failure | ✅ |
| Forge suite | 69 passed / 0 failed | 69/0, 9 suites | ✅ |
| Exp11 Halmos (T1–T4) | 4 pass | 4 passed / 0.95s | ✅ |
| Exp17 Halmos (voucher) | 7 pass | 7 passed / 0.18s | ✅ |
| Exp20 Halmos (gate) | 5 pass | 5 passed / 0.37s | ✅ |
| Exp12 Halmos (panel, loop33) | PA/PB/PC/P4 pass | 4 passed / 256s (PB 1086 paths) | ✅ |
| Exp3 on-chain | hallu 50→8 / ours 50→49 / 8 Forge | exact | ✅ |
| Exp5 on-chain (8004) | 50→50 / 50→0 / rep 100·84·50 | exact | ✅ |
| Exp7 on-chain (panel) | corrupt 14 / panel 0 | exact | ✅ |
| Exp14 zk proof | logrows 18; prove ~17s; verify 0.1s; argmax 20/20 | logrows 18; prove 19.0s; verify 0.1s; 40,114B; argmax✓ | ✅ ** |
| Exp15 on-chain verify | 864,652 gas; code 19,683B < EIP-170 | **864,388 gas**; 19,683B; ok true | ✅ (gas ±0.03%) |
| Exp16 binding | 975,182 gas; 24,257B; 63 inst; tamper rejected | **975,218 gas**; 24,257B; 63; rejected (with k2_retest) | ✅ ** |

## Corrections made (overclaims the audit caught)

1. **Exp8 winner-bounty "profitable from ~30%" — WRONG, corrected.** The sim's
   with-bounty E[profit] is **negative at every fraction** (least-negative −0.29
   at 50%); it subsidizes the attack (raises profit toward zero) but never crosses
   positive. The *profitable* bounty regime is real but established **analytically
   by Theorem 3 (Exp13, z3)**, not by this Monte Carlo. Fixed in
   `docs/whitepaper-draft.md` and `exp8/EXP8.md`.
2. **Exp8 "ε=1% → 0.6%" — imprecise, corrected** to the reproduced value: 0.048
   wrongful slashes/panel (**≈0.96%/judge**), still < the 2% kill limit.
3. Gas figures cited exactly (864,652 / 975,182) reproduce within run-to-run
   variance (864,388 / 975,218 this run); the whitepaper now reads them as
   approximate.

## Reproducibility friction (fixed or documented)

- **matplotlib was missing** from the research venv, so several scripts crashed at
  the final plot step (exit 1) *after* writing `out/results.json` — numbers were
  fine but a non-zero exit could mislead. Fixed: matplotlib added; `requirements.txt`
  now lists it. (The `EXP*.md` docs already used `python3`, which had it.)
- **Undocumented numeric deps**: several `EXP*.md` say `python3 run_exp*.py`, but a
  bare interpreter lacks numpy — a venv per `requirements.txt` is required. Now
  documented here and in `requirements.txt`.
- **Hardcoded absolute paths** in `run_exp2.py`, `run_exp5.py`/`run_exp19.py`
  (`CDIR=/Users/yubbi/iis-lab/...`), and `exp15` (`../exp14/out`): experiments are
  not location-portable and `exp15` requires `exp14` to have run first. Documented;
  full de-hardcoding is a follow-up.
- **Exp13 has no `EXP13.md`** with a 재현 section (only `prove.py`). **Exp14's
  "20/20"** comes from a separate `k3_check.py`, not `run_exp14.py`. **Exp16's
  tamper-rejection** requires `run_exp16.py` **and** `k2_retest.py` (the single
  command alone reports the naive-tamper false). These command/claim gaps are now
  stated in the table above.

## How to reproduce

```bash
# Python experiments (deterministic, fixed seeds)
.venv/bin/python exp1/train.py     # +  exp2/run_exp2.py exp8/sim.py exp10/recon.py exp13/prove.py exp18/run_exp18.py
# Machine proofs
cd exp3/contracts && forge test
../../.venv/bin/halmos --contract BondedValidatorProofs       # ServiceVoucherProofs / ZkVerdictGateProofs
../../.venv/bin/halmos --contract BondedJudgePanelV2Proofs --loop 33   # heavy (~4 min)
# On-chain (each starts its own anvil)
.venv/bin/python exp3/run_exp3.py  # exp5 exp7 exp19
# zkML (network for SRS)
.venv/bin/python exp14/run_exp14.py && .venv/bin/python exp15/run_exp15.py
.venv/bin/python exp16/run_exp16.py && .venv/bin/python exp16/k2_retest.py
```

\* Exp8 reproduces its pass verdict exactly; two prose figures were corrected (above).
\** Exp14/16 full claim needs the companion script (`k3_check.py` / `k2_retest.py`).
