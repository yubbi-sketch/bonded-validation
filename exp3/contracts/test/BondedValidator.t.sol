// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidator} from "../src/BondedValidator.sol";

interface Vm {
    function prank(address) external;
    function startPrank(address) external;
    function stopPrank() external;
    function warp(uint256) external;
    function expectRevert(bytes calldata) external;
}

contract BondedValidatorTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    IdentityRegistry idReg;
    ValidationRegistry valReg;
    BondedValidator bv;
    address wallet = address(uint160(uint256(keccak256("exp5.agent.wallet"))));
    uint256 agentId;

    function setUp() public {
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        bv = new BondedValidator(address(token), address(idReg), address(valReg),
                                 address(this), 1e18, 60);
        token.mint(wallet, 100e18);
        vm.startPrank(wallet);
        agentId = idReg.register("ipfs://agent-card");
        token.approve(address(bv), type(uint256).max);
        bv.stake(agentId, 10e18);
        vm.stopPrank();
    }

    function _claim(bytes32 h) internal {
        vm.prank(wallet);
        bv.requestValidation(agentId, "", h);
    }

    function test_request_requires_bond() public {
        vm.startPrank(wallet);
        uint256 poorId = idReg.register("ipfs://poor");
        vm.expectRevert("insufficient free bond");
        bv.requestValidation(poorId, "", bytes32(uint256(1)));
        vm.stopPrank();
    }

    function test_only_agent_wallet_can_speak() public {
        vm.prank(address(0xBEEF));
        vm.expectRevert("not agent wallet");
        bv.requestValidation(agentId, "", bytes32(uint256(2)));
    }

    function test_low_score_slashes_and_records() public {
        bytes32 h = bytes32(uint256(3));
        _claim(h);
        bv.submitVerdict(h, 0, "", bytes32(uint256(0xE0)), "wrong");
        (uint256 bonded,,, uint256 slashedTotal) = bv.agents(agentId);
        require(bonded == 9e18 && slashedTotal == 1e18, "slash failed");
        (, , uint8 score,, bool responded) = valReg.getValidationStatus(h);
        require(responded && score == 0, "registry not updated");
    }

    function test_high_score_releases() public {
        bytes32 h = bytes32(uint256(4));
        _claim(h);
        bv.submitVerdict(h, 100, "", bytes32(0), "correct");
        (uint256 bonded, uint256 atRisk,,) = bv.agents(agentId);
        require(bonded == 10e18 && atRisk == 0, "release failed");
    }

    function test_abstain_no_loss_even_with_zero_score() public {
        bytes32 h = bytes32(uint256(5));
        _claim(h);
        bv.submitVerdict(h, 0, "", bytes32(0), "abstain");
        (uint256 bonded,,, uint256 slashedTotal) = bv.agents(agentId);
        require(bonded == 10e18 && slashedTotal == 0, "abstain slashed!");
    }

    function test_registry_summary_averages_scores() public {
        _claim(bytes32(uint256(6)));
        _claim(bytes32(uint256(7)));
        bv.submitVerdict(bytes32(uint256(6)), 100, "", bytes32(0), "correct");
        bv.submitVerdict(bytes32(uint256(7)), 0, "", bytes32(0), "wrong");
        (uint64 count, uint256 avg) = valReg.getSummary(agentId);
        require(count == 2 && avg == 50, "summary wrong");
    }

    function test_only_bonded_validator_can_respond_registry() public {
        bytes32 h = bytes32(uint256(8));
        _claim(h);
        vm.prank(address(0xBEEF));
        vm.expectRevert("not validator");
        valReg.validationResponse(h, 100, "", bytes32(0), "x");
    }

    function test_withdraw_blocked_by_pending_then_ok() public {
        bytes32 h = bytes32(uint256(9));
        _claim(h);
        vm.prank(wallet);
        bv.requestUnbond(agentId);
        vm.warp(block.timestamp + 61);
        vm.prank(wallet);
        vm.expectRevert("claims pending");
        bv.withdraw(agentId);
        bv.submitVerdict(h, 100, "", bytes32(0), "correct");
        vm.prank(wallet);
        bv.withdraw(agentId);
        require(token.balanceOf(wallet) == 100e18, "not returned");
    }
}
