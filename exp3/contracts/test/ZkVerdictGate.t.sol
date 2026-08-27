// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidator} from "../src/BondedValidator.sol";
import {ZkVerdictGate, IZkVerifier} from "../src/ZkVerdictGate.sol";

interface Vm {
    function prank(address) external;
    function expectRevert(bytes4) external;
}

contract MockVerifierT is IZkVerifier {
    bool public ret = true;
    function set(bool v) external { ret = v; }
    function verify(bytes calldata, uint256[] calldata) external view returns (bool) { return ret; }
}

contract ZkVerdictGateTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token; IdentityRegistry idReg; ValidationRegistry valReg;
    BondedValidator bv; ZkVerdictGate gate; MockVerifierT verifier;
    address wallet = address(0xB0B);
    uint256 aid;
    bytes32 constant H = bytes32(uint256(0xCA5E));

    function _predict(address d, uint256 n) internal pure returns (address) {
        return address(uint160(uint256(keccak256(abi.encodePacked(
            bytes1(0xd6), bytes1(0x94), d, bytes1(uint8(n)))))));
    }

    function setUp() public {
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        verifier = new MockVerifierT();
        address predicted = _predict(address(this), 6);
        bv = new BondedValidator(address(token), address(idReg), address(valReg),
                                 predicted, 1e18, 60);
        gate = new ZkVerdictGate(address(bv), address(verifier), address(token), 5e17);
        require(address(gate) == predicted, "prediction");
        token.mint(wallet, 100e18);
        token.mint(address(gate), 10e18);
        vm.prank(wallet); token.approve(address(bv), type(uint256).max);
        vm.prank(wallet); aid = idReg.register("a://p");
        vm.prank(wallet); bv.stake(aid, 10e18);
        vm.prank(wallet); bv.requestValidation(aid, "", H);
    }

    function _inst(uint256 a, uint256 b) internal pure returns (uint256[] memory r) {
        r = new uint256[](2); r[0] = a; r[1] = b;
    }

    function test_attest_settles_and_reimburses() public {
        uint256 before = token.balanceOf(wallet);
        vm.prank(wallet);
        gate.attest(H, 90, "", _inst(uint256(H), 90));
        require(gate.proven(H) && gate.provenScore(H) == 90, "proven");
        require(bv.claimSettled(H), "settled");
        require(token.balanceOf(wallet) == before + 5e17, "reimb cap");
    }

    function test_wrong_case_binding_reverts() public {
        vm.expectRevert(ZkVerdictGate.CaseMismatch.selector);
        gate.attest(H, 90, "", _inst(uint256(bytes32(uint256(0xBEEF))), 90));
    }

    function test_score_forgery_reverts() public {
        vm.expectRevert(ZkVerdictGate.ScoreMismatch.selector);
        gate.attest(H, 90, "", _inst(uint256(H), 20));
    }

    function test_bad_verify_reverts() public {
        verifier.set(false);
        vm.expectRevert(ZkVerdictGate.BadVerify.selector);
        gate.attest(H, 90, "", _inst(uint256(H), 90));
    }

    function test_no_double_attest() public {
        gate.attest(H, 90, "", _inst(uint256(H), 90));
        vm.expectRevert(ZkVerdictGate.AlreadyProven.selector);
        gate.attest(H, 30, "", _inst(uint256(H), 30));
    }

    function test_wrong_verdict_slashes_agent() public {
        (uint256 b0,,,) = bv.agents(aid);
        gate.attest(H, 10, "", _inst(uint256(H), 10)); // score<50 → slash
        (uint256 b1,,, uint256 slashed) = bv.agents(aid);
        require(b1 == b0 - 1e18 && slashed == 1e18, "slash");
    }
}
