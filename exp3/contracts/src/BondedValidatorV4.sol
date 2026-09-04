// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {IdentityRegistry, ValidationRegistry} from "./Erc8004Registries.sol";
import {IERC20} from "./BondedValidator.sol";

/// @title BondedValidatorV4 — v0.4: stake() CEI 순서 수리 (RT-0032)
/// @notice BondedValidatorV3의 후계. v0.3과 로직 100% 동일, stake() 딱 하나만 다르다 —
///         token.transferFrom(외부 호출)이 상태 갱신(bonded += amount)보다 먼저였던
///         것을 뒤바꿨다. transferFrom 실패 시 트랜잭션 전체가 원자적으로 되돌아가므로
///         순서를 바꿔도 안전하고, 콜백 있는 토큰으로 교체되는 미래에도 재진입 창이
///         남지 않는다. (근본 원인: Exp7 최초 구현 이후 재감사 누락, v0.2.1/v0.3 승계)
/// @dev    아래는 v0.3 원문 그대로 — v0.2.1 의 활성(liveness) 공백을 닫는다:
///         v0.2.1 은 requestValidation 이 담보를 잠근 뒤 해제 경로가 judge 의
///         submitVerdict 뿐이었다 — 아무도 사건을 열지(judgeFee) 않으면 담보는 영원히
///         잠겼다(withdraw 'claims pending'). v0.3 은 다음을 추가한다:
///           R1 claimedAt — 주장 시각 기록
///           R2 engage    — judge 만, 창(challengeWindow) 안에서만 '개설됨' 표식
///           R3 disengage — judge 만, 패널이 추첨되지 못한 채 커밋 시한이 지났을 때 표식 해제
///           R4 settleUnchallenged — 누구든(gas 만), 창이 닫혔고 미개설이면 무손실 소멸
///                                  (점수 50 · 태그 "unchallenged" — 검증 아님, 미검증 해제)
///           R5 submitVerdict 는 engaged ∨ 창 안 에서만 — 모든 시각에 {engage, lapse} 중
///              정확히 하나만 활성(UMA 와 같은 < / ≥ 분할, 경계 경합 없음)
///         소멸에는 권한자 0명·보상 0·토큰 이동 0 (Exp27 L0 의 직계). R_c = 0 (Exp30 §3.1 b).
/// @dev    정직성: "unchallenged" 는 검증이 아니다. 소비자는 {"abstain","disputed",
///         "unchallenged"} 를 검증 건수에서 제외해야 한다(ERC 초안 R12). 억지력은 도전
///         확률 q 에 조건부가 된다 — v0.3 은 q 를 만들지 않고 가격표만 붙인다.
///         스크래치 원본: scratchpad/exp30-openlens/src/BondedValidatorV4.sol 에서
///         openerRefund·deadPool·OpenerRefunded 제거, disengage·생성자 범위검사·ClaimLapsed 추가.
contract BondedValidatorV4 {
    IERC20 public immutable token;
    IdentityRegistry public immutable idReg;
    ValidationRegistry public immutable valReg;
    address public immutable judge;
    uint256 public immutable minBondPerClaim;
    uint256 public immutable unbondDelay;
    uint256 public immutable challengeWindow;   // W — 개설(engage) 가능 기간
    uint8 public constant THRESHOLD = 50;       // 점수 < 50 ⇒ 슬래시
    uint8 public constant LAPSE_SCORE = 50;     // = THRESHOLD ⇒ T2 에 의해 슬래시 불가
    string public constant LAPSE_TAG = "unchallenged";

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
    mapping(bytes32 => uint64) public claimedAt;      // R1
    mapping(bytes32 => bool) public engaged;          // R2/R3 — 개설 표식

    event Staked(uint256 indexed agentId, uint256 amount);
    event ClaimBonded(uint256 indexed agentId, bytes32 indexed requestHash);
    event ClaimSettled(uint256 indexed agentId, bytes32 indexed requestHash,
                       uint8 score, bool slashed, bool abstained);
    event Engaged(bytes32 indexed requestHash);
    event Disengaged(bytes32 indexed requestHash);
    event ClaimLapsed(bytes32 indexed requestHash);
    event UnbondRequested(uint256 indexed agentId, uint256 unlockAt);
    event Withdrawn(uint256 indexed agentId, uint256 amount);

    constructor(address token_, address idReg_, address valReg_, address judge_,
                uint256 minBondPerClaim_, uint256 unbondDelay_, uint256 challengeWindow_) {
        require(challengeWindow_ > 0 && challengeWindow_ <= 365 days, "window range"); // R9
        token = IERC20(token_);
        idReg = IdentityRegistry(idReg_);
        valReg = ValidationRegistry(valReg_);
        judge = judge_;
        minBondPerClaim = minBondPerClaim_;
        unbondDelay = unbondDelay_;
        challengeWindow = challengeWindow_;
    }

    modifier onlyAgentWallet(uint256 agentId) {
        require(msg.sender == idReg.getAgentWallet(agentId), "not agent wallet");
        _;
    }

    modifier onlyJudge() {
        require(msg.sender == judge, "not judge");
        _;
    }

    /// @dev RT-0032 수리: 상태 먼저, 외부 호출 나중.
    function stake(uint256 agentId, uint256 amount) external onlyAgentWallet(agentId) {
        agents[agentId].bonded += amount;
        agents[agentId].unlockAt = 0;
        require(token.transferFrom(msg.sender, address(this), amount), "transfer");
        emit Staked(agentId, amount);
    }

    /// @notice 담보 잡힌 발화 — v0.2.1 과 동일 + claimedAt 기록 (R1).
    function requestValidation(uint256 agentId, string calldata requestURI, bytes32 requestHash)
        external onlyAgentWallet(agentId)
    {
        Agent storage a = agents[agentId];
        require(a.bonded - a.atRisk >= minBondPerClaim, "insufficient free bond");
        require(!claimExists[requestHash], "dup claim");
        a.atRisk += minBondPerClaim;
        claimAgent[requestHash] = agentId;
        claimExists[requestHash] = true;
        claimedAt[requestHash] = uint64(block.timestamp);
        valReg.validationRequest(address(this), agentId, requestURI, requestHash);
        emit ClaimBonded(agentId, requestHash);
    }

    /// @notice 창 열림 = block.timestamp < claimedAt + W (엄격 부등호 — 경계 초는 '닫힘').
    function windowOpen(bytes32 requestHash) public view returns (bool) {
        return block.timestamp < uint256(claimedAt[requestHash]) + challengeWindow;
    }

    /// @notice R2 개설 표식 — judge 만, 창 안에서만. 표식된 주장은 소멸 경로가 막히고
    ///         judge 의 판정만이 닫는다(패널 openCase 가 수수료 예치 직후 호출).
    function engage(bytes32 requestHash) external onlyJudge {
        require(claimExists[requestHash], "no claim");
        require(!claimSettled[requestHash], "settled");
        require(!engaged[requestHash], "engaged");
        require(windowOpen(requestHash), "window closed");
        engaged[requestHash] = true;
        emit Engaged(requestHash);
    }

    /// @notice R3 표식 해제 — judge 만. 패널이 커밋 시한까지 추첨되지 못한 사건을
    ///         되돌릴 때 호출한다(무패널 커밋은 도전이 아니다). 주장은 정산되지 않고
    ///         창이 계속 흐른다: 열려 있으면 재개설 가능, 닫혀 있으면 즉시 소멸 가능.
    function disengage(bytes32 requestHash) external onlyJudge {
        require(engaged[requestHash], "not engaged");
        require(!claimSettled[requestHash], "settled");
        engaged[requestHash] = false;
        emit Disengaged(requestHash);
    }

    /// @notice 판정 — judge 만. R5: 표식됐거나 창이 아직 열려 있어야 한다.
    ///         창 안에서는 개설 없이도 직접 정산 가능(ZkVerdictGate.attest 경로 보존).
    function submitVerdict(bytes32 requestHash, uint8 score, string calldata responseURI,
                           bytes32 evidenceHash, string calldata tag) external onlyJudge {
        require(claimExists[requestHash], "no claim");
        require(!claimSettled[requestHash], "settled");
        require(engaged[requestHash] || windowOpen(requestHash), "window closed");
        _settle(requestHash, score, responseURI, evidenceHash, tag);
    }

    /// @notice R4 소멸 — 누구든(권한·토큰 불요, gas 만). 창이 닫혔고 표식되지 않은
    ///         주장을 무손실로 닫는다. 토큰 이동 0 · bonded·slashedTotal 불변 · atRisk −= B_a.
    ///         레지스트리에는 (50, "unchallenged") — 검증이 아니라 '미검증 해제'.
    function settleUnchallenged(bytes32 requestHash) external {
        require(claimExists[requestHash], "no claim");
        require(!claimSettled[requestHash], "settled");
        require(!engaged[requestHash], "engaged");
        require(!windowOpen(requestHash), "window open");
        _settle(requestHash, LAPSE_SCORE, "", bytes32(0), LAPSE_TAG);
        emit ClaimLapsed(requestHash);
    }

    /// @dev v0.2.1 submitVerdict 본문 그대로 — T1~T4 의 대상.
    function _settle(bytes32 requestHash, uint8 score, string memory responseURI,
                     bytes32 evidenceHash, string memory tag) internal {
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
