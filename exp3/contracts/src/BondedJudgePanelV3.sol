// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {BondedValidatorV3} from "./BondedValidatorV3.sol";
import {IERC20} from "./BondedValidator.sol";

/// @title BondedJudgePanelV3 — v0.3 (Exp30): 소멸 창과 결합한 커밋-리빌 패널
/// @notice BondedJudgePanelV2(v0.2.1)의 후계. 정산·추첨 로직은 v0.2.1 과 동일하고
///         다음 네 가지만 다르다(Exp30 §4 R6):
///           1) openCase 가 수수료 예치 직후 bonded.engage(h) — 창 밖 개설은 여기서 되돌려짐
///           2) Committed 시한(패널 미추첨)은 정산이 아니라 리셋(_resetCommit):
///              사건 삭제(Phase.None 복귀)·수수료 개설자 반환·bonded.disengage —
///              무패널 커밋은 도전이 아니다(낙관적창 반박 A: 풀<3 자기개설로 창 우회 봉쇄)
///           3) voteVerdict 에 score ≤ 100 · 태그 ≤ 1024B · 예약 태그 금지 —
///              v0.2.1 기존 웨지(score 101 2표 → 레지스트리 'range' 영구 되돌림) 수리
///           4) 상환·보상 없음(R_c = 0) — 수수료 규칙은 v0.2.1 그대로
///         Initial/ExpandedCommit/Expanded 시한은 v0.2.1 그대로(실제 추첨된 뒤의 시한
///         환급은 '실제 분쟁' — 50/"disputed" 유지).
/// @dev    v0.2.1 의 커밋-리빌 정직성 한계(제안자 편향)는 그대로 승계.
contract BondedJudgePanelV3 {
    BondedValidatorV3 public immutable bonded;
    IERC20 public immutable token;
    uint256 public immutable perCaseBond;
    uint256 public immutable judgeFee;
    uint256 public immutable voteTimeout;
    uint256 public immutable disputeTimeout;
    uint256 public immutable veteranThreshold;

    uint256 public constant NEWCOMER_NUM = 3;
    uint256 public constant NEWCOMER_DEN = 2;
    uint256 public constant VETERAN_WEIGHT = 5;
    address public constant BURN = 0x000000000000000000000000000000000000dEaD;
    uint8 public constant PANEL_SIZE = 3;
    uint8 public constant EXPANDED_SIZE = 5;
    uint256 public constant SEED_WINDOW = 256; // blockhash 가용 창
    uint256 public constant MAX_TAG_BYTES = 1024; // Exp30 R6 — 태그 가스 웨지 상한(Halmos 태그 bound 와 동일)
    uint8 public constant MAX_SCORE = 100;        // Exp30 R6 — 레지스트리 'range' 웨지 원천 차단

    struct Judge {
        bool registered;
        uint256 agentId;
        uint256 bondedAmt;
        uint256 atRisk;
        uint256 unlockAt;
        uint256 settledCount;
        uint256 slashedTotal;
    }

    struct Vote {
        address judge;
        uint8 score;
        string tag;
        bytes32 evidence;
    }

    enum Phase { None, Committed, Initial, ExpandedCommit, Expanded, Settled }

    struct CaseData {
        Phase phase;
        bool disputed;
        uint64 commitBlock;   // 시드가 태어날 블록 (커밋 시점엔 미래)
        uint64 committedAt;
        uint64 openedAt;      // 초심 추첨 완료 시각 (투표 시한 기준)
        uint64 disputedAt;
        address opener;       // 무투표 환급 시 수수료 반환처
        address[] panel;
        address[] expanded;
        Vote[] votes;
        uint8 initialVotes;
        uint8 expandedVotes;
    }

    address[] public pool;
    mapping(address => Judge) public judges;
    mapping(bytes32 => CaseData) internal cases;
    mapping(bytes32 => mapping(address => bool)) public onCase;
    mapping(bytes32 => mapping(address => bool)) public hasVoted;

    event JudgeRegistered(address indexed judge, uint256 indexed agentId, uint256 deposit);
    event JudgeStaked(address indexed judge, uint256 amount);
    event CaseCommitted(bytes32 indexed requestHash, uint256 commitBlock);
    event Recommitted(bytes32 indexed requestHash, uint256 commitBlock);
    event PanelDrawn(bytes32 indexed requestHash, address[] panel);
    event Voted(bytes32 indexed requestHash, address indexed judge, uint8 score, string tag, bool expandedPhase);
    event Escalated(bytes32 indexed requestHash, uint256 commitBlock);
    event ExpandedDrawn(bytes32 indexed requestHash, address[] expanded);
    event JudgeSlashed(bytes32 indexed requestHash, address indexed judge, uint256 burned, uint256 compensated);
    event FeePaid(bytes32 indexed requestHash, address indexed judge, uint256 amount);
    event FeeReturned(bytes32 indexed requestHash, address indexed opener, uint256 amount);
    event Settled(bytes32 indexed requestHash, uint8 score, string tag);
    event TimeoutRefund(bytes32 indexed requestHash);
    event CommitReset(bytes32 indexed requestHash, address indexed opener, uint256 feeReturned);
    event NonParticipation(bytes32 indexed requestHash, address indexed judge);
    event UnbondRequested(address indexed judge, uint256 unlockAt);
    event Withdrawn(address indexed judge, uint256 amount);

    constructor(address bonded_, uint256 perCaseBond_, uint256 judgeFee_,
                uint256 voteTimeout_, uint256 disputeTimeout_, uint256 veteranThreshold_) {
        bonded = BondedValidatorV3(bonded_);
        token = bonded.token();
        perCaseBond = perCaseBond_;
        judgeFee = judgeFee_;
        voteTimeout = voteTimeout_;
        disputeTimeout = disputeTimeout_;
        veteranThreshold = veteranThreshold_;
    }

    // ─── 판정자 풀 (v0.2 동일) ───────────────────────────────────

    function isVeteran(address j) public view returns (bool) {
        return judges[j].settledCount >= veteranThreshold;
    }

    function requiredFreeBond(address j) public view returns (uint256) {
        return isVeteran(j) ? perCaseBond : perCaseBond * NEWCOMER_NUM / NEWCOMER_DEN;
    }

    function registerJudge(uint256 agentId, uint256 deposit) external {
        Judge storage j = judges[msg.sender];
        require(!j.registered, "registered");
        require(msg.sender == bonded.idReg().getAgentWallet(agentId), "not agent wallet");
        require(deposit >= requiredFreeBond(msg.sender), "deposit below entry bond");
        require(token.transferFrom(msg.sender, address(this), deposit), "transfer");
        j.registered = true;
        j.agentId = agentId;
        j.bondedAmt = deposit;
        pool.push(msg.sender);
        emit JudgeRegistered(msg.sender, agentId, deposit);
    }

    function stakeMore(uint256 amount) external {
        Judge storage j = judges[msg.sender];
        require(j.registered, "not judge");
        require(token.transferFrom(msg.sender, address(this), amount), "transfer");
        j.bondedAmt += amount;
        j.unlockAt = 0;
        emit JudgeStaked(msg.sender, amount);
    }

    function requestUnbond() external {
        Judge storage j = judges[msg.sender];
        require(j.registered && j.bondedAmt > 0, "nothing bonded");
        j.unlockAt = block.timestamp + disputeTimeout;
        emit UnbondRequested(msg.sender, j.unlockAt);
    }

    function withdraw() external {
        Judge storage j = judges[msg.sender];
        require(j.unlockAt != 0 && block.timestamp >= j.unlockAt, "locked");
        require(j.atRisk == 0, "cases pending");
        uint256 amount = j.bondedAmt;
        j.bondedAmt = 0;
        j.unlockAt = 0;
        require(token.transfer(msg.sender, amount), "transfer");
        emit Withdrawn(msg.sender, amount);
    }

    function poolSize() external view returns (uint256) { return pool.length; }

    // ─── 커밋-리빌 개설·추첨 ─────────────────────────────────────

    /// @notice 1단계(커밋) — 수수료 예치·커밋 블록 기록. 시드는 아직 없다:
    ///         이 트랜잭션이 포함될 블록의 해시는 이 시점에 계산 불가능하므로
    ///         requestHash를 아무리 골라도 패널을 예측할 수 없다.
    function openCase(bytes32 requestHash) external {
        require(bonded.claimExists(requestHash), "no claim");
        require(!bonded.claimSettled(requestHash), "claim settled");
        CaseData storage c = cases[requestHash];
        require(c.phase == Phase.None, "case open");
        require(token.transferFrom(msg.sender, address(this), judgeFee), "fee transfer");
        bonded.engage(requestHash); // Exp30 R2 — 창 안에서만; 창 밖이면 "window closed" 로 되돌림
        c.phase = Phase.Committed;
        c.commitBlock = uint64(block.number);
        c.committedAt = uint64(block.timestamp);
        c.opener = msg.sender;
        emit CaseCommitted(requestHash, block.number);
    }

    /// @notice 2단계(리빌) — 다음 블록부터 누구든 호출. 시드 = 커밋 블록의 해시.
    function drawPanel(bytes32 requestHash) external {
        CaseData storage c = cases[requestHash];
        require(c.phase == Phase.Committed, "not committed");
        bytes32 seed = _revealSeed(requestHash, c);
        _draw(requestHash, c.panel, PANEL_SIZE, seed);
        c.phase = Phase.Initial;
        c.openedAt = uint64(block.timestamp);
        emit PanelDrawn(requestHash, c.panel);
    }

    /// @notice 확대재판 리빌 — 풀이 5인을 못 채우면 무손실 환급.
    function drawExpanded(bytes32 requestHash) external {
        CaseData storage c = cases[requestHash];
        require(c.phase == Phase.ExpandedCommit, "not expanded commit");
        if (_eligibleCount(requestHash) < EXPANDED_SIZE) {
            _refund(requestHash, c);
            return;
        }
        bytes32 seed = _revealSeed(requestHash, c);
        _draw(requestHash, c.expanded, EXPANDED_SIZE, seed);
        c.phase = Phase.Expanded;
        emit ExpandedDrawn(requestHash, c.expanded);
    }

    /// @notice 256블록 내 리빌이 안 됐으면 커밋 갱신 — 추첨은 무산되지만
    ///         지연으로 얻는 그라인딩 이득은 없다(새 시드도 미래 해시).
    function recommit(bytes32 requestHash) external {
        CaseData storage c = cases[requestHash];
        require(c.phase == Phase.Committed || c.phase == Phase.ExpandedCommit, "no pending draw");
        require(block.number > uint256(c.commitBlock) + SEED_WINDOW, "seed still available");
        c.commitBlock = uint64(block.number);
        emit Recommitted(requestHash, block.number);
    }

    /// @dev virtual은 검증 가능 설계 — 증명 하네스가 결정론 시드로 오버라이드해
    ///      정산 계층을 심볼릭 증명한다(추첨 분포는 확률적 성질이라 증명 범위 밖).
    function _revealSeed(bytes32 requestHash, CaseData storage c) internal view virtual returns (bytes32) {
        require(block.number > c.commitBlock, "seed not born"); // 같은 블록 리빌 불가
        require(block.number <= uint256(c.commitBlock) + SEED_WINDOW, "seed expired: recommit");
        return keccak256(abi.encodePacked(blockhash(c.commitBlock), requestHash, address(this)));
    }

    struct DrawState {
        address[] elig;
        uint256[] w;
        uint256 m;
        uint256 totalW;
        bytes32 seed;
    }

    function _draw(bytes32 requestHash, address[] storage into, uint8 k, bytes32 seed) internal {
        DrawState memory s;
        s.elig = new address[](pool.length);
        s.w = new uint256[](pool.length);
        for (uint256 i = 0; i < pool.length; i++) {
            address a = pool[i];
            Judge storage j = judges[a];
            if (onCase[requestHash][a]) continue;
            if (j.bondedAmt - j.atRisk < requiredFreeBond(a)) continue;
            uint256 wi = isVeteran(a) ? VETERAN_WEIGHT : 1;
            s.elig[s.m] = a; s.w[s.m] = wi; s.totalW += wi; s.m++;
        }
        require(s.m >= k, "pool too small");
        s.seed = seed;
        for (uint256 pick = 0; pick < k; pick++) {
            address chosen = _pickOne(s);
            into.push(chosen);
            onCase[requestHash][chosen] = true;
            judges[chosen].atRisk += perCaseBond;
            s.seed = keccak256(abi.encodePacked(s.seed, pick));
        }
    }

    function _pickOne(DrawState memory s) internal pure returns (address chosen) {
        uint256 r = uint256(s.seed) % s.totalW;
        uint256 acc; uint256 sel;
        for (uint256 i = 0; i < s.m; i++) {
            acc += s.w[i];
            if (r < acc) { sel = i; break; }
        }
        chosen = s.elig[sel];
        s.totalW -= s.w[sel];
        s.elig[sel] = s.elig[s.m - 1];
        s.w[sel] = s.w[s.m - 1];
        s.m--;
    }

    function _eligibleCount(bytes32 requestHash) internal view returns (uint256 m) {
        for (uint256 i = 0; i < pool.length; i++) {
            address a = pool[i];
            Judge storage j = judges[a];
            if (onCase[requestHash][a]) continue;
            if (j.bondedAmt - j.atRisk < requiredFreeBond(a)) continue;
            m++;
        }
    }

    // ─── 투표 (v0.2 동일, 확대 이행만 2단계) ─────────────────────

    function _verdictHash(uint8 score, string memory tag) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(score, tag));
    }

    function voteVerdict(bytes32 requestHash, uint8 score, string calldata tag,
                         bytes32 evidenceHash) external {
        CaseData storage c = cases[requestHash];
        require(c.phase == Phase.Initial || c.phase == Phase.Expanded, "no open case");
        require(onCase[requestHash][msg.sender], "not on case");
        require(!hasVoted[requestHash][msg.sender], "double vote");
        require(score <= MAX_SCORE, "score range");                    // Exp30 R6 (웨지 수리)
        require(bytes(tag).length <= MAX_TAG_BYTES, "tag too long");   // Exp30 R6 (태그 가스)
        require(!_reservedTag(tag), "reserved tag");                   // Exp30 R6 (예약 태그)
        bool expandedPhase = c.phase == Phase.Expanded;
        if (expandedPhase) {
            require(_inList(c.expanded, msg.sender), "initial judge in expanded phase");
        }
        hasVoted[requestHash][msg.sender] = true;
        c.votes.push(Vote(msg.sender, score, tag, evidenceHash));
        emit Voted(requestHash, msg.sender, score, tag, expandedPhase);

        if (!expandedPhase) {
            c.initialVotes++;
            if (!c.disputed && c.initialVotes > 1) {
                Vote storage v0 = c.votes[0];
                if (_verdictHash(score, tag) != _verdictHash(v0.score, v0.tag)) c.disputed = true;
            }
            if (c.initialVotes == PANEL_SIZE) {
                if (c.disputed) _escalate(requestHash, c);
                else _settleUnanimous(requestHash, c);
            }
        } else {
            c.expandedVotes++;
            if (c.expandedVotes == EXPANDED_SIZE) _settleExpanded(requestHash, c);
        }
    }

    /// @dev 예약 태그 — 프로토콜이 소멸·시한환급에 쓰는 태그를 판정자가 사칭할 수 없다.
    function _reservedTag(string calldata tag) internal pure returns (bool) {
        bytes32 t = keccak256(bytes(tag));
        return t == keccak256(bytes("unchallenged")) || t == keccak256(bytes("disputed"));
    }

    function _inList(address[] storage list, address x) internal view returns (bool) {
        for (uint256 i = 0; i < list.length; i++) if (list[i] == x) return true;
        return false;
    }

    /// @dev 확대재판도 커밋-리빌: 여기선 커밋만 하고 추첨은 drawExpanded가 한다.
    function _escalate(bytes32 requestHash, CaseData storage c) internal {
        c.phase = Phase.ExpandedCommit;
        c.commitBlock = uint64(block.number);
        c.disputedAt = uint64(block.timestamp);
        emit Escalated(requestHash, block.number);
    }

    // ─── 정산 (v0.2 동일) ────────────────────────────────────────

    function _settleUnanimous(bytes32 requestHash, CaseData storage c) internal {
        Vote storage v0 = c.votes[0];
        _finalize(requestHash, c, v0.score, v0.tag, v0.evidence);
    }

    function _settleExpanded(bytes32 requestHash, CaseData storage c) internal {
        uint256 start = c.votes.length - EXPANDED_SIZE;
        bytes32 majHash; uint256 majIdx; bool found;
        for (uint256 i = start; i < c.votes.length && !found; i++) {
            bytes32 h = _verdictHash(c.votes[i].score, c.votes[i].tag);
            uint256 cnt;
            for (uint256 k2 = start; k2 < c.votes.length; k2++) {
                if (_verdictHash(c.votes[k2].score, c.votes[k2].tag) == h) cnt++;
            }
            if (cnt * 2 > EXPANDED_SIZE) { majHash = h; majIdx = i; found = true; }
        }
        if (!found) { // 2/2/1 분할 — 몰수할 다수 부재
            _refund(requestHash, c);
            return;
        }
        address agentWallet = bonded.idReg().getAgentWallet(bonded.claimAgent(requestHash));
        for (uint256 i = 0; i < c.votes.length; i++) {
            Vote storage v = c.votes[i];
            if (_verdictHash(v.score, v.tag) != majHash) {
                Judge storage j = judges[v.judge];
                j.bondedAmt -= perCaseBond;
                j.slashedTotal += perCaseBond;
                uint256 half = perCaseBond / 2;
                require(token.transfer(BURN, half), "burn");
                require(token.transfer(agentWallet, perCaseBond - half), "comp");
                emit JudgeSlashed(requestHash, v.judge, half, perCaseBond - half);
            }
        }
        Vote storage maj = c.votes[majIdx];
        _finalize(requestHash, c, maj.score, maj.tag, maj.evidence);
    }

    /// @notice 활성 보장 백스톱. Committed(패널 미추첨) 시한은 정산이 아니라 리셋 —
    ///         사건을 None 으로 되돌리고 수수료를 개설자에게 반환하며 표식을 해제한다
    ///         (Exp30 R3/R6). 추첨된 뒤의 시한(Initial/ExpandedCommit/Expanded)은 v0.2.1
    ///         그대로 무손실 환급(50/"disputed").
    function resolveTimeout(bytes32 requestHash) external {
        CaseData storage c = cases[requestHash];
        if (c.phase == Phase.Committed) {
            require(block.timestamp >= c.committedAt + voteTimeout, "commit window open");
            _resetCommit(requestHash, c);
        } else if (c.phase == Phase.Initial) {
            require(block.timestamp >= c.openedAt + voteTimeout, "vote window open");
            _recordLaggards(requestHash, c.panel);
            if (c.disputed) {
                _escalate(requestHash, c);
            } else if (c.initialVotes >= 2) {
                _settleUnanimous(requestHash, c);
            } else {
                _refund(requestHash, c);
            }
        } else if (c.phase == Phase.ExpandedCommit) {
            require(block.timestamp >= c.disputedAt + disputeTimeout, "dispute window open");
            _refund(requestHash, c);
        } else if (c.phase == Phase.Expanded) {
            require(block.timestamp >= c.disputedAt + disputeTimeout, "dispute window open");
            _recordLaggards(requestHash, c.expanded);
            _refund(requestHash, c);
        } else {
            revert("no open case");
        }
    }

    /// @dev Exp30 R3 — 무패널 커밋 리셋. 추첨이 없었으므로 판정자 atRisk·onCase 는 비어 있다.
    ///      주장은 정산되지 않는다(창이 계속 흐름): 창 열림 → 재개설 가능, 닫힘 → 소멸 가능.
    function _resetCommit(bytes32 requestHash, CaseData storage c) internal {
        address opener = c.opener;
        delete cases[requestHash]; // Phase.None 복귀 (배열·카운터 전부 초기화)
        if (judgeFee > 0) require(token.transfer(opener, judgeFee), "fee return");
        bonded.disengage(requestHash);
        emit CommitReset(requestHash, opener, judgeFee);
    }

    function _refund(bytes32 requestHash, CaseData storage c) internal {
        _finalize(requestHash, c, 50, "disputed", bytes32(0));
        emit TimeoutRefund(requestHash);
    }

    function _finalize(bytes32 requestHash, CaseData storage c, uint8 score,
                       string memory tag, bytes32 evidence) internal {
        c.phase = Phase.Settled;
        for (uint256 i = 0; i < c.panel.length; i++) judges[c.panel[i]].atRisk -= perCaseBond;
        for (uint256 i = 0; i < c.expanded.length; i++) judges[c.expanded[i]].atRisk -= perCaseBond;
        uint256 nVoters = c.votes.length;
        if (nVoters > 0) {
            uint256 share = judgeFee / nVoters;
            for (uint256 i = 0; i < nVoters; i++) {
                judges[c.votes[i].judge].settledCount++;
                if (share > 0) {
                    require(token.transfer(c.votes[i].judge, share), "fee");
                    emit FeePaid(requestHash, c.votes[i].judge, share);
                }
            }
        } else if (judgeFee > 0) {
            // 아무도 판정에 이르지 못한 사건 — 수수료를 개설자에게 되돌린다.
            require(token.transfer(c.opener, judgeFee), "fee return");
            emit FeeReturned(requestHash, c.opener, judgeFee);
        }
        bonded.submitVerdict(requestHash, score, "", evidence, tag);
        emit Settled(requestHash, score, tag);
    }

    function _recordLaggards(bytes32 requestHash, address[] storage members) internal {
        for (uint256 i = 0; i < members.length; i++) {
            if (!hasVoted[requestHash][members[i]]) emit NonParticipation(requestHash, members[i]);
        }
    }

    // ─── 조회 ────────────────────────────────────────────────────

    function caseStatus(bytes32 requestHash) external view
        returns (Phase phase, bool disputed, uint8 initialVotes, uint8 expandedVotes, uint64 commitBlock)
    {
        CaseData storage c = cases[requestHash];
        return (c.phase, c.disputed, c.initialVotes, c.expandedVotes, c.commitBlock);
    }

    function casePanel(bytes32 requestHash) external view returns (address[] memory) {
        return cases[requestHash].panel;
    }

    function caseExpanded(bytes32 requestHash) external view returns (address[] memory) {
        return cases[requestHash].expanded;
    }
}
