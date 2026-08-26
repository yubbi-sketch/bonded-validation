# IIS Swarm Orchestrator

여러 LLM을 연구 동료·비판자·판정자로 돌리는 로컬 오케스트레이터다. LLM 합의만으로
통과시키지 않고, 문제별 acceptance criteria와 선택적 테스트 결과를 함께 기록한다.

## 빠른 실행

```bash
# API 키 없이 mock AI들로 회의 흐름 검증
python3 swarm/orchestrator.py --provider mock --problem exp8_judge_bond_attack_sim

# 저장된 문제 목록 보기
python3 swarm/orchestrator.py --list

# 실제 테스트까지 게이트에 포함
python3 swarm/orchestrator.py --provider mock --problem exp8_judge_bond_attack_sim --run-tests
```

실행 결과는 `swarm/runs/<timestamp>_<problem_id>/`에 생긴다.

- `transcript.jsonl`: 모든 에이전트 발언과 테스트 결과
- `verdict.json`: 최종 판정
- `SUMMARY.md`: 사람이 읽는 요약
- `ASK_USER.md`: 오너 결정이 필요한 경우에만 생성

## 실제 LLM 연결

환경변수가 있으면 provider를 직접 지정할 수 있다.

```bash
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export GEMINI_API_KEY="..."

python3 swarm/orchestrator.py \
  --providers openai,anthropic,gemini \
  --problem exp8_judge_bond_attack_sim \
  --run-tests
```

모델명은 환경변수로 교체한다.

```bash
export OPENAI_MODEL="gpt-5"
export ANTHROPIC_MODEL="claude-3-5-sonnet-latest"
export GEMINI_MODEL="gemini-1.5-pro"
```

`--providers auto`는 API 키가 있는 provider만 쓰고, 아무 키도 없으면 `mock`으로
떨어진다.

## 판정 원칙

1. LLM은 제안·반박·정리를 한다.
2. 통과는 acceptance criteria, 테스트 결과, judge 판정으로만 난다.
3. 실패가 구현 문제가 아니라 연구 방향 선택이면 `ASK_USER.md`를 만든다.
4. 통과하면 `--all` 모드에서 다음 문제로 넘어간다.

## 새 문제 추가

`swarm/problems.json`에 항목을 추가한다.

```json
{
  "id": "short_unique_id",
  "title": "문제 제목",
  "question": "이번 라운드에서 풀 질문",
  "context_files": ["docs/some-design.md", "exp3/contracts/src/Foo.sol"],
  "acceptance": ["통과 기준 1", "통과 기준 2"],
  "test_commands": [{"cmd": "forge test", "cwd": "exp3/contracts"}],
  "ask_user_when": ["방향 선택이 필요한 조건"],
  "max_rounds": 2
}
```
