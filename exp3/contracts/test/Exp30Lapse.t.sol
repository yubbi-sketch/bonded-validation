// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LabToken} from "../src/LabToken.sol";
import {IdentityRegistry, ValidationRegistry} from "../src/Erc8004Registries.sol";
import {BondedValidatorV3} from "../src/BondedValidatorV3.sol";
import {BondedJudgePanelV3} from "../src/BondedJudgePanelV3.sol";
import {ReputationLens} from "../src/ReputationLens.sol";

interface Vm {
    function prank(address) external;
    function startPrank(address) external;
    function stopPrank() external;
    function warp(uint256) external;
    function roll(uint256) external;
    function expectRevert(bytes calldata) external;
}

/// @notice Exp30 — 미개설 주장의 소멸(Optimistic Lapse) Forge 실측. Sepolia 파라미터
///         (docs/deployments.md) + challengeWindow W = 86,400s(잠정, EXP30.md R10).
///         K2(a) 활성 상한 T_max = W + 2·voteTimeout + disputeTimeout = 180,000s ·
///         K2(b) 웨지 · K4(a)(b)(c)(d) 공격면 · R2/R3/R5/R9 · 낙관적창 반박 A 재현.
///         정직성: 이것은 실측(몇 개 사례)이지 증명이 아니다 — ∀ 는 Halmos
///         (BondedValidatorV3Proofs · BondedJudgePanelV3Proofs) 가 맡는다.
contract Exp30LapseTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    LabToken token;
    IdentityRegistry idReg;
    ValidationRegistry valReg;
    BondedValidatorV3 bv;      // judge = panel
    BondedJudgePanelV3 panel;
    ReputationLens lens;
    BondedValidatorV3 bvD;     // judge = this (직접 판정 경로: ZkVerdictGate·Exp11 하네스 대리)
    ReputationLens lensD;

    address wallet = address(uint160(uint256(keccak256("exp30.wallet"))));
    address challenger = address(uint160(uint256(keccak256("exp30.challenger"))));
    address stranger = address(0xBEEF);
    address constant BURN = 0x000000000000000000000000000000000000dEaD;
    address[] js;
    uint256 aid;
    uint256 aidD;

    // Sepolia v0.2.1 파라미터 + W 잠정
    uint256 constant MIN_BOND = 1e18;
    uint256 constant UNBOND = 3600;
    uint256 constant BOND = 10e18;
    uint256 constant FEE = 1e18;
    uint256 constant VOTE_T = 3600;
    uint256 constant DISP_T = 86400;
    uint256 constant W = 86400;
    uint256 constant T_MAX = W + 2 * VOTE_T + DISP_T; // 180,000
    uint256 constant ENTRY = 15e18;
    uint256 t0;

    function setUp() public {
        token = new LabToken();
        idReg = new IdentityRegistry();
        valReg = new ValidationRegistry();
        address predicted = _predictNext(address(this), 5);
        bv = new BondedValidatorV3(address(token), address(idReg), address(valReg),
                                   predicted, MIN_BOND, UNBOND, W);
        panel = new BondedJudgePanelV3(address(bv), BOND, FEE, VOTE_T, DISP_T, 3);
        require(address(panel) == predicted, "prediction failed");
        lens = new ReputationLens(address(valReg), address(bv));
        bvD = new BondedValidatorV3(address(token), address(idReg), address(valReg),
                                    address(this), MIN_BOND, UNBOND, W);
        lensD = new ReputationLens(address(valReg), address(bvD));

        token.mint(wallet, 100e18);
        vm.startPrank(wallet);
        aid = idReg.register("agent://exp30");
        aidD = idReg.register("agent://exp30-direct");
        token.approve(address(bv), type(uint256).max);
        token.approve(address(bvD), type(uint256).max);
        token.approve(address(panel), type(uint256).max);
        bv.stake(aid, 10e18);
        bvD.stake(aidD, 10e18);
        vm.stopPrank();

        token.mint(challenger, 1000e18);
        vm.prank(challenger);
        token.approve(address(panel), type(uint256).max);

        vm.warp(1_000_000);
        t0 = block.timestamp;
    }

    // ─── helpers ─────────────────────────────────────────────────

    function _predictNext(address deployer, uint256 nonce) internal pure returns (address) {
        return address(uint160(uint256(keccak256(abi.encodePacked(
            bytes1(0xd6), bytes1(0x94), deployer, bytes1(uint8(nonce)))))));
    }

    function _judges(uint256 n) internal {
        for (uint256 i = 0; i < n; i++) _judge(address(uint160(uint256(keccak256(abi.encodePacked("exp30.judge", i))))));
    }

    function _judge(address j) internal {
        js.push(j);
        token.mint(j, 20e18);
        vm.startPrank(j);
        uint256 jid = idReg.register("agent://judge");
        token.approve(address(panel), type(uint256).max);
        panel.registerJudge(jid, ENTRY);
        vm.stopPrank();
    }

    function _claim(bytes32 h) internal {
        vm.prank(wallet);
        bv.requestValidation(aid, "", h);
    }

    function _claimD(bytes32 h) internal {
        vm.prank(wallet);
        bvD.requestValidation(aidD, "", h);
    }

    function _open(bytes32 h, address opener) internal {
        vm.prank(opener);
        panel.openCase(h);
    }

    function _draw(bytes32 h) internal returns (address[] memory p) {
        vm.roll(block.number + 1);
        panel.drawPanel(h);
        p = panel.casePanel(h);
    }

    function _vote(address j, bytes32 h, uint8 s, string memory tag) internal {
        vm.prank(j);
        panel.voteVerdict(h, s, tag, bytes32(0));
    }

    function _agent() internal view returns (uint256 b, uint256 r, uint256 s) {
        (b, r,, s) = bv.agents(aid);
    }

    function _judgeState(address j) internal view returns (uint256 b, uint256 atRisk, uint256 settled, uint256 slashed) {
        (, , b, atRisk, , settled, slashed) = panel.judges(j);
    }

    function _phase(bytes32 h) internal view returns (BondedJudgePanelV3.Phase ph) {
        (ph,,,,) = panel.caseStatus(h);
    }

    function _tagIs(bytes32 h, string memory want) internal view returns (bool ok, uint8 score) {
        string memory tag;
        bool responded;
        (, , score, tag, responded) = valReg.getValidationStatus(h);
        ok = responded && keccak256(bytes(tag)) == keccak256(bytes(want));
    }

    function _bigTag(uint256 n) internal pure returns (string memory s) {
        bytes memory b = new bytes(n);
        for (uint256 i = 0; i < n; i++) b[i] = "z";
        s = string(b);
    }

    function _withdrawWithin(uint256 deadline) internal {
        vm.prank(wallet);
        bv.requestUnbond(aid);
        vm.warp(block.timestamp + UNBOND);
        vm.prank(wallet);
        bv.withdraw(aid);
        require(block.timestamp - t0 <= deadline, "withdraw past bound");
    }

    // ═══ K2(a) 활성 상한 — 도달 가능한 상태 전부에서 t_claim + T_max 안 정산 ═══

    /// 미개설: 정확히 t_claim+W 에 제3자가 소멸 → 무손실·레지스트리 50/"unchallenged"·
    /// 토큰 이동 0. 유동 토큰 0 인 에이전트가 + unbondDelay 안에 인출(v0.2.1 프로브 4 공백 폐쇄).
    function test_K2a_unopened_lapses_at_W_zero_liquidity_agent_withdraws() public {
        _judges(9);
        bytes32 h = bytes32(uint256(0x30));
        _claim(h);
        uint256 liquid = token.balanceOf(wallet);
        vm.prank(wallet);
        token.transfer(stranger, liquid); // 유동 토큰 0
        require(token.balanceOf(wallet) == 0, "liquidity not zero");

        vm.warp(t0 + W - 1);
        vm.expectRevert("window open");
        bv.settleUnchallenged(h);

        vm.warp(t0 + W);
        uint256 bvBal = token.balanceOf(address(bv));
        vm.prank(stranger);
        bv.settleUnchallenged(h);
        require(bv.claimSettled(h) && !bv.engaged(h), "not lapsed");
        (uint256 b, uint256 r, uint256 s) = _agent();
        require(b == 10e18 && r == 0 && s == 0, "lapse not lossless");
        require(token.balanceOf(address(bv)) == bvBal, "token moved on lapse");
        (bool ok, uint8 score) = _tagIs(h, "unchallenged");
        require(ok && score == 50, "registry not 50/unchallenged");

        vm.prank(stranger);
        vm.expectRevert("claim settled");
        panel.openCase(h); // 소멸 뒤 개설 불가

        _withdrawWithin(T_MAX + UNBOND);
        require(token.balanceOf(wallet) == 10e18, "stake not returned");
    }

    /// 창 마지막 초 개설 · 풀 0 → 표식이 소멸을 막음 → 커밋 시한에 리셋(수수료 반환·None) → 즉시 소멸.
    /// 총 잠금 = W − 1 + voteTimeout ≤ T_max.
    function test_K2a_last_second_open_pool0_resets_then_lapses() public {
        bytes32 h = bytes32(uint256(0x31));
        _claim(h);
        vm.warp(t0 + W - 1);
        uint256 c0 = token.balanceOf(challenger);
        _open(h, challenger);
        require(bv.engaged(h), "not engaged");
        require(token.balanceOf(challenger) == c0 - FEE, "fee not taken");
        vm.roll(block.number + 1);
        vm.expectRevert("pool too small");
        panel.drawPanel(h);

        vm.warp(t0 + W + 1000);
        vm.expectRevert("engaged");
        bv.settleUnchallenged(h); // 표식 봉쇄
        vm.expectRevert("commit window open");
        panel.resolveTimeout(h);

        vm.warp(t0 + W - 1 + VOTE_T);
        panel.resolveTimeout(h); // 리셋
        require(_phase(h) == BondedJudgePanelV3.Phase.None, "not reset to None");
        require(!bv.engaged(h) && !bv.claimSettled(h), "reset must not settle");
        require(token.balanceOf(challenger) == c0, "fee not returned");
        (uint256 b, uint256 r, uint256 s) = _agent();
        require(b == 10e18 && r == MIN_BOND && s == 0, "reset touched bond");

        vm.prank(stranger);
        bv.settleUnchallenged(h);
        require(bv.claimSettled(h), "not lapsed after reset");
        require(block.timestamp - t0 == W - 1 + VOTE_T, "timing");
        require(block.timestamp - t0 <= T_MAX, "exceeds T_max");
        _withdrawWithin(T_MAX + UNBOND);
    }

    /// 풀 2 (추첨 불가) — 풀 0 과 동일 경로.
    function test_K2a_pool2_resets_then_lapses() public {
        _judges(2);
        bytes32 h = bytes32(uint256(0x32));
        _claim(h);
        vm.warp(t0 + W - 1);
        _open(h, challenger);
        vm.roll(block.number + 1);
        vm.expectRevert("pool too small");
        panel.drawPanel(h);
        vm.warp(t0 + W - 1 + VOTE_T);
        panel.resolveTimeout(h);
        bv.settleUnchallenged(h);
        require(bv.claimSettled(h), "not lapsed");
        require(block.timestamp - t0 <= T_MAX, "exceeds T_max");
        for (uint256 i = 0; i < 2; i++) {
            (uint256 b, uint256 atRisk,,) = _judgeState(js[i]);
            require(b == ENTRY && atRisk == 0, "judge touched");
        }
    }

    /// 리셋 → 창 안 재개설 → 다시 리셋 → 창 닫힘 → 재개설 불가(수수료 미차감) → 소멸. 그리핑 연장 유계.
    function test_K2a_reset_reopen_reset_lapse_bounded() public {
        _judges(2);
        bytes32 h = bytes32(uint256(0x33));
        _claim(h);
        _open(h, challenger);                       // t0
        vm.warp(t0 + VOTE_T);
        panel.resolveTimeout(h);                    // 리셋 1
        require(!bv.engaged(h) && _phase(h) == BondedJudgePanelV3.Phase.None, "reset1");
        vm.warp(t0 + W - 1);
        _open(h, challenger);                       // 재개설 (창 안)
        require(bv.engaged(h), "reopen failed");
        vm.warp(t0 + W - 1 + VOTE_T);
        panel.resolveTimeout(h);                    // 리셋 2
        uint256 c0 = token.balanceOf(challenger);
        vm.prank(challenger);
        vm.expectRevert("window closed");
        panel.openCase(h);                          // 창 밖 재개설 불가
        require(token.balanceOf(challenger) == c0, "fee taken on failed open");
        bv.settleUnchallenged(h);
        require(bv.claimSettled(h), "not lapsed");
        require(block.timestamp - t0 <= T_MAX, "exceeds T_max");
    }

    /// 리셋 뒤 재개설된 사건은 깨끗하게 추첨·정산된다(onCase·votes 잔재 없음).
    function test_reopen_after_reset_draws_and_settles_cleanly() public {
        _judges(9);
        bytes32 h = bytes32(uint256(0x34));
        _claim(h);
        _open(h, challenger);
        vm.warp(t0 + VOTE_T);
        panel.resolveTimeout(h);                    // 리셋 (추첨 없이)
        _open(h, challenger);                       // 재개설
        address[] memory p = _draw(h);
        require(p.length == 3, "panel size");
        (, , uint8 iv, ,) = panel.caseStatus(h);
        require(iv == 0, "stale votes");
        for (uint256 i = 0; i < 3; i++) _vote(p[i], h, 100, "ok");
        require(bv.claimSettled(h), "not settled");
        (uint256 b,, uint256 s) = _agent();
        require(b == 10e18 && s == 0, "agent harmed");
    }

    /// 초심 2표 일치 — 창 마지막 초 개설, 커밋 시한 1초 전 추첨, 투표 시한 정산.
    function test_K2a_two_matching_votes_timeout_settles_within_Tmax() public {
        _judges(9);
        bytes32 h = bytes32(uint256(0x35));
        _claim(h);
        vm.warp(t0 + W - 1);
        _open(h, challenger);
        vm.warp(t0 + W - 1 + VOTE_T - 1);
        address[] memory p = _draw(h);
        uint256 openedAt = block.timestamp;
        _vote(p[0], h, 100, "ok");
        _vote(p[1], h, 100, "ok");
        vm.warp(openedAt + VOTE_T);
        panel.resolveTimeout(h);
        require(bv.claimSettled(h), "not settled");
        (bool ok, uint8 score) = _tagIs(h, "ok");
        require(ok && score == 100, "verdict not recorded");
        require(block.timestamp - t0 <= T_MAX, "exceeds T_max");
    }

    /// 확대 2/2/1 분할 — 무손실 환급(50/"disputed"), T_max 안.
    function test_K2a_expanded_split_221_refunds_within_Tmax() public {
        _judges(9);
        bytes32 h = bytes32(uint256(0x36));
        _claim(h);
        vm.warp(t0 + W - 1);
        _open(h, challenger);
        vm.warp(t0 + W - 1 + VOTE_T - 1);
        address[] memory p = _draw(h);
        _vote(p[0], h, 100, "a");
        _vote(p[1], h, 100, "a");
        _vote(p[2], h, 0, "b");                      // → ExpandedCommit
        vm.roll(block.number + 1);
        panel.drawExpanded(h);
        address[] memory e = panel.caseExpanded(h);
        require(e.length == 5, "expanded size");
        _vote(e[0], h, 100, "a");
        _vote(e[1], h, 100, "a");
        _vote(e[2], h, 0, "b");
        _vote(e[3], h, 0, "b");
        _vote(e[4], h, 50, "c");
        require(bv.claimSettled(h), "not settled");
        (bool ok, uint8 score) = _tagIs(h, "disputed");
        require(ok && score == 50, "not disputed refund");
        (uint256 b,, uint256 s) = _agent();
        require(b == 10e18 && s == 0, "agent harmed on split");
        require(block.timestamp - t0 <= T_MAX, "exceeds T_max");
    }

    /// 확대 커밋 시한(아무도 확대 추첨 안 함) — T_max 안.
    function test_K2a_expanded_commit_timeout_within_Tmax() public {
        _judges(9);
        bytes32 h = bytes32(uint256(0x37));
        _claim(h);
        vm.warp(t0 + W - 1);
        _open(h, challenger);
        vm.warp(t0 + W - 1 + VOTE_T - 1);
        address[] memory p = _draw(h);
        uint256 openedAt = block.timestamp;
        _vote(p[0], h, 100, "a");
        _vote(p[1], h, 0, "b");                      // 분쟁, p[2] 침묵
        vm.warp(openedAt + VOTE_T);
        panel.resolveTimeout(h);                    // → ExpandedCommit
        require(_phase(h) == BondedJudgePanelV3.Phase.ExpandedCommit, "not expanded commit");
        uint256 disputedAt = block.timestamp;
        vm.warp(disputedAt + DISP_T);
        panel.resolveTimeout(h);                    // 환급
        require(bv.claimSettled(h), "not settled");
        require(block.timestamp - t0 <= T_MAX, "exceeds T_max");
    }

    /// 최악 경로: 창 마지막 초 개설 → 커밋 시한 직전 추첨 → 초심 분쟁 시한 → 확대 추첨 → 확대 시한.
    /// 정산 시각 = t_claim + T_max − 2 (상한 R11 실측). 판정자 무손실·수수료 균등·인출 +unbondDelay.
    function test_K2a_worst_path_expanded_timeout_hits_Tmax_bound() public {
        _judges(9);
        bytes32 h = bytes32(uint256(0x38));
        _claim(h);
        vm.warp(t0 + W - 1);
        _open(h, challenger);
        vm.warp(t0 + W - 1 + VOTE_T - 1);
        address[] memory p = _draw(h);
        uint256 openedAt = block.timestamp;
        uint256 p0 = token.balanceOf(p[0]);
        uint256 p1 = token.balanceOf(p[1]);
        _vote(p[0], h, 100, "a");
        _vote(p[1], h, 0, "b");
        vm.warp(openedAt + VOTE_T);
        panel.resolveTimeout(h);                    // → ExpandedCommit
        uint256 disputedAt = block.timestamp;
        vm.roll(block.number + 1);
        panel.drawExpanded(h);                      // Expanded, 아무도 투표 안 함
        require(panel.caseExpanded(h).length == 5, "expanded not drawn");
        vm.warp(disputedAt + DISP_T - 1);
        vm.expectRevert("dispute window open");
        panel.resolveTimeout(h);
        vm.warp(disputedAt + DISP_T);
        panel.resolveTimeout(h);                    // 환급
        require(bv.claimSettled(h), "not settled");
        require(block.timestamp - t0 == T_MAX - 2, "worst path timing");
        require(block.timestamp - t0 <= T_MAX, "exceeds T_max");
        (uint256 b,, uint256 s) = _agent();
        require(b == 10e18 && s == 0, "agent harmed");
        for (uint256 i = 0; i < 9; i++) {
            (uint256 jb, uint256 atRisk,,) = _judgeState(js[i]);
            require(jb == ENTRY && atRisk == 0, "judge harmed on timeout");
        }
        require(token.balanceOf(p[0]) == p0 + FEE / 2 && token.balanceOf(p[1]) == p1 + FEE / 2, "fee split");
        _withdrawWithin(T_MAX + UNBOND);
    }

    // ═══ K2(b) 웨지 — score>100 · 32KB 태그 · 예약 태그 ═══

    function test_K2b_wedge_closed_score_range_tag_length_reserved() public {
        _judges(9);
        bytes32 h = bytes32(uint256(0x40));
        _claim(h);
        _open(h, challenger);
        address[] memory p = _draw(h);

        vm.prank(p[0]);
        vm.expectRevert("score range");
        panel.voteVerdict(h, 101, "x", bytes32(0));
        vm.prank(p[0]);
        vm.expectRevert("score range");
        panel.voteVerdict(h, 255, "x", bytes32(0));
        vm.prank(p[0]);
        vm.expectRevert("tag too long");
        panel.voteVerdict(h, 100, _bigTag(32768), bytes32(0));
        vm.prank(p[0]);
        vm.expectRevert("tag too long");
        panel.voteVerdict(h, 100, _bigTag(1025), bytes32(0));
        vm.prank(p[0]);
        vm.expectRevert("reserved tag");
        panel.voteVerdict(h, 50, "unchallenged", bytes32(0));
        vm.prank(p[0]);
        vm.expectRevert("reserved tag");
        panel.voteVerdict(h, 50, "disputed", bytes32(0));

        // 경계: 정확히 1024B 태그·score 100 두 표 → 시한 해소 무되돌림(웨지 폐쇄)
        _vote(p[0], h, 100, _bigTag(1024));
        _vote(p[1], h, 100, _bigTag(1024));
        vm.warp(block.timestamp + VOTE_T);
        panel.resolveTimeout(h);
        require(bv.claimSettled(h), "wedge not closed");
    }

    // ═══ K4 공격면 상한 ═══

    /// K4(a) 소멸 1회의 토큰 이동 = 0 (모든 관련 잔고·totalSupply 불변).
    function test_K4a_lapse_moves_zero_tokens() public {
        _judges(3);
        bytes32 h = bytes32(uint256(0x50));
        _claim(h);
        vm.warp(t0 + W);
        address[7] memory who = [address(bv), address(panel), wallet, challenger, stranger, BURN, js[0]];
        uint256[7] memory before;
        for (uint256 i = 0; i < 7; i++) before[i] = token.balanceOf(who[i]);
        uint256 supply = token.totalSupply();
        vm.prank(stranger);
        bv.settleUnchallenged(h);
        for (uint256 i = 0; i < 7; i++) require(token.balanceOf(who[i]) == before[i], "balance moved");
        require(token.totalSupply() == supply, "supply moved");
    }

    /// K4(b) B5 형: 풀 전체 장악(ρ=1, 판정자 3인 + 개설자 = 공격자)이 정답 주장을 개설해 0점 만장일치로
    /// 그리핑 — 연합의 프로토콜 내 순수입 = −F + F(수수료 환류) = 0 ≤ 0. 몰수분 1e18 은 누구에게도 가지 않는다.
    function test_K4b_captured_pool_griefing_correct_claim_net_income_zero() public {
        address[3] memory atk;
        for (uint256 i = 0; i < 3; i++) {
            atk[i] = address(uint160(uint256(keccak256(abi.encodePacked("exp30.atk", i)))));
            _judge(atk[i]);
        }
        address opener = address(uint160(uint256(keccak256("exp30.atk.opener"))));
        token.mint(opener, FEE);
        vm.prank(opener);
        token.approve(address(panel), FEE);
        uint256 liquid0 = token.balanceOf(opener);
        for (uint256 i = 0; i < 3; i++) liquid0 += token.balanceOf(atk[i]);

        bytes32 h = bytes32(uint256(0x51));
        _claim(h);
        _open(h, opener);
        address[] memory p = _draw(h);
        for (uint256 i = 0; i < 3; i++) require(p[i] == atk[0] || p[i] == atk[1] || p[i] == atk[2], "pool not captured");
        for (uint256 i = 0; i < 3; i++) _vote(p[i], h, 0, "wrong");
        (uint256 b,, uint256 s) = _agent();
        require(b == 9e18 && s == 1e18, "griefing slash happened");

        uint256 liquid1 = token.balanceOf(opener);
        for (uint256 i = 0; i < 3; i++) liquid1 += token.balanceOf(atk[i]);
        // 연합 순수입 = −F + 3·⌊F/3⌋ = −(F mod 3) = −1 wei (잔여는 패널 컨트랙트에 남음, v0.2.1 성질)
        require(liquid0 - liquid1 == FEE % 3, "coalition net income != -(F mod 3)");
        for (uint256 i = 0; i < 3; i++) {
            (uint256 jb, uint256 atRisk,,) = _judgeState(atk[i]);
            require(jb == ENTRY && atRisk == 0, "judge bond changed");
        }
        require(token.balanceOf(address(bv)) == 10e18, "slashed tokens left BV");
        require(int256(liquid1) - int256(liquid0) <= 0, "K4(b) violated");
    }

    /// K4(b) B3 형: 2석 + 침묵 1석 시한 평결 — 연합 순수입 = −F + 2·(F/2) = 0 ≤ 0.
    function test_K4b_two_seats_silent_third_timeout_verdict_net_income_zero() public {
        address[2] memory atk;
        for (uint256 i = 0; i < 2; i++) {
            atk[i] = address(uint160(uint256(keccak256(abi.encodePacked("exp30.atk2", i)))));
            _judge(atk[i]);
        }
        address honest = address(uint160(uint256(keccak256("exp30.honest.judge"))));
        _judge(honest);
        address opener = address(uint160(uint256(keccak256("exp30.atk2.opener"))));
        token.mint(opener, FEE);
        vm.prank(opener);
        token.approve(address(panel), FEE);
        uint256 liquid0 = token.balanceOf(opener) + token.balanceOf(atk[0]) + token.balanceOf(atk[1]);

        bytes32 h = bytes32(uint256(0x52));
        _claim(h);
        _open(h, opener);
        _draw(h);
        uint256 openedAt = block.timestamp;
        _vote(atk[0], h, 0, "wrong");
        _vote(atk[1], h, 0, "wrong");               // honest 침묵
        vm.warp(openedAt + VOTE_T);
        panel.resolveTimeout(h);                    // 2표 일치 = 정식 평결(P4)
        (uint256 b,, uint256 s) = _agent();
        require(b == 9e18 && s == 1e18, "timeout verdict slash");
        uint256 liquid1 = token.balanceOf(opener) + token.balanceOf(atk[0]) + token.balanceOf(atk[1]);
        require(liquid1 == liquid0, "coalition net income != 0");
        require(int256(liquid1) - int256(liquid0) <= 0, "K4(b) violated");
    }

    /// K4(c) 정직 에이전트 추가 잠금: 도전 없으면 정확히 W (선무장 인출은 소멸 정각).
    function test_K4c_unchallenged_lock_is_exactly_W_with_prearmed_unbond() public {
        bytes32 h = bytes32(uint256(0x53));
        vm.prank(wallet);
        bv.requestUnbond(aid);                      // 선무장: unlockAt = t0 + 3600 < t0 + W
        _claim(h);
        vm.warp(t0 + W - 1);
        vm.prank(wallet);
        vm.expectRevert("claims pending");
        bv.withdraw(aid);
        vm.warp(t0 + W);
        bv.settleUnchallenged(h);
        vm.prank(wallet);
        bv.withdraw(aid);                           // 소멸 정각 인출
        require(token.balanceOf(wallet) == 90e18, "not all returned"); // 100e18 − bvD 예치 10e18
        require(block.timestamp - t0 == W, "lock != W");
    }

    /// K4(d) 소멸 100건 뒤 렌즈: requiredBondBp = 15000(신참 할증 유지)·creditScore 무되돌림.
    function test_K4d_100_lapses_lens_stable() public {
        for (uint256 i = 0; i < 100; i++) {
            bytes32 h = keccak256(abi.encode("lapse", i));
            _claim(h);
            vm.warp(block.timestamp + W);
            bv.settleUnchallenged(h);
        }
        require(valReg.getSummaryByTag(aid, "unchallenged") == 100, "lapse count");
        (uint256 score, uint64 answered) = lens.creditScore(aid);
        require(score == 0 && answered == 0, "lapses must not count as answered");
        require(lens.requiredBondBp(aid) == 15000, "newcomer premium bypassed by lapses");
        require(lens.requiredBond(aid) == 15e17, "absolute bond");
    }

    /// R8 렌즈 — "unchallenged" 중립화 + 언더플로 가드 (judge = this 로 직접 기록).
    function test_R8_lens_neutralizes_unchallenged_and_guards_underflow() public {
        // 오답 1건(0점) + 소멸 3건(50점) → 순진 평균 37, 37·4 = 148 < 150 → 가드 없으면 언더플로 되돌림
        bytes32 hw = keccak256("R8.wrong");
        _claimD(hw);
        bvD.submitVerdict(hw, 0, "", bytes32(0), "wrong");
        for (uint256 i = 0; i < 3; i++) {
            bytes32 h = keccak256(abi.encode("R8.lapse", i));
            _claimD(h);
        }
        vm.warp(block.timestamp + W);
        for (uint256 i = 0; i < 3; i++) bvD.settleUnchallenged(keccak256(abi.encode("R8.lapse", i)));
        (uint256 score, uint64 answered) = lensD.creditScore(aidD);
        require(score == 0 && answered == 1, "underflow guard");
        require(lensD.requiredBondBp(aidD) == 15000, "bp after guard");

        // 정답 12건 + "disputed" 1건 추가 → 중립화 후 answered 13.
        // 정확값 (1400−200)/13 = 92.3 이나 레지스트리 avg 는 내림(1400/17 = 82)이라
        // 렌즈의 합계 복원 82·17 = 1394 → (1394−200)/13 = 91.8 → 91. 하향 편향 ≤ (count−1)/answered 은
        // v0.2.1 렌즈(Exp6) 기존 성질 — Exp30 범위 밖, 한계로 등재.
        for (uint256 i = 0; i < 12; i++) {
            bytes32 h = keccak256(abi.encode("R8.ok", i));
            _claimD(h);
            bvD.submitVerdict(h, 100, "", bytes32(0), "correct");
        }
        bytes32 hd = keccak256("R8.disputed");
        _claimD(hd);
        bvD.submitVerdict(hd, 50, "", bytes32(0), "disputed"); // 패널 시한환급 대리
        (score, answered) = lensD.creditScore(aidD);
        require(answered == 13 && score == 91, "neutralization wrong");
        require(lensD.requiredBondBp(aidD) == 5000 + (100 - 91) * 100, "bp");
    }

    /// §12.6-A① 수리 회귀 1 — 정확 합계: 정답 100점 10건 + 소멸 990건 → (100, 10) · 5000bp.
    ///         수리 전(내림 평균 복원)은 (50, 10) · 10000bp 였다(logs/lens-gas-probe.log).
    function test_R8fix_exact_sum_100x10_plus_990_lapses() public {
        for (uint256 i = 0; i < 10; i++) {
            bytes32 h = keccak256(abi.encode("R8fix.ok", i));
            _claimD(h);
            bvD.submitVerdict(h, 100, "", bytes32(0), "correct");
        }
        for (uint256 i = 0; i < 990; i++) {
            bytes32 h = keccak256(abi.encode("R8fix.lapse", i));
            _claimD(h);
            vm.warp(block.timestamp + W);
            bvD.settleUnchallenged(h);
        }
        require(valReg.getSummaryByTag(aidD, "unchallenged") == 990, "lapse count");
        (uint256 score, uint64 answered) = lensD.creditScore(aidD);
        require(score == 100 && answered == 10, "floor bias not fixed");
        require(lensD.requiredBondBp(aidD) == 5000, "bp must be perfect discount");
        require(lensD.requiredBond(aidD) == 5e17, "absolute bond");
        require(lensD.abstainRateBp(aidD) == 0, "abstain rate");
        (uint256 b, uint256 atRisk,, uint256 slashed) = bvD.agents(aidD);
        require(b == 10e18 && atRisk == 0 && slashed == 0, "lapses must be lossless");
    }

    /// §12.6-A① 수리 회귀 2 — 49점 10건 + 소멸 100건 → 49 (수리 전 39). 순서 무관을 보이려
    ///         소멸 50 · 답 10 · 소멸 50 으로 끼워 넣는다. 49 < THRESHOLD 라 답 10건은 전부
    ///         슬래시(10e18) — 담보 10e18 추가 예치 후 실행.
    function test_R8fix_exact_sum_49x10_plus_100_lapses() public {
        vm.prank(wallet);
        bvD.stake(aidD, 10e18);
        for (uint256 i = 0; i < 100; i++) {
            if (i == 50) {
                for (uint256 k = 0; k < 10; k++) {
                    bytes32 ha = keccak256(abi.encode("R8fix.49", k));
                    _claimD(ha);
                    bvD.submitVerdict(ha, 49, "", bytes32(0), "partial");
                }
            }
            bytes32 h = keccak256(abi.encode("R8fix.lapse49", i));
            _claimD(h);
            vm.warp(block.timestamp + W);
            bvD.settleUnchallenged(h);
        }
        require(valReg.getSummaryByTag(aidD, "unchallenged") == 100, "lapse count");
        (uint256 score, uint64 answered) = lensD.creditScore(aidD);
        require(score == 49 && answered == 10, "floor bias not fixed (49)");
        require(lensD.requiredBondBp(aidD) == 5000 + (100 - 49) * 100, "bp 10100");
        (uint256 b, uint256 atRisk,, uint256 slashed) = bvD.agents(aidD);
        require(b == 10e18 && atRisk == 0 && slashed == 10e18, "slash accounting");
    }

    // ═══ R2/R3/R5/R9 — 권한·창·생성자 ═══

    /// R2/R3 engage·disengage 는 judge 전용; 비표식 disengage 불가.
    function test_R2R3_engage_disengage_only_judge() public {
        bytes32 h = bytes32(uint256(0x60));
        _claim(h);
        vm.prank(stranger);
        vm.expectRevert("not judge");
        bv.engage(h);
        vm.prank(stranger);
        vm.expectRevert("not judge");
        bv.disengage(h);
        vm.prank(address(panel));
        vm.expectRevert("not engaged");
        bv.disengage(h);
        vm.prank(address(panel));
        bv.engage(h);
        vm.prank(address(panel));
        vm.expectRevert("engaged");
        bv.engage(h);
        vm.prank(address(panel));
        bv.disengage(h);
        require(!bv.engaged(h), "disengage failed");
    }

    /// R5 judge 직접 판정(개설 없음): 창 안 가능·창 밖 불가; 표식이 있으면 창 밖도 가능.
    function test_R5_direct_verdict_inside_window_only_unless_engaged() public {
        bytes32 h1 = bytes32(uint256(0x61));
        bytes32 h2 = bytes32(uint256(0x62));
        bytes32 h3 = bytes32(uint256(0x63));
        _claimD(h1);
        _claimD(h2);
        _claimD(h3);
        bvD.engage(h3);                              // 창 안 표식
        vm.warp(t0 + W - 1);
        bvD.submitVerdict(h1, 100, "", bytes32(0), "ok"); // 창 안 직접 판정 (ZkVerdictGate 경로)
        vm.warp(t0 + W);
        vm.expectRevert("window closed");
        bvD.submitVerdict(h2, 100, "", bytes32(0), "ok");
        bvD.submitVerdict(h3, 0, "", bytes32(0), "wrong"); // 표식된 주장은 창 밖 판정 가능
        (uint256 b,,, uint256 s) = bvD.agents(aidD);
        require(b == 9e18 && s == 1e18, "engaged verdict not applied");
        vm.expectRevert("settled");
        bvD.settleUnchallenged(h3);                  // 이미 정산(검사 순서 exists → settled → engaged)
    }

    /// L5 구체: 소멸 뒤 verdict·lapse·engage 전부 되돌림; verdict 뒤 lapse·engage 되돌림.
    function test_L5_single_settlement_concrete() public {
        bytes32 h1 = bytes32(uint256(0x64));
        bytes32 h2 = bytes32(uint256(0x65));
        _claimD(h1);
        _claimD(h2);
        bvD.submitVerdict(h2, 100, "", bytes32(0), "ok");
        vm.warp(t0 + W);
        bvD.settleUnchallenged(h1);
        vm.expectRevert("settled");
        bvD.submitVerdict(h1, 0, "", bytes32(0), "wrong");
        vm.expectRevert("settled");
        bvD.settleUnchallenged(h1);
        vm.expectRevert("settled");
        bvD.engage(h1);
        vm.expectRevert("settled");
        bvD.settleUnchallenged(h2);
        vm.expectRevert("settled");
        bvD.engage(h2);
    }

    /// R9 생성자: 0 < W ≤ 365 days.
    function test_R9_constructor_rejects_bad_window() public {
        bool failed;
        try new BondedValidatorV3(address(token), address(idReg), address(valReg), address(this), 1e18, 60, 0) {
            failed = false;
        } catch { failed = true; }
        require(failed, "W=0 accepted");
        try new BondedValidatorV3(address(token), address(idReg), address(valReg), address(this), 1e18, 60, 365 days + 1) {
            failed = false;
        } catch { failed = true; }
        require(failed, "W>365d accepted");
        BondedValidatorV3 okv = new BondedValidatorV3(address(token), address(idReg), address(valReg), address(this), 1e18, 60, 365 days);
        require(okv.challengeWindow() == 365 days, "W=365d rejected");
    }

    // ═══ 낙관적창 반박 A 재현 — 풀 < 3 자기개설이 더 이상 창을 우회하지 못한다 ═══

    /// v0.2.1 계열(세 스크래치 설계 공통): 거짓말쟁이가 풀 2 에서 자기개설 → 3,600s 뒤 _refund 로
    /// 50/"disputed" 무손실 정산 → 남은 창 동안 도전자 영구 봉쇄. v0.3: 리셋이라 주장은 살아 있고
    /// 판정자가 3인이 되는 즉시 도전자가 개설·슬래시할 수 있다.
    function test_A_thin_pool_self_open_no_longer_bypasses_window() public {
        _judges(2);
        bytes32 h = bytes32(uint256(0x70));
        _claim(h);                                  // 거짓 주장
        _open(h, wallet);                           // 즉시 자기개설
        vm.roll(block.number + 1);
        vm.expectRevert("pool too small");
        panel.drawPanel(h);
        vm.warp(t0 + VOTE_T);
        panel.resolveTimeout(h);                    // v0.2.1: 정산(봉쇄) / v0.3: 리셋
        require(!bv.claimSettled(h), "v0.2.1 bypass still present");
        require(_phase(h) == BondedJudgePanelV3.Phase.None && !bv.engaged(h), "not reset");
        _judge(address(uint160(uint256(keccak256("exp30.late.judge")))));
        vm.warp(t0 + VOTE_T + 1);
        _open(h, challenger);                       // 창 안(3,601s < 86,400s) 도전 가능
        address[] memory p = _draw(h);
        for (uint256 i = 0; i < 3; i++) _vote(p[i], h, 0, "wrong");
        (uint256 b,, uint256 s) = _agent();
        require(b == 9e18 && s == 1e18, "liar escaped");
    }
}
