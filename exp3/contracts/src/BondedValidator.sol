// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {IdentityRegistry, ValidationRegistry} from "./Erc8004Registries.sol";

interface IERC20 {
    function transferFrom(address, address, uint256) external returns (bool);
    function transfer(address, uint256) external returns (bool);
}

/// @title BondedValidator — ERC-8004 위 "발화자 담보" 검증 프로토콜 v0 (Exp5)
/// @notice BondManager(Exp3)의 후계. 차이:
///         1) 에이전트는 8004 Identity 레지스트리의 agentId로 신원 확인
///         2) 발화(주장)는 8004 Validation 레지스트리에 표준 이벤트로 기록
///         3) 판정 점수(0~100)가 레지스트리에 남아 평판 원료가 됨
///         4) 기권(tag "abstain")은 담보 무손실 — Exp2 실증 규칙
/// @dev    v0 정직성: judge는 여전히 신뢰 오라클(탈중앙 판정은 후속 연구 —
///         결정론 범주는 재실행 만장일치, 비결정 범주는 zkML/검증자 담보층).
contract BondedValidator {
    IERC20 public immutable token;
    IdentityRegistry public immutable idReg;
    ValidationRegistry public immutable valReg;
    address public immutable judge;
    uint256 public immutable minBondPerClaim;
    uint256 public immutable unbondDelay;
    uint8 public constant THRESHOLD = 50; // 점수 < 50 ⇒ 슬래시

    struct Agent {
        uint256 bonded;
        uint256 atRisk;
        uint256 unlockAt;
        uint256 slashedTotal;
    }

    mapping(uint256 => Agent) public agents;          // agentId 기준
    mapping(bytes32 => uint256) public claimAgent;    // requestHash → agentId
    mapping(bytes32 => bool) public claimExists;
    mapping(bytes32 => bool) public claimSettled;

    event Staked(uint256 indexed agentId, uint256 amount);
    event ClaimBonded(uint256 indexed agentId, bytes32 indexed requestHash);
    event ClaimSettled(uint256 indexed agentId, bytes32 indexed requestHash,
                       uint8 score, bool slashed, bool abstained);
    event UnbondRequested(uint256 indexed agentId, uint256 unlockAt);
    event Withdrawn(uint256 indexed agentId, uint256 amount);

    constructor(address token_, address idReg_, address valReg_, address judge_,
                uint256 minBondPerClaim_, uint256 unbondDelay_) {
        token = IERC20(token_);
        idReg = IdentityRegistry(idReg_);
        valReg = ValidationRegistry(valReg_);
        judge = judge_;
        minBondPerClaim = minBondPerClaim_;
        unbondDelay = unbondDelay_;
    }

    modifier onlyAgentWallet(uint256 agentId) {
        require(msg.sender == idReg.getAgentWallet(agentId), "not agent wallet");
        _;
    }

    function stake(uint256 agentId, uint256 amount) external onlyAgentWallet(agentId) {
        require(token.transferFrom(msg.sender, address(this), amount), "transfer");
        agents[agentId].bonded += amount;
        agents[agentId].unlockAt = 0;
        emit Staked(agentId, amount);
    }

    /// @notice 담보 잡힌 발화 — 자유 담보 없으면 8004 검증 요청 자체가 성립하지 않는다.
    function requestValidation(uint256 agentId, string calldata requestURI, bytes32 requestHash)
        external onlyAgentWallet(agentId)
    {
        Agent storage a = agents[agentId];
        require(a.bonded - a.atRisk >= minBondPerClaim, "insufficient free bond");
        require(!claimExists[requestHash], "dup claim");
        a.atRisk += minBondPerClaim;
        claimAgent[requestHash] = agentId;
        claimExists[requestHash] = true;
        valReg.validationRequest(address(this), agentId, requestURI, requestHash);
        emit ClaimBonded(agentId, requestHash);
    }

    /// @notice 판정 — 점수는 8004 레지스트리에 기록되고, 담보는 여기서 정산된다.
    ///         tag "abstain" = 기권: 점수 무관 무손실 (Exp2 기권 무손실 규칙).
    function submitVerdict(bytes32 requestHash, uint8 score, string calldata responseURI,
                           bytes32 evidenceHash, string calldata tag) external {
        require(msg.sender == judge, "not judge");
        require(claimExists[requestHash], "no claim");
        require(!claimSettled[requestHash], "settled");
        claimSettled[requestHash] = true;

        uint256 agentId = claimAgent[requestHash];
        Agent storage a = agents[agentId];
        a.atRisk -= minBondPerClaim;

        bool abstained = keccak256(bytes(tag)) == keccak256(bytes("abstain"));
        bool slashed;
        if (!abstained && score < THRESHOLD) {
            slashed = true;
            a.bonded -= minBondPerClaim;
            a.slashedTotal += minBondPerClaim;
        }
        valReg.validationResponse(requestHash, score, responseURI, evidenceHash, tag);
        emit ClaimSettled(agentId, requestHash, score, slashed, abstained);
    }

    function requestUnbond(uint256 agentId) external onlyAgentWallet(agentId) {
        require(agents[agentId].bonded > 0, "nothing bonded");
        agents[agentId].unlockAt = block.timestamp + unbondDelay;
        emit UnbondRequested(agentId, agents[agentId].unlockAt);
    }

    function withdraw(uint256 agentId) external onlyAgentWallet(agentId) {
        Agent storage a = agents[agentId];
        require(a.unlockAt != 0 && block.timestamp >= a.unlockAt, "locked");
        require(a.atRisk == 0, "claims pending");
        uint256 amount = a.bonded;
        a.bonded = 0;
        a.unlockAt = 0;
        require(token.transfer(msg.sender, amount), "transfer");
        emit Withdrawn(agentId, amount);
    }

    function freeBond(uint256 agentId) external view returns (uint256) {
        return agents[agentId].bonded - agents[agentId].atRisk;
    }
}
