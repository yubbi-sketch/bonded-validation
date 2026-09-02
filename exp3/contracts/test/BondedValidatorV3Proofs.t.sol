// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidatorV3} from "../src/BondedValidatorV3.sol";

interface Vm {
    function prank(address) external;
    function startPrank(address) external;
    function stopPrank() external;
    function warp(uint256) external;
    function assume(bool) external;
}

/// @notice Exp30 — BondedValidatorV3 기계 증명 (Halmos 심볼릭 실행).
///         T1~T4 (Exp11) 회귀: 단언 무수정, 창 열린 시점(dt = 0)·미표식 상태에서
///         judge 직접 정산. 신규 L1~L5: 소멸(lapse) 경로의 무손실·완전성·상호배타·
///         표식 봉쇄·단일 정산.
///
///         증명 범위(정직성): 단일 주장 · W 구체값(86,400) · dt 심볼릭 uint64 ·
///         점수 전 uint8 · 태그 심볼릭. 다중 주장 교차·재진입·패널 계층·disengage
///         후 재개설 반복은 Forge 실측(Exp30Lapse.t.sol)만.
contract BondedValidatorV3Proofs {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    IdentityRegistry idReg;
    ValidationRegistry valReg;
    BondedValidatorV3 bv;
    address wallet = address(0x1001);
    uint256 aid;
    uint256 constant MIN_BOND = 1e18;
    uint256 constant W = 86400;
    bytes32 constant H = bytes32(uint256(0xC1A1)); // 대상 주장 (상태만 심볼릭이면 충분)
    uint256 t0;

    function setUp() public {
        vm.warp(1_000_000); // claimedAt 을 구체값으로 고정 — dt 만 심볼릭
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        // judge = 이 컨트랙트 — 판정·표식 입력을 심볼릭으로 직접 주입한다
        bv = new BondedValidatorV3(address(token), address(idReg), address(valReg),
                                   address(this), MIN_BOND, 60, W);
        token.mint(wallet, 10e18);
        vm.startPrank(wallet);
        aid = idReg.register("agent://p");
        token.approve(address(bv), type(uint256).max);
        bv.stake(aid, 5e18);
        bv.requestValidation(aid, "", H);
        vm.stopPrank();
        t0 = block.timestamp;
    }

    function _agent() internal view returns (uint256 b, uint256 atRisk, uint256 slashed) {
        (b, atRisk,, slashed) = bv.agents(aid);
    }

    function _lapse() internal returns (bool ok) {
        (ok,) = address(bv).call(abi.encodeWithSelector(bv.settleUnchallenged.selector, H));
    }

    function _engage() internal returns (bool ok) {
        (ok,) = address(bv).call(abi.encodeWithSelector(bv.engage.selector, H));
    }

    function _verdict(uint8 score, string memory tag) internal returns (bool ok) {
        (ok,) = address(bv).call(abi.encodeWithSelector(
            bv.submitVerdict.selector, H, score, "", bytes32(0), tag));
    }

    // ═══ T1~T4 회귀 (Exp11 단언 무수정) ═══

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

    // ═══ L1~L5 소멸 (Exp30) ═══

    /// L1 소멸 무손실·완전성: ∀ dt ≥ W, ∀ caller — 미표식 주장은 소멸 성공 ∧ bonded′=bonded
    ///    ∧ slashedTotal′=slashedTotal ∧ atRisk−atRisk′=B_a ∧ balance(BV)′=balance(BV)
    ///    ∧ claimSettled′ ∧ registry=(responded, 50, "unchallenged").
    function check_L1_lapse_lossless_complete(uint64 dt, address caller) public {
        vm.assume(dt >= W);
        vm.warp(t0 + dt);
        (uint256 b0, uint256 r0, uint256 s0) = _agent();
        uint256 bal0 = token.balanceOf(address(bv));
        vm.prank(caller);
        bv.settleUnchallenged(H);
        (uint256 b1, uint256 r1, uint256 s1) = _agent();
        assert(b1 == b0);
        assert(s1 == s0);
        assert(r0 - r1 == MIN_BOND);
        assert(token.balanceOf(address(bv)) == bal0);
        assert(bv.claimSettled(H));
        assert(!bv.engaged(H));
        (, , uint8 score, string memory tag, bool responded) = valReg.getValidationStatus(H);
        assert(responded);
        assert(score == 50);
        assert(keccak256(bytes(tag)) == keccak256(bytes("unchallenged")));
    }

    /// L2 조기 소멸 불가: ∀ dt < W, ∀ caller — 소멸 되돌림 ∧ atRisk′ = atRisk.
    function check_L2_no_early_lapse(uint64 dt, address caller) public {
        vm.assume(dt < W);
        vm.warp(t0 + dt);
        (, uint256 r0,) = _agent();
        vm.prank(caller);
        bool ok = _lapse();
        assert(!ok);
        (, uint256 r1,) = _agent();
        assert(r1 == r0);
        assert(!bv.claimSettled(H));
    }

    /// L3 상호배타·완전성: ∀ dt — enabled(engage) XOR enabled(lapse).
    ///    dt < W ⟹ lapse 실패·engage 성공 ; dt ≥ W ⟹ engage 실패·verdict 실패·lapse 성공.
    function check_L3_engage_xor_lapse(uint64 dt, uint8 score, string memory tag) public {
        vm.warp(t0 + dt);
        bool okE;
        bool okL;
        if (dt < W) {
            okL = _lapse();
            assert(!okL);
            okE = _engage();
            assert(okE);
        } else {
            okE = _engage();
            assert(!okE);
            assert(!_verdict(score, tag)); // 창 밖·미표식: 판정 경로도 닫혀 있다
            okL = _lapse();
            assert(okL);
        }
        assert(okE != okL);
    }

    /// L4 표식 봉쇄·해제: 표식 후 ∀ dt lapse 되돌림; disengage 후엔 미표식과 동일 거동
    ///    (창 밖이면 lapse 성공, 창 안이면 실패).
    function check_L4_engaged_blocks_lapse_disengage_restores(uint64 dt0, uint64 dt) public {
        vm.assume(dt0 < W);
        vm.warp(t0 + dt0);
        bv.engage(H);
        uint256 t1 = t0 + uint256(dt0) + uint256(dt);
        vm.warp(t1);
        assert(!_lapse());
        (, uint256 r,) = _agent();
        assert(r == MIN_BOND);
        bv.disengage(H);
        assert(!bv.engaged(H));
        bool okL = _lapse();
        assert(okL == (t1 >= t0 + W));
        if (okL) assert(bv.claimSettled(H)); else assert(!bv.claimSettled(H));
    }

    /// L5a 단일 정산(T3 확장): 소멸 뒤 verdict·lapse 재호출·engage 전부 되돌림.
    function check_L5a_lapse_then_nothing(uint64 dt, uint8 score, string memory tag) public {
        vm.assume(dt >= W);
        vm.warp(t0 + dt);
        bv.settleUnchallenged(H);
        assert(!_verdict(score, tag));
        assert(!_lapse());
        assert(!_engage());
        (, uint256 r,) = _agent();
        assert(r == 0);
    }

    /// L5b 단일 정산: 판정 뒤 ∀ dt lapse·engage 되돌림.
    function check_L5b_verdict_then_nothing(uint8 score, string memory tag, uint64 dt) public {
        bv.submitVerdict(H, score, "", bytes32(0), tag);
        (uint256 b0,, uint256 s0) = _agent();
        vm.warp(t0 + dt);
        assert(!_lapse());
        assert(!_engage());
        (uint256 b1, uint256 r1, uint256 s1) = _agent();
        assert(b1 == b0 && s1 == s0 && r1 == 0);
    }
}
