// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidator} from "../src/BondedValidator.sol";
import {ReputationLens} from "../src/ReputationLens.sol";

interface Vm {
    function prank(address) external;
    function startPrank(address) external;
    function stopPrank() external;
}

contract ReputationLensTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    IdentityRegistry idReg;
    ValidationRegistry valReg;
    BondedValidator bv;
    ReputationLens lens;
    address wallet = address(uint160(uint256(keccak256("exp6.wallet"))));
    uint256 aid;

    function setUp() public {
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        bv = new BondedValidator(address(token), address(idReg), address(valReg),
                                 address(this), 1e18, 60);
        lens = new ReputationLens(address(valReg), address(bv));
        token.mint(wallet, 100e18);
        vm.startPrank(wallet);
        aid = idReg.register("agent://t");
        token.approve(address(bv), type(uint256).max);
        bv.stake(aid, 50e18);
        vm.stopPrank();
    }

    function _round(uint256 n, uint8 score, string memory tag, uint256 salt) internal {
        for (uint256 i = 0; i < n; i++) {
            bytes32 h = keccak256(abi.encode(salt, i));
            vm.prank(wallet);
            bv.requestValidation(aid, "", h);
            bv.submitVerdict(h, score, "", bytes32(0), tag);
        }
    }

    function test_abstain_neutral_score() public {
        // 정답 12 + 기권 8 (점수 0) → 순진 평균 60, 기권 중립 평균 100이어야 함
        _round(12, 100, "correct", 1);
        _round(8, 0, "abstain", 2);
        (uint64 cAll, uint256 avgAll) = valReg.getSummary(aid);
        (uint256 score, uint64 answered) = lens.creditScore(aid);
        require(cAll == 20 && avgAll == 60, "naive avg wrong");
        require(score == 100 && answered == 12, "abstain-neutral score wrong");
    }

    function test_abstain_rate_exposed_separately() public {
        _round(12, 100, "correct", 3);
        _round(8, 0, "abstain", 4);
        require(lens.abstainRateBp(aid) == 4000, "abstain rate wrong"); // 8/20
    }

    function test_wrongs_still_hurt() public {
        _round(10, 100, "correct", 5);
        _round(10, 0, "wrong", 6);
        (uint256 score,) = lens.creditScore(aid);
        require(score == 50, "wrong not counted");
    }

    function test_required_bond_tiers() public {
        // 신참(이력<10) 1.5x
        require(lens.requiredBondBp(aid) == 15000, "newcomer premium");
        // 만점 이력 → 0.5x
        _round(12, 100, "correct", 7);
        require(lens.requiredBondBp(aid) == 5000, "perfect discount");
        require(lens.requiredBond(aid) == 5e17, "absolute bond");
    }

    function test_half_score_full_bond() public {
        _round(10, 100, "correct", 8);
        _round(10, 0, "wrong", 9);
        require(lens.requiredBondBp(aid) == 10000, "50 score should be 1.0x");
    }
}
