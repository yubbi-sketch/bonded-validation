# Exp11 — 첫 기계 증명 (B 전환 1보)

테스트 → 정리 승격: `exp3/contracts/test/BondedValidatorProofs.t.sol`을
Halmos(심볼릭 실행, SMT)로 전 입력 공간에서 증명.

- T1 기권 무손실 · T2 슬래시 정확성 · T3 이중정산 불가 · T4 회계 보존 — 4/4
- 범위 정직성: 단일 주장 1회 정산 상태공간, tag 길이 0~1024 바운드.
  다중 주장 교차·패널 계층은 후속 증명 대상.

재현:
```bash
python3 -m venv .venv-halmos && .venv-halmos/bin/pip install halmos
cd exp3/contracts && ../../.venv-halmos/bin/halmos --contract BondedValidatorProofs
```
