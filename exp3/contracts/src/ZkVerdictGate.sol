// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {BondedValidator, IERC20} from "./BondedValidator.sol";

interface IZkVerifier {
    /// @return true iff `proof` is a valid halo2 proof for `instances`.
    ///         (Exp15/16: real ezkl verifier, ~864k gas; here an interface.)
    function verify(bytes calldata proof, uint256[] calldata instances) external view returns (bool);
}

/// @title ZkVerdictGate — proofHash v0.4: 바인딩 닫은 증명 실린 판정 (Exp20)
/// @notice BondedValidator의 judge 자리에 앉아, zk 증명으로 결정론 사건을 최종
///         정산한다. 심의(적군석 R2·R3 KILL / 메커니즘석 R1'~R7)가 지목한 두
///         급소를 구조로 닫는다:
///         (A) 바인딩 — 사건 정체성 = 회로가 커밋한 입력 해시. attest는
///             instances[0] == uint256(requestHash)를 강제한다. 엉뚱한 입력의
///             유효 증명으로 이 사건을 정산할 수 없다(Attack1 봉쇄).
///         (B) 점수 확정 — 증명 인스턴스에 최종 점수 포함(instances[1]). 게이트가
///             정산 점수를 instances[1]로 강제하므로 점수 위조 불가(Attack2 봉쇄).
///         그 위에서: R4 무허가 제출(누구나 attest), R5 무보상 상환(결과 독립·상한),
///         비소급 단일 정산(Attack4 봉쇄). 오버라이드-패널·소수파 슬래시는
///         구현하지 않는다 — 게이트가 직접 정산하므로 상충표가 없다(KILL 회피).
/// @dev    정직성: halo2 검증자는 외부·검증됨 가정(verify=true ⟹ instances가
///         커밋된 (입력해시, 점수)). 회로 공개 인스턴스에 결정론 점수를 포함하도록
///         하는 확장은 회로측 후속(현 Exp14/16은 로짓 출력). 상환의 무보상성은
///         소ن드니스(거짓 판정엔 유효 증명 불가)에 기댄 오프체인 논증이며, 컨트랙트는
///         상환액을 상한으로 묶고 결과 독립으로 만든다.
contract ZkVerdictGate {
    BondedValidator public immutable bonded;
    IZkVerifier public immutable verifier;
    IERC20 public immutable reimbToken;
    uint256 public immutable reimbCap;   // 상환 상한 (측정 비용 이하로 설정)

    mapping(bytes32 => bool) public proven;       // 단일사용 nullifier
    mapping(bytes32 => uint8) public provenScore;
    mapping(bytes32 => address) public prover;

    event Attested(bytes32 indexed requestHash, address indexed prover, uint8 score);
    event Reimbursed(address indexed prover, uint256 amount);

    error BadVerify();
    error CaseMismatch();   // instances[0] != requestHash (바인딩 실패)
    error ScoreMismatch();  // score != instances[1] (점수 위조)
    error AlreadyProven();
    error BadInstances();

    constructor(address bonded_, address verifier_, address reimbToken_, uint256 reimbCap_) {
        bonded = BondedValidator(bonded_);
        verifier = IZkVerifier(verifier_);
        reimbToken = IERC20(reimbToken_);
        reimbCap = reimbCap_;
    }

    /// @notice 증명 실린 최종 판정 — 누구나 호출(R4). 성공 시 결정론 사건이
    ///         instances[1] 점수로 최종 정산되고, 제출자는 상한 내 상환을 받는다.
    function attest(bytes32 requestHash, uint8 score, bytes calldata proof,
                    uint256[] calldata instances) external {
        if (instances.length < 2) revert BadInstances();
        if (proven[requestHash]) revert AlreadyProven();               // K3 비소급 단일
        if (instances[0] != uint256(requestHash)) revert CaseMismatch(); // K1 바인딩
        if (instances[1] != uint256(score)) revert ScoreMismatch();      // K2 점수 확정
        if (!verifier.verify(proof, instances)) revert BadVerify();

        proven[requestHash] = true;
        provenScore[requestHash] = score;
        prover[requestHash] = msg.sender;

        // 결정론 사건 최종 정산(R2'). 태그는 점수에서 결정 — 증명이 곧 근거.
        string memory tag = score >= 50 ? "proven-correct" : "proven-wrong";
        bonded.submitVerdict(requestHash, score, "", bytes32(uint256(instances[0])), tag);
        emit Attested(requestHash, msg.sender, score);

        // R5 무보상 상환: 결과 독립·상한. 유효 증명에만 지급(소ن드니스 진실 게이트).
        _reimburse(msg.sender);
    }

    /// @dev 상환액은 점수와 무관한 상수(≤ reimbCap). 승자 보상금이 될 수 없다.
    function _reimburse(address to) internal {
        uint256 bal = _tokenBalance();
        uint256 amt = bal < reimbCap ? bal : reimbCap;
        if (amt > 0) {
            require(reimbToken.transfer(to, amt), "reimb");
            emit Reimbursed(to, amt);
        }
    }

    function _tokenBalance() internal view returns (uint256) {
        (bool ok, bytes memory d) = address(reimbToken).staticcall(
            abi.encodeWithSignature("balanceOf(address)", address(this)));
        return ok && d.length >= 32 ? abi.decode(d, (uint256)) : 0;
    }
}
