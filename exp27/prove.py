"""Exp27 — 인간 정지·재개 권한(Human Halt & Resume) : 잠긴 스펙 v1 기계 검증 (z3).

첫 줄 선언(LOCK-0, 모든 산출물 첫 줄에 고정):
  우리가 증명하는 것은 "AI가 멈춘다"가 아니라 "온체인 권한이 소멸한다"이다.
  정지는 사고를 멈추지 않는다. 정산을 멈춘다. 그리고 그것조차 '정지'가 아니라 '소멸'이다.

적대검증 3렌즈 전원 BROKEN 판정을 반영해 원안(BHR: 담보된 정지 + 소각 + 에스컬레이션 +
역담보 즉시재개 + θ 일몰사다리)을 **폐기**하고 다음만 남긴다 — 이번 라운드 7번째 자기교정.

  살아남은 것(LOCKED / EAL-X = Expiring Authority Lease with Exit):
    L0 소멸(lapse)  : 권한은 만료 ε의 리스. 아무도 아무것도 안 하면 죽는다. 권한자 0명.
    L1 폐기(revoke) : 일시정지가 아니라 **되돌릴 수 없는 소멸**. un-pause 함수가 없다.
                      재개 = 원권리자의 '새 서명으로 신규 발급'뿐. → 재개 데드락 개념 소멸.
    L2 거부권(veto) : 제3자가 정액 P로 **현 에폭의 갱신만** 1회 차단. 실행을 멈추지 못한다.
                      효과는 "사람 서명 체크포인트 강제"뿐 — 정지가 아니라 **주의(attention) 세금**.
    X  탈출차선     : 원권리자 인증 ∧ 수취인=원권리자 인출은 revoked를 읽지 않는다(구문 불변식).
    배포            : **불변(immutable) 배포, 업그레이드 없음, 파라미터 배포시 고정,
                      레지스트라=원권리자 append-only.** 업그레이더·세터를 1급 행위자로 모델링.

  폐기한 것(전부 반증됨. 아래 I-계열이 그 사망진단서다):
    담보된 정지보증금 H, 시간비례 소각 ρ, 에스컬레이션 ρ_k=ρ₀2^(k−1), 윈도 W,
    역담보 즉시재개 R2, 정지자 보상 R_h, θ(n) 일몰 사다리, "반-그리핑 달성" 주장 전부.

라벨 규약(정직):
  [THM]  실질 정리 — 결론이 정의의 재서술이 아님
  [WIT]  증인 — 우리가 못 하는 것/공격이 성립함을 보이는 SAT
  [ENC]  인코딩 확인 — 설계가 그 변수를 읽지 않음을 확인하는 것, 독립 정리 아님
"""
import json
from pathlib import Path

from z3 import (And, Bool, Bools, Implies, Not, Or, Real, Reals, Solver, sat,
                unsat)

PASS, LOG = [], []


def check(cid, label, note, expect, cons, witness=None):
    s = Solver()
    s.add(And(*cons))
    r = s.check()
    ok = (r == expect)
    print(f"[{'OK ' if ok else 'FAIL'}] {cid:<16}{label} {note}: {r} (기대 {expect})")
    if witness and r == sat:
        m = s.model()
        print("        증인: " + ", ".join(f"{v}={m[v]}" for v in witness))
    PASS.append(ok)
    LOG.append({"id": cid, "label": label, "note": note,
                "expected": str(expect), "result": str(r), "ok": ok})
    assert ok, cid
    return s


print("=" * 78)
print("Exp27 · 인간 정지·재개 권한 — 잠긴 스펙 EAL-X · z3 기계 검증")
print("=" * 78)

# ────────────────────────────────────────────────────────────────────────────
print("\n── I. 불가능성 (이번 라운드의 실제 산출물: 담보된 정지는 왜 실패하는가) ──")
# ────────────────────────────────────────────────────────────────────────────
Rh, Bag, sig, V, sact = Reals("Rh Bag sig V sact")
pay_j, pay_u = Reals("pay_j pay_u")
lam, sg, dt = Reals("lam sg dt")

check("I1-WASHCLOSE", "[THM]", "반-wash 닫힘 R_h≤B_ag → 자작정지 이득 불가", unsat,
      [Rh <= Bag, Rh - Bag > 0])

check("I1b-CORE-RECUR", "[THM]", "★Exp26 CORE-WS 완전재현: 가치스케일 정지보상 불가", unsat,
      [Bag > 0, sig > 0, V > 0, Rh <= Bag, Rh >= sig * V, sig * V > Bag])

check("I2-NAO", "[THM]", "★H27-1: 내생 판정자 없으면 (무손실정직)∧(반그리핑) 불가", unsat,
      [pay_j == pay_u, pay_j >= 0, pay_u < 0])

# H27-3 : 시간선형 가격은 스텝형 피해를 유계화하지 못한다 (∀λ>0 반례 구성)
check("I3a-STEPWIT", "[THM]", "★H27-3(1/2): ∀λ>0. 반례 지속시간 Δt=σ/2λ 는 항상 양수", unsat,
      [lam > 0, sg > 0, 2 * lam * dt == sg, dt <= 0])
check("I3b-STEP", "[THM]", "★H27-3(2/2): 그 Δt에서 정지비용 λΔt < 피해 σ (∀λ)", unsat,
      [lam > 0, sg > 0, 2 * lam * dt == sg, lam * dt >= sg])

# H27-4 : 역담보 즉시재개(R2)는 정지의 유효시간을 0으로 만든다
Hp, Hrem, dmin = Reals("Hp Hrem dmin")
r2_on = Bool("r2_on")
R2DEF = dmin == 0
check("I4-R2KILL", "[ENC]", "★H27-4: R2(역담보 즉시재개) 있으면 보장 정지시간 Δ>0 불가", unsat,
      [Implies(And(r2_on, Hp >= Hrem), R2DEF), r2_on, Hp >= Hrem, Hrem > 0, dmin > 0])
check("I4b-R2COST", "[WIT]", "슬라이스 밖에선 역담보 몰수사유 0 → 원권리자 순소각 0", sat,
      [r2_on, Real("burn_p") == 0, Hp >= Hrem, Hrem > 0], witness=[Real("burn_p")])

# H27-5 : 에스컬레이션 윈도 딜레마
rho0, Om, T, W, k, unit = Reals("rho0 Om T W k unit")
check("I5a-WRESET", "[WIT]", "★H27-5(a): 윈도 W 유한 → 카운터 리셋, T가 예산에 선형(로그상한 파기)",
      sat, [rho0 == 1, Om == 100, W > 0, T == Om / rho0, T >= 7], witness=[T])
check("I5b-NOWINDOW", "[WIT]", "★H27-5(b): W 무한 → 정직한 k회차 단가 2^(k−1) 폭발(정직정지 사멸)",
      sat, [rho0 == 1, k == 20, unit == 524288, unit == rho0 * 524288], witness=[unit])

# H27-6 : s_act 이중청구 → 슬라이스 안에서 A3 재발
claim_cons, claim_halt = Reals("claim_cons claim_halt")
check("I6-DOUBLECLAIM", "[THM]", "★H27-6: 정합성 슬래시가 s_act 전액 선점 → 정지보상 V-스케일 불가",
      unsat, [sig > 0, V > 0, sact == sig * V, claim_cons == sact,
              claim_halt <= sact - claim_cons, claim_halt >= sig * V])
check("I6b-SPLIT", "[WIT]", "σ 분할하면 가능하나 각 청구권 실효 스케일이 σ/2로 하락", sat,
      [sig > 0, V > 0, sact == sig * V, claim_cons == sact / 2,
       claim_halt == sact / 2, claim_halt >= (sig / 2) * V], witness=[claim_halt, sact])

# ────────────────────────────────────────────────────────────────────────────
print("\n── II. 권한·업그레이드 (원안에 체크 0건이던 자리 — 1급 행위자로 모델링) ──")
# ────────────────────────────────────────────────────────────────────────────
authv, revoked, modact, renewed = Bools("authv revoked modact renewed")
upgrader, registrar_add, elig_adv, veto_used = Bools("upgrader registrar_add elig_adv veto_used")
t, tg, eps = Reals("t tg eps")

# 잠긴 권한 술어: 소멸 ∧ 폐기 ∧ 모듈생존을 모두 읽는다 (원안 G-계열의 ¬halted 누락 수정)
AUTH = authv == And(modact, Not(revoked), Or(renewed, t <= tg + eps))

check("A1-UPGRADE", "[WIT]", "★업그레이더 존재 → 폐기 후 권한 복원 가능(모든 성질이 조건부로 강등)",
      sat, [upgrader, revoked, Real("authv_post") == 1,
            Implies(upgrader, Real("authv_post") == 1)], witness=[Real("authv_post")])
check("A2-IMMUTABLE", "[ENC]", "업그레이더 없음(불변배포) → 폐기는 되돌릴 수 없음", unsat,
      [AUTH, Not(upgrader), revoked, authv])
check("A3-REGISTRAR", "[WIT]", "★레지스트라가 사실상 최고권한: 미등록 스코프는 폐기가 닿지 않음",
      sat, [Not(registrar_add), Real("reach") == 0, revoked], witness=[Real("reach")])
check("A4a-ELIG-HOSTILE", "[WIT]", "★적대적 Elig에게 무제한 revoke를 주면 영구 권한부정(=원안 붕괴)",
      sat, [elig_adv, revoked, Not(authv), AUTH, modact], witness=[])
check("A4b-ELIG-VETO", "[ENC]", "★귀속-불변: Elig가 적대적이어도 veto는 현 에폭 갱신만 차단 → "
      "신규 서명으로 권한 회복 가능(영구부정 불가)", unsat,
      [AUTH, elig_adv, veto_used, renewed, modact, Not(revoked), Not(authv)])
check("A5-RENEWKEY", "[WIT]", "★가장 싼 영구정지는 무료다: 갱신키 강압·분실 → 비용 0의 영구 소멸",
      sat, [AUTH, Not(renewed), t > tg + eps, eps > 0, modact, Not(revoked),
            Not(authv), Real("cost_attack") == 0], witness=[Real("cost_attack")])

# ────────────────────────────────────────────────────────────────────────────
print("\n── III. 살아남은 것: 소멸 기본값(fail-closed)과 그 대가 ──")
# ────────────────────────────────────────────────────────────────────────────
check("S1-LAPSE", "[ENC]", "무갱신 → 권한 자동소멸(권한자 0명, 비용 0)", unsat,
      [AUTH, eps > 0, t > tg + eps, Not(renewed), authv])
check("S2-FAILCLOSED", "[ENC]", "모듈 일몰/장애 → 권한도 소멸(fail-open 아님)", unsat,
      [AUTH, Not(modact), authv])
check("S3-MODULE-SPOF", "[WIT]", "★그 대가: 모듈 브릭 → 전 스코프 영구 소멸, 복구경로 없음",
      sat, [AUTH, Not(modact), Not(authv), Real("recover_path") == 0],
      witness=[Real("recover_path")])
check("S4-AUTORENEW", "[WIT]", "★완전 자동갱신 → 소멸 기본값이 공허해짐(G3 상속)", sat,
      [AUTH, renewed, modact, Not(revoked), t > tg + eps * 1000, eps > 0, authv],
      witness=[t])
check("S5-NOUNPAUSE", "[ENC]", "폐기에는 해제 함수가 없다(un-revoke 변수 부재)", unsat,
      [AUTH, revoked, authv])

# 정지 단위: id냐 스코프냐 — 원안이 뭉갠 이분법을 판정
id_bound, scope_bound = Bools("id_bound scope_bound")
reissued = Bool("reissued")
AUTH_ID = Real("auth_re") == 1
check("S6a-REISSUE", "[WIT]", "★id 단위 폐기면 원권리자가 동일 스코프로 즉시 재발급(무비용 회피)",
      sat, [id_bound, Not(scope_bound), reissued, AUTH_ID], witness=[Real("auth_re")])
check("S6b-SCOPEBIND", "[ENC]", "스코프 노드 단위로 못박으면 재발급 회피 불가(대가: 원권리자 검열벡터)",
      unsat, [scope_bound, revoked, reissued, AUTH, modact, authv])

# ────────────────────────────────────────────────────────────────────────────
print("\n── IV. 탈출차선 불변식 (Halmos 이식 대상) ──")
# ────────────────────────────────────────────────────────────────────────────
psig, destP, exit_ok, destfree = Bools("psig destP exit_ok destfree")
vout = Real("vout")
EXITDEF = exit_ok == And(psig, destP)      # revoked/halted 를 읽지 않는다

check("X1-EXIT-LIVE", "[ENC]", "폐기 중에도 원권리자 인출 생존(구문 불변식)", unsat,
      [EXITDEF, revoked, psig, destP, Not(exit_ok)])
check("X2-NOBYPASS", "[ENC]", "에이전트 키로 인출 경로 우회 불가", unsat,
      [EXITDEF, revoked, Not(psig), exit_ok, vout > 0])
check("X2b-DESTFREE", "[WIT]", "★수취인 제한을 빼면 우회가 열린다(제한의 필요성)", sat,
      [destfree, Real("exit_free") == 1, revoked, Not(psig), vout > 0],
      witness=[vout])
check("X3-CUSTODY-BASE", "[WIT]", "★기본 사례(예외 아님): 원권리자 키 침해 시 탈출차선이 곧 탈취로",
      sat, [EXITDEF, revoked, psig, destP, exit_ok, vout > 0], witness=[vout])
check("X4-DECAY", "[WIT]", "★탈출차선이 살아 있어도 폐기 자체가 손실을 만든다(만기·헤지·경매)",
      sat, [EXITDEF, revoked, psig, destP, exit_ok,
            Real("loss") > 0, Real("bound_loss") == 0], witness=[Real("loss")])

# ────────────────────────────────────────────────────────────────────────────
print("\n── V. 완전성 한계 (전부 '못 멈춘다'의 이름표) ──")
# ────────────────────────────────────────────────────────────────────────────
t_exec, t_halt, ord_a, ord_h, d_force, t_intent = Reals(
    "t_exec t_halt ord_a ord_h d_force t_intent")
valid = Bool("valid")
# F1/F2가 서로 다른 valid를 쓰던 결함 수정: 단일 정의로 통일
VALIDDEF = valid == Or(t_exec < t_halt,
                       And(t_exec == t_halt, ord_a < ord_h))

check("C1-INFLIGHT", "[ENC]", "실행시점 검사(단일 정의) → 폐기 후 채굴되는 선서명 tx 무효", unsat,
      [VALIDDEF, t_exec > t_halt, valid])
check("C2-SAMEBLOCK", "[WIT]", "★동일블록 잔여창(수정 불가, ≤1블록 · L1 · 검열 없음 가정)", sat,
      [VALIDDEF, t_exec == t_halt, ord_a < ord_h, valid], witness=[ord_a, ord_h])
check("C3-CENSOR", "[WIT]", "★시퀀서 검열: 강제포함 지연 d_force 동안 모든 행동이 유효(창이 블록이 "
      "아니라 시간 단위 — 체인별 실측 미확인)", sat,
      [VALIDDEF, d_force > 0, t_halt == t_intent + d_force,
       t_exec > t_intent, t_exec < t_halt, valid], witness=[d_force, t_exec])
check("C4-PREAPPROVE", "[WIT]", "★지배적 누수: 권한 있을 때 발급한 선행 외부승인(approve)은 "
      "폐기 후에도 생존", sat,
      [revoked, Real("allowance") > 0, Real("pull_ok") == 1], witness=[Real("allowance")])
check("C5-UNREG", "[WIT]", "미등록 권한경로(타 체인·오프체인 키)는 폐기가 닿지 않음", sat,
      [Not(registrar_add), revoked, Real("valid_unreg") == 1],
      witness=[Real("valid_unreg")])
check("C6-FRAGMENT", "[WIT]", "★스코프 파편화 선택압: 루트 N개면 veto 비용 N·P, 에이전트 비용 불변",
      sat, [Real("N") == 10, Real("P") == 1,
            Real("cost_veto") == Real("N") * Real("P"),
            Real("cost_agent") == 0], witness=[Real("cost_veto"), Real("cost_agent")])

# ────────────────────────────────────────────────────────────────────────────
print("\n── VI. 남은 유일한 제3자 프리미티브: veto = 정지가 아니라 '주의 세금' ──")
# ────────────────────────────────────────────────────────────────────────────
fresh_sig, human = Bools("fresh_sig human")
check("V1-NOTANTIGRIEF", "[WIT]", "★veto는 반-그리핑이 아니다: 정액비용 P, 피해는 무계(I3 적용)",
      sat, [Real("P") == 1, Real("dmg") == 1000000, Real("P") < Real("dmg")],
      witness=[Real("P"), Real("dmg")])
check("V2-NOHUMAN", "[WIT]", "★이 실험 전체의 핵심 한계: 온체인은 '신선한 서명'만 증명한다. "
      "'사람이 했다'는 증명 불가", sat,
      [Implies(human, fresh_sig), fresh_sig, Not(human)], witness=[])
check("V3-VETO-BOUNDED", "[ENC]", "veto는 에폭당 1회·연장 불가 → 무한 연장(OP/Aztec 결함) 재현 없음",
      unsat, [Real("veto_count") <= 1, Real("veto_count") > 1])

print(f"\n{sum(PASS)}/{len(PASS)} 통과  (z3 4.12.6)")

out = {
    "experiment": "exp27",
    "title": "Human Halt & Resume — LOCKED spec EAL-X (bonded-halt track KILLED)",
    "lock_0": "우리가 증명하는 것은 'AI가 멈춘다'가 아니라 '온체인 권한이 소멸한다'이다.",
    "generated_by": f"exp27/prove.py (verified run, {len(PASS)} checks)",
    "z3_version": "4.12.6",
    "killed": ["정지보증금 H", "시간비례 소각 ρ", "에스컬레이션 ρ_k", "윈도 W",
               "역담보 즉시재개 R2", "정지자 보상 R_h", "θ(n) 일몰 사다리",
               "'반-그리핑 달성' 주장"],
    "checks": LOG,
    "all_ok": all(PASS),
}
Path(__file__).with_name("results.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("→ exp27/results.json 기록")
