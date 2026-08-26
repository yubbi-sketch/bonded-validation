// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidator} from "../src/BondedValidator.sol";
import {BondedJudgePanelV2} from "../src/BondedJudgePanelV2.sol";

interface Vm {
    function prank(address) external;
    function startPrank(address) external;
    function stopPrank() external;
    function warp(uint256) external;
    function roll(uint256) external;
    function expectRevert(bytes calldata) external;
}

/// @notice v0.2.1(Exp9) 테스트 — 커밋-리빌 추첨 불변식:
///         커밋 블록에선 추첨 불가(시드 미탄생), 256블록 소실 시 재커밋,
///         커밋 방치 사건도 시한 후 무손실 환급(수수료는 개설자 반환).
///         v0.2의 경제 불변식(무보상금·소수파 몰수·분할 무몰수)도 재검증.
contract BondedJudgePanelV2Test {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    IdentityRegistry idReg;
    ValidationRegistry valReg;
    BondedValidator bv;
    BondedJudgePanelV2 panel;
    address wallet = address(uint160(uint256(keccak256("bjp2.wallet"))));
    address[] js;
    uint256 aid;
    uint256 constant BOND = 10e18;
    uint256 constant FEE = 8e18;
    uint256 constant VOTE_T = 100;
    uint256 constant DISP_T = 200;
    uint256 constant ENTRY = 15e18;
    address constant BURN = 0x000000000000000000000000000000000000dEaD;

    function setUp() public {
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        address predicted = _predictNext(address(this), 5);
        bv = new BondedValidator(address(token), address(idReg), address(valReg),
                                 predicted, 1e18, 60);
        panel = new BondedJudgePanelV2(address(bv), BOND, FEE, VOTE_T, DISP_T, 3);
        require(address(panel) == predicted, "prediction failed");

        token.mint(wallet, 100e18);
        vm.startPrank(wallet);
        aid = idReg.register("agent://speaker");
        token.approve(address(bv), type(uint256).max);
        token.approve(address(panel), type(uint256).max);
        bv.stake(aid, 10e18);
        vm.stopPrank();

        for (uint256 i = 0; i < 9; i++) {
            address j = address(uint160(uint256(keccak256(abi.encodePacked("bjp2.judge", i)))));
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

    function _commit(bytes32 h) internal {
        _claim(h);
        vm.prank(wallet);
        panel.openCase(h);
    }

    function _openDrawn(bytes32 h) internal returns (address[] memory p) {
        _commit(h);
        vm.roll(block.number + 1);
        panel.drawPanel(h);
        p = panel.casePanel(h);
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

    // ─── 커밋-리빌 ───────────────────────────────────────────────

    function test_draw_blocked_in_commit_block() public {
        bytes32 h = bytes32(uint256(1));
        _commit(h);
        vm.expectRevert("seed not born"); // 같은 블록 — 그라인딩 봉쇄의 핵심
        panel.drawPanel(h);
        vm.roll(block.number + 1);
        panel.drawPanel(h);
        require(panel.casePanel(h).length == 3, "panel size");
    }

    function test_seed_expiry_forces_recommit() public {
        bytes32 h = bytes32(uint256(2));
        _commit(h);
        vm.expectRevert("seed still available");
        panel.recommit(h);
        vm.roll(block.number + 257);
        vm.expectRevert("seed expired: recommit");
        panel.drawPanel(h);
        panel.recommit(h);
        vm.roll(block.number + 1);
        panel.drawPanel(h);
        require(panel.casePanel(h).length == 3, "panel after recommit");
    }

    function test_committed_timeout_refunds_fee_to_opener() public {
        bytes32 h = bytes32(uint256(3));
        _commit(h); // 아무도 리빌하지 않고 방치
        uint256 openerBefore = token.balanceOf(wallet);
        vm.expectRevert("commit window open");
        panel.resolveTimeout(h);
        vm.warp(block.timestamp + VOTE_T + 1);
        panel.resolveTimeout(h);
        require(bv.claimSettled(h), "claim not settled");
        require(token.balanceOf(wallet) == openerBefore + FEE, "fee not returned");
        (uint256 ab, uint256 aslash) = _agentBonded();
        require(ab == 10e18 && aslash == 0, "refund not neutral");
    }

    function test_vote_blocked_before_reveal() public {
        bytes32 h = bytes32(uint256(4));
        _commit(h);
        vm.prank(js[0]);
        vm.expectRevert("no open case"); // Committed 단계 — 패널이 없다
        panel.voteVerdict(h, 100, "correct", bytes32(0));
    }

    // ─── v0.2 경제 불변식 재검증 ─────────────────────────────────

    function test_unanimous_settles_fee_split() public {
        bytes32 h = bytes32(uint256(5));
        address[] memory p = _openDrawn(h);
        uint256 before0 = token.balanceOf(p[0]);
        _vote(p[0], h, 100, "correct");
        _vote(p[1], h, 100, "correct");
        _vote(p[2], h, 100, "correct");
        require(bv.claimSettled(h), "not settled");
        require(token.balanceOf(p[0]) == before0 + FEE / 3, "fee share wrong");
        (uint256 jb, uint256 atRisk) = _judgeBonded(p[0]);
        require(jb == ENTRY && atRisk == 0, "judge bond touched");
    }

    function _disputeAndExpand(bytes32 h) internal returns (address[] memory p, address[] memory e) {
        p = _openDrawn(h);
        _vote(p[0], h, 100, "correct");
        _vote(p[1], h, 100, "correct");
        _vote(p[2], h, 0, "wrong"); // → ExpandedCommit
        vm.expectRevert("seed not born"); // 확대 추첨도 커밋-리빌
        panel.drawExpanded(h);
        vm.roll(block.number + 1);
        panel.drawExpanded(h);
        e = panel.caseExpanded(h);
        require(e.length == 5, "expanded size");
        for (uint256 i = 0; i < 5; i++) {
            for (uint256 k = 0; k < 3; k++) require(e[i] != p[k], "overlap");
        }
    }

    function test_expanded_majority_slashes_minority_no_bounty() public {
        bytes32 h = bytes32(uint256(6));
        (address[] memory p, address[] memory e) = _disputeAndExpand(h);
        uint256 walletBefore = token.balanceOf(wallet);
        uint256 burnBefore = token.balanceOf(BURN);
        uint256 majBefore = token.balanceOf(e[0]);
        _vote(e[0], h, 100, "correct");
        _vote(e[1], h, 100, "correct");
        _vote(e[2], h, 0, "wrong");
        _vote(e[3], h, 100, "correct");
        _vote(e[4], h, 100, "correct");
        require(bv.claimSettled(h), "not settled");
        (uint256 jb2,) = _judgeBonded(p[2]);
        (uint256 je2,) = _judgeBonded(e[2]);
        require(jb2 == ENTRY - BOND && je2 == ENTRY - BOND, "minority not slashed");
        require(token.balanceOf(BURN) == burnBefore + BOND, "burn half wrong");
        require(token.balanceOf(wallet) == walletBefore + BOND, "compensation wrong");
        require(token.balanceOf(e[0]) == majBefore + FEE / 8, "winner got a bounty");
        (uint256 ab, uint256 aslash) = _agentBonded();
        require(ab == 10e18 && aslash == 0, "agent wrongly slashed");
    }

    function test_expanded_split_refunds_without_slash() public {
        bytes32 h = bytes32(uint256(7));
        (, address[] memory e) = _disputeAndExpand(h);
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

    function test_expanded_commit_timeout_refunds() public {
        bytes32 h = bytes32(uint256(8));
        address[] memory p = _openDrawn(h);
        _vote(p[0], h, 100, "correct");
        _vote(p[1], h, 100, "correct");
        _vote(p[2], h, 0, "wrong"); // ExpandedCommit — 아무도 리빌 안 함
        vm.expectRevert("dispute window open");
        panel.resolveTimeout(h);
        vm.warp(block.timestamp + DISP_T + 1);
        panel.resolveTimeout(h);
        require(bv.claimSettled(h), "not settled");
        (uint256 ab, uint256 aslash) = _agentBonded();
        require(ab == 10e18 && aslash == 0, "refund not neutral");
        for (uint256 i = 0; i < 3; i++) {
            (uint256 jb, uint256 atRisk) = _judgeBonded(p[i]);
            require(jb == ENTRY && atRisk == 0, "judge harmed on commit timeout");
        }
    }

    function test_initial_timeout_disputed_goes_to_expanded_commit() public {
        bytes32 h = bytes32(uint256(9));
        address[] memory p = _openDrawn(h);
        _vote(p[0], h, 100, "correct");
        _vote(p[1], h, 0, "wrong"); // 분쟁, p[2] 불참
        vm.warp(block.timestamp + VOTE_T + 1);
        panel.resolveTimeout(h);
        (BondedJudgePanelV2.Phase phase,,,,) = panel.caseStatus(h);
        require(phase == BondedJudgePanelV2.Phase.ExpandedCommit, "not expanded commit");
        vm.roll(block.number + 1);
        panel.drawExpanded(h);
        require(panel.caseExpanded(h).length == 5, "expanded not drawn");
    }
}
