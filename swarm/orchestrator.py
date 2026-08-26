#!/usr/bin/env python3
"""Multi-LLM research orchestrator for IIS.

This is intentionally dependency-free: standard Python plus provider HTTP APIs.
The default mock provider lets the workflow run without paid API keys.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SWARM_DIR = Path(__file__).resolve().parent
AGENTS_DIR = SWARM_DIR / "agents"
PROBLEMS_FILE = SWARM_DIR / "problems.json"
RUNS_DIR = SWARM_DIR / "runs"

AGENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "role": {"type": "string"},
        "verdict": {"type": "string", "enum": ["propose", "reject", "pass", "retry", "ask_user", "fail"]},
        "confidence": {"type": "number"},
        "main_claim": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "required_fix": {"type": "string"},
        "next_action": {"type": "string"},
        "ask_user": {"type": "string"}
    },
    "required": [
        "role",
        "verdict",
        "confidence",
        "main_claim",
        "evidence",
        "risks",
        "required_fix",
        "next_action",
        "ask_user"
    ]
}


class ProviderError(RuntimeError):
    pass


@dataclass
class Provider:
    name: str
    model: str

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:
        raise NotImplementedError


class MockProvider(Provider):
    def __init__(self, name: str = "mock", model: str = "deterministic-mock") -> None:
        super().__init__(name, model)

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:
        role = _extract_role(user)
        title = _extract_problem_title(user)
        test_status = _extract_marker(user, "TEST_STATUS") or "not_run"
        if role == "planner":
            data = {
                "role": role,
                "verdict": "propose",
                "confidence": 0.76,
                "main_claim": f"{title} should be split into attack simulation, trust-assumption audit, and owner-governance decision gates.",
                "evidence": [
                    "The problem has explicit K1-K4 acceptance criteria.",
                    "The repository already has JudgePanelV2 and ReputationLens context."
                ],
                "risks": [
                    "A design can appear to pass if economic parameters are left symbolic.",
                    "Panel-dispute logic can hide a governance choice behind implementation details."
                ],
                "required_fix": "Make every pass condition numeric or explicitly owner-decided.",
                "next_action": "Ask builders for a concrete simulation and test plan.",
                "ask_user": ""
            }
        elif role == "critic":
            data = {
                "role": role,
                "verdict": "reject",
                "confidence": 0.84,
                "main_claim": "The proposal must bind the loser-pays design to adversarial budgets, otherwise it is only a narrative.",
                "evidence": [
                    "K1 requires comparing bribery cost with protected value.",
                    "K4 requires queue-cost accounting for dispute spam."
                ],
                "risks": [
                    "Minority slashing can punish honest judges if the escalation panel is captured.",
                    "New-judge discounts can make sybil attacks cheaper than expected."
                ],
                "required_fix": "Add explicit attack parameters: panel size, bribe cost, slash size, dispute bond, queue capacity, and protected value.",
                "next_action": "Retry with a parameterized simulation before implementation.",
                "ask_user": "Set initial economic parameters or approve a conservative default grid."
            }
        elif role == "judge":
            problem_id = _extract_problem_id(user)
            owner_notes = _extract_section(user, "OWNER_NOTES", "PREVIOUS_ROUNDS").lower()
            owner_approved_grid = (
                "conservative default grid" in owner_notes
                and ("use" in owner_notes or "approve" in owner_notes or "승인" in owner_notes)
            )
            if test_status == "failed":
                verdict = "retry"
                claim = "Tests failed, so the problem cannot pass this round."
                fix = "Fix the failing command output before continuing."
                ask = ""
            elif problem_id == "exp8_judge_bond_attack_sim" and test_status == "passed" and owner_approved_grid:
                verdict = "pass"
                claim = "The owner approved the default grid and repository tests passed, so this orchestration gate can advance."
                fix = "Use the approved grid to create the Exp8 simulation artifact."
                ask = ""
            elif problem_id == "exp8_judge_bond_attack_sim" and not owner_approved_grid:
                verdict = "ask_user"
                claim = "The remaining blocker is an owner policy choice, not an LLM reasoning issue."
                fix = "Owner should choose economic defaults or authorize the default grid."
                ask = "May I use a conservative default grid for Exp8: panel sizes 3/5/7, bribe cost 1-20 bonds, judge slash 1-10 bonds, dispute bond 1-5 bonds, and protected value 10-100 bonds?"
            else:
                if test_status in ("not_run", "no_tests"):
                    verdict = "ask_user"
                    claim = "This problem is a document or research-scope decision, so the owner should approve whether to turn the review into edits."
                    fix = "Decide whether to apply draft edits, keep review notes only, or rerun with real providers."
                    ask = "Should I turn this review into concrete document edits now, keep it as review notes, or rerun it with real providers first?"
                else:
                    verdict = "pass"
                    claim = "The configured evidence gate passed and no owner-only blocker remains."
                    fix = "Record the result and continue to the next queued problem."
                    ask = ""
            data = {
                "role": role,
                "verdict": verdict,
                "confidence": 0.68,
                "main_claim": claim,
                "evidence": [
                    f"TEST_STATUS={test_status}",
                    "Acceptance criteria are explicit in the problem queue."
                ],
                "risks": [
                    "Passing without empirical artifacts would weaken the research trail."
                ],
                "required_fix": fix,
                "next_action": "Continue to another round or ask the owner.",
                "ask_user": ask
            }
        elif role == "scribe":
            data = {
                "role": role,
                "verdict": "propose",
                "confidence": 0.7,
                "main_claim": "The swarm completed a controlled research round and left a machine-readable transcript.",
                "evidence": [
                    "planner, builder, critic, judge, and scribe outputs were recorded",
                    f"TEST_STATUS={test_status}"
                ],
                "risks": [
                    "Mock output validates orchestration only, not real multi-company model quality."
                ],
                "required_fix": "Use real providers with API keys for adversarial diversity.",
                "next_action": "Review verdict.json and ASK_USER.md if present.",
                "ask_user": ""
            }
        else:
            data = {
                "role": role or "builder",
                "verdict": "propose",
                "confidence": 0.78,
                "main_claim": "Build a parameterized Exp8 simulation before touching contracts.",
                "evidence": [
                    "docs/exp8 names K1-K4 as pre-implementation kill criteria.",
                    "JudgePanelV2 already solves timeout refund but not loser-pays economics."
                ],
                "risks": [
                    "Implementing judge slashing before simulation can hard-code the wrong economics.",
                    "A captured escalation panel can invert loser-pays against honest judges."
                ],
                "required_fix": "Create a simulation grid and require K1-K4 pass before contract changes.",
                "next_action": "Have critics attack the proposed simulation assumptions.",
                "ask_user": ""
            }
        return json.dumps(data, ensure_ascii=False)


class OpenAIProvider(Provider):
    def __init__(self) -> None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ProviderError("OPENAI_API_KEY is not set")
        super().__init__("openai", os.environ.get("OPENAI_MODEL", "gpt-5"))
        self.key = key

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:
        body = {
            "model": self.model,
            "store": False,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "iis_swarm_agent_response",
                    "schema": schema,
                    "strict": True
                }
            }
        }
        data = _post_json(
            "https://api.openai.com/v1/responses",
            body,
            {
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json"
            }
        )
        return _openai_text(data)


class AnthropicProvider(Provider):
    def __init__(self) -> None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ProviderError("ANTHROPIC_API_KEY is not set")
        super().__init__("anthropic", os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"))
        self.key = key

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:
        body = {
            "model": self.model,
            "max_tokens": 1800,
            "temperature": 0.2,
            "system": system,
            "messages": [{"role": "user", "content": user}]
        }
        data = _post_json(
            "https://api.anthropic.com/v1/messages",
            body,
            {
                "x-api-key": self.key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
        )
        parts = data.get("content", [])
        return "\n".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()


class GeminiProvider(Provider):
    def __init__(self) -> None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ProviderError("GEMINI_API_KEY is not set")
        super().__init__("gemini", os.environ.get("GEMINI_MODEL", "gemini-1.5-pro"))
        self.key = key

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.key}"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }
        data = _post_json(url, body, {"Content-Type": "application/json"})
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Unexpected Gemini response: {data}") from exc


PROVIDER_FACTORIES = {
    "mock": MockProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider
}


def main() -> int:
    args = parse_args()
    problems = load_problems()

    if args.list:
        list_problems(problems)
        return 0

    selected = select_problems(problems, args.problem, args.all)
    providers = build_providers(args.providers or args.provider)
    print("providers:", ", ".join(f"{p.name}:{p.model}" for p in providers), flush=True)

    final_code = 0
    for problem in selected:
        verdict = run_problem(problem, providers, args)
        print(f"{problem['id']}: {verdict['status']} -> {verdict['run_dir']}", flush=True)
        if verdict["status"] not in ("pass",):
            final_code = 2
            if args.all:
                break
    return final_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem", help="Problem id from swarm/problems.json. Defaults to the first problem.")
    parser.add_argument("--provider", default="auto", help="Single provider name. Alias for --providers.")
    parser.add_argument("--providers", help="Comma list: auto, mock, openai, anthropic, gemini.")
    parser.add_argument("--all", action="store_true", help="Run every queued problem until one does not pass.")
    parser.add_argument("--list", action="store_true", help="List queued problems and exit.")
    parser.add_argument("--run-tests", action="store_true", help="Run problem test_commands as part of the gate.")
    parser.add_argument("--interactive", action="store_true", help="Prompt for owner answer when judge asks the user.")
    parser.add_argument("--user-note", default="", help="Owner note to include in this run.")
    parser.add_argument("--context-chars", type=int, default=6000, help="Max chars to include per context file.")
    parser.add_argument("--timeout", type=int, default=120, help="Seconds per test command.")
    return parser.parse_args()


def load_problems() -> list[dict[str, Any]]:
    with PROBLEMS_FILE.open(encoding="utf-8") as f:
        problems = json.load(f)
    if not isinstance(problems, list):
        raise SystemExit("swarm/problems.json must contain a list")
    return problems


def list_problems(problems: list[dict[str, Any]]) -> None:
    for p in problems:
        print(f"{p['id']}: {p['title']}")


def select_problems(problems: list[dict[str, Any]], problem_id: str | None, all_: bool) -> list[dict[str, Any]]:
    if all_:
        return problems
    if problem_id is None:
        return [problems[0]]
    for p in problems:
        if p.get("id") == problem_id:
            return [p]
    raise SystemExit(f"Unknown problem id: {problem_id}")


def build_providers(spec: str) -> list[Provider]:
    names = [x.strip() for x in spec.split(",") if x.strip()]
    if names == ["auto"]:
        detected: list[str] = []
        if os.environ.get("OPENAI_API_KEY"):
            detected.append("openai")
        if os.environ.get("ANTHROPIC_API_KEY"):
            detected.append("anthropic")
        if os.environ.get("GEMINI_API_KEY"):
            detected.append("gemini")
        names = detected or ["mock"]

    providers: list[Provider] = []
    for name in names:
        factory = PROVIDER_FACTORIES.get(name)
        if factory is None:
            raise SystemExit(f"Unknown provider: {name}")
        providers.append(factory())
    return providers


def run_problem(problem: dict[str, Any], providers: list[Provider], args: argparse.Namespace) -> dict[str, Any]:
    run_dir = make_run_dir(problem["id"])
    transcript = JsonlLog(run_dir / "transcript.jsonl")
    context = read_context(problem, args.context_chars)
    owner_notes = [args.user_note] if args.user_note else []
    rounds: list[dict[str, Any]] = []
    status = "retry"
    last_judge: dict[str, Any] | None = None
    test_result = {"status": "not_run", "commands": []}

    max_rounds = int(problem.get("max_rounds", 2))
    for round_no in range(1, max_rounds + 1):
        round_state: dict[str, Any] = {"round": round_no}
        base_payload = build_problem_payload(problem, context, owner_notes, rounds)

        planner = ask_agent(providers[0], "planner", base_payload, transcript)
        round_state["planner"] = planner

        builders = [
            ask_agent(provider, "builder", base_payload + "\n\nPLANNER:\n" + json.dumps(planner, ensure_ascii=False), transcript)
            for provider in providers
        ]
        round_state["builders"] = builders

        critics_payload = base_payload + "\n\nBUILDER_PROPOSALS:\n" + json.dumps(builders, ensure_ascii=False, indent=2)
        critics = [ask_agent(provider, "critic", critics_payload, transcript) for provider in providers]
        round_state["critics"] = critics

        if args.run_tests:
            test_result = run_tests(problem, args.timeout)
            transcript.write({"type": "tests", "round": round_no, "result": test_result})
        round_state["tests"] = test_result

        judge_payload = (
            base_payload
            + "\n\nPLANNER:\n" + json.dumps(planner, ensure_ascii=False, indent=2)
            + "\n\nBUILDER_PROPOSALS:\n" + json.dumps(builders, ensure_ascii=False, indent=2)
            + "\n\nCRITIQUES:\n" + json.dumps(critics, ensure_ascii=False, indent=2)
            + "\n\nTEST_STATUS: " + test_result["status"]
            + "\nTEST_RESULT:\n" + json.dumps(test_result, ensure_ascii=False, indent=2)
        )
        judge = ask_agent(providers[0], "judge", judge_payload, transcript)
        last_judge = judge
        round_state["judge"] = judge
        rounds.append(round_state)

        status = decide_status(judge, test_result, args.run_tests, round_no, max_rounds)
        if status == "ask_user" and args.interactive:
            answer = input((judge.get("ask_user") or "Owner input needed") + "\n> ").strip()
            owner_notes.append(answer)
            status = "retry"
            continue
        if status in ("pass", "ask_user", "fail"):
            break

    scribe_payload = build_problem_payload(problem, context, owner_notes, rounds)
    if last_judge:
        scribe_payload += "\n\nFINAL_JUDGE:\n" + json.dumps(last_judge, ensure_ascii=False, indent=2)
    scribe_payload += "\n\nTEST_STATUS: " + test_result["status"]
    scribe = ask_agent(providers[0], "scribe", scribe_payload, transcript)

    verdict = {
        "problem_id": problem["id"],
        "title": problem["title"],
        "status": status,
        "provider_models": [{"provider": p.name, "model": p.model} for p in providers],
        "rounds": len(rounds),
        "run_tests": bool(args.run_tests),
        "test_status": test_result["status"],
        "judge": last_judge,
        "scribe": scribe,
        "run_dir": str(run_dir)
    }
    write_json(run_dir / "verdict.json", verdict)
    write_summary(run_dir / "SUMMARY.md", problem, verdict, rounds, test_result)
    if status == "ask_user":
        write_ask_user(run_dir / "ASK_USER.md", problem, last_judge)
    return verdict


def make_run_dir(problem_id: str) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", problem_id)
    run_dir = RUNS_DIR / f"{stamp}_{safe}"
    run_dir.mkdir()
    return run_dir


def read_context(problem: dict[str, Any], max_chars: int) -> str:
    chunks: list[str] = []
    for rel in problem.get("context_files", []):
        path = (ROOT / rel).resolve()
        if ROOT not in path.parents and path != ROOT:
            chunks.append(f"\n## {rel}\n[skipped: outside repository]\n")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            chunks.append(f"\n## {rel}\n[skipped: non-utf8 file]\n")
            continue
        except FileNotFoundError:
            chunks.append(f"\n## {rel}\n[missing]\n")
            continue
        suffix = "\n[truncated]\n" if len(text) > max_chars else ""
        chunks.append(f"\n## {rel}\n{text[:max_chars]}{suffix}")
    return "\n".join(chunks)


def build_problem_payload(
    problem: dict[str, Any],
    context: str,
    owner_notes: list[str],
    previous_rounds: list[dict[str, Any]]
) -> str:
    compact = {
        "id": problem.get("id"),
        "title": problem.get("title"),
        "question": problem.get("question"),
        "acceptance": problem.get("acceptance", []),
        "ask_user_when": problem.get("ask_user_when", [])
    }
    prior = summarize_rounds(previous_rounds)
    return (
        "PROBLEM:\n"
        + json.dumps(compact, ensure_ascii=False, indent=2)
        + "\n\nOWNER_NOTES:\n"
        + ("\n".join(owner_notes) if owner_notes else "[none]")
        + "\n\nPREVIOUS_ROUNDS:\n"
        + (prior if prior else "[none]")
        + "\n\nREPOSITORY_CONTEXT:\n"
        + context
    )


def summarize_rounds(rounds: list[dict[str, Any]]) -> str:
    rows = []
    for r in rounds:
        judge = r.get("judge") or {}
        rows.append({
            "round": r.get("round"),
            "judge_verdict": judge.get("verdict"),
            "judge_claim": judge.get("main_claim"),
            "required_fix": judge.get("required_fix")
        })
    return json.dumps(rows, ensure_ascii=False, indent=2) if rows else ""


def ask_agent(provider: Provider, role: str, payload: str, transcript: "JsonlLog") -> dict[str, Any]:
    role_prompt = (AGENTS_DIR / f"{role}.md").read_text(encoding="utf-8")
    system = textwrap.dedent(
        f"""
        You are one role in a multi-LLM research system for Bonded Validation / IIS.
        Follow the role instructions exactly.

        JSON response schema:
        {json.dumps(AGENT_SCHEMA, ensure_ascii=False)}

        Field rules:
        - role: "{role}"
        - verdict: propose/reject/pass/retry/ask_user/fail
        - confidence: 0.0 to 1.0
        - evidence and risks: concrete bullet strings
        - ask_user: empty string unless owner input is required

        {role_prompt}
        """
    ).strip()
    user = f"ROLE: {role}\n\n{payload}\n\nReturn only JSON."
    t0 = time.perf_counter()
    try:
        raw = provider.complete(system, user, AGENT_SCHEMA)
        parsed = parse_agent_json(raw, role)
        error = None
    except Exception as exc:
        raw = ""
        parsed = error_response(role, exc)
        error = repr(exc)
    elapsed = round(time.perf_counter() - t0, 3)
    transcript.write({
        "type": "agent",
        "provider": provider.name,
        "model": provider.model,
        "role": role,
        "elapsed_seconds": elapsed,
        "raw": raw,
        "parsed": parsed,
        "error": error
    })
    return parsed


def parse_agent_json(raw: str, role: str) -> dict[str, Any]:
    text = raw.strip()
    if not text:
        raise ProviderError("empty provider response")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ProviderError("agent response is not an object")
    normalized = {
        "role": str(data.get("role") or role),
        "verdict": str(data.get("verdict") or "retry"),
        "confidence": float(data.get("confidence") or 0.0),
        "main_claim": str(data.get("main_claim") or ""),
        "evidence": list(map(str, data.get("evidence") or [])),
        "risks": list(map(str, data.get("risks") or [])),
        "required_fix": str(data.get("required_fix") or ""),
        "next_action": str(data.get("next_action") or ""),
        "ask_user": str(data.get("ask_user") or "")
    }
    if normalized["verdict"] not in {"propose", "reject", "pass", "retry", "ask_user", "fail"}:
        normalized["verdict"] = "retry"
    return normalized


def error_response(role: str, exc: Exception) -> dict[str, Any]:
    return {
        "role": role,
        "verdict": "retry",
        "confidence": 0.0,
        "main_claim": "Provider call failed.",
        "evidence": [repr(exc)],
        "risks": ["The round lacks this role's independent review."],
        "required_fix": "Fix provider configuration or retry with mock.",
        "next_action": "Retry.",
        "ask_user": ""
    }


def decide_status(
    judge: dict[str, Any],
    test_result: dict[str, Any],
    tests_requested: bool,
    round_no: int,
    max_rounds: int
) -> str:
    if tests_requested and test_result["status"] == "failed":
        return "ask_user" if round_no >= max_rounds else "retry"
    if judge.get("ask_user") or judge.get("verdict") == "ask_user":
        return "ask_user"
    if judge.get("verdict") == "pass":
        return "pass"
    if judge.get("verdict") == "fail":
        return "fail"
    if round_no >= max_rounds:
        return "ask_user"
    return "retry"


def run_tests(problem: dict[str, Any], timeout: int) -> dict[str, Any]:
    commands = []
    failed = False
    for spec in problem.get("test_commands", []):
        cmd = spec["cmd"] if isinstance(spec, dict) else str(spec)
        cwd_rel = spec.get("cwd", ".") if isinstance(spec, dict) else "."
        cwd = (ROOT / cwd_rel).resolve()
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                shell=True,
                text=True,
                capture_output=True,
                timeout=timeout
            )
            out = proc.stdout[-6000:]
            err = proc.stderr[-6000:]
            code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or "")[-6000:] if isinstance(exc.stdout, str) else ""
            err = (exc.stderr or "")[-6000:] if isinstance(exc.stderr, str) else ""
            code = 124
        elapsed = round(time.perf_counter() - started, 3)
        failed = failed or code != 0
        commands.append({
            "cmd": cmd,
            "cwd": str(cwd.relative_to(ROOT) if ROOT in cwd.parents or cwd == ROOT else cwd),
            "returncode": code,
            "elapsed_seconds": elapsed,
            "stdout_tail": out,
            "stderr_tail": err
        })
    if not commands:
        status = "no_tests"
    else:
        status = "failed" if failed else "passed"
    return {"status": status, "commands": commands}


def write_summary(
    path: Path,
    problem: dict[str, Any],
    verdict: dict[str, Any],
    rounds: list[dict[str, Any]],
    test_result: dict[str, Any]
) -> None:
    lines = [
        f"# {problem['title']}",
        "",
        f"- problem_id: `{problem['id']}`",
        f"- status: `{verdict['status']}`",
        f"- rounds: `{verdict['rounds']}`",
        f"- tests: `{test_result['status']}`",
        "",
        "## Judge",
        "",
    ]
    judge = verdict.get("judge") or {}
    lines += [
        judge.get("main_claim", ""),
        "",
        f"- verdict: `{judge.get('verdict', '')}`",
        f"- confidence: `{judge.get('confidence', '')}`",
        f"- required_fix: {judge.get('required_fix', '')}",
        f"- next_action: {judge.get('next_action', '')}",
        "",
        "## Evidence",
        ""
    ]
    for item in judge.get("evidence", []):
        lines.append(f"- {item}")
    lines += ["", "## Risks", ""]
    for item in judge.get("risks", []):
        lines.append(f"- {item}")
    lines += ["", "## Rounds", ""]
    for r in rounds:
        lines.append(f"- round {r['round']}: judge={r.get('judge', {}).get('verdict', '')}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_ask_user(path: Path, problem: dict[str, Any], judge: dict[str, Any] | None) -> None:
    question = (judge or {}).get("ask_user") or "Owner decision required."
    body = f"""# Owner Decision Needed

Problem: `{problem['id']}` — {problem['title']}

{question}

Context:
- Judge claim: {(judge or {}).get('main_claim', '')}
- Required fix: {(judge or {}).get('required_fix', '')}

Answer with a short policy decision, then rerun with:

```bash
python3 swarm/orchestrator.py --problem {problem['id']} --user-note "YOUR_DECISION"
```
"""
    path.write_text(body, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class JsonlLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, event: dict[str, Any]) -> None:
        event = {"ts": datetime.now().isoformat(timespec="seconds"), **event}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _post_json(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Network error: {exc}") from exc


def _openai_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    texts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if isinstance(content.get("text"), str):
                texts.append(content["text"])
            elif isinstance(content.get("output_text"), str):
                texts.append(content["output_text"])
    if texts:
        return "\n".join(texts)
    raise ProviderError(f"Unexpected OpenAI response: {data}")


def _extract_role(user: str) -> str:
    match = re.search(r"^ROLE:\s*(\w+)", user, flags=re.M)
    return match.group(1) if match else "builder"


def _extract_problem_title(user: str) -> str:
    match = re.search(r'"title":\s*"([^"]+)"', user)
    return match.group(1) if match else "the current problem"


def _extract_problem_id(user: str) -> str:
    match = re.search(r'"id":\s*"([^"]+)"', user)
    return match.group(1) if match else ""


def _extract_marker(user: str, marker: str) -> str:
    match = re.search(rf"^{re.escape(marker)}:\s*(.+)$", user, flags=re.M)
    return match.group(1).strip() if match else ""


def _extract_section(user: str, start: str, end: str) -> str:
    pattern = rf"^{re.escape(start)}:\n(.*?)(?:\n\n{re.escape(end)}:|\Z)"
    match = re.search(pattern, user, flags=re.M | re.S)
    return match.group(1).strip() if match else ""


if __name__ == "__main__":
    raise SystemExit(main())
