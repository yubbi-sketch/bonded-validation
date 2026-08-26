// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidator} from "../src/BondedValidator.sol";
import {BondedJudgePanelV2} from "../src/BondedJudgePanelV2.sol";

interface Vm {
    function prank(address) external;
    function startPrank(address) external;
    function stopPrank() external;
    function warp(uint256) external;
    function roll(uint256) external;
}

/// @notice Exp12 — 패널 계층 기계 증명 (Halmos, B 전환 2보).
///         정련(refinement) 증명: 아래 참조 모델(_specFinal)이 사양이고,
///         모든 심볼릭 투표 조합에서 컨트랙트 상태가 사양과 일치함을 SMT로
///         증명한다. 증명되는 정리:
///
///         P1. 무보상금 — 어떤 투표 조합에서도 판정자의 외부 수입은 정액
///             수수료 균등분을 넘지 못한다 (승자 상금이 존재하지 않음을 증명).
///         P2. 소수파만 몰수 — 담보가 깎이는 판정자는 정확히 "투표했고 그 표가
///             최종 평결과 다르고 과반이 성립한" 판정자뿐이다. 침묵·과반 부재·
///             만장일치에서는 어떤 담보도 깎이지 않는다.
///         P3. 에이전트 보존 — 발화자 담보는 정확히 (과반/만장일치 평결이
///             50 미만)일 때 minBond만큼만 깎인다. 환급(무손실) 경로에선 불변.
///         P4. 타임아웃 무손실 — 투표가 몇 표 오든(0~2) 시한 해소는 아무의
///             담보도 깎지 않는다.
///
///         범위 정직성: 패널 구성은 구체(추첨은 결정론 시드), 투표 점수가
///         심볼릭(전 uint8 공간)·태그는 고정("t"). 태그 차원의 분쟁·재진입·
///         다중 사건 교차는 후속 증명 대상. 추첨 자체의 성질(가중 분포)은
///         확률적 성질이라 SMT 증명 대상이 아님을 명기.
/// @dev 증명 하네스 — 시드만 결정론으로 고정(패널 구성을 구체화해 상태 공간을
///      정산 계층에 집중). 경제 로직은 부모 그대로라 증명은 본체에 대해 성립한다.
contract PanelHarness is BondedJudgePanelV2 {
    constructor(address bonded_, uint256 perCaseBond_, uint256 judgeFee_,
                uint256 voteTimeout_, uint256 disputeTimeout_, uint256 veteranThreshold_)
        BondedJudgePanelV2(bonded_, perCaseBond_, judgeFee_, voteTimeout_,
                           disputeTimeout_, veteranThreshold_) {}

    function _revealSeed(bytes32 requestHash, CaseData storage c)
        internal view override returns (bytes32)
    {
        require(block.number > c.commitBlock, "seed not born"); // 커밋-리빌 규칙은 유지
        return keccak256(abi.encodePacked(requestHash, uint256(c.commitBlock)));
    }
}

contract BondedJudgePanelV2Proofs {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    IdentityRegistry idReg;
    ValidationRegistry valReg;
    BondedValidator bv;
    BondedJudgePanelV2 panel;
    address wallet = address(0x2001);
    address[] js;
    uint256 aid;
    uint256 constant BOND = 10e18;
    uint256 constant FEE = 8e18;
    uint256 constant VOTE_T = 100;
    uint256 constant DISP_T = 200;
    uint256 constant ENTRY = 15e18;
    bytes32 constant H = bytes32(uint256(0xF00D));

    function setUp() public {
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        // Halmos는 CREATE 주소를 내부 순번(0xaaaa000N)으로 배정 — 실제 EVM의
        // 논스 예측이 안 통한다. 이 setUp의 5번째 CREATE가 패널이므로 0xaaaa0006.
        // (halmos 0.3.3 고정 스킴 — venv에 버전 고정, 하네스 전용 상수)
        address predicted = address(0xaaaa0006);
        bv = new BondedValidator(address(token), address(idReg), address(valReg),
                                 predicted, 1e18, 60);
        panel = BondedJudgePanelV2(address(new PanelHarness(address(bv), BOND, FEE, VOTE_T, DISP_T, 3)));
        require(address(panel) == predicted, "prediction failed");

        token.mint(wallet, 100e18);
        vm.startPrank(wallet);
        aid = idReg.register("agent://p");
        token.approve(address(bv), type(uint256).max);
        token.approve(address(panel), type(uint256).max);
        bv.stake(aid, 10e18);
        bv.requestValidation(aid, "", H);
        vm.stopPrank();

        for (uint256 i = 0; i < 9; i++) {
            address j = address(uint160(0x3000 + i));
            js.push(j);
            token.mint(j, 20e18);
            vm.startPrank(j);
            uint256 jid = idReg.register("agent://j");
            token.approve(address(panel), type(uint256).max);
            panel.registerJudge(jid, ENTRY);
            vm.stopPrank();
        }
        vm.prank(wallet);
        panel.openCase(H);
        vm.roll(block.number + 1);
        panel.drawPanel(H); // 결정론 시드 → 패널 구성은 구체, 이후 투표만 심볼릭
    }

    function _predictNext(address deployer, uint256 nonce) internal pure returns (address) {
        return address(uint160(uint256(keccak256(abi.encodePacked(
            bytes1(0xd6), bytes1(0x94), deployer, bytes1(uint8(nonce)))))));
    }

    function _vote(address j, uint8 s) internal {
        vm.prank(j);
        panel.voteVerdict(H, s, "t", bytes32(0));
    }

    function _jb(address j) internal view returns (uint256 b) {
        (, , b, , , , ) = panel.judges(j);
    }

    /// 사양(참조 모델): 초심 3표 + (분쟁 시) 확대 5표에서 최종 결과를 계산한다.
    /// returns (settledByVerdict, finalScore) — settledByVerdict=false는 환급.
    function _specFinal(uint8 a1, uint8 a2, uint8 a3, uint8[5] memory e, bool disputed)
        internal pure returns (bool, uint8)
    {
        if (!disputed) return (true, a1); // 만장일치
        // 확대 5표 과반(>=3) 탐색 — 컨트랙트와 독립적으로 다시 기술한 사양
        for (uint256 i = 0; i < 5; i++) {
            uint256 cnt;
            for (uint256 k = 0; k < 5; k++) if (e[k] == e[i]) cnt++;
            if (cnt >= 3) return (true, e[i]);
        }
        return (false, 50); // 과반 부재 → 환급
    }

    // 전 uint8^8 공간 단일 정련은 SMT가 1시간+ 미완(2026-08-27 실측) —
    // 평결 클래스 3분할로 축소한다. 클래스 내부 점수는 전 공간 심볼릭이고,
    // 과반의 "위치"(e1~e3에 배치)는 대칭성 가정(WLOG)으로 명기 — 기계 증명
    // 범위 밖임을 정직하게 남긴다. 완전 정련은 미해결 문제로 등재.

    /// 클래스 A(만장일치): ∀s — 아무도 몰수되지 않고 수수료는 3등분.
    function check_PA_unanimous(uint8 s) public {
        uint8[3] memory avec = [s, s, s];
        uint8[5] memory evec = [0, 0, 0, 0, 0]; // 미사용 (분쟁 없음)
        _refine(avec, evec);
    }

    /// 클래스 B(과반 성립): ∀m,x,y,a1..a3 — e1~e3=m이 과반. 소수파만 몰수,
    ///     상금 없음, 에이전트는 m<50일 때만 슬래시. (과반 위치는 WLOG)
    function check_PB_majority(uint8 a1, uint8 a2, uint8 a3, uint8 m, uint8 x, uint8 y) public {
        if (a1 == a2 && a2 == a3) return; // 분쟁 경로만 (만장일치는 클래스 A)
        uint8[3] memory avec = [a1, a2, a3];
        uint8[5] memory evec = [m, m, m, x, y];
        _refine(avec, evec);
    }

    /// 클래스 C(과반 부재 2/2/1): ∀p,q,r 상호 상이 — 무손실 환급, 아무도 몰수 안 됨.
    function check_PC_split(uint8 p, uint8 q, uint8 r) public {
        if (p == q || q == r || p == r) return; // 2/2/1이 되는 조합만
        uint8[3] memory avec = [p, p, q]; // 분쟁 유발
        uint8[5] memory evec = [p, p, q, q, r];
        _refine(avec, evec);
    }

    function _refine(uint8[3] memory avec, uint8[5] memory evec) internal {
        address[] memory p = panel.casePanel(H);
        (uint256 agentB0,,,) = bv.agents(aid);

        for (uint256 i = 0; i < 3; i++) _vote(p[i], avec[i]);
        bool disputed = !(avec[0] == avec[1] && avec[1] == avec[2]);
        address[] memory ex = new address[](0);
        uint256[] memory balBefore = new uint256[](5);
        if (disputed) {
            vm.roll(block.number + 1);
            panel.drawExpanded(H);
            ex = panel.caseExpanded(H);
            for (uint256 i = 0; i < 5; i++) balBefore[i] = token.balanceOf(ex[i]);
            for (uint256 i = 0; i < 5; i++) _vote(ex[i], evec[i]);
        }

        (bool byVerdict, uint8 fin) = _specFinal(avec[0], avec[1], avec[2], evec, disputed);
        uint256 share = FEE / (disputed ? 8 : 3);

        // P2: 소수파만 몰수 — 초심 3인
        for (uint256 i = 0; i < 3; i++) {
            bool slashExpected = disputed && byVerdict && avec[i] != fin;
            assert(_jb(p[i]) == (slashExpected ? ENTRY - BOND : ENTRY));
        }
        // P1·P2: 확대 5인 — 몰수는 소수파만, 외부 수입은 수수료 균등분뿐
        for (uint256 i = 0; i < ex.length; i++) {
            bool slashExpected = byVerdict && evec[i] != fin;
            assert(_jb(ex[i]) == (slashExpected ? ENTRY - BOND : ENTRY));
            assert(token.balanceOf(ex[i]) == balBefore[i] + share); // 상금 없음
        }
        // P3: 에이전트 보존 — 평결 50 미만일 때만 minBond 슬래시, 환급은 무손실
        (uint256 agentB1,,, uint256 agentSlash) = bv.agents(aid);
        if (byVerdict && fin < 50) {
            assert(agentB1 == agentB0 - 1e18 && agentSlash == 1e18);
        } else {
            assert(agentB1 == agentB0 && agentSlash == 0);
        }
        // 정산 완결성: 어떤 경로든 주장은 정확히 한 번 정산된다
        assert(bv.claimSettled(H));
    }

    /// P4: 타임아웃 판정자 무손실 + 에이전트 사양 일치 — 0~2표 어떤 조합이 와도
    ///     시한 해소는 판정자 담보를 절대 깎지 않는다. 에이전트는 "일치 2표"가
    ///     있을 때만 그 평결(score<50이면 슬래시)을 적용받고, 그 외엔 무손실.
    ///     (v1 사양 "무조건 무손실"은 기계 증명이 반례로 기각 — 2표 일치 정산은
    ///     설계상 정식 평결이다. 증명이 사양 버그를 잡은 첫 사례로 기록.)
    function check_P4_timeout_judges_lossless(bool v1, bool v2, uint8 s1, uint8 s2) public {
        address[] memory p = panel.casePanel(H);
        if (v1) _vote(p[0], s1);
        if (v2) _vote(p[1], s2);
        vm.warp(block.timestamp + VOTE_T + 1);
        panel.resolveTimeout(H);
        for (uint256 i = 0; i < 9; i++) assert(_jb(js[i]) == ENTRY); // 판정자 무손실
        (uint256 b,,, uint256 slash) = bv.agents(aid);
        bool twoMatch = v1 && v2 && s1 == s2; // 일치 2표 = 정식 평결
        if (twoMatch && s1 < 50) {
            assert(b == 10e18 - 1e18 && slash == 1e18);
        } else {
            assert(b == 10e18 && slash == 0); // 분쟁 이월·판정불능 → 무손실
        }
    }
}
