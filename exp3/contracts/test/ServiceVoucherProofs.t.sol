// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {ServiceVoucher} from "../src/ServiceVoucher.sol";

interface Vm {
    function prank(address) external;
    function assume(bool) external;
    function store(address, bytes32, bytes32) external;
    function load(address, bytes32) external view returns (bytes32);
}

/// @dev 증명 하네스 — 임의 초기 상태를 세팅할 setter만 추가(로직은 부모 그대로).
///      __set*는 테스트 전용이며 프로덕션 ServiceVoucher에는 없다.
contract VoucherHarness is ServiceVoucher {
    constructor(address p, uint256 price, uint256 spc) ServiceVoucher(p, price, spc) {}
    function __setCredits(address a, uint256 v) external { credits[a] = v; }
    function __setEscrow(uint256 v) external { escrow = v; }
}

/// @notice Exp17 — 규제 불변 바우처의 네 조건을 Halmos로 증명.
///         외부 상태변경 표면 전부(buy·use·refund·transfer·transferFrom·approve)를
///         함수별로 덮어 "투자 실질을 만드는 경로가 없음"을 성립시킨다(K4).
contract ServiceVoucherProofs {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    VoucherHarness h;
    uint256 constant PRICE = 3;   // 1 크레딧 = 3 결제토큰 (고정)
    uint256 constant SPC = 5;     // 1 크레딧 = 5 서비스 단위 (고정)

    address caller = address(0xA11CE);
    address other = address(0xB0B);

    function setUp() public {
        token = new LabToken();
        h = new VoucherHarness(address(token), PRICE, SPC);
    }

    // ── K1 전매 봉쇄: 어떤 입력에서도 revert ─────────────────────────
    function check_K1_transfer_reverts(address to, uint256 amt) public {
        (bool ok,) = address(h).call(abi.encodeWithSelector(h.transfer.selector, to, amt));
        assert(!ok);
    }
    function check_K1_transferFrom_reverts(address f, address t, uint256 amt) public {
        (bool ok,) = address(h).call(abi.encodeWithSelector(h.transferFrom.selector, f, t, amt));
        assert(!ok);
    }
    function check_K1_approve_reverts(address s, uint256 amt) public {
        (bool ok,) = address(h).call(abi.encodeWithSelector(h.approve.selector, s, amt));
        assert(!ok);
    }

    // ── K2 비증식: use는 호출자 본인만 감소, 제3자·escrow 불변, 증가 불가 ──
    function check_K2_use_conserves(uint256 pre, uint256 preOther, uint256 amt) public {
        vm.assume(caller != other);
        h.__setCredits(caller, pre);
        h.__setCredits(other, preOther);
        h.__setEscrow(12345);
        vm.prank(caller);
        address(h).call(abi.encodeWithSelector(h.use.selector, amt));
        // 성공(정확 감소)이든 revert(롤백)든, 안전 불변식은 무조건 성립:
        uint256 post = h.credits(caller);
        assert(post == pre || post == pre - amt);   // 두 결과 외 없음
        assert(post <= pre);                        // 절대 증가 불가 (홀딩=무수익)
        assert(h.credits(other) == preOther);       // 제3자 불변
        assert(h.escrow() == 12345);                // 돈 안 움직임 (사용은 소비뿐)
    }

    // ── K3 무이익 환불: 정확히 액면, 그 이상 불가 ────────────────────
    function check_K3_refund_face_value(uint256 pre, uint256 amt) public {
        vm.assume(caller != other);
        vm.assume(amt <= pre);
        vm.assume(amt < 1e30);       // 현실 범위 — amt*PRICE 오버플로 배제(명기)
        uint256 ret = amt * PRICE;
        // escrow 담보를 실제 토큰으로 채워 환불 경로를 실행 가능하게
        token.mint(address(h), ret + 1000);
        h.__setEscrow(ret + 1000);
        h.__setCredits(caller, pre);
        h.__setCredits(other, 777);
        uint256 c0 = token.balanceOf(caller);
        vm.prank(caller);
        (bool ok,) = address(h).call(abi.encodeWithSelector(h.refund.selector, amt));
        assert(ok);
        // 정확히 액면만 — 산 값(구매 시 amt*PRICE)과 동일, 이익 0
        assert(token.balanceOf(caller) == c0 + ret);
        assert(h.credits(caller) == pre - amt);
        assert(h.credits(other) == 777);            // 제3자 불변
        // 크레딧당 현금 회수 == PRICE == 크레딧당 지불가 → 상승 불가
    }

    // ── K2 비증식(구매 경로): buy는 구매자만 증가, 그것도 결제 대가로만 ──
    function check_K2_buy_only_against_payment(uint256 amt, uint256 preOther) public {
        vm.assume(caller != other);
        vm.assume(amt > 0 && amt < 1e30);
        uint256 pay = amt * PRICE;
        token.mint(caller, pay);
        vm.prank(caller);
        token.approve(address(h), pay);
        h.__setCredits(other, preOther);
        uint256 e0 = h.escrow();
        vm.prank(caller);
        (bool ok,) = address(h).call(abi.encodeWithSelector(h.buy.selector, amt));
        assert(ok);
        assert(h.credits(caller) == amt);           // 구매분만큼만
        assert(h.escrow() == e0 + pay);             // 낸 돈이 그대로 담보로 (풀링 아님)
        assert(h.credits(other) == preOther);       // 제3자 불변
        assert(token.balanceOf(caller) == 0);       // 대가 없이 발행 없음
    }

    // ── K3 불변 파라미터: 가격·효용이 고정(상승 경로 부재) ────────────
    function check_K3_rate_is_fixed() public view {
        assert(h.priceWei() == PRICE);
        assert(h.serviceUnitPerCredit() == SPC);
        // 이 둘은 immutable — 변경 함수가 소스에 존재하지 않는다(K4 표면 열거로 보증).
    }
}
