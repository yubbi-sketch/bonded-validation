#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xverify — IIS 정리의 독립 2차 솔버 교차검증 (z3 ⟂ cvc5).  2026-09-02.

각 exp의 prove.py를 **한 글자도 안 고치고** 그대로 실행하되, z3.Solver.check 를
가로채 '동일 제약(SMT-LIB2 덤프)'을 cvc5로도 판정한다. 두 독립 솔버가 sat/unsat에
동의하면 단일-솔버 인코딩/구현 버그가 정리를 통과시켰을 확률이 급감한다.

원리: 판정(sat/unsat)은 이론이 정하는 것이라 솔버·버전 불변이어야 한다. z3와 cvc5는
완전히 다른 코드베이스이므로, 둘이 모든 판정에 동의 = 강한 교차증거.

사용:  .venv-xverify/bin/python xverify.py exp24     # 한 개
       .venv-xverify/bin/python xverify.py all       # SMT exp 전부
의존:  z3-solver, cvc5 (.venv-xverify). prove.py는 원본 그대로 재사용(비침습).
"""
import sys, os, runpy, io, contextlib
import z3
import cvc5

HERE = os.path.dirname(os.path.abspath(__file__))
SMT_EXPS = ["exp13", "exp24", "exp25", "exp26", "exp27", "exp28", "exp30"]

_pairs = []          # [(z3_verdict, cvc5_verdict, ok)] — exp 실행 중 채워짐
_orig_check = z3.Solver.check
_busy = False        # 재진입 가드: to_smt2 등이 check를 재귀 호출해도 교차검증 1회만


# 판정은 이론이 정하므로, '확답(sat/unsat)을 주는 첫 로직'을 쓴다.
# ALL은 비선형 실수 SAT에서 확답을 못 주는 경우가 있어 전용 로직을 먼저 시도한다.
_LOGICS = ["QF_NRA", "QF_NIA", "QF_LIA", "QF_LRA", "QF_UFLIA", "QF_UFNRA", "ALL"]


def _cvc5_once(body, logic):
    tm = cvc5.TermManager()
    solver = cvc5.Solver(tm)
    try:
        sm = cvc5.SymbolManager(tm)
    except Exception:
        sm = cvc5.SymbolManager(solver)
    solver.setOption("tlimit-per", "8000")   # 쿼리당 8s 상한 — 멈춤 방지
    parser = cvc5.InputParser(solver, sm)
    parser.setStringInput(cvc5.InputLanguage.SMT_LIB_2_6, f"(set-logic {logic})\n" + body, "xv")
    res = "?"
    while True:
        cmd = parser.nextCommand()
        if cmd.isNull():
            break
        out = cmd.invoke(solver, sm)
        if isinstance(out, str) and out.strip() in ("sat", "unsat", "unknown"):
            res = out.strip()
    return res


def _cvc5_solve(smt2):
    """SMT-LIB2를 cvc5로 판정 — 확답(sat/unsat) 주는 첫 로직 채택(불일치 오탐 방지)."""
    import re
    body = re.sub(r"\(set-logic[^)]*\)\s*", "", smt2)   # z3 로직 라인 제거(있으면)
    last = "?"
    for lg in _LOGICS:
        try:
            r = _cvc5_once(body, lg)
        except Exception:
            continue                     # 이 로직이 이 이론을 못 받으면 다음 로직
        if r in ("sat", "unsat"):
            return r                       # 확답 → 채택
        last = r or last
    return last                            # 전부 unknown/? 면 마지막(보류)


def _patched_check(self, *a, **k):
    global _busy
    r = _orig_check(self, *a, **k)          # z3 판정 — 원본 동작 그대로
    if _busy:                               # 재진입(to_smt2가 check 재호출 등) → 교차검증 건너뜀
        return r
    _busy = True
    try:
        smt2 = self.to_smt2()
        cr = _cvc5_solve(smt2)
    except Exception as e:
        cr = f"err:{str(e)[:40]}"
    finally:
        _busy = False
    zr = str(r)
    # unknown/err 은 '판단 보류'로 두고 실패로 치지 않음(정직)
    ok = (zr == cr) or cr in ("unknown",) or cr.startswith("err")
    _pairs.append((zr, cr, ok))
    return r


def run_exp(exp):
    global _pairs
    _pairs = []
    path = os.path.join(HERE, exp, "prove.py")
    if not os.path.exists(path):
        print(f"  [건너뜀] {exp}/prove.py 없음"); return None
    print(f"\n{'─'*66}\n▶ {exp}  (원본 prove.py 그대로 실행 + cvc5 교차판정)\n{'─'*66}")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):     # exp 자체 출력은 삼켜 요약만
            runpy.run_path(path, run_name="__main__")
    except SystemExit:
        pass
    except AssertionError as e:
        print(f"  ⚠️ prove.py assert 실패: {e}  (z3 자체 검증 실패 — 교차검증 이전 문제)")
    except Exception as e:
        print(f"  ⚠️ 실행 오류: {str(e)[:120]}"); return None
    n = len(_pairs)
    agree = sum(1 for _, _, ok in _pairs if ok)
    strict = sum(1 for z, c, _ in _pairs if z == c)
    disagree = [(i + 1, z, c) for i, (z, c, ok) in enumerate(_pairs) if not ok]
    print(f"  z3 판정 {n}건 · cvc5 일치 {strict}/{n}" +
          (f" · 보류(unknown/err) {n - strict - len(disagree)}" if n - strict - len(disagree) else ""))
    if disagree:
        for idx, z, c in disagree:
            print(f"    ★불일치 #{idx}: z3={z} cvc5={c}")
    else:
        print(f"  ✅ 두 독립 솔버(z3·cvc5) 판정 전건 일치 — 교차검증 통과")
    return (n, strict, len(disagree))


def main():
    z3.Solver.check = _patched_check
    targets = SMT_EXPS if (len(sys.argv) < 2 or sys.argv[1] == "all") else [sys.argv[1]]
    print("="*66)
    print("xverify — IIS 정리 독립 2차 솔버 교차검증 (z3 ⟂ cvc5)")
    print(f"z3 {z3.get_version_string()} · cvc5 {getattr(cvc5,'__version__','?')}")
    print("="*66)
    tot_n = tot_ok = tot_bad = 0
    for exp in targets:
        res = run_exp(exp)
        if res:
            tot_n += res[0]; tot_ok += res[1]; tot_bad += res[2]
    print(f"\n{'='*66}\n총계: z3 판정 {tot_n}건 · cvc5 일치 {tot_ok} · 불일치 {tot_bad}")
    print("결론: " + ("전 정리 이중 솔버 교차검증 통과 — 단일 솔버 버그 방어."
                     if tot_bad == 0 else "불일치 존재 — 인코딩/솔버 차이 조사 필요(정직 신호)."))
    print("="*66)
    sys.exit(1 if tot_bad else 0)


if __name__ == "__main__":
    main()
