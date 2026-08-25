// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

interface IERC20 {
    function transferFrom(address, address, uint256) external returns (bool);
    function transfer(address, uint256) external returns (bool);
}

/// @title BondManager — "모든 AI 발화는 담보 잡힌다"의 최소 실장 (Exp3)
/// @notice 에이전트는 토큰을 예치해야 주장(claim)을 제출할 수 있다.
///         판정자(judge)가 오류를 입증하면 해당 주장의 담보가 몰수된다.
///         출금은 지연창 이후에만 — 몰수 전에 도망가는 것을 막는다(펄체인 지연창 계승).
/// @dev    v0 정직성 주석: judge는 신뢰되는 오라클(실험실에선 합성 정답지)이다.
///         후속 단계에서 ZK 증명 또는 도전 게임으로 대체하는 것이 연구 목표이며,
///         이 컨트랙트는 그 경제 골격만 검증한다.
///         토큰 주소는 생성자 주입 — 체인·토큰 교체 가능 설계 원칙.
contract BondManager {
    IERC20 public immutable token;
    address public immutable judge;
    uint256 public immutable minBondPerClaim; // 주장 1건당 걸리는 담보
    uint256 public immutable unbondDelay;     // 출금 지연창 (초)

    struct Agent {
        uint256 bonded;        // 예치 총액
        uint256 atRisk;        // 미판정 주장에 걸린 담보 합
        uint256 unlockAt;      // 출금 가능 시각 (requestUnbond 이후)
        uint256 slashedTotal;  // 누적 몰수액 (관측용)
    }

    struct Claim {
        address agent;
        bytes32 claimHash;     // 주장 내용 커밋 (명제 집합+답의 해시)
        uint256 stakeAmount;
        bool settled;
        bool slashed;
    }

    mapping(address => Agent) public agents;
    Claim[] public claims;

    event Staked(address indexed agent, uint256 amount);
    event ClaimSubmitted(uint256 indexed id, address indexed agent, bytes32 claimHash);
    event ClaimUpheld(uint256 indexed id, address indexed agent);
    event ClaimSlashed(uint256 indexed id, address indexed agent, uint256 amount, bytes32 evidenceHash);
    event UnbondRequested(address indexed agent, uint256 unlockAt);
    event Withdrawn(address indexed agent, uint256 amount);

    constructor(address token_, address judge_, uint256 minBondPerClaim_, uint256 unbondDelay_) {
        token = IERC20(token_);
        judge = judge_;
        minBondPerClaim = minBondPerClaim_;
        unbondDelay = unbondDelay_;
    }

    function stake(uint256 amount) external {
        require(token.transferFrom(msg.sender, address(this), amount), "transfer");
        agents[msg.sender].bonded += amount;
        agents[msg.sender].unlockAt = 0; // 재예치는 출금 요청 취소로 간주
        emit Staked(msg.sender, amount);
    }

    /// @notice 주장 제출 — 자유 담보(bonded - atRisk)가 최소 담보 이상이어야 한다.
    ///         담보 없는 발화는 존재할 수 없다: 이것이 이 컨트랙트의 존재 이유.
    function submitClaim(bytes32 claimHash) external returns (uint256 id) {
        Agent storage a = agents[msg.sender];
        require(a.bonded - a.atRisk >= minBondPerClaim, "insufficient free bond");
        a.atRisk += minBondPerClaim;
        claims.push(Claim(msg.sender, claimHash, minBondPerClaim, false, false));
        id = claims.length - 1;
        emit ClaimSubmitted(id, msg.sender, claimHash);
    }

    /// @notice 판정: 오류 입증 시 몰수. evidenceHash = 반증 근거 커밋(감사 추적).
    function settle(uint256 id, bool violated, bytes32 evidenceHash) external {
        require(msg.sender == judge, "not judge");
        Claim storage c = claims[id];
        require(!c.settled, "settled");
        c.settled = true;
        Agent storage a = agents[c.agent];
        a.atRisk -= c.stakeAmount;
        if (violated) {
            c.slashed = true;
            a.bonded -= c.stakeAmount;
            a.slashedTotal += c.stakeAmount;
            // 몰수분은 컨트랙트에 잔류(소각 대체) — 실험 관측 목적
            emit ClaimSlashed(id, c.agent, c.stakeAmount, evidenceHash);
        } else {
            emit ClaimUpheld(id, c.agent);
        }
    }

    function requestUnbond() external {
        Agent storage a = agents[msg.sender];
        require(a.bonded > 0, "nothing bonded");
        a.unlockAt = block.timestamp + unbondDelay;
        emit UnbondRequested(msg.sender, a.unlockAt);
    }

    function withdraw() external {
        Agent storage a = agents[msg.sender];
        require(a.unlockAt != 0 && block.timestamp >= a.unlockAt, "locked");
        require(a.atRisk == 0, "claims pending");
        uint256 amount = a.bonded;
        a.bonded = 0;
        a.unlockAt = 0;
        require(token.transfer(msg.sender, amount), "transfer");
        emit Withdrawn(msg.sender, amount);
    }

    function freeBond(address agent) external view returns (uint256) {
        return agents[agent].bonded - agents[agent].atRisk;
    }

    function claimCount() external view returns (uint256) {
        return claims.length;
    }
}
