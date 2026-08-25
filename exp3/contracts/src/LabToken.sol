// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @title LabToken — 지능 불변 보안 연구 실험 전용 토큰
/// @notice 가치 없음·판매 없음·상장 없음. Anvil 로컬 실험에서 담보(슬래싱) 메커니즘
///         검증에만 쓰인다. 최소 ERC-20 (외부 의존성 0 — 재현성 원칙).
contract LabToken {
    string public constant name = "IIS Lab Token";
    string public constant symbol = "IISLAB";
    uint8 public constant decimals = 18;

    uint256 public totalSupply;
    address public immutable minter;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    constructor() {
        minter = msg.sender;
    }

    function mint(address to, uint256 amount) external {
        require(msg.sender == minter, "not minter");
        totalSupply += amount;
        balanceOf[to] += amount;
        emit Transfer(address(0), to, amount);
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        return _transfer(msg.sender, to, amount);
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 a = allowance[from][msg.sender];
        require(a >= amount, "allowance");
        if (a != type(uint256).max) allowance[from][msg.sender] = a - amount;
        return _transfer(from, to, amount);
    }

    function _transfer(address from, address to, uint256 amount) internal returns (bool) {
        require(balanceOf[from] >= amount, "balance");
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
        return true;
    }
}
