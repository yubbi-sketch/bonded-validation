// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {BondedValidator, IERC20} from "./BondedValidator.sol";

/// @title BondedJudgePanel — v0.2: 판정자 담보·확대재판·무보상금 (Exp8 승격분)
/// @notice JudgePanelV2(v0.1)의 후계. Exp8 공격 시뮬레이션(K1~K4 전부 통과)이
///         검증한 설계를 온체인으로 옮긴 것. 바뀐 것:
///         1) 판정자 담보 — 판정도 담보 잡힌 발화다. 풀 등록에 예치 필수,
///            사건 배정 시 사건당 담보(perCaseBond)가 잠긴다.
///         2) 확대재판 — 초심 3인 불일치 시 새 5인 추첨 재실행, 과반(>=3)이 최종.
///            최종 평결과 다른 표를 낸 모든 판정자(초심 포함)는 사건당 담보 몰수.
///         3) 무보상금(Exp8 제1원칙) — 승자 보상금은 매수 자금이 된다(매수 30%부터
///            공격 흑자 전환 실측). 몰수분은 절반 소각 + 절반 동결 피해 에이전트
///            배상. 판정 보수는 결과 무관 정액 수수료 균등 분배뿐.
///         4) 상급심(arbiter) 제거 — 훈련바퀴 탈거. 백스톱은 타임아웃 무손실
///            환급(태그 "disputed")만 남는다.
///         5) 시빌 방어 — 신참은 담보 1.5×(NEWCOMER_NUM/DEN) + 추첨 가중 1/5
///            (베테랑 5). Exp8 K2: 5% 장악 비용 = 정직 담보의 300배.
/// @dev    정직성 한계(연구 프로토타입):
///         - 추첨 시드는 prevrandao 기반 — 제안자 편향 가능. 실전은 VRF/커밋 몫.
///         - 소수파 슬래싱의 정당성은 결정론 범주(재실행 만장일치 기대) 한정.
///           비결정 범주·zk 증명은 P3 과제 (K3: ε=1%에서 부당 슬래시 0.6% 관측).
///         - 과반 부패(5인 중 3+ 담합)는 여전히 방어 밖 — 방어선은 경제(무수익)와
///           온체인 기록이지 물리적 차단이 아니다 (Exp8 K1 한계 명기 그대로).
contract BondedJudgePanel {
    BondedValidator public immutable bonded;
    IERC20 public immutable token;
    uint256 public immutable perCaseBond;    // 사건당 판정자 담보(=몰수 단위)
    uint256 public immutable judgeFee;       // 사건당 정액 수수료(개설자 부담)
    uint256 public immutable voteTimeout;    // 초심 시한 (개설 시각 기준)
    uint256 public immutable disputeTimeout; // 확대재판 시한 (분쟁 시각 기준)
    uint256 public immutable veteranThreshold; // 이 횟수 참여 정산 후 베테랑

    uint256 public constant NEWCOMER_NUM = 3;  // 신참 담보 할증 3/2 = 1.5×
    uint256 public constant NEWCOMER_DEN = 2;
    uint256 public constant VETERAN_WEIGHT = 5; // 추첨 가중 (신참 1)
    address public constant BURN = 0x000000000000000000000000000000000000dEaD;
    uint8 public constant PANEL_SIZE = 3;
    uint8 public constant EXPANDED_SIZE = 5;

    struct Judge {
        bool registered;
        uint256 agentId;        // 8004 신원
        uint256 bondedAmt;
        uint256 atRisk;
        uint256 unlockAt;
        uint256 settledCount;   // 참여 정산 횟수 (베테랑 판단)
        uint256 slashedTotal;
    }

    struct Vote {
        address judge;
        uint8 score;
        string tag;
        bytes32 evidence;
    }

    enum Phase { None, Initial, Expanded, Settled }

    struct CaseData {
        Phase phase;
        bool disputed;
        uint64 openedAt;
        uint64 disputedAt;
        address[] panel;     // 초심 3
        address[] expanded;  // 확대 5
        Vote[] votes;        // 캐스트된 모든 표 (초심+확대)
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
    event CaseOpened(bytes32 indexed requestHash, address[] panel);
    event Voted(bytes32 indexed requestHash, address indexed judge, uint8 score, string tag, bool expandedPhase);
    event Escalated(bytes32 indexed requestHash, address[] expanded);
    event JudgeSlashed(bytes32 indexed requestHash, address indexed judge, uint256 burned, uint256 compensated);
    event FeePaid(bytes32 indexed requestHash, address indexed judge, uint256 amount);
    event Settled(bytes32 indexed requestHash, uint8 score, string tag);
    event TimeoutRefund(bytes32 indexed requestHash);
    event NonParticipation(bytes32 indexed requestHash, address indexed judge);
    event UnbondRequested(address indexed judge, uint256 unlockAt);
    event Withdrawn(address indexed judge, uint256 amount);

    constructor(address bonded_, uint256 perCaseBond_, uint256 judgeFee_,
                uint256 voteTimeout_, uint256 disputeTimeout_, uint256 veteranThreshold_) {
        bonded = BondedValidator(bonded_);
        token = bonded.token();
        perCaseBond = perCaseBond_;
        judgeFee = judgeFee_;
        voteTimeout = voteTimeout_;
        disputeTimeout = disputeTimeout_;
        veteranThreshold = veteranThreshold_;
    }

    // ─── 판정자 풀 ───────────────────────────────────────────────

    function isVeteran(address j) public view returns (bool) {
        return judges[j].settledCount >= veteranThreshold;
    }

    /// @notice 배정 자격에 필요한 자유 담보 — 신참은 1.5× (Exp8 K2 방어).
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
        j.unlockAt = block.timestamp + disputeTimeout; // 최장 사건 시한과 동일 지연
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

    // ─── 사건 개설·추첨 ──────────────────────────────────────────

    /// @notice 사건 개설 — 개설자가 정액 수수료를 예치하고 초심 3인이 추첨된다.
    ///         발화 에이전트가 개설하는 게 정상 경로지만 누구든 가능(활성 보장).
    function openCase(bytes32 requestHash) external {
        require(bonded.claimExists(requestHash), "no claim");
        require(!bonded.claimSettled(requestHash), "claim settled");
        CaseData storage c = cases[requestHash];
        require(c.phase == Phase.None, "case open");
        require(token.transferFrom(msg.sender, address(this), judgeFee), "fee transfer");
        c.phase = Phase.Initial;
        c.openedAt = uint64(block.timestamp);
        _draw(requestHash, c.panel, PANEL_SIZE);
        emit CaseOpened(requestHash, c.panel);
    }

    struct DrawState {
        address[] elig;
        uint256[] w;
        uint256 m;
        uint256 totalW;
        bytes32 seed;
    }

    /// @dev 가중 무작위 비복원 추첨. 시드는 prevrandao — 연구 프로토타입 한계 명기.
    function _draw(bytes32 requestHash, address[] storage into, uint8 k) internal {
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
        s.seed = keccak256(abi.encodePacked(block.prevrandao, requestHash, address(this), into.length));
        for (uint256 pick = 0; pick < k; pick++) {
            address chosen = _pickOne(s);
            into.push(chosen);
            onCase[requestHash][chosen] = true;
            judges[chosen].atRisk += perCaseBond;
            s.seed = keccak256(abi.encodePacked(s.seed, pick));
        }
    }

    /// @dev 누적 가중 워크로 1인 선발 후 비복원 제거(swap-pop).
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

    // ─── 투표 ────────────────────────────────────────────────────

    function _verdictHash(uint8 score, string memory tag) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(score, tag));
    }

    function voteVerdict(bytes32 requestHash, uint8 score, string calldata tag,
                         bytes32 evidenceHash) external {
        CaseData storage c = cases[requestHash];
        require(c.phase == Phase.Initial || c.phase == Phase.Expanded, "no open case");
        require(onCase[requestHash][msg.sender], "not on case");
        require(!hasVoted[requestHash][msg.sender], "double vote");
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

    function _inList(address[] storage list, address x) internal view returns (bool) {
        for (uint256 i = 0; i < list.length; i++) if (list[i] == x) return true;
        return false;
    }

    /// @dev 풀이 확대재판 5인을 못 채우면 몰수 없이 무손실 환급 — 판정 불능을
    ///      동결로 바꾸지 않는다(활성 우선, v0.1 계승).
    function _escalate(bytes32 requestHash, CaseData storage c) internal {
        if (_eligibleCount(requestHash) < EXPANDED_SIZE) {
            _refund(requestHash, c);
            return;
        }
        c.phase = Phase.Expanded;
        c.disputedAt = uint64(block.timestamp);
        _draw(requestHash, c.expanded, EXPANDED_SIZE);
        emit Escalated(requestHash, c.expanded);
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

    // ─── 정산 ────────────────────────────────────────────────────

    function _settleUnanimous(bytes32 requestHash, CaseData storage c) internal {
        Vote storage v0 = c.votes[0];
        _finalize(requestHash, c, v0.score, v0.tag, v0.evidence);
    }

    /// @dev 확대 5표에서 과반(>=3) 평결 탐색. 없으면(2/2/1 분할) 무손실 환급 —
    ///      "소수=틀림"을 주장할 다수가 없으므로 아무도 몰수하지 않는다.
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
        if (!found) { // 2/2/1 분할 — "소수=틀림"을 주장할 다수 부재, 아무도 몰수 안 함
            _refund(requestHash, c);
            return;
        }
        // 소수파 몰수: 최종 평결과 다른 표(초심 포함) 전부. 무보상금 —
        // 절반 소각, 절반은 담보가 동결됐던 발화 에이전트에게 배상.
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

    /// @notice 활성 보장 백스톱 (상급심 없음 — v0.2에서 훈련바퀴 탈거).
    ///         초심 시한: 일치 2표면 정산, 분쟁이면 확대재판, 1표 이하면 환급.
    ///         확대 시한: 5표 미달이면 무손실 환급(아무도 몰수 안 됨) + 불참 기록.
    function resolveTimeout(bytes32 requestHash) external {
        CaseData storage c = cases[requestHash];
        if (c.phase == Phase.Initial) {
            require(block.timestamp >= c.openedAt + voteTimeout, "vote window open");
            _recordLaggards(requestHash, c.panel);
            if (c.disputed) {
                _escalate(requestHash, c);
            } else if (c.initialVotes >= 2) {
                _settleUnanimous(requestHash, c);
            } else {
                _refund(requestHash, c);
            }
        } else if (c.phase == Phase.Expanded) {
            require(block.timestamp >= c.disputedAt + disputeTimeout, "dispute window open");
            _recordLaggards(requestHash, c.expanded);
            _refund(requestHash, c);
        } else {
            revert("no open case");
        }
    }

    function _refund(bytes32 requestHash, CaseData storage c) internal {
        _finalize(requestHash, c, 50, "disputed", bytes32(0)); // 50 >= THRESHOLD → 무슬래시
        emit TimeoutRefund(requestHash);
    }

    /// @dev 공통 마무리: BondedValidator 정산, 사건 담보 해제, 수수료 균등 분배
    ///      (결과 무관 정액 — Exp8 제1원칙: 승자에게 상금을 주지 않는다).
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
        returns (Phase phase, bool disputed, uint8 initialVotes, uint8 expandedVotes)
    {
        CaseData storage c = cases[requestHash];
        return (c.phase, c.disputed, c.initialVotes, c.expandedVotes);
    }

    function casePanel(bytes32 requestHash) external view returns (address[] memory) {
        return cases[requestHash].panel;
    }

    function caseExpanded(bytes32 requestHash) external view returns (address[] memory) {
        return cases[requestHash].expanded;
    }
}
