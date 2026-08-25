// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidator} from "../src/BondedValidator.sol";
import {JudgePanelV2} from "../src/JudgePanelV2.sol";
import {ReputationLens} from "../src/ReputationLens.sol";

interface Vm {
    function prank(address) external;
    function startPrank(address) external;
    function stopPrank() external;
    function warp(uint256) external;
    function expectRevert(bytes calldata) external;
}

contract JudgePanelV2Test {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    IdentityRegistry idReg;
    ValidationRegistry valReg;
    BondedValidator bv;
    JudgePanelV2 panel;
    ReputationLens lens;
    address wallet = address(uint160(uint256(keccak256("v2.wallet"))));
    address ja = address(uint160(uint256(keccak256("v2.ja"))));
    address jb = address(uint160(uint256(keccak256("v2.jb"))));
    address jc = address(uint160(uint256(keccak256("v2.jc"))));
    address arb = address(uint160(uint256(keccak256("v2.arbiter"))));
    uint256 aid;
    uint256 constant VOTE_T = 100;
    uint256 constant DISP_T = 200;

    function setUp() public {
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        address predicted = _predictNext(address(this), 5);
        bv = new BondedValidator(address(token), address(idReg), address(valReg),
                                 predicted, 1e18, 60);
        panel = new JudgePanelV2(address(bv), ja, jb, jc, arb, VOTE_T, DISP_T);
        require(address(panel) == predicted, "prediction failed");
        lens = new ReputationLens(address(valReg), address(bv));
        token.mint(wallet, 100e18);
        vm.startPrank(wallet);
        aid = idReg.register("agent://t");
        token.approve(address(bv), type(uint256).max);
        bv.stake(aid, 10e18);
        vm.stopPrank();
    }

    function _predictNext(address deployer, uint256 nonce) internal pure returns (address) {
        return address(uint160(uint256(keccak256(abi.encodePacked(
            bytes1(0xd6), bytes1(0x94), deployer, bytes1(uint8(nonce)))))));
    }

    function _claim(bytes32 h) internal {
        vm.prank(wallet);
        bv.requestValidation(aid, "", h);
    }

    function _vote(address j, bytes32 h, uint8 s, string memory tag) internal {
        vm.prank(j);
        panel.voteVerdict(h, s, tag, bytes32(0));
    }

    function _bonded() internal view returns (uint256 b) {
        (b,,,) = bv.agents(aid);
    }

    function test_dispute_timeout_refunds_neutral() public {
        bytes32 h = bytes32(uint256(1));
        _claim(h);
        _vote(ja, h, 100, "correct"); _vote(jc, h, 0, "wrong"); _vote(jb, h, 100, "correct");
        vm.expectRevert("dispute window open");
        panel.resolveTimeout(h);
        vm.warp(block.timestamp + DISP_T + 1);
        panel.resolveTimeout(h); // 누구든 호출 가능
        (uint256 b, uint256 atRisk,, uint256 slashed) = bv.agents(aid);
        require(b == 10e18 && atRisk == 0 && slashed == 0, "refund not neutral");
        // 평판 중립: disputed@50 걷어내면 이력 0건
        (uint256 score, uint64 answered) = lens.creditScore(aid);
        require(score == 0 && answered == 0, "lens counted disputed");
    }

    function test_laggard_two_votes_settle_and_record() public {
        bytes32 h = bytes32(uint256(2));
        _claim(h);
        _vote(ja, h, 100, "correct"); _vote(jb, h, 100, "correct"); // jc 불참
        vm.warp(block.timestamp + VOTE_T + 1);
        panel.resolveTimeout(h);
        (uint256 b, uint256 atRisk,,) = bv.agents(aid);
        require(b == 10e18 && atRisk == 0, "not settled");
        (uint256 score, uint64 answered) = lens.creditScore(aid);
        require(score == 100 && answered == 1, "score wrong");
    }

    function test_single_vote_timeout_refunds() public {
        bytes32 h = bytes32(uint256(3));
        _claim(h);
        _vote(ja, h, 0, "wrong"); // 1표뿐 — 판정 불능
        vm.warp(block.timestamp + VOTE_T + 1);
        panel.resolveTimeout(h);
        (uint256 b,,, uint256 slashed) = bv.agents(aid);
        require(b == 10e18 && slashed == 0, "1-vote should not slash");
    }

    function test_arbiter_resolves_dispute_with_slash() public {
        bytes32 h = bytes32(uint256(4));
        _claim(h);
        _vote(ja, h, 0, "wrong"); _vote(jb, h, 100, "correct"); _vote(jc, h, 0, "wrong");
        vm.prank(arb);
        panel.resolveByArbiter(h, 0, "wrong", bytes32(uint256(0xE0)));
        (uint256 b,,, uint256 slashed) = bv.agents(aid);
        require(b == 9e18 && slashed == 1e18, "arbiter slash failed");
    }

    function test_arbiter_only_on_disputes() public {
        bytes32 h = bytes32(uint256(5));
        _claim(h);
        _vote(ja, h, 100, "correct");
        vm.prank(arb);
        vm.expectRevert("not disputed");
        panel.resolveByArbiter(h, 0, "wrong", bytes32(0));
    }

    function test_non_arbiter_cannot_rule() public {
        bytes32 h = bytes32(uint256(6));
        _claim(h);
        _vote(ja, h, 0, "wrong"); _vote(jb, h, 100, "correct");
        vm.prank(ja);
        vm.expectRevert("not arbiter");
        panel.resolveByArbiter(h, 0, "wrong", bytes32(0));
    }

    function test_unanimous_still_settles_immediately() public {
        bytes32 h = bytes32(uint256(7));
        _claim(h);
        _vote(ja, h, 0, "wrong"); _vote(jb, h, 0, "wrong"); _vote(jc, h, 0, "wrong");
        (uint256 b,,, uint256 slashed) = bv.agents(aid);
        require(b == 9e18 && slashed == 1e18, "unanimity broken");
    }
}
