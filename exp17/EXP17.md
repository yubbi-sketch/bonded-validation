# Exp17 — 규제 불변 바우처: 투자 실질 제거를 기계 증명 (R 트랙 1보)

> 2026-08-27 · "합법성을 관할 규제가 아니라 구조에서" — 도식의 실물화.
> 바우처 컨트랙트(ServiceVoucher)가 네 조건을 만족함을 Halmos로 증명한다.

## 네 조건 (투자 실질 = 0)

1. 가치 상승 불가 — 1크레딧 = 고정 액면·고정 서비스량(immutable), 상승 경로 없음
2. 전매 불가 — transfer/transferFrom/approve 전부 revert, 2차 시장 없음
3. 풀링 없음 — escrow는 환불 담보일 뿐, 홀더에게 수익 배분 경로 없음
4. 수익 없음 — 홀딩은 아무것도 안 낳음(잔액은 구매로만 증가)

## 사전 등록 킬 기준 (실행 전 박제)

- **K1 전매 봉쇄**: ∀ 입력에서 transfer·transferFrom·approve가 revert (Halmos UNSAT).
- **K2 비증식**: 구매(buy) 외 어떤 호출도 홀더 잔액을 늘리지 못한다. use·refund는
  호출자 본인 잔액만 감소, 제3자 잔액·escrow 불변(사용 시 돈 안 움직임).
- **K3 무이익 환불**: refund는 정확히 액면(amount×priceWei) 반환, 그 이상 불가.
  priceWei·serviceUnitPerCredit는 immutable(setter 없음) → 크레딧 현금가치 상승 불가능.
- **K4 표면 완전성**: 위 증명이 외부 상태변경 함수 전부(buy·use·refund·transfer·
  transferFrom·approve)를 덮는다. 다른 변경 경로가 있으면 실패.

## 정직성 라벨

- Halmos는 함수별로 증명한다. "어떤 경로도 없음"은 외부 상태변경 표면을 코드로
  열거해 그 전부를 증명함으로써 성립(K4) — 열거가 틀리면 증명도 빈다.
- 증명 대상은 **구조**(투자 실질 부재)이지 **특정 관할의 합법 판정이 아니다.**
  실런치 전 면허 변호사 확인 필수 — 이건 의존성 최소화이지 합법 보증이 아님.
- 결제(fiat)는 오프체인, 여기선 결제 토큰(LabToken)으로 모델링.

## 재현
```bash
cd exp3/contracts && forge clean
../../.venv-halmos/bin/halmos --contract ServiceVoucherProofs
forge test --match-contract ServiceVoucherTest
```

## 결과 (2026-08-27) — K1~K4 전부 충족

| 킬 기준 | 증명 | 판정 |
|---|---|---|
| K1 전매 봉쇄 | transfer·transferFrom·approve ∀입력 revert (Halmos) | ✅ |
| K2 비증식 | buy만 증가(결제 대가로만)·use는 안전 불변식(증가 없음·타인/escrow 불변) | ✅ |
| K3 무이익 환불 | refund 정확히 액면(amount×PRICE), priceWei·SPC immutable | ✅ |
| K4 표면 완전성 | 외부 상태변경 함수 6개 전부 함수별 증명으로 덮음 | ✅ |

Halmos 7/7 (심볼릭, 전 입력), 동작 Forge 4/4, 전체 스위트 63/63.

**의미:** "이 토큰은 어떤 실행 경로로도 상승·전매·수익을 못 만든다"가 주장이
아니라 **기계 증명된 컨트랙트 불변식**이 됐다. 규제 불변 축의 첫 실물 — 합법성이
'허가'가 아니라 '구조'에서 성립하는 것을 코드로 시연.

**정직성 한계(변함없음):** 구조(투자 실질 부재)를 증명한 것이지 특정 관할의
합법 판정이 아니다. use의 안전 불변식은 무바운드 증명, 결제 곱셈(buy·refund)은
amt<1e30 현실 범위 명기. 실런치 전 면허 변호사 확인 필수.
