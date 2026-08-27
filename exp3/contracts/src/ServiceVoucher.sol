// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

interface IERC20 {
    function transfer(address, uint256) external returns (bool);
    function transferFrom(address, address, uint256) external returns (bool);
}

/// @title ServiceVoucher — 규제 불변 바우처 (Exp17)
/// @notice AI 서비스 사용권을 파는 선불 크레딧. "투자 실질"을 구조에서 제거해
///         규제 분류가 관할·시점에 의존하지 않도록 설계한다. 네 성질이 컨트랙트
///         불변식이고, ServiceVoucherProofs가 Halmos로 이를 증명한다:
///         1) 가치 상승 불가 — priceWei·serviceUnitPerCredit가 immutable(변경
///            함수 없음), 1크레딧의 액면·효용이 영구 고정.
///         2) 전매 불가 — transfer/transferFrom/approve 전부 revert. 2차 시장 없음.
///         3) 풀링 없음 — escrow는 환불 담보일 뿐, 홀더에게 배분되는 수익 경로 없음.
///         4) 수익 없음 — 잔액은 구매(buy)로만 증가. 홀딩은 아무것도 낳지 않는다.
/// @dev    정직성: 이 구조는 "투자 실질 부재"를 증명하지 특정 관할의 합법을
///         보증하지 않는다. 실런치 전 면허 변호사 확인 필수. 결제(fiat)는
///         오프체인이며 여기선 payment ERC-20으로 모델링한다.
contract ServiceVoucher {
    IERC20 public immutable payment;
    address public immutable issuer;
    uint256 public immutable priceWei;              // 1 크레딧 = priceWei 결제토큰 (고정)
    uint256 public immutable serviceUnitPerCredit;  // 1 크레딧 = N 서비스 단위 (고정)

    mapping(address => uint256) public credits;
    uint256 public escrow;                           // 환불 담보로 보관된 결제토큰

    event Bought(address indexed buyer, uint256 credits, uint256 paid);
    event Used(address indexed holder, uint256 credits, uint256 serviceUnits);
    event Refunded(address indexed holder, uint256 credits, uint256 returned);

    error NonTransferable();

    constructor(address payment_, uint256 priceWei_, uint256 serviceUnitPerCredit_) {
        require(priceWei_ > 0 && serviceUnitPerCredit_ > 0, "params");
        payment = IERC20(payment_);
        issuer = msg.sender;
        priceWei = priceWei_;
        serviceUnitPerCredit = serviceUnitPerCredit_;
    }

    /// @notice 구매 — 결제토큰을 escrow에 넣고 크레딧 발행. 가격 고정 → 상승 불가.
    function buy(uint256 amount) external {
        require(amount > 0, "zero");
        uint256 pay = amount * priceWei;
        require(payment.transferFrom(msg.sender, address(this), pay), "pay");
        escrow += pay;
        credits[msg.sender] += amount;
        emit Bought(msg.sender, amount, pay);
    }

    /// @notice 사용 — 크레딧 소각(서비스 소비). 돈은 움직이지 않는다.
    function use(uint256 amount) external {
        require(credits[msg.sender] >= amount, "insufficient");
        credits[msg.sender] -= amount;
        emit Used(msg.sender, amount, amount * serviceUnitPerCredit);
    }

    /// @notice 환불 — 액면 그대로(1:1 고정). 산 값 이상은 절대 못 받는다.
    function refund(uint256 amount) external {
        require(credits[msg.sender] >= amount, "insufficient");
        uint256 ret = amount * priceWei;
        credits[msg.sender] -= amount;
        escrow -= ret;
        require(payment.transfer(msg.sender, ret), "refund");
        emit Refunded(msg.sender, amount, ret);
    }

    // ─── 전매 봉쇄 (ERC-20 표면이지만 이전은 전부 거부) ──────────────
    function transfer(address, uint256) external pure returns (bool) { revert NonTransferable(); }
    function transferFrom(address, address, uint256) external pure returns (bool) { revert NonTransferable(); }
    function approve(address, uint256) external pure returns (bool) { revert NonTransferable(); }

    function balanceOf(address a) external view returns (uint256) { return credits[a]; }
}
