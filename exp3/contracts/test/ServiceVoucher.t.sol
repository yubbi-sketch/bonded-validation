// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {ServiceVoucher} from "../src/ServiceVoucher.sol";

interface Vm {
    function prank(address) external;
    function expectRevert(bytes calldata) external;
    function expectRevert(bytes4) external;
}

contract ServiceVoucherTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    ServiceVoucher v;
    address buyer = address(0xB0B);
    uint256 constant PRICE = 3;
    uint256 constant SPC = 5;

    function setUp() public {
        token = new LabToken();
        v = new ServiceVoucher(address(token), PRICE, SPC);
        token.mint(buyer, 100);
        vm.prank(buyer);
        token.approve(address(v), type(uint256).max);
    }

    function test_buy_use_flow() public {
        vm.prank(buyer);
        v.buy(10);
        require(v.credits(buyer) == 10 && v.escrow() == 30, "buy");
        require(token.balanceOf(buyer) == 70, "paid");
        vm.prank(buyer);
        v.use(4);
        require(v.credits(buyer) == 6, "use"); // 4 소각(=20 서비스 단위)
        require(token.balanceOf(buyer) == 70, "use moves no money");
    }

    function test_refund_face_value() public {
        vm.prank(buyer);
        v.buy(10);
        vm.prank(buyer);
        v.refund(4);
        require(v.credits(buyer) == 6, "refund credits");
        require(token.balanceOf(buyer) == 82, "face value"); // 70 + 4*3
        require(v.escrow() == 18, "escrow"); // 30 - 12
    }

    function test_transfer_blocked() public {
        vm.prank(buyer);
        v.buy(5);
        vm.expectRevert(ServiceVoucher.NonTransferable.selector);
        v.transfer(address(0xA), 1);
        vm.expectRevert(ServiceVoucher.NonTransferable.selector);
        v.approve(address(0xA), 1);
        vm.expectRevert(ServiceVoucher.NonTransferable.selector);
        v.transferFrom(buyer, address(0xA), 1);
    }

    function test_use_over_balance_reverts() public {
        vm.prank(buyer);
        v.buy(3);
        vm.expectRevert(bytes("insufficient"));
        vm.prank(buyer);
        v.use(4);
    }
}
