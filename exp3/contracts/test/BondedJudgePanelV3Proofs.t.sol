// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidatorV3} from "../src/BondedValidatorV3.sol";
import {BondedJudgePanelV3} from "../src/BondedJudgePanelV3.sol";

interface Vm {
    function prank(address) external;
    function startPrank(address) external;
    function stopPrank() external;
    function warp(uint256) external;
    function roll(uint256) external;
    function assume(bool) external;
}

/// @notice Exp30 — 패널 v0.3 기계 증명 (Halmos). Exp12 의 PA/PB/PC/P4 를 단언 무수정으로
///         회귀시키고(정산 로직 무수정의 기계 확인), 신규 PL1~PL3 을 더한다:
///
///         PL1. 시한 활성 — ∀ s1,s2 ≤ 100: 초심 2표 뒤 resolveTimeout 이 되돌리지 않는다
///              (저수준 call + assert(ok): Halmos 는 require 되돌림 경로를 조용히 버리므로
///              P4 는 이 영역에서 공허했다 — 스크래치 반례 s1=s2=0x80). ∀ s>100: 투표 자체 되돌림.
///         PL2. 커밋 시한 리셋 — Committed ∧ 무추첨 ∧ t ≥ committedAt+voteTimeout ⟹
///              phase′=None ∧ opener 잔고 +F ∧ ¬engaged′ ∧ ¬claimSettled′.
///         PL3. 예약 태그 거부 + 판정자 보존 — voteVerdict("unchallenged"|"disputed") 되돌림;
///              소멸 전후 ∀ j ∈ pool: (bondedAmt, atRisk, settledCount, slashedTotal, balance) 불변.
///
///         범위 정직성(Exp12 승계): 패널 구성은 구체(결정론 시드), 투표 점수 심볼릭·태그 고정("t").
///         PB/PC 의 과반 위치는 WLOG(대칭성) — 기계 증명 범위 밖.
/// @dev 증명 하네스 — 시드만 결정론으로 고정. 경제 로직은 부모 그대로.
contract PanelHarnessV3 is BondedJudgePanelV3 {
    constructor(address bonded_, uint256 perCaseBond_, uint256 judgeFee_,
                uint256 voteTimeout_, uint256 disputeTimeout_, uint256 veteranThreshold_)
        BondedJudgePanelV3(bonded_, perCaseBond_, judgeFee_, voteTimeout_,
                           disputeTimeout_, veteranThreshold_) {}

    function _revealSeed(bytes32 requestHash, CaseData storage c)
        internal view override returns (bytes32)
    {
        require(block.number > c.commitBlock, "seed not born"); // 커밋-리빌 규칙은 유지
        return keccak256(abi.encodePacked(requestHash, uint256(c.commitBlock)));
    }
}

contract BondedJudgePanelV3Proofs {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    IdentityRegistry idReg;
    ValidationRegistry valReg;
    BondedValidatorV3 bv;
    BondedJudgePanelV3 panel;
    address wallet = address(0x2001);
    address[] js;
    uint256 aid;
    uint256 constant BOND = 10e18;
    uint256 constant FEE = 8e18;
    uint256 constant VOTE_T = 100;
    uint256 constant DISP_T = 200;
    uint256 constant ENTRY = 15e18;
    uint256 constant W = 86400;
    bytes32 constant H = bytes32(uint256(0xF00D));
    bytes32 constant H2 = bytes32(uint256(0xF00E)); // PL2 (커밋만, 추첨 없음)
    bytes32 constant H3 = bytes32(uint256(0xF00F)); // PL3 (미개설 → 소멸)

    function setUp() public {
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        // Halmos는 CREATE 주소를 내부 순번(0xaaaa000N)으로 배정 — Exp12 와 동일 순서·동일 상수.
        address predicted = address(0xaaaa0006);
        bv = new BondedValidatorV3(address(token), address(idReg), address(valReg),
                                   predicted, 1e18, 60, W);
        panel = BondedJudgePanelV3(address(new PanelHarnessV3(address(bv), BOND, FEE, VOTE_T, DISP_T, 3)));
        require(address(panel) == predicted, "prediction failed");

        token.mint(wallet, 100e18);
        vm.startPrank(wallet);
        aid = idReg.register("agent://p");
        token.approve(address(bv), type(uint256).max);
        token.approve(address(panel), type(uint256).max);
        bv.stake(aid, 10e18);
        bv.requestValidation(aid, "", H);
        vm.stopPrank();

        for (uint256 i = 0; i < 9; i++) {
            address j = address(uint160(0x3000 + i));
            js.push(j);
            token.mint(j, 20e18);
            vm.startPrank(j);
            uint256 jid = idReg.register("agent://j");
            token.approve(address(panel), type(uint256).max);
            panel.registerJudge(jid, ENTRY);
            vm.stopPrank();
        }
        vm.prank(wallet);
        panel.openCase(H); // engage — 창 안(dt=0)
        vm.roll(block.number + 1);
        panel.drawPanel(H); // 결정론 시드 → 패널 구성은 구체, 이후 투표만 심볼릭
    }

    function _vote(address j, uint8 s) internal {
        vm.prank(j);
        panel.voteVerdict(H, s, "t", bytes32(0));
    }

    function _jb(address j) internal view returns (uint256 b) {
        (, , b, , , , ) = panel.judges(j);
    }

    function _jstate(address j) internal view returns (uint256 b, uint256 atRisk, uint256 settled, uint256 slashed) {
        (, , b, atRisk, , settled, slashed) = panel.judges(j);
    }

    function _phase(bytes32 h) internal view returns (BondedJudgePanelV3.Phase ph) {
        (ph,,,,) = panel.caseStatus(h);
    }

    /// 사양(참조 모델): 초심 3표 + (분쟁 시) 확대 5표에서 최종 결과를 계산한다.
    /// returns (settledByVerdict, finalScore) — settledByVerdict=false는 환급.
    function _specFinal(uint8 a1, uint8 a2, uint8 a3, uint8[5] memory e, bool disputed)
        internal pure returns (bool, uint8)
    {
        if (!disputed) return (true, a1); // 만장일치
        for (uint256 i = 0; i < 5; i++) {
            uint256 cnt;
            for (uint256 k = 0; k < 5; k++) if (e[k] == e[i]) cnt++;
            if (cnt >= 3) return (true, e[i]);
        }
        return (false, 50); // 과반 부재 → 환급
    }

    // ═══ PA/PB/PC/P4 회귀 (Exp12 본문 무수정 — assume 도 없음. v0.3 은 score>100 표를 voteVerdict 에서
    //     되돌리므로 그 영역은 Halmos 가 버리는 되돌림 경로가 된다; 그 영역의 성질은 PL1a 가 명시적으로 증명) ═══

    /// 클래스 A(만장일치): ∀s — 아무도 몰수되지 않고 수수료는 3등분.
    function check_PA_unanimous(uint8 s) public {
        uint8[3] memory avec = [s, s, s];
        uint8[5] memory evec = [0, 0, 0, 0, 0];
        _refine(avec, evec);
    }

    /// 클래스 B(과반 성립): ∀m,x,y,a1..a3 — e1~e3=m이 과반. 소수파만 몰수,
    ///     상금 없음, 에이전트는 m<50일 때만 슬래시. (과반 위치는 WLOG)
    function check_PB_majority(uint8 a1, uint8 a2, uint8 a3, uint8 m, uint8 x, uint8 y) public {
        if (a1 == a2 && a2 == a3) return; // 분쟁 경로만 (만장일치는 클래스 A)
        uint8[3] memory avec = [a1, a2, a3];
        uint8[5] memory evec = [m, m, m, x, y];
        _refine(avec, evec);
    }

    /// 클래스 C(과반 부재 2/2/1): ∀p,q,r 상호 상이 — 무손실 환급, 아무도 몰수 안 됨.
    function check_PC_split(uint8 p, uint8 q, uint8 r) public {
        if (p == q || q == r || p == r) return; // 2/2/1이 되는 조합만
        uint8[3] memory avec = [p, p, q]; // 분쟁 유발
        uint8[5] memory evec = [p, p, q, q, r];
        _refine(avec, evec);
    }

    function _refine(uint8[3] memory avec, uint8[5] memory evec) internal {
        address[] memory p = panel.casePanel(H);
        (uint256 agentB0,,,) = bv.agents(aid);

        for (uint256 i = 0; i < 3; i++) _vote(p[i], avec[i]);
        bool disputed = !(avec[0] == avec[1] && avec[1] == avec[2]);
        address[] memory ex = new address[](0);
        uint256[] memory balBefore = new uint256[](5);
        if (disputed) {
            vm.roll(block.number + 1);
            panel.drawExpanded(H);
            ex = panel.caseExpanded(H);
            for (uint256 i = 0; i < 5; i++) balBefore[i] = token.balanceOf(ex[i]);
            for (uint256 i = 0; i < 5; i++) _vote(ex[i], evec[i]);
        }

        (bool byVerdict, uint8 fin) = _specFinal(avec[0], avec[1], avec[2], evec, disputed);
        uint256 share = FEE / (disputed ? 8 : 3);

        // P2: 소수파만 몰수 — 초심 3인
        for (uint256 i = 0; i < 3; i++) {
            bool slashExpected = disputed && byVerdict && avec[i] != fin;
            assert(_jb(p[i]) == (slashExpected ? ENTRY - BOND : ENTRY));
        }
        // P1·P2: 확대 5인 — 몰수는 소수파만, 외부 수입은 수수료 균등분뿐
        for (uint256 i = 0; i < ex.length; i++) {
            bool slashExpected = byVerdict && evec[i] != fin;
            assert(_jb(ex[i]) == (slashExpected ? ENTRY - BOND : ENTRY));
            assert(token.balanceOf(ex[i]) == balBefore[i] + share); // 상금 없음
        }
        // P3: 에이전트 보존 — 평결 50 미만일 때만 minBond 슬래시, 환급은 무손실
        (uint256 agentB1,,, uint256 agentSlash) = bv.agents(aid);
        if (byVerdict && fin < 50) {
            assert(agentB1 == agentB0 - 1e18 && agentSlash == 1e18);
        } else {
            assert(agentB1 == agentB0 && agentSlash == 0);
        }
        // 정산 완결성: 어떤 경로든 주장은 정확히 한 번 정산된다
        assert(bv.claimSettled(H));
    }

    /// P4: 타임아웃 판정자 무손실 + 에이전트 사양 일치 — 0~2표 어떤 조합이 와도
    ///     시한 해소는 판정자 담보를 절대 깎지 않는다. 에이전트는 "일치 2표"가
    ///     있을 때만 그 평결(score<50이면 슬래시)을 적용받고, 그 외엔 무손실.
    function check_P4_timeout_judges_lossless(bool v1, bool v2, uint8 s1, uint8 s2) public {
        address[] memory p = panel.casePanel(H);
        if (v1) _vote(p[0], s1);
        if (v2) _vote(p[1], s2);
        vm.warp(block.timestamp + VOTE_T + 1);
        panel.resolveTimeout(H);
        for (uint256 i = 0; i < 9; i++) assert(_jb(js[i]) == ENTRY); // 판정자 무손실
        (uint256 b,,, uint256 slash) = bv.agents(aid);
        bool twoMatch = v1 && v2 && s1 == s2; // 일치 2표 = 정식 평결
        if (twoMatch && s1 < 50) {
            assert(b == 10e18 - 1e18 && slash == 1e18);
        } else {
            assert(b == 10e18 && slash == 0); // 분쟁 이월·판정불능 → 무손실
        }
    }

    // ═══ PL1~PL3 (Exp30) ═══

    /// PL1a: ∀ s — 투표는 정확히 s ≤ 100 일 때만 착지한다(레지스트리 'range' 웨지 원천 차단).
    function check_PL1a_vote_lands_iff_score_le_100(uint8 s) public {
        address[] memory p = panel.casePanel(H);
        vm.prank(p[0]);
        (bool ok,) = address(panel).call(abi.encodeWithSelector(
            panel.voteVerdict.selector, H, s, "t", bytes32(0)));
        assert(ok == (s <= 100));
    }

    /// PL1b: ∀ s1,s2 ≤ 100 — 초심 2표(일치든 분쟁이든) 뒤 시한 해소는 되돌리지 않는다.
    ///       (스크래치 v0.2.1 반례 s1=s2=0x80 이 여기서 닫힌다.)
    function check_PL1b_timeout_after_two_votes_never_reverts(uint8 s1, uint8 s2) public {
        vm.assume(s1 <= 100 && s2 <= 100);
        address[] memory p = panel.casePanel(H);
        _vote(p[0], s1);
        _vote(p[1], s2);
        vm.warp(block.timestamp + VOTE_T + 1);
        (bool ok,) = address(panel).call(abi.encodeWithSelector(panel.resolveTimeout.selector, H));
        assert(ok);
        bool settled = bv.claimSettled(H);
        bool escalated = _phase(H) == BondedJudgePanelV3.Phase.ExpandedCommit;
        assert(settled != escalated);
        assert((s1 == s2) == settled); // 일치 → 정산, 분쟁 → 확대 이월
    }

    /// PL2: ∀ dt ≥ voteTimeout — Committed ∧ 무추첨 시한 해소는 리셋이다:
    ///      phase′ = None ∧ opener 잔고 +F ∧ ¬engaged′ ∧ ¬claimSettled′ ∧ atRisk 불변.
    function check_PL2_commit_timeout_resets(uint64 dt) public {
        vm.assume(dt >= VOTE_T);
        vm.prank(wallet);
        bv.requestValidation(aid, "", H2);
        vm.prank(wallet);
        panel.openCase(H2);
        assert(bv.engaged(H2));
        uint256 w0 = token.balanceOf(wallet);
        (, uint256 r0,,) = bv.agents(aid);
        vm.warp(block.timestamp + dt);
        panel.resolveTimeout(H2);
        assert(_phase(H2) == BondedJudgePanelV3.Phase.None);
        assert(token.balanceOf(wallet) == w0 + FEE);
        assert(!bv.engaged(H2));
        assert(!bv.claimSettled(H2));
        (, uint256 r1,,) = bv.agents(aid);
        assert(r1 == r0);
        for (uint256 i = 0; i < 9; i++) {
            (, uint256 atRisk,,) = _jstate(js[i]);
            assert(!panel.onCase(H2, js[i]));
            assert(atRisk == (panel.onCase(H, js[i]) ? BOND : 0)); // H 의 패널만 잠김
        }
    }

    /// PL3a: 예약 태그 거부 — 판정자는 소멸·시한환급 태그를 사칭할 수 없다.
    function check_PL3a_reserved_tags_revert(uint8 s) public {
        vm.assume(s <= 100);
        address[] memory p = panel.casePanel(H);
        vm.prank(p[0]);
        (bool ok1,) = address(panel).call(abi.encodeWithSelector(
            panel.voteVerdict.selector, H, s, "unchallenged", bytes32(0)));
        assert(!ok1);
        vm.prank(p[0]);
        (bool ok2,) = address(panel).call(abi.encodeWithSelector(
            panel.voteVerdict.selector, H, s, "disputed", bytes32(0)));
        assert(!ok2);
        assert(!panel.hasVoted(H, p[0]));
    }

    /// PL3b: 판정자 보존 — ∀ dt ≥ W, ∀ caller: 미개설 주장의 소멸은 풀의 어떤 판정자 상태도
    ///       (bondedAmt, atRisk, settledCount, slashedTotal, balance) 바꾸지 않는다.
    function check_PL3b_lapse_preserves_judges(uint64 dt, address caller) public {
        vm.assume(dt >= W);
        vm.prank(wallet);
        bv.requestValidation(aid, "", H3);
        uint256[9] memory b0; uint256[9] memory r0; uint256[9] memory c0; uint256[9] memory s0; uint256[9] memory t0;
        for (uint256 i = 0; i < 9; i++) {
            (b0[i], r0[i], c0[i], s0[i]) = _jstate(js[i]);
            t0[i] = token.balanceOf(js[i]);
        }
        uint256 panelBal0 = token.balanceOf(address(panel));
        vm.warp(block.timestamp + dt);
        vm.prank(caller);
        bv.settleUnchallenged(H3);
        assert(bv.claimSettled(H3));
        for (uint256 i = 0; i < 9; i++) {
            (uint256 b1, uint256 r1, uint256 c1, uint256 s1) = _jstate(js[i]);
            assert(b1 == b0[i] && r1 == r0[i] && c1 == c0[i] && s1 == s0[i]);
            assert(token.balanceOf(js[i]) == t0[i]);
        }
        assert(token.balanceOf(address(panel)) == panelBal0);
    }
}
