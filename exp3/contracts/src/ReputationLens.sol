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

    /// @notice 신용 점수 0~100 = 기권·분쟁환급 제외 평균 검증 점수. 이력 없으면 0.
    /// @dev 분쟁 타임아웃 환급은 점수 50 고정 태그 "disputed"로 기록되므로
    ///      (JudgePanelV2), 합계에서 50×건수를 걷어내면 중립화된다 — 분쟁은
    ///      에이전트의 잘못이 증명된 게 아니므로 신용에 중립이어야 한다.
    function creditScore(uint256 agentId) public view returns (uint256 score, uint64 answered) {
        (uint64 count, uint256 avg) = valReg.getSummaryExcluding(agentId, ABSTAIN_TAG);
        uint64 d = valReg.getSummaryByTag(agentId, DISPUTED_TAG);
        if (count <= d) return (0, 0);
        answered = count - d;
        score = (avg * count - 50 * uint256(d)) / answered;
    }

    /// @notice 기권률(bp, 0~10000) — 감점이 아니라 정보로 노출.
    function abstainRateBp(uint256 agentId) external view returns (uint256) {
        (, uint64 answered) = creditScore(agentId);
        uint64 abstains = valReg.getSummaryByTag(agentId, ABSTAIN_TAG);
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
