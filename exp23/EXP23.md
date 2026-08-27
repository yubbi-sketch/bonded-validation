# Exp23 — 프로덕션 STARK 이식 (P10)

> 2026-08-27 · Exp22의 교육급 FRI를 감사받은 프로덕션 prover로 승격. 정직한
> 환경 제약: 이 머신엔 Rust/cargo 없고 crates.io 차단(403) — **프로덕션 prover를
> 여기서 실행 불가.** 그래서 "여기서 이식 완료"가 아니라 **다른 머신에서 바로
> 실행 가능한 이식 패키지**(prover 선정 + 정수 골든 레퍼런스 + 게스트 + 빌드법)를
> 만든다. prover 무관한 핵심(정수 명세)은 여기서 검증한다.

## 사전 등록 킬 기준 (실행 전 박제)

- **K1 정수 골든 레퍼런스**: 순수 정수(i64) 순전파가 float argmax와 테스트
  100문장에서 ≥95% 일치. (zkVM 게스트가 재현할 결정론 명세.)
- **K2 오버플로 안전**: 누적 최대 크기가 i64(63비트) 안. 로짓 비트폭 실측.
- **K3 prover 선정**: 4종(risc0/plonky2/winterfell/cairo-stwo) 평가로 PQ·투명·
  NN 적합·벤치마크 근거의 이식 결정 산출.

## 정직성 라벨

- **프로덕션 prover 실행은 이 환경에서 불가**(Rust 없음·네트워크 차단). 정수
  골든 레퍼런스는 실행·검증하지만, 실제 STARK 증명 생성은 별도 Rust 머신 몫.
- rsqrt는 결정론 정수 근사(게스트에선 룩업/제약). tanh는 정수 LUT(범위 실측).

## 결과 (2026-08-27)

### K1·K2 정수 골든 레퍼런스 — 통과
`fixed_point_ref.py` (scale 2^11, ezkl param_scale=11 일치):
- **정수 argmax == float argmax: 100/100 = 100%.**
- 최대 로짓 정수 38,836 (**16비트**), 누적 79k MAC × (2^11)^2 ≈ 2^39 < i64 → 오버플로 없음.
- tanh 정수 LUT 215,755개(입력 범위 [-125134, 90620] 실측).
- 이 정수 명세가 프로덕션 zkVM 게스트가 정확히 재현할 계산이다(prover 독립).

### K3 prover 선정 — 완료
prover 4종 병렬 평가(웹 근거, Ultracode 워크플로우) → `docs/stark-migration.md`:
- **risc0 zkVM = primary**(순전파를 Rust 게스트로, hand-AIR 불필요, 우리 규모 작음).
- **치명 주의: risc0 기본 Groth16-BN254 래퍼는 페어링→PQ 아님. STARK/succinct
  리시트 그대로 쓰고 Groth16 거부해야 양자 내성 유지.**
- winterfell(조밀 hand-AIR)·stwo/cairo(성능)·plonky2(대안)는 대안.

## 산출물
- `fixed_point_ref.py` — 정수 골든 레퍼런스(argmax 100/100, prover 독립·여기서 검증).
- `risc0_guest.rs` — risc0 게스트 스켈레톤(정수 순전파, journal=입력해시+튜플, image ID=모델 커밋).
- `docs/stark-migration.md` — prover 결정·PQ 함정·빌드법·남은 실측.

## 결론
정직한 환경 제약(Rust 없음) 하에서 **이식을 설계·정수코어 검증·패키징**했다.
실제 프로덕션 증명 실행은 별도 Rust 머신 몫 — 그 패키지가 준비됐다.
