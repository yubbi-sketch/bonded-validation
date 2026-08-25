// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {BondedValidator} from "./BondedValidator.sol";

/// @title JudgePanelV2 — 분쟁 해소 v0.1 (심의 2026-08-26 결정 C의 A-안전판)
/// @notice JudgePanel(Exp7)의 후계. 추가된 것:
///         1) 분쟁 타임아웃 환급 — 분쟁이 disputeTimeout 내 미해소면 누구든
///            무손실 정산 호출 가능(태그 "disputed", 점수 50=무슬래시).
///            동결이 영구 → 유한으로. 공격자는 몰수도 영구동결도 못 얻는다.
///         2) 지각 판정자 처리 — voteTimeout 후 일치하는 2표만 있으면 정산(활성),
///            불참자는 NonParticipation 이벤트로 기록(객관적 결함만 기록 —
///            경제 페널티는 Exp8 검증 후).
///         3) 오너 상급심(훈련바퀴) — arbiter가 분쟁을 수동 판결 가능. 명시적
///            중앙화이며 v0.1 한정. Exp8(판정자 담보)이 검증되면 제거 예정.
/// @dev    주관적 반대표에 대한 슬래싱 없음(심의 판정: 소수=틀림이 온체인
///         미증명 — zk 전까지). 담합(과반 부패)은 여전히 방어 밖.
contract JudgePanelV2 {
    BondedValidator public immutable bonded;
    address public immutable j1;
    address public immutable j2;
    address public immutable j3;
    address public immutable arbiter;
    uint256 public immutable voteTimeout;     // 첫 표 이후 전원 투표 시한
    uint256 public immutable disputeTimeout;  // 분쟁 발생 후 상급심 시한

    struct Tally {
        uint8 votes;
        uint8 score0;
        bytes32 tagHash0;
        string tag0;
        bytes32 evidence0;
        bool disputed;
        bool settled;
        uint64 firstVoteAt;
        uint64 disputedAt;
    }

    mapping(bytes32 => Tally) public tallies;
    mapping(bytes32 => mapping(address => bool)) public hasVoted;

    event Voted(bytes32 indexed requestHash, address indexed judge, uint8 score, string tag);
    event Disputed(bytes32 indexed requestHash, address indexed dissenter);
    event Settled(bytes32 indexed requestHash, uint8 score, string tag);
    event TimeoutRefund(bytes32 indexed requestHash);
    event NonParticipation(bytes32 indexed requestHash, address indexed judge);
    event ArbiterRuled(bytes32 indexed requestHash, uint8 score, string tag);

    constructor(address bonded_, address a, address b, address c, address arbiter_,
                uint256 voteTimeout_, uint256 disputeTimeout_) {
        bonded = BondedValidator(bonded_);
        j1 = a; j2 = b; j3 = c;
        arbiter = arbiter_;
        voteTimeout = voteTimeout_;
        disputeTimeout = disputeTimeout_;
    }

    function isJudge(address x) public view returns (bool) {
        return x == j1 || x == j2 || x == j3;
    }

    function voteVerdict(bytes32 requestHash, uint8 score, string calldata tag,
                         bytes32 evidenceHash) external {
        require(isJudge(msg.sender), "not judge");
        require(!hasVoted[requestHash][msg.sender], "double vote");
        Tally storage t = tallies[requestHash];
        require(!t.settled, "settled");
        hasVoted[requestHash][msg.sender] = true;

        if (t.votes == 0) {
            t.score0 = score;
            t.tagHash0 = keccak256(bytes(tag));
            t.tag0 = tag;
            t.evidence0 = evidenceHash;
            t.firstVoteAt = uint64(block.timestamp);
        } else if (score != t.score0 || keccak256(bytes(tag)) != t.tagHash0) {
            if (!t.disputed) {
                t.disputed = true;
                t.disputedAt = uint64(block.timestamp);
                emit Disputed(requestHash, msg.sender);
            }
        }
        t.votes++;
        emit Voted(requestHash, msg.sender, score, tag);

        if (t.votes == 3 && !t.disputed) {
            _settle(t, requestHash, t.score0, t.tag0);
        }
    }

    /// @notice 활성 보장 — 누구든 호출 가능(허가 불요).
    ///         분쟁: disputeTimeout 경과 시 무손실 환급.
    ///         지각: voteTimeout 경과 + 일치 2표면 정산, 불참자 기록.
    ///         1표 이하: voteTimeout 경과 시 무손실 환급(판정 불능).
    function resolveTimeout(bytes32 requestHash) external {
        Tally storage t = tallies[requestHash];
        require(t.votes > 0, "no votes");
        require(!t.settled, "settled");
        if (t.disputed) {
            require(block.timestamp >= t.disputedAt + disputeTimeout, "dispute window open");
            _settle(t, requestHash, 50, "disputed"); // 50 >= THRESHOLD → 무슬래시
            emit TimeoutRefund(requestHash);
        } else {
            require(block.timestamp >= t.firstVoteAt + voteTimeout, "vote window open");
            _recordLaggards(requestHash);
            if (t.votes >= 2) {
                _settle(t, requestHash, t.score0, t.tag0); // 2표 일치(분쟁 아님이 보장)
            } else {
                _settle(t, requestHash, 50, "disputed"); // 판정 불능 — 무손실
                emit TimeoutRefund(requestHash);
            }
        }
    }

    /// @notice 오너 상급심 — 분쟁 상태에서만, 훈련바퀴(v0.1 한정).
    function resolveByArbiter(bytes32 requestHash, uint8 score, string calldata tag,
                              bytes32 evidenceHash) external {
        require(msg.sender == arbiter, "not arbiter");
        Tally storage t = tallies[requestHash];
        require(t.disputed && !t.settled, "not disputed");
        t.evidence0 = evidenceHash;
        _settle(t, requestHash, score, tag);
        emit ArbiterRuled(requestHash, score, tag);
    }

    function _settle(Tally storage t, bytes32 requestHash, uint8 score, string memory tag) internal {
        t.settled = true;
        bonded.submitVerdict(requestHash, score, "", t.evidence0, tag);
        emit Settled(requestHash, score, tag);
    }

    function _recordLaggards(bytes32 requestHash) internal {
        if (!hasVoted[requestHash][j1]) emit NonParticipation(requestHash, j1);
        if (!hasVoted[requestHash][j2]) emit NonParticipation(requestHash, j2);
        if (!hasVoted[requestHash][j3]) emit NonParticipation(requestHash, j3);
    }

    function status(bytes32 requestHash) external view
        returns (uint8 votes, bool disputed, bool settled)
    {
        Tally storage t = tallies[requestHash];
        return (t.votes, t.disputed, t.settled);
    }
}
