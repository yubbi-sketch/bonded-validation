// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {BondManager} from "../src/BondManager.sol";

interface Vm {
    function prank(address) external;
    function startPrank(address) external;
    function stopPrank() external;
    function warp(uint256) external;
    function expectRevert(bytes calldata) external;
}

contract BondManagerTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    BondManager bm;
    address agent = address(uint160(uint256(keccak256("exp3.agent"))));

    function setUp() public {
        token = new LabToken();
        bm = new BondManager(address(token), address(this), 1e18, 60);
        token.mint(agent, 100e18);
        vm.startPrank(agent);
        token.approve(address(bm), type(uint256).max);
        bm.stake(10e18);
        vm.stopPrank();
    }

    function test_claim_requires_bond() public {
        // 담보 없는 주소는 발화 불가
        vm.prank(address(0xBEEF));
        vm.expectRevert("insufficient free bond");
        bm.submitClaim(bytes32(uint256(1)));
    }

    function test_slash_reduces_bond() public {
        vm.prank(agent);
        uint256 id = bm.submitClaim(bytes32(uint256(1)));
        bm.settle(id, true, bytes32(uint256(0xE0)));
        (uint256 bonded,, ,uint256 slashedTotal) = bm.agents(agent);
        require(bonded == 9e18, "bond not reduced");
        require(slashedTotal == 1e18, "slash not recorded");
    }

    function test_uphold_keeps_bond() public {
        vm.prank(agent);
        uint256 id = bm.submitClaim(bytes32(uint256(2)));
        bm.settle(id, false, bytes32(0));
        (uint256 bonded, uint256 atRisk,,) = bm.agents(agent);
        require(bonded == 10e18 && atRisk == 0, "bond changed");
    }

    function test_only_judge_settles() public {
        vm.prank(agent);
        uint256 id = bm.submitClaim(bytes32(uint256(3)));
        vm.prank(agent);
        vm.expectRevert("not judge");
        bm.settle(id, true, bytes32(0));
    }

    function test_no_double_settle() public {
        vm.prank(agent);
        uint256 id = bm.submitClaim(bytes32(uint256(4)));
        bm.settle(id, true, bytes32(0));
        vm.expectRevert("settled");
        bm.settle(id, false, bytes32(0));
    }

    function test_withdraw_needs_delay_and_no_pending() public {
        // 미판정 주장 있으면 출금 불가 — 도망 방지
        vm.startPrank(agent);
        bm.submitClaim(bytes32(uint256(5)));
        bm.requestUnbond();
        vm.stopPrank();
        vm.warp(block.timestamp + 61);
        vm.prank(agent);
        vm.expectRevert("claims pending");
        bm.withdraw();
    }

    function test_withdraw_after_delay() public {
        vm.prank(agent);
        bm.requestUnbond();
        vm.warp(block.timestamp + 61);
        vm.prank(agent);
        bm.withdraw();
        require(token.balanceOf(agent) == 100e18, "not returned");
    }

    function test_free_bond_gates_parallel_claims() public {
        // 담보 10 → 동시 미판정 주장 최대 10건, 11번째는 거부
        vm.startPrank(agent);
        for (uint256 i = 0; i < 10; i++) bm.submitClaim(bytes32(i));
        vm.expectRevert("insufficient free bond");
        bm.submitClaim(bytes32(uint256(99)));
        vm.stopPrank();
    }
}
