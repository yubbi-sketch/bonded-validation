// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidator} from "../src/BondedValidator.sol";
import {JudgePanel} from "../src/JudgePanel.sol";

interface Vm {
    function prank(address) external;
    function startPrank(address) external;
    function stopPrank() external;
    function expectRevert(bytes calldata) external;
}

contract JudgePanelTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    IdentityRegistry idReg;
    ValidationRegistry valReg;
    BondedValidator bv;
    JudgePanel panel;
    address wallet = address(uint160(uint256(keccak256("exp7.wallet"))));
    address ja = address(uint160(uint256(keccak256("judge.a"))));
    address jb = address(uint160(uint256(keccak256("judge.b"))));
    address jc = address(uint160(uint256(keccak256("judge.c"))));
    uint256 aid;

    function setUp() public {
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        // BondedValidator의 judge 자리는 배포 시점에 패널 주소여야 하므로
        // 주소 선계산이 필요 — 간단히 두 번 배포: 임시 판별 후 재배포 대신
        // CREATE 주소 예측: 이 테스트 컨트랙트의 다음 nonce 컨트랙트가 panel.
        // 실무적으로는 패널 먼저 배포가 불가(패널이 bonded 주소 필요)라
        // 순환 의존 — bonded를 먼저 배포하되 judge=예측주소.
        address predicted = _predictNext(address(this), 5); // token(1)·id(2)·val(3)·bv(4)→panel(5)
        bv = new BondedValidator(address(token), address(idReg), address(valReg),
                                 predicted, 1e18, 60);
        panel = new JudgePanel(address(bv), ja, jb, jc);
        require(address(panel) == predicted, "prediction failed");
        token.mint(wallet, 100e18);
        vm.startPrank(wallet);
        aid = idReg.register("agent://t");
        token.approve(address(bv), type(uint256).max);
        bv.stake(aid, 10e18);
        vm.stopPrank();
    }

    function _predictNext(address deployer, uint256 nonce) internal pure returns (address) {
        // RLP: nonce 1~127 가정
        return address(uint160(uint256(keccak256(abi.encodePacked(
            bytes1(0xd6), bytes1(0x94), deployer, bytes1(uint8(nonce)))))));
    }

    function _claim(bytes32 h) internal {
        vm.prank(wallet);
        bv.requestValidation(aid, "", h);
    }

    function _vote(address j, bytes32 h, uint8 s, string memory tag) internal {
        vm.prank(j);
        panel.voteVerdict(h, s, tag, bytes32(0));
    }

    function test_unanimous_wrong_slashes() public {
        bytes32 h = bytes32(uint256(1));
        _claim(h);
        _vote(ja, h, 0, "wrong"); _vote(jb, h, 0, "wrong"); _vote(jc, h, 0, "wrong");
        (uint256 bonded_,,, uint256 slashed) = bv.agents(aid);
        require(bonded_ == 9e18 && slashed == 1e18, "no slash");
    }

    function test_unanimous_correct_releases() public {
        bytes32 h = bytes32(uint256(2));
        _claim(h);
        _vote(ja, h, 100, "correct"); _vote(jb, h, 100, "correct"); _vote(jc, h, 100, "correct");
        (uint256 bonded_, uint256 atRisk,,) = bv.agents(aid);
        require(bonded_ == 10e18 && atRisk == 0, "not released");
    }

    function test_single_dissent_blocks_slash() public {
        // 부패 판정자 1인이 "wrong"을 외쳐도 나머지가 "correct"면 몰수 불가
        bytes32 h = bytes32(uint256(3));
        _claim(h);
        _vote(ja, h, 100, "correct"); _vote(jc, h, 0, "wrong"); _vote(jb, h, 100, "correct");
        (, bool disputed, bool settled) = panel.status(h);
        require(disputed && !settled, "should be disputed");
        (uint256 bonded_,,, uint256 slashed) = bv.agents(aid);
        require(bonded_ == 10e18 && slashed == 0, "wrongful slash happened!");
    }

    function test_single_corrupt_cannot_exonerate_either() public {
        // 역방향: 진짜 오답을 부패 판정자가 "correct"로 감싸도 사면 불가 (분쟁)
        bytes32 h = bytes32(uint256(4));
        _claim(h);
        _vote(ja, h, 0, "wrong"); _vote(jb, h, 0, "wrong"); _vote(jc, h, 100, "correct");
        (, bool disputed, bool settled) = panel.status(h);
        require(disputed && !settled, "should be disputed");
    }

    function test_double_vote_reverts() public {
        bytes32 h = bytes32(uint256(5));
        _claim(h);
        _vote(ja, h, 100, "correct");
        vm.prank(ja);
        vm.expectRevert("double vote");
        panel.voteVerdict(h, 100, "correct", bytes32(0));
    }

    function test_non_judge_reverts() public {
        bytes32 h = bytes32(uint256(6));
        _claim(h);
        vm.prank(address(0xBEEF));
        vm.expectRevert("not judge");
        panel.voteVerdict(h, 100, "correct", bytes32(0));
    }

    function test_eoa_cannot_bypass_panel() public {
        // 판정자 개인이 BondedValidator를 직접 부르면 거부 (judge=패널 컨트랙트)
        bytes32 h = bytes32(uint256(7));
        _claim(h);
        vm.prank(ja);
        vm.expectRevert("not judge");
        bv.submitVerdict(h, 0, "", bytes32(0), "wrong");
    }
}
