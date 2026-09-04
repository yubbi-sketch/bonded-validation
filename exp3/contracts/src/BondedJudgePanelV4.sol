// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {BondedValidatorV4} from "./BondedValidatorV4.sol";
import {IERC20} from "./BondedValidator.sol";

/// @title BondedJudgePanelV4 — v0.4: 판정 투표 자체를 커밋-리빌로 (RT-0031 수리)
/// @notice BondedJudgePanelV3의 후계. 딱 하나만 다르다:
///         v0.2~v0.3은 "누가 판정단으로 뽑히는가"(패널 추첨)만 커밋-리빌로 그라인딩을
///         막았고, "판정자가 뭐라고 투표하는가"는 voteVerdict 한 번에 즉시 온체인
///         기록했다 — 늦게 투표하는 판정자가 앞선 표를 그대로 보고 따라갈 수 있었다
///         (정보 폭포/담합). Kleros·UMA가 기대는 셸링 포인트("남이 뭐라 할지 모르는
///         상태에서 각자 독립적으로 판단")의 전제가 이 지점에서 새고 있었다.
///         (RT-0031, 근본 원인: Exp7의 원판 투표 로직이 Exp9의 패널-추첨 커밋-리빌
///         도입 이후에도 재감사 없이 그대로 승계됨 — v0.2/v0.2.1/v0.3 전부 동일)
/// @dev    수리: voteVerdict 한 함수를 commitVerdict(해시만) + revealVerdict(실값)
///         두 함수로 쪼갠다. 패널 추첨에 이미 쓰던 것과 같은 커밋-리빌 패턴 재사용 —
///         새 암호 도구 없음, 새 신뢰 가정 없음. Initial/Expanded 두 페이즈 모두 동일
///         패턴 적용. 정산·수수료·슬래싱 로직은 v0.3과 100% 동일(오직 투표 취합
///         시점만 커밋→리빌로 이동).
contract BondedJudgePanelV4 {
    BondedValidatorV4 public immutable bonded;
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
    uint256 public constant MAX_TAG_BYTES = 1024;
    uint8 public constant MAX_SCORE = 100;

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

    /// @dev InitialReveal·ExpandedReveal 두 페이즈를 v0.3에 추가한 것이 유일한 확장.
    enum Phase { None, Committed, Initial, InitialReveal, ExpandedCommit, Expanded, ExpandedReveal, Settled }

    struct CaseData {
        Phase phase;
        bool disputed;
        uint64 commitBlock;
        uint64 committedAt;
        uint64 openedAt;      // 초심 추첨 완료 시각(커밋 시한 기준) → 전원 커밋 시 리빌 시한 기준으로 갱신
        uint64 disputedAt;
        address opener;
        address[] panel;
        address[] expanded;
        Vote[] votes;
        uint8 initialVotes;
        uint8 expandedVotes;
        uint8 commitCount;    // 이번 라운드(Initial 또는 Expanded)에서 커밋한 수
        mapping(address => bytes32) voteCommit;
        mapping(address => bool) hasCommitted;
    }

    address[] public pool;
    mapping(address => Judge) public judges;
    mapping(bytes32 => CaseData) internal cases;
    mapping(bytes32 => mapping(address => bool)) public onCase;
    mapping(bytes32 => mapping(address => bool)) public hasVoted; // = 리빌 완료

    event JudgeRegistered(address indexed judge, uint256 indexed agentId, uint256 deposit);
    event JudgeStaked(address indexed judge, uint256 amount);
    event CaseCommitted(bytes32 indexed requestHash, uint256 commitBlock);
    event Recommitted(bytes32 indexed requestHash, uint256 commitBlock);
    event PanelDrawn(bytes32 indexed requestHash, address[] panel);
    event VoteCommitted(bytes32 indexed requestHash, address indexed judge, bool expandedPhase);
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
        bonded = BondedValidatorV4(bonded_);
        token = bonded.token();
        perCaseBond = perCaseBond_;
        judgeFee = judgeFee_;
        voteTimeout = voteTimeout_;
        disputeTimeout = disputeTimeout_;
        veteranThreshold = veteranThreshold_;
    }

    // ─── 판정자 풀 (v0.3 동일) ───────────────────────────────────

    function isVeteran(address j) public view returns (bool) {
        return judges[j].settledCount >= veteranThreshold;
    }

    function requiredFreeBond(address j) public view returns (uint256) {
        return isVeteran(j) ? perCaseBond : perCaseBond * NEWCOMER_NUM / NEWCOMER_DEN;
    }

    /// @dev RT-0032 수리: 상태(effects)를 외부 호출(interaction)보다 먼저 반영한다 —
    ///      transferFrom 실패 시 트랜잭션 전체가 원자적으로 되돌아가므로 순서를
    ///      바꿔도 안전하다. 콜백 있는 토큰으로 교체되더라도 재진입 시점에 이미
    ///      최종 상태가 보이므로 이중 등록·이중 담보 반영 창이 없다.
    function registerJudge(uint256 agentId, uint256 deposit) external {
        Judge storage j = judges[msg.sender];
        require(!j.registered, "registered");
        require(msg.sender == bonded.idReg().getAgentWallet(agentId), "not agent wallet");
        require(deposit >= requiredFreeBond(msg.sender), "deposit below entry bond");
        j.registered = true;
        j.agentId = agentId;
        j.bondedAmt = deposit;
        pool.push(msg.sender);
        require(token.transferFrom(msg.sender, address(this), deposit), "transfer");
        emit JudgeRegistered(msg.sender, agentId, deposit);
    }

    /// @dev RT-0032 수리: 위와 동일한 이유로 순서 변경.
    function stakeMore(uint256 amount) external {
        Judge storage j = judges[msg.sender];
        require(j.registered, "not judge");
        j.bondedAmt += amount;
        j.unlockAt = 0;
        require(token.transferFrom(msg.sender, address(this), amount), "transfer");
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

    // ─── 커밋-리빌 개설·추첨 (v0.3 동일 — 패널이 누구인지 그라인딩 방지) ──

    function openCase(bytes32 requestHash) external {
        require(bonded.claimExists(requestHash), "no claim");
        require(!bonded.claimSettled(requestHash), "claim settled");
        CaseData storage c = cases[requestHash];
        require(c.phase == Phase.None, "case open");
        require(token.transferFrom(msg.sender, address(this), judgeFee), "fee transfer");
        bonded.engage(requestHash);
        c.phase = Phase.Committed;
        c.commitBlock = uint64(block.number);
        c.committedAt = uint64(block.timestamp);
        c.opener = msg.sender;
        emit CaseCommitted(requestHash, block.number);
    }

    function drawPanel(bytes32 requestHash) external {
        CaseData storage c = cases[requestHash];
        require(c.phase == Phase.Committed, "not committed");
        bytes32 seed = _revealSeed(requestHash, c);
        _draw(requestHash, c.panel, PANEL_SIZE, seed);
        c.phase = Phase.Initial;
        c.openedAt = uint64(block.timestamp); // 투표 커밋 시한 기준
        emit PanelDrawn(requestHash, c.panel);
    }

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
        c.openedAt = uint64(block.timestamp); // 투표 커밋 시한 기준(재사용)
        emit ExpandedDrawn(requestHash, c.expanded);
    }

    function recommit(bytes32 requestHash) external {
        CaseData storage c = cases[requestHash];
        require(c.phase == Phase.Committed || c.phase == Phase.ExpandedCommit, "no pending draw");
        require(block.number > uint256(c.commitBlock) + SEED_WINDOW, "seed still available");
        c.commitBlock = uint64(block.number);
        emit Recommitted(requestHash, block.number);
    }

    function _revealSeed(bytes32 requestHash, CaseData storage c) internal view virtual returns (bytes32) {
        require(block.number > c.commitBlock, "seed not born");
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

    // ─── 투표: 커밋 (신규 — RT-0031 수리 본체) ────────────────────

    /// @notice 판정자가 (score,tag,evidence,salt)의 해시만 올린다 — 값은 아직 아무도 못 봄.
    function commitVerdict(bytes32 requestHash, bytes32 voteCommitHash) external {
        CaseData storage c = cases[requestHash];
        require(c.phase == Phase.Initial || c.phase == Phase.Expanded, "no open case");
        require(onCase[requestHash][msg.sender], "not on case");
        require(!c.hasCommitted[msg.sender], "already committed");
        require(voteCommitHash != bytes32(0), "empty commit");
        c.hasCommitted[msg.sender] = true;
        c.voteCommit[msg.sender] = voteCommitHash;
        c.commitCount++;
        bool expandedPhase = c.phase == Phase.Expanded;
        emit VoteCommitted(requestHash, msg.sender, expandedPhase);

        uint8 need = expandedPhase ? EXPANDED_SIZE : PANEL_SIZE;
        if (c.commitCount == need) {
            c.phase = expandedPhase ? Phase.ExpandedReveal : Phase.InitialReveal;
            c.openedAt = uint64(block.timestamp); // 리빌 시한 기준으로 갱신
        }
    }

    /// @notice 전원 커밋 뒤 값을 공개 — 검증 실패 시 revert(잘못 커밋한 값으로 리빌 불가).
    function revealVerdict(bytes32 requestHash, uint8 score, string calldata tag,
                           bytes32 evidenceHash, bytes32 salt) external {
        CaseData storage c = cases[requestHash];
        bool expandedPhase = c.phase == Phase.ExpandedReveal;
        require(c.phase == Phase.InitialReveal || expandedPhase, "not reveal phase");
        require(c.hasCommitted[msg.sender], "not committed");
        require(!hasVoted[requestHash][msg.sender], "double reveal");
        require(
            keccak256(abi.encodePacked(score, tag, evidenceHash, salt)) == c.voteCommit[msg.sender],
            "commit mismatch"
        );
        require(score <= MAX_SCORE, "score range");
        require(bytes(tag).length <= MAX_TAG_BYTES, "tag too long");
        require(!_reservedTag(tag), "reserved tag");

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

    function _verdictHash(uint8 score, string memory tag) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(score, tag));
    }

    function _reservedTag(string calldata tag) internal pure returns (bool) {
        bytes32 t = keccak256(bytes(tag));
        return t == keccak256(bytes("unchallenged")) || t == keccak256(bytes("disputed"));
    }

    function _escalate(bytes32 requestHash, CaseData storage c) internal {
        c.phase = Phase.ExpandedCommit;
        c.commitBlock = uint64(block.number);
        c.disputedAt = uint64(block.timestamp);
        emit Escalated(requestHash, block.number);
    }

    // ─── 정산 (v0.3 과 100% 동일 로직) ────────────────────────────

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
        if (!found) {
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

    /// @notice 활성 보장 백스톱. Committed(패널 미추첨)·Initial/Expanded(투표 미커밋)
    ///         시한은 정산이 아니라 리셋/환급. InitialReveal/ExpandedReveal(리빌 미완료)
    ///         시한은 v0.3의 옛 Initial/Expanded 타임아웃 로직 그대로(부분 리빌만으로 판정).
    function resolveTimeout(bytes32 requestHash) external {
        CaseData storage c = cases[requestHash];
        if (c.phase == Phase.Committed) {
            require(block.timestamp >= c.committedAt + voteTimeout, "commit window open");
            _resetCommit(requestHash, c);
        } else if (c.phase == Phase.Initial || c.phase == Phase.Expanded) {
            // 투표 커밋 자체가 안 채워짐 — 무손실 환급(판정자 슬래시 없음, 신뢰 지연일 뿐).
            require(block.timestamp >= c.openedAt + voteTimeout, "vote-commit window open");
            _refund(requestHash, c);
        } else if (c.phase == Phase.InitialReveal) {
            require(block.timestamp >= c.openedAt + voteTimeout, "reveal window open");
            _recordLaggardsCommitted(requestHash, c.panel, c);
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
        } else if (c.phase == Phase.ExpandedReveal) {
            require(block.timestamp >= c.openedAt + voteTimeout, "reveal window open");
            _recordLaggardsCommitted(requestHash, c.expanded, c);
            _refund(requestHash, c);
        } else {
            revert("no open case");
        }
    }

    function _resetCommit(bytes32 requestHash, CaseData storage c) internal {
        address opener = c.opener;
        delete cases[requestHash];
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
            require(token.transfer(c.opener, judgeFee), "fee return");
            emit FeeReturned(requestHash, c.opener, judgeFee);
        }
        bonded.submitVerdict(requestHash, score, "", evidence, tag);
        emit Settled(requestHash, score, tag);
    }

    /// @dev v0.3의 _recordLaggards — "투표 안 한 판정자"를 "커밋해놓고 리빌 안 한 판정자"로 재정의.
    function _recordLaggardsCommitted(bytes32 requestHash, address[] storage members, CaseData storage c) internal {
        for (uint256 i = 0; i < members.length; i++) {
            if (c.hasCommitted[members[i]] && !hasVoted[requestHash][members[i]]) {
                emit NonParticipation(requestHash, members[i]);
            }
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

    function myCommit(bytes32 requestHash, address j) external view returns (bytes32) {
        return cases[requestHash].voteCommit[j];
    }

    function hasCommitted(bytes32 requestHash, address j) external view returns (bool) {
        return cases[requestHash].hasCommitted[j];
    }
}
