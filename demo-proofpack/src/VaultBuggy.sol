// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @title VaultBuggy (representative DEMO — BUGGY variant)
/// @notice Minimal ERC-4626-style vault reduced to the assets<->shares
///         accounting where the well-known "rounding must always favor the
///         vault" rule (EIP-4626) matters. This is NOT a real product and does
///         not target any specific project. The vulnerability CLASS
///         (deposit-path rounding direction) is public and appears repeatedly
///         in audit reports.
///
///         Unlike a pure-conversion toy, `deposit` MUTATES pool state (mints
///         shares, adds assets), so the property is checked against a real
///         state transition, not a frozen rate.
contract VaultBuggy {
    uint256 public totalSupply; // total shares outstanding
    uint256 public totalAssets; // total underlying assets backing the shares
    mapping(address => uint256) public balanceOf;

    /// @param shares0 pre-existing shares (credited to holder0)
    /// @param assets0 pre-existing assets backing them
    /// @param holder0 the initial (existing) shareholder
    constructor(uint256 shares0, uint256 assets0, address holder0) {
        totalSupply = shares0;
        totalAssets = assets0;
        balanceOf[holder0] = shares0;
    }

    function mulDivDown(uint256 x, uint256 y, uint256 d) internal pure returns (uint256) {
        return (x * y) / d; // floor
    }

    function mulDivUp(uint256 x, uint256 y, uint256 d) internal pure returns (uint256) {
        return (x * y + d - 1) / d; // ceil
    }

    /// @notice assets -> shares.
    /// @dev BUG: rounds UP. The depositor is credited MORE shares than the
    ///      assets they paid are worth — rounding favors the depositor,
    ///      violating EIP-4626's rule that rounding must favor the vault
    ///      (and therefore existing holders).
    function convertToShares(uint256 assets) public view returns (uint256) {
        return mulDivUp(assets, totalSupply, totalAssets); // <-- BUG: Up
    }

    /// @notice shares -> assets. Correct: rounds DOWN (favors the vault).
    function convertToAssets(uint256 shares) public view returns (uint256) {
        return mulDivDown(shares, totalAssets, totalSupply);
    }

    /// @notice Deposit `assets`, mint shares at the CURRENT (pre-state) rate,
    ///         then mutate pool state.
    function deposit(uint256 assets, address receiver) public returns (uint256 shares) {
        shares = convertToShares(assets); // priced at pre-state rate
        totalAssets += assets;
        totalSupply += shares;
        balanceOf[receiver] += shares;
    }
}
