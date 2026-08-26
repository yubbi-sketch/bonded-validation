// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidator} from "../src/BondedValidator.sol";

interface Vm {
    function prank(address) external;
    function startPrank(address) external;
    function stopPrank() external;
}

/// @notice Exp11 — 첫 기계 증명 (Halmos 심볼릭 실행).
///         Forge 테스트는 "몇 개 사례에서 참"이고, 여기의 check_*는 "모든
///         입력(전 심볼릭 공간)에서 참"을 SMT 솔버로 증명한다. B 전환의 1보:
///         Bonded Validation의 경제 불변식을 테스트에서 정리(theorem)로 승격.
///
///         증명 대상 (지붕 명제의 경제 코어):
///         T1. 기권 무손실 — 어떤 점수가 나와도 tag "abstain"이면 담보 불변
///         T2. 슬래시 정확성 — 몰수는 정확히 (score<50 && !abstain)일 때,
///             정확히 minBondPerClaim만큼만 일어난다 (과다몰수 불가능)
///         T3. 이중 정산 불가 — 같은 주장은 두 번 정산될 수 없다
///         T4. 정산 보존 — 정산은 atRisk를 정확히 minBond만큼 해제한다
///
///         정직성: 증명 범위는 "단일 주장 1회 정산" 상태 공간이다. 다중 주장
///         교차·재진입·패널 계층은 후속 증명 대상으로 명시해 남긴다.
contract BondedValidatorProofs {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    IdentityRegistry idReg;
    ValidationRegistry valReg;
    BondedValidator bv;
    address wallet = address(0x1001);
    uint256 aid;
    uint256 constant MIN_BOND = 1e18;
    bytes32 constant H = bytes32(uint256(0xC1A1)); // 대상 주장 (상태만 심볼릭이면 충분)

    function setUp() public {
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        // judge = 이 컨트랙트 — 판정 입력(score·tag)을 심볼릭으로 직접 주입한다
        bv = new BondedValidator(address(token), address(idReg), address(valReg),
                                 address(this), MIN_BOND, 60);
        token.mint(wallet, 10e18);
        vm.startPrank(wallet);
        aid = idReg.register("agent://p");
        token.approve(address(bv), type(uint256).max);
        bv.stake(aid, 5e18);
        bv.requestValidation(aid, "", H);
        vm.stopPrank();
    }

    function _agent() internal view returns (uint256 b, uint256 atRisk, uint256 slashed) {
        (b, atRisk,, slashed) = bv.agents(aid);
    }

    /// T1: ∀ score — 기권은 무손실이다.
    function check_T1_abstain_never_slashes(uint8 score) public {
        (uint256 b0,,) = _agent();
        bv.submitVerdict(H, score, "", bytes32(0), "abstain");
        (uint256 b1, uint256 atRisk1, uint256 slashed1) = _agent();
        assert(b1 == b0);          // 담보 불변
        assert(slashed1 == 0);     // 몰수 이력 없음
        assert(atRisk1 == 0);      // 잠금 해제
    }

    /// T2: ∀ score, ∀ tag — 몰수는 정확히 (score<50 && tag!="abstain")에서만,
    ///     정확히 minBondPerClaim만큼. 과다몰수·자의적 몰수는 불가능하다.
    function check_T2_slash_exactness(uint8 score, string memory tag) public {
        (uint256 b0,,) = _agent();
        bv.submitVerdict(H, score, "", bytes32(0), tag);
        (uint256 b1,, uint256 slashed1) = _agent();
        bool abstained = keccak256(bytes(tag)) == keccak256(bytes("abstain"));
        if (!abstained && score < 50) {
            assert(b1 == b0 - MIN_BOND);
            assert(slashed1 == MIN_BOND);
        } else {
            assert(b1 == b0);
            assert(slashed1 == 0);
        }
    }

    /// T3: ∀ score1, score2 — 이중 정산은 불가능하다 (두 번째 호출은 반드시 실패).
    function check_T3_no_double_settle(uint8 s1, uint8 s2, string memory tag) public {
        bv.submitVerdict(H, s1, "", bytes32(0), tag);
        (bool ok,) = address(bv).call(abi.encodeWithSelector(
            bv.submitVerdict.selector, H, s2, "", bytes32(0), tag));
        assert(!ok);
    }

    /// T4: ∀ score, ∀ tag — 정산은 atRisk를 정확히 minBond만큼 해제하며,
    ///     해제는 담보 잔액을 초과할 수 없다 (회계 보존).
    function check_T4_settlement_conservation(uint8 score, string memory tag) public {
        (uint256 b0, uint256 r0,) = _agent();
        bv.submitVerdict(H, score, "", bytes32(0), tag);
        (uint256 b1, uint256 r1,) = _agent();
        assert(r0 - r1 == MIN_BOND); // 정확히 한 주장 분량 해제
        assert(b1 <= b0);            // 담보는 늘지 않는다 (판정으로 이득 불가)
        assert(b1 >= r1);            // 잠긴 양이 잔액을 초과하는 상태 불가
    }
}
