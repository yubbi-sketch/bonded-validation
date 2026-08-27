// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidator} from "../src/BondedValidator.sol";
import {ZkVerdictGate, IZkVerifier} from "../src/ZkVerdictGate.sol";

interface Vm {
    function prank(address) external;
    function assume(bool) external;
}

/// @dev 항상 true를 반환하는 mock 검증자 — Halmos는 verify=true 전제 하에서
///      게이트 결정 로직(바인딩·점수·단일·상환)을 증명한다. 실제 halo2 검증은
///      Exp15/16(864k 가스)이 담당하며, 게이트 안전은 검증자 내부가 아니라
///      "verify=true ⟹ instances가 커밋된 (입력해시, 점수)"에만 의존한다.
contract MockVerifier is IZkVerifier {
    function verify(bytes calldata, uint256[] calldata) external pure returns (bool) {
        return true;
    }
}

/// @notice Exp20 — proofHash v0.4 게이트의 K1~K4를 Halmos로 증명.
contract ZkVerdictGateProofs {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    IdentityRegistry idReg;
    ValidationRegistry valReg;
    BondedValidator bv;
    ZkVerdictGate gate;
    MockVerifier verifier;
    address wallet = address(0xA11CE);
    uint256 aid;
    uint256 constant MIN_BOND = 1e18;
    uint256 constant CAP = 5e17;
    bytes32 constant H = bytes32(uint256(0xCA5E));

    function setUp() public {
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        verifier = new MockVerifier();
        // Halmos CREATE 주소 스킴(0xaaaa000N): token2·idReg3·valReg4·mock5·bv6·gate7.
        address predicted = address(0xaaaa0007);
        bv = new BondedValidator(address(token), address(idReg), address(valReg),
                                 predicted, MIN_BOND, 60);
        gate = new ZkVerdictGate(address(bv), address(verifier), address(token), CAP);
        require(address(gate) == predicted, "prediction");

        token.mint(wallet, 100e18);
        token.mint(address(gate), 10e18); // 상환 풀
        vm.prank(wallet); token.approve(address(bv), type(uint256).max);
        vm.prank(wallet); aid = idReg.register("agent://p");
        vm.prank(wallet); bv.stake(aid, 10e18);
        vm.prank(wallet); bv.requestValidation(aid, "", H);
    }


    function _instances(uint256 i0, uint256 i1) internal pure returns (uint256[] memory a) {
        a = new uint256[](2);
        a[0] = i0; a[1] = i1;
    }

    // ── K1 바인딩: instances[0] != requestHash면 반드시 revert ──────
    function check_K1_binding(uint256 i0, uint8 score) public {
        vm.assume(i0 != uint256(H));
        uint256[] memory inst = _instances(i0, uint256(score));
        (bool ok,) = address(gate).call(
            abi.encodeWithSelector(gate.attest.selector, H, score, bytes(""), inst));
        assert(!ok);                       // 엉뚱한 입력 증명 → 이 사건 정산 불가
        assert(!gate.proven(H));
    }

    // ── K2 점수 확정: score 인자 != instances[1]이면 revert ─────────
    function check_K2_score_binding(uint8 score, uint256 i1) public {
        vm.assume(i1 != uint256(score));
        uint256[] memory inst = _instances(uint256(H), i1);
        (bool ok,) = address(gate).call(
            abi.encodeWithSelector(gate.attest.selector, H, score, bytes(""), inst));
        assert(!ok);                       // 점수 위조 불가
        assert(!gate.proven(H));
    }

    // ── K2b 정합 시 정산 점수 == instances[1] ───────────────────────
    function check_K2b_settled_score_equals_instance(uint8 score) public {
        vm.assume(score <= 100);  // 점수는 프로토콜상 0~100 (레지스트리 도메인)
        uint256[] memory inst = _instances(uint256(H), uint256(score));
        (bool ok,) = address(gate).call(
            abi.encodeWithSelector(gate.attest.selector, H, score, bytes(""), inst));
        assert(ok);
        assert(gate.proven(H));
        assert(gate.provenScore(H) == score);
        assert(bv.claimSettled(H));
    }

    // ── K3 단일·비소급: 두 번째 attest는 반드시 실패 ────────────────
    function check_K3_no_double(uint8 s1, uint8 s2) public {
        vm.assume(s1 <= 100 && s2 <= 100);
        uint256[] memory i1 = _instances(uint256(H), uint256(s1));
        (bool ok1,) = address(gate).call(
            abi.encodeWithSelector(gate.attest.selector, H, s1, bytes(""), i1));
        assert(ok1);
        uint256[] memory i2 = _instances(uint256(H), uint256(s2));
        (bool ok2,) = address(gate).call(
            abi.encodeWithSelector(gate.attest.selector, H, s2, bytes(""), i2));
        assert(!ok2);                      // 소급 재정산 불가
        assert(gate.provenScore(H) == s1); // 첫 판정 불변
    }

    // ── K4 무보상 상환: 상환액이 점수와 무관(결과 독립)하고 상한 이하 ──
    //    상환액 = min(게이트잔액, CAP)으로 점수를 전혀 참조하지 않음을 증명.
    //    prover=wallet의 토큰 잔액 증가분이 정확히 그 상수여야 한다(∀ score).
    function check_K4_reimbursement_outcome_independent(uint8 score) public {
        vm.assume(score <= 100);
        uint256 gateBal = token.balanceOf(address(gate));
        uint256 expected = gateBal < CAP ? gateBal : CAP; // 점수 미참조 상수
        uint256 before = token.balanceOf(wallet);
        uint256[] memory inst = _instances(uint256(H), uint256(score));
        vm.prank(wallet);
        (bool ok,) = address(gate).call(
            abi.encodeWithSelector(gate.attest.selector, H, score, bytes(""), inst));
        assert(ok);
        // 어떤 점수든 prover는 정확히 같은 상수만 받는다 → 승자 보상금 불가.
        assert(token.balanceOf(wallet) == before + expected);
        assert(expected <= CAP);
    }
}
