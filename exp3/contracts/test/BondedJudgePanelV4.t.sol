// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidatorV4} from "../src/BondedValidatorV4.sol";
import {BondedJudgePanelV4} from "../src/BondedJudgePanelV4.sol";

interface Vm {
    function prank(address) external;
    function startPrank(address) external;
    function stopPrank() external;
    function warp(uint256) external;
    function roll(uint256) external;
    function expectRevert(bytes calldata) external;
}

/// @notice RT-0031 수리 검증: 투표 자체의 커밋-리빌.
///         핵심 불변식(신규): 전원이 커밋하기 전엔 어떤 리빌도 통과하지 못한다 —
///         즉 판정자가 남의 표를 본 뒤에 자기 표를 정할 방법이 없다.
///         회귀(기존): 만장일치 정산·분쟁 에스컬레이션·수수료 분배·판정자 슬래시는
///         v0.3과 동일하게 동작해야 한다(오직 취합 시점만 커밋→리빌로 이동).
contract BondedJudgePanelV4Test {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    IdentityRegistry idReg;
    ValidationRegistry valReg;
    BondedValidatorV4 bv;
    BondedJudgePanelV4 panel;
    address wallet = address(uint160(uint256(keccak256("bjp4.wallet"))));
    address[] js;
    uint256 aid;
    uint256 constant BOND = 10e18;
    uint256 constant FEE = 9e18;
    uint256 constant VOTE_T = 100;
    uint256 constant DISP_T = 200;
    uint256 constant ENTRY = 15e18;
    uint256 constant W = 86400;

    function setUp() public {
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        address predicted = _predictNext(address(this), 5);
        bv = new BondedValidatorV4(address(token), address(idReg), address(valReg),
                                   predicted, 1e18, 60, W);
        panel = new BondedJudgePanelV4(address(bv), BOND, FEE, VOTE_T, DISP_T, 3);
        require(address(panel) == predicted, "prediction failed");

        token.mint(wallet, 100e18);
        vm.startPrank(wallet);
        aid = idReg.register("agent://speaker");
        token.approve(address(bv), type(uint256).max);
        token.approve(address(panel), type(uint256).max);
        bv.stake(aid, 10e18);
        vm.stopPrank();

        for (uint256 i = 0; i < 9; i++) {
            address j = address(uint160(uint256(keccak256(abi.encodePacked("bjp4.judge", i)))));
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

    function _drawn(bytes32 h) internal returns (address[] memory p) {
        vm.prank(wallet);
        bv.requestValidation(aid, "", h);
        vm.prank(wallet);
        panel.openCase(h);
        vm.roll(block.number + 1);
        panel.drawPanel(h);
        p = panel.casePanel(h);
    }

    function _commitHash(uint8 score, string memory tag, bytes32 salt) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(score, tag, bytes32(0), salt));
    }

    // ── 신규 불변식: 전원 커밋 전엔 리빌 불가 ──────────────────────

    function test_reveal_blocked_until_all_committed() public {
        bytes32 h = keccak256("case-A");
        address[] memory p = _drawn(h);

        vm.prank(p[0]);
        panel.commitVerdict(h, _commitHash(100, "correct", bytes32(uint256(1))));

        // 1/3만 커밋 — 아직 Phase.Initial(커밋 단계), 리빌 시도는 revert 되어야 함
        vm.prank(p[0]);
        vm.expectRevert(bytes("not reveal phase"));
        panel.revealVerdict(h, 100, "correct", bytes32(0), bytes32(uint256(1)));

        vm.prank(p[1]);
        panel.commitVerdict(h, _commitHash(100, "correct", bytes32(uint256(2))));
        // 2/3만 커밋 — 여전히 리빌 불가
        vm.prank(p[1]);
        vm.expectRevert(bytes("not reveal phase"));
        panel.revealVerdict(h, 100, "correct", bytes32(0), bytes32(uint256(2)));

        vm.prank(p[2]);
        panel.commitVerdict(h, _commitHash(100, "correct", bytes32(uint256(3))));
        // 전원 커밋 완료 — 이제서야 리빌 가능해야 함(별도 revert 없이 통과)
        vm.prank(p[0]);
        panel.revealVerdict(h, 100, "correct", bytes32(0), bytes32(uint256(1)));
    }

    function test_commit_mismatch_reverts() public {
        bytes32 h = keccak256("case-B");
        address[] memory p = _drawn(h);
        for (uint256 i = 0; i < 3; i++) {
            vm.prank(p[i]);
            panel.commitVerdict(h, _commitHash(100, "correct", bytes32(uint256(i + 1))));
        }
        // 커밋한 값과 다른 값으로 리빌 시도 -> revert
        vm.prank(p[0]);
        vm.expectRevert(bytes("commit mismatch"));
        panel.revealVerdict(h, 0, "wrong", bytes32(0), bytes32(uint256(1)));
    }

    function test_double_commit_reverts() public {
        bytes32 h = keccak256("case-C");
        address[] memory p = _drawn(h);
        vm.prank(p[0]);
        panel.commitVerdict(h, _commitHash(100, "correct", bytes32(uint256(1))));
        vm.prank(p[0]);
        vm.expectRevert(bytes("already committed"));
        panel.commitVerdict(h, _commitHash(0, "wrong", bytes32(uint256(9))));
    }

    // ── 회귀: 만장일치 정산이 v0.3과 동일하게 동작 ──────────────────

    function test_regression_unanimous_correct_not_slashed() public {
        bytes32 h = keccak256("case-D");
        address[] memory p = _drawn(h);
        bytes32[3] memory salts = [bytes32(uint256(11)), bytes32(uint256(12)), bytes32(uint256(13))];
        for (uint256 i = 0; i < 3; i++) {
            vm.prank(p[i]);
            panel.commitVerdict(h, _commitHash(100, "correct", salts[i]));
        }
        for (uint256 i = 0; i < 3; i++) {
            vm.prank(p[i]);
            panel.revealVerdict(h, 100, "correct", bytes32(0), salts[i]);
        }
        require(bv.claimSettled(h), "not settled");
        (uint256 bonded,,, uint256 slashed) = bv.agents(aid);
        require(bonded == 10e18 && slashed == 0, "agent should not be slashed on correct verdict");
    }

    function test_regression_disputed_escalates() public {
        bytes32 h = keccak256("case-E");
        address[] memory p = _drawn(h);
        // 판정자 0,1 은 correct, 판정자 2 는 wrong -> 만장일치 아님 -> 확대재판
        bytes32[3] memory salts = [bytes32(uint256(21)), bytes32(uint256(22)), bytes32(uint256(23))];
        vm.prank(p[0]); panel.commitVerdict(h, _commitHash(100, "correct", salts[0]));
        vm.prank(p[1]); panel.commitVerdict(h, _commitHash(100, "correct", salts[1]));
        vm.prank(p[2]); panel.commitVerdict(h, _commitHash(0, "wrong", salts[2]));

        vm.prank(p[0]); panel.revealVerdict(h, 100, "correct", bytes32(0), salts[0]);
        vm.prank(p[1]); panel.revealVerdict(h, 100, "correct", bytes32(0), salts[1]);
        vm.prank(p[2]); panel.revealVerdict(h, 0, "wrong", bytes32(0), salts[2]);

        (BondedJudgePanelV4.Phase phase, bool disputed,,,) = panel.caseStatus(h);
        require(disputed, "should be disputed");
        require(phase == BondedJudgePanelV4.Phase.ExpandedCommit, "should escalate to expanded commit");
        require(!bv.claimSettled(h), "should not settle yet - escalated");
    }

    function test_vote_commit_timeout_refunds_no_slash() public {
        bytes32 h = keccak256("case-F");
        address[] memory p = _drawn(h);
        vm.prank(p[0]);
        panel.commitVerdict(h, _commitHash(100, "correct", bytes32(uint256(1))));
        // 나머지 둘은 끝까지 커밋 안 함 -> voteTimeout 경과 후 무손실 환급
        vm.warp(block.timestamp + VOTE_T + 1);
        panel.resolveTimeout(h);
        require(bv.claimSettled(h), "should settle via timeout refund");
        (uint256 bonded,,, uint256 slashed) = bv.agents(aid);
        require(bonded == 10e18 && slashed == 0, "no slash on commit-stall refund");
    }
}
