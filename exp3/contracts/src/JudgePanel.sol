// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {BondedValidator} from "./BondedValidator.sol";

/// @title JudgePanel — 판정 탈중앙 1보: 3인 재실행 만장일치 (Exp7)
/// @notice BondedValidator의 judge 자리에 EOA 대신 이 컨트랙트를 앉힌다.
///         결정론적 주장(기호 검증 가능 범주)은 독립 재실행 시 반드시 같은 답이
///         나오므로, 정직한 판정자들은 항상 만장일치다. 따라서:
///           - 정산(슬래시/해제)은 3표 전원 일치 시에만 집행
///           - 1표라도 어긋나면 Dispute — 정산 불가, 어떤 판정자도 단독으로
///             에이전트를 몰수시키거나 사면할 수 없다
/// @dev    v0 정직성: Dispute의 해소(재판정·판정자 슬래싱·타임아웃 환급)는
///         미설계 — 담보가 잠긴 채 남는다. 다음 단계 과제로 명시.
///         판정자 명단은 불변 3인 — 동적 패널·판정자 담보는 후속.
contract JudgePanel {
    BondedValidator public immutable bonded;
    address public immutable j1;
    address public immutable j2;
    address public immutable j3;

    struct Tally {
        uint8 votes;
        uint8 score0;       // 첫 표의 점수 (일치 비교 기준)
        bytes32 tagHash0;   // 첫 표의 태그 해시
        string tag0;        // 정산 전달용 원문
        bytes32 evidence0;
        bool disputed;
        bool settled;
    }

    mapping(bytes32 => Tally) public tallies;
    mapping(bytes32 => mapping(address => bool)) public hasVoted;

    event Voted(bytes32 indexed requestHash, address indexed judge, uint8 score, string tag);
    event Disputed(bytes32 indexed requestHash, address indexed dissenter);
    event Settled(bytes32 indexed requestHash, uint8 score, string tag);

    constructor(address bonded_, address a, address b, address c) {
        bonded = BondedValidator(bonded_);
        j1 = a; j2 = b; j3 = c;
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
        } else if (score != t.score0 || keccak256(bytes(tag)) != t.tagHash0) {
            t.disputed = true;
            emit Disputed(requestHash, msg.sender);
        }
        t.votes++;
        emit Voted(requestHash, msg.sender, score, tag);

        if (t.votes == 3 && !t.disputed) {
            t.settled = true;
            bonded.submitVerdict(requestHash, t.score0, "", t.evidence0, t.tag0);
            emit Settled(requestHash, t.score0, t.tag0);
        }
    }

    function status(bytes32 requestHash) external view
        returns (uint8 votes, bool disputed, bool settled)
    {
        Tally storage t = tallies[requestHash];
        return (t.votes, t.disputed, t.settled);
    }
}
