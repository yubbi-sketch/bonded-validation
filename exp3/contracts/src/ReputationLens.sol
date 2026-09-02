// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {ValidationRegistry} from "./Erc8004Registries.sol";
import {BondedValidator} from "./BondedValidator.sol";

/// @title ReputationLens — "담보 이력 = 신용 점수" (Exp6)
/// @notice 온체인 검증·담보 기록을 읽어 신용 점수와 위험 조정 요구 담보를 계산하는
///         순수 조회(view) 렌즈. 상태 없음 — 누구든 같은 데이터에서 같은 점수를 얻는다.
///
///         설계 원칙 (Exp2 실증 계승):
///         1) 기권 중립 — 점수는 "답한 것 중 맞은 비율"에서 나온다. 기권은 감점 없음.
///         2) 기권은 별도 신호 — abstainRate는 숨기지 않고 따로 노출 (소비자가 판단).
///         3) 정직 할인 — 신용이 높을수록 요구 담보가 싸진다. 이력 없으면 할증.
contract ReputationLens {
    ValidationRegistry public immutable valReg;
    BondedValidator public immutable bonded;
    string public constant ABSTAIN_TAG = "abstain";

    constructor(address valReg_, address bonded_) {
        valReg = ValidationRegistry(valReg_);
        bonded = BondedValidator(bonded_);
    }

    string public constant DISPUTED_TAG = "disputed";
    string public constant UNCHALLENGED_TAG = "unchallenged"; // Exp30 R8 — 소멸(미검증 해제)

    /// @dev 레지스트리 직접 순회 — 정확 합계 (Exp30 §12.6-A① 수리, §13).
    ///      이전 구현은 getSummaryExcluding 의 내림 평균에서 avg·count 로 합계를 복원했다.
    ///      복원 오차 ≤ count−1 이 answered 로 나뉘므로 d ≫ answered 이면 편향이 무계였다
    ///      (정답 100점 10건 + 소멸 990건 → 50, 정확값 100). 순회 합계는 반올림이 없어
    ///      내림은 마지막 나눗셈 한 번(< 1점)뿐이다.
    ///      중립 태그("disputed" 시한환급 · "unchallenged" 소멸)는 점수와 무관하게 통째로
    ///      제외한다 — R8 '소멸은 평판 중립' 을 "50점을 걷어냄" 이 아니라 "답한 이력에
    ///      없음" 으로 실현한다(둘 다 에이전트의 잘못이 증명된 게 아니고, 소멸은 검증도
    ///      아니다 — 규격 v0.1 §1 'VERIFIED 없음'). 예약 태그에 50 이외 점수가 기록돼도
    ///      (judge = EOA 경로, §12.6-A⑤) 렌즈는 흔들리지 않는다. 언더플로 가드는 불필요해져
    ///      제거. 레지스트리(정본·Sepolia 배포본)는 무수정 — 기존 view 인터페이스만 쓴다.
    ///      대가: 가스가 이력 길이에 선형(외부호출 n+1 회) — 수치는 EXP30.md §13.
    function _tally(uint256 agentId)
        internal view returns (uint256 sum, uint64 answered, uint64 abstains)
    {
        bytes32[] memory reqs = valReg.getAgentValidations(agentId);
        bytes32 tAbstain = keccak256(bytes(ABSTAIN_TAG));
        bytes32 tDisputed = keccak256(bytes(DISPUTED_TAG));
        bytes32 tUnchallenged = keccak256(bytes(UNCHALLENGED_TAG));
        for (uint256 i = 0; i < reqs.length; i++) {
            (, , uint8 response, string memory tag, bool responded) =
                valReg.getValidationStatus(reqs[i]);
            if (!responded) continue;
            bytes32 t = keccak256(bytes(tag));
            if (t == tAbstain) { abstains++; continue; }
            if (t == tDisputed || t == tUnchallenged) continue;
            answered++;
            sum += response;
        }
    }

    /// @notice 신용 점수 0~100 = 기권·분쟁환급·소멸 제외 평균 검증 점수(정확 합계 / 답한 건수).
    ///         이력 없으면 (0, 0). 신참 할증(answered < 10)은 소멸·기권으로 우회 불가.
    function creditScore(uint256 agentId) public view returns (uint256 score, uint64 answered) {
        uint256 sum;
        (sum, answered, ) = _tally(agentId);
        if (answered == 0) return (0, 0);
        score = sum / answered;
    }

    /// @notice 기권률(bp, 0~10000) — 감점이 아니라 정보로 노출.
    function abstainRateBp(uint256 agentId) external view returns (uint256) {
        (, uint64 answered, uint64 abstains) = _tally(agentId);
        uint64 total = answered + abstains;
        return total == 0 ? 0 : (uint256(abstains) * 10000) / total;
    }

    /// @notice 위험 조정 요구 담보 — 기준 담보의 배율(bp).
    ///         이력 <10건: 15000bp(1.5x, 신참 할증)
    ///         그 외: 5000 + (100-score)*100 → score 100=0.5x · 50=1.0x · 0=1.5x
    function requiredBondBp(uint256 agentId) public view returns (uint256) {
        (uint256 score, uint64 answered) = creditScore(agentId);
        if (answered < 10) return 15000;
        return 5000 + (100 - score) * 100;
    }

    /// @notice 요구 담보 절대액 = BondedValidator 기준 담보 × 배율.
    function requiredBond(uint256 agentId) external view returns (uint256) {
        return (bonded.minBondPerClaim() * requiredBondBp(agentId)) / 10000;
    }
}
