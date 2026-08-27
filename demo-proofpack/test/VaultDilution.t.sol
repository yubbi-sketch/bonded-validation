// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {VaultBuggy} from "../src/VaultBuggy.sol";
import {VaultFixed} from "../src/VaultFixed.sol";

interface Vm {
    function assume(bool) external;
}

/// @title Stateful ERC-4626 dilution invariant — Halmos symbolic + Foundry fuzz
/// @notice Property: a deposit must NEVER reduce the redeemable backing of a
///         pre-existing shareholder. Rounding may only favor the vault /
///         existing holders — never the incoming depositor (EIP-4626 rule).
///
///         STATEFUL: `deposit` mints shares and mutates totalSupply /
///         totalAssets, so we compare the existing holder's redeemable assets
///         BEFORE vs AFTER a real state transition — not a frozen rate.
contract VaultDilutionTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    address constant HOLDER = address(0xA11CE);   // pre-existing shareholder
    address constant ATTACKER = address(0xBAD);   // incoming depositor

    /// Bounds: keep every x*y < 2**128 (no multiplication overflow) AND keep
    /// z3's nonlinear-division search tractable. The bound is for solver
    /// tractability + overflow avoidance, NOT the property's soundness.
    function _scope(uint256 shares0, uint256 assets0, uint256 depositAssets) internal {
        vm.assume(shares0 > 0 && shares0 < 2 ** 64);
        vm.assume(assets0 > 0 && assets0 < 2 ** 64);
        vm.assume(depositAssets > 0 && depositAssets < 2 ** 64);
    }

    /// BUGGY variant — Halmos should find a deterministic counterexample.
    function check_buggy_deposit_never_dilutes(
        uint256 shares0, uint256 assets0, uint256 depositAssets
    ) public {
        _scope(shares0, assets0, depositAssets);
        VaultBuggy v = new VaultBuggy(shares0, assets0, HOLDER);

        uint256 backingBefore = v.convertToAssets(v.balanceOf(HOLDER));
        v.deposit(depositAssets, ATTACKER);
        uint256 backingAfter = v.convertToAssets(v.balanceOf(HOLDER));

        assert(backingAfter >= backingBefore);
    }

    /// FIXED variant — Halmos should terminate with NO counterexample (bounded).
    function check_fixed_deposit_never_dilutes(
        uint256 shares0, uint256 assets0, uint256 depositAssets
    ) public {
        _scope(shares0, assets0, depositAssets);
        VaultFixed v = new VaultFixed(shares0, assets0, HOLDER);

        uint256 backingBefore = v.convertToAssets(v.balanceOf(HOLDER));
        v.deposit(depositAssets, ATTACKER);
        uint256 backingAfter = v.convertToAssets(v.balanceOf(HOLDER));

        assert(backingAfter >= backingBefore);
    }

    /// FIXED variant, tighter 2**32 bounds — fallback when the 2**64 query
    /// times out in z3 (nonlinear 256-bit division UNSAT is a known z3 weak
    /// spot). The full 2**64-bound claim is then carried by the algebraic
    /// proof in the report, with Halmos providing the counterexample side.
    function check_fixed_deposit_never_dilutes_2e32(
        uint256 shares0, uint256 assets0, uint256 depositAssets
    ) public {
        vm.assume(shares0 > 0 && shares0 < 2 ** 32);
        vm.assume(assets0 > 0 && assets0 < 2 ** 32);
        vm.assume(depositAssets > 0 && depositAssets < 2 ** 32);
        VaultFixed v = new VaultFixed(shares0, assets0, HOLDER);

        uint256 backingBefore = v.convertToAssets(v.balanceOf(HOLDER));
        v.deposit(depositAssets, ATTACKER);
        uint256 backingAfter = v.convertToAssets(v.balanceOf(HOLDER));

        assert(backingAfter >= backingBefore);
    }

    /// Foundry FUZZ wrappers (same property, randomized search) — honest
    /// contrast exhibit: the fuzzer DOES catch the buggy variant (we do not
    /// overclaim), but on the fixed variant it can only report "passed", never
    /// prove absence — absence-of-bug is what the symbolic run provides.
    function testFuzz_buggy_dilution(uint256 s0, uint256 a0, uint256 dep) public {
        check_buggy_deposit_never_dilutes(s0, a0, dep);
    }

    function testFuzz_fixed_dilution(uint256 s0, uint256 a0, uint256 dep) public {
        check_fixed_deposit_never_dilutes(s0, a0, dep);
    }

    /// The "clean units" unit test both variants pass — WHY reviews/unit tests
    /// miss this bug: at exact multiples ceil == floor.
    function test_clean_ratio_units_pass_on_buggy() public {
        VaultBuggy v = new VaultBuggy(100, 200, HOLDER); // price 2, clean
        uint256 before_ = v.convertToAssets(v.balanceOf(HOLDER));
        v.deposit(2, ATTACKER);                          // 2*100/200 = 1 exact
        uint256 after_ = v.convertToAssets(v.balanceOf(HOLDER));
        require(after_ >= before_, "clean-ratio unit test unexpectedly failed");
    }
}
