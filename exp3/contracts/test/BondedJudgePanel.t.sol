// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidator} from "../src/BondedValidator.sol";
import {BondedJudgePanel} from "../src/BondedJudgePanel.sol";

interface Vm {
    function prank(address) external;
    function startPrank(address) external;
    function stopPrank() external;
    function warp(uint256) external;
    function expectRevert(bytes calldata) external;
}

/// @notice v0.2 승격 테스트 — Exp8 통과 설계의 온체인 불변식:
///         무보상금(다수파 수익 = 정액 수수료뿐), 소수파 몰수(소각+배상),
///         판정자 담보 게이트, 신참 할증, 상급심 부재(타임아웃만이 백스톱).
contract BondedJudgePanelTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    IdentityRegistry idReg;
    ValidationRegistry valReg;
    BondedValidator bv;
    BondedJudgePanel panel;
    address wallet = address(uint160(uint256(keccak256("bjp.wallet"))));
    address[] js;
    uint256 aid;
    uint256 constant BOND = 10e18;   // perCaseBond
    uint256 constant FEE = 8e18;     // judgeFee (8인까지 균등 분배 시 1e18씩)
    uint256 constant VOTE_T = 100;
    uint256 constant DISP_T = 200;
    uint256 constant ENTRY = 15e18;  // 신참 1.5×
    address constant BURN = 0x000000000000000000000000000000000000dEaD;

    function setUp() public {
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        address predicted = _predictNext(address(this), 5);
        bv = new BondedValidator(address(token), address(idReg), address(valReg),
                                 predicted, 1e18, 60);
        panel = new BondedJudgePanel(address(bv), BOND, FEE, VOTE_T, DISP_T, 3);
        require(address(panel) == predicted, "prediction failed");

        token.mint(wallet, 100e18);
        vm.startPrank(wallet);
        aid = idReg.register("agent://speaker");
        token.approve(address(bv), type(uint256).max);
        token.approve(address(panel), type(uint256).max);
        bv.stake(aid, 10e18);
        vm.stopPrank();

        for (uint256 i = 0; i < 9; i++) {
            address j = address(uint160(uint256(keccak256(abi.encodePacked("bjp.judge", i)))));
            js.push(j);
            token.mint(j, 20e18);
            vm.startPrank(j);
            uint256 jid = idReg.register("agent://judge");
            token.approve(address(panel), type(uint256).max);
            panel.registerJudge(jid, ENTRY);
            vm.stopPrank();
        }
    }

    function _predictNext(address deployer, uint256 nonce) internal pure returns (address) {
        return address(uint160(uint256(keccak256(abi.encodePacked(
            bytes1(0xd6), bytes1(0x94), deployer, bytes1(uint8(nonce)))))));
    }

    function _claim(bytes32 h) internal {
        vm.prank(wallet);
        bv.requestValidation(aid, "", h);
    }

    function _open(bytes32 h) internal {
        _claim(h);
        vm.prank(wallet);
        panel.openCase(h);
    }

    function _vote(address j, bytes32 h, uint8 s, string memory tag) internal {
        vm.prank(j);
        panel.voteVerdict(h, s, tag, bytes32(0));
    }

    function _judgeBonded(address j) internal view returns (uint256 b, uint256 atRisk) {
        (, , b, atRisk, , , ) = panel.judges(j);
    }

    function _agentBonded() internal view returns (uint256 b, uint256 slashed) {
        (b,,, slashed) = bv.agents(aid);
    }

    // ─── 풀·등록 ─────────────────────────────────────────────────

    function test_register_requires_entry_bond_and_identity() public {
        address x = address(uint160(uint256(keccak256("bjp.x"))));
        token.mint(x, 20e18);
        vm.startPrank(x);
        uint256 xid = idReg.register("agent://x");
        token.approve(address(panel), type(uint256).max);
        vm.expectRevert("deposit below entry bond");
        panel.registerJudge(xid, ENTRY - 1); // 신참 1.5× 미달
        vm.expectRevert("not agent wallet");
        panel.registerJudge(aid, ENTRY);     // 남의 신원
        panel.registerJudge(xid, ENTRY);
        vm.stopPrank();
        require(panel.poolSize() == 10, "pool");
    }

    function test_veteran_threshold_zero_lowers_entry() public {
        BondedJudgePanel p2 = new BondedJudgePanel(address(bv), BOND, FEE, VOTE_T, DISP_T, 0);
        require(p2.requiredFreeBond(js[0]) == BOND, "veteran entry should be 1x");
        require(panel.requiredFreeBond(js[0]) == ENTRY, "newcomer entry should be 1.5x");
    }

    // ─── 개설·초심 ───────────────────────────────────────────────

    function test_open_draws_three_and_locks_bonds() public {
        bytes32 h = bytes32(uint256(1));
        _open(h);
        address[] memory p = panel.casePanel(h);
        require(p.length == 3, "panel size");
        for (uint256 i = 0; i < 3; i++) {
            (, uint256 atRisk) = _judgeBonded(p[i]);
            require(atRisk == BOND, "bond not locked");
            require(panel.onCase(h, p[i]), "not marked");
        }
        require(token.balanceOf(address(panel)) == 9 * ENTRY + FEE, "fee not escrowed");
    }

    function test_open_requires_existing_unsettled_claim() public {
        vm.prank(wallet);
        vm.expectRevert("no claim");
        panel.openCase(bytes32(uint256(99)));
    }

    function test_unanimous_settles_fee_split_no_agent_slash() public {
        bytes32 h = bytes32(uint256(2));
        _open(h);
        address[] memory p = panel.casePanel(h);
        uint256 before0 = token.balanceOf(p[0]);
        _vote(p[0], h, 100, "correct");
        _vote(p[1], h, 100, "correct");
        _vote(p[2], h, 100, "correct");
        (uint256 ab, uint256 aslash) = _agentBonded();
        require(ab == 10e18 && aslash == 0, "agent harmed");
        require(bv.claimSettled(h), "claim not settled");
        // 결과 무관 정액: 각자 fee/3, 담보 원상 복귀
        require(token.balanceOf(p[0]) == before0 + FEE / 3, "fee share wrong");
        (uint256 jb, uint256 atRisk) = _judgeBonded(p[0]);
        require(jb == ENTRY && atRisk == 0, "judge bond touched");
        (,,,,, uint256 sc,) = panel.judges(p[0]);
        require(sc == 1, "settledCount");
    }

    function test_non_panelist_and_double_vote_revert() public {
        bytes32 h = bytes32(uint256(3));
        _open(h);
        address[] memory p = panel.casePanel(h);
        address outsider;
        for (uint256 i = 0; i < 9; i++) {
            if (js[i] != p[0] && js[i] != p[1] && js[i] != p[2]) { outsider = js[i]; break; }
        }
        vm.prank(outsider);
        vm.expectRevert("not on case");
        panel.voteVerdict(h, 100, "correct", bytes32(0));
        _vote(p[0], h, 100, "correct");
        vm.prank(p[0]);
        vm.expectRevert("double vote");
        panel.voteVerdict(h, 100, "correct", bytes32(0));
    }

    // ─── 확대재판·몰수·무보상금 ──────────────────────────────────

    function _disputeAndExpand(bytes32 h) internal returns (address[] memory p, address[] memory e) {
        _open(h);
        p = panel.casePanel(h);
        _vote(p[0], h, 100, "correct");
        _vote(p[1], h, 100, "correct");
        _vote(p[2], h, 0, "wrong"); // 반대표 → 3표 도달 시 확대재판
        e = panel.caseExpanded(h);
        require(e.length == 5, "expanded size");
        for (uint256 i = 0; i < 5; i++) {
            for (uint256 k = 0; k < 3; k++) require(e[i] != p[k], "overlap");
        }
    }

    function test_expanded_majority_slashes_minority_burn_and_compensate() public {
        bytes32 h = bytes32(uint256(4));
        (address[] memory p, address[] memory e) = _disputeAndExpand(h);
        uint256 walletBefore = token.balanceOf(wallet);
        uint256 burnBefore = token.balanceOf(BURN);
        uint256 majBefore = token.balanceOf(e[0]);
        // 확대 5인: 4 correct vs 1 wrong → 최종 correct@100
        _vote(e[0], h, 100, "correct");
        _vote(e[1], h, 100, "correct");
        _vote(e[2], h, 0, "wrong");
        _vote(e[3], h, 100, "correct");
        _vote(e[4], h, 100, "correct");
        require(bv.claimSettled(h), "not settled");
        // 소수파 = 초심 p[2] + 확대 e[2] → 각 BOND 몰수: 절반 소각, 절반 에이전트 배상
        (uint256 jb2,) = _judgeBonded(p[2]);
        (uint256 je2,) = _judgeBonded(e[2]);
        require(jb2 == ENTRY - BOND && je2 == ENTRY - BOND, "minority not slashed");
        require(token.balanceOf(BURN) == burnBefore + BOND, "burn half wrong");
        require(token.balanceOf(wallet) == walletBefore + BOND, "compensation wrong");
        // 무보상금: 다수파 수익 = 수수료 균등분(FEE/8)뿐 — 몰수분 배당 없음
        require(token.balanceOf(e[0]) == majBefore + FEE / 8, "winner got a bounty");
        // 에이전트: 최종 100 >= 50 → 무슬래시
        (uint256 ab, uint256 aslash) = _agentBonded();
        require(ab == 10e18 && aslash == 0, "agent wrongly slashed");
    }

    function test_expanded_majority_wrong_slashes_agent_too() public {
        bytes32 h = bytes32(uint256(5));
        (address[] memory p, address[] memory e) = _disputeAndExpand(h);
        // 확대 5인 전원 wrong@0 → 최종 wrong: 초심 correct 2인이 소수파
        for (uint256 i = 0; i < 5; i++) _vote(e[i], h, 0, "wrong");
        (uint256 jb0,) = _judgeBonded(p[0]);
        (uint256 jb1,) = _judgeBonded(p[1]);
        require(jb0 == ENTRY - BOND && jb1 == ENTRY - BOND, "initial majority not slashed");
        (uint256 ab, uint256 aslash) = _agentBonded();
        require(ab == 9e18 && aslash == 1e18, "agent slash missing"); // score 0 < 50
    }

    function test_expanded_split_no_majority_refunds_without_slash() public {
        bytes32 h = bytes32(uint256(6));
        (, address[] memory e) = _disputeAndExpand(h);
        // 2/2/1 분할 — 과반 부재
        _vote(e[0], h, 100, "correct");
        _vote(e[1], h, 100, "correct");
        _vote(e[2], h, 0, "wrong");
        _vote(e[3], h, 0, "wrong");
        _vote(e[4], h, 50, "unclear");
        require(bv.claimSettled(h), "not settled");
        (uint256 ab, uint256 aslash) = _agentBonded();
        require(ab == 10e18 && aslash == 0, "refund not neutral");
        for (uint256 i = 0; i < 5; i++) {
            (uint256 jb, uint256 atRisk) = _judgeBonded(e[i]);
            require(jb == ENTRY && atRisk == 0, "judge slashed on split");
        }
    }

    function test_slashed_newcomer_loses_draw_eligibility() public {
        bytes32 h = bytes32(uint256(7));
        (address[] memory p,) = _disputeAndExpand(h);
        address[] memory e = panel.caseExpanded(h);
        for (uint256 i = 0; i < 5; i++) _vote(e[i], h, 100, "correct");
        // p[2] 몰수됨 → 자유담보 5e18 < 신참 요구 15e18 → 다음 추첨 배제
        (uint256 jb,) = _judgeBonded(p[2]);
        require(jb == ENTRY - BOND, "precondition");
        bytes32 h2 = bytes32(uint256(8));
        _open(h2);
        address[] memory p2 = panel.casePanel(h2);
        for (uint256 i = 0; i < 3; i++) require(p2[i] != p[2], "slashed judge drawn");
    }

    // ─── 타임아웃 백스톱 (상급심 없음) ───────────────────────────

    function test_initial_timeout_two_matching_settle() public {
        bytes32 h = bytes32(uint256(9));
        _open(h);
        address[] memory p = panel.casePanel(h);
        _vote(p[0], h, 100, "correct");
        _vote(p[1], h, 100, "correct"); // p[2] 불참
        vm.expectRevert("vote window open");
        panel.resolveTimeout(h);
        vm.warp(block.timestamp + VOTE_T + 1);
        panel.resolveTimeout(h);
        require(bv.claimSettled(h), "not settled");
        (uint256 ab,) = _agentBonded();
        require(ab == 10e18, "agent harmed");
    }

    function test_initial_timeout_single_vote_refunds() public {
        bytes32 h = bytes32(uint256(10));
        _open(h);
        address[] memory p = panel.casePanel(h);
        _vote(p[0], h, 100, "correct");
        vm.warp(block.timestamp + VOTE_T + 1);
        panel.resolveTimeout(h);
        (uint256 ab, uint256 aslash) = _agentBonded();
        require(ab == 10e18 && aslash == 0, "refund not neutral");
    }

    function test_initial_timeout_disputed_escalates() public {
        bytes32 h = bytes32(uint256(11));
        _open(h);
        address[] memory p = panel.casePanel(h);
        _vote(p[0], h, 100, "correct");
        _vote(p[1], h, 0, "wrong"); // 분쟁, p[2] 불참
        vm.warp(block.timestamp + VOTE_T + 1);
        panel.resolveTimeout(h);
        (BondedJudgePanel.Phase phase,,,) = panel.caseStatus(h);
        require(phase == BondedJudgePanel.Phase.Expanded, "not escalated");
        require(panel.caseExpanded(h).length == 5, "expanded not drawn");
    }

    function test_expanded_timeout_refunds_without_slash() public {
        bytes32 h = bytes32(uint256(12));
        (, address[] memory e) = _disputeAndExpand(h);
        _vote(e[0], h, 100, "correct"); // 5표 미달 방치
        vm.expectRevert("dispute window open");
        panel.resolveTimeout(h);
        vm.warp(block.timestamp + DISP_T + 1);
        panel.resolveTimeout(h);
        require(bv.claimSettled(h), "not settled");
        (uint256 ab, uint256 aslash) = _agentBonded();
        require(ab == 10e18 && aslash == 0, "refund not neutral");
        for (uint256 i = 0; i < 5; i++) {
            (uint256 jb, uint256 atRisk) = _judgeBonded(e[i]);
            require(jb == ENTRY && atRisk == 0, "judge slashed on timeout");
        }
    }

    // ─── 인출 ────────────────────────────────────────────────────

    function test_withdraw_delayed_and_blocked_while_at_risk() public {
        bytes32 h = bytes32(uint256(13));
        _open(h);
        address[] memory p = panel.casePanel(h);
        vm.startPrank(p[0]);
        panel.requestUnbond();
        vm.expectRevert("locked");
        panel.withdraw();
        vm.stopPrank();
        vm.warp(block.timestamp + DISP_T + 1);
        vm.prank(p[0]);
        vm.expectRevert("cases pending"); // 사건 계류 중 인출 불가
        panel.withdraw();
        _vote(p[0], h, 100, "correct");
        _vote(p[1], h, 100, "correct");
        _vote(p[2], h, 100, "correct");
        uint256 before = token.balanceOf(p[0]);
        vm.prank(p[0]);
        panel.withdraw();
        require(token.balanceOf(p[0]) == before + ENTRY, "withdraw amount");
    }
}
