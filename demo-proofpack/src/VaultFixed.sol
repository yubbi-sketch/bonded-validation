// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @title VaultFixed (representative DEMO — FIXED variant)
/// @notice Identical to VaultBuggy except ONE line: the deposit path
///         (convertToShares) now rounds DOWN instead of up, so both
///         directions round in the vault's favor (EIP-4626 compliant).
contract VaultFixed {
    uint256 public totalSupply;
    uint256 public totalAssets;
    mapping(address => uint256) public balanceOf;

    constructor(uint256 shares0, uint256 assets0, address holder0) {
        totalSupply = shares0;
        totalAssets = assets0;
        balanceOf[holder0] = shares0;
    }

    function mulDivDown(uint256 x, uint256 y, uint256 d) internal pure returns (uint256) {
        return (x * y) / d; // floor
    }

    function mulDivUp(uint256 x, uint256 y, uint256 d) internal pure returns (uint256) {
        return (x * y + d - 1) / d; // ceil (kept for parity; unused after fix)
    }

    /// @notice assets -> shares. FIX: rounds DOWN (favors the vault).
    function convertToShares(uint256 assets) public view returns (uint256) {
        return mulDivDown(assets, totalSupply, totalAssets); // <-- FIX: Up -> Down
    }

    /// @notice shares -> assets. Rounds DOWN (favors the vault).
    function convertToAssets(uint256 shares) public view returns (uint256) {
        return mulDivDown(shares, totalAssets, totalSupply);
    }

    function deposit(uint256 assets, address receiver) public returns (uint256 shares) {
        shares = convertToShares(assets);
        totalAssets += assets;
        totalSupply += shares;
        balanceOf[receiver] += shares;
    }
}
