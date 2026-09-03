#!/bin/zsh
# Exp30 K2(c) 후반 — 미개설 주장 소멸 호출 (제3자 EOA). 키 값은 어디에도 출력하지 않는다.
# 사전등록(EXP30.md §5 K2(c)): 실주장 1건 미개설 → W 후 제3자 EOA settleUnchallenged 성공(tx 해시·ClaimLapsed).
set -u
export PATH=$HOME/.foundry/bin:$PATH
LAB=$HOME/iis-lab
LOG=$LAB/exp30/logs/sepolia-v03-k2c-settle.log
RPC=${SEPOLIA_RPC:-https://ethereum-sepolia-rpc.publicnode.com}
BV3=0xd881d52F10220687297651DeC4d55C1644d3a2A7
H=0xa4f55aa9d15b3847884b887662e1b9562f3c96abb2453abeef6a9fcec9579740
LAPSE_AT=1788471864
KS=$LAB/keys/exp30-k2c-thirdparty
PW=$LAB/keys/exp30-k2c-thirdparty.pw
THIRD=0xd9E90164623bFe77d7DfE008d21032943808bb79
mkdir -p "$(dirname "$LOG")"
{
  echo "=== $(date -u +%FT%TZ) k2c_settle start (mode=${1:-run}) ==="
  TS=$(cast block latest --rpc-url "$RPC" -f timestamp)
  echo "chain ts=$TS lapse_at=$LAPSE_AT"
  echo "before: claimSettled=$(cast call $BV3 'claimSettled(bytes32)(bool)' $H --rpc-url $RPC) engaged=$(cast call $BV3 'engaged(bytes32)(bool)' $H --rpc-url $RPC 2>/dev/null)"
  if [ "${1:-run}" = "dry" ]; then
    echo "dry-run: cast call (no tx)"; cast call $BV3 'settleUnchallenged(bytes32)' $H --from $THIRD --rpc-url $RPC 2>&1 | tail -2
    echo "=== dry end ==="; exit 0
  fi
  if [ "$TS" -le "$LAPSE_AT" ]; then echo "window still open (ts<=lapse_at) — abort, rerun later"; exit 2; fi
  BAL=$(cast balance $THIRD --rpc-url $RPC); echo "third-party balance wei=$BAL"
  if [ "$BAL" = "0" ]; then echo "third-party wallet unfunded — abort"; exit 3; fi
  cast send $BV3 'settleUnchallenged(bytes32)' $H --rpc-url "$RPC" --keystore "$KS" --password-file "$PW" --json 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('tx', d.get('transactionHash'), 'status', d.get('status'), 'block', d.get('blockNumber')); print('logs', len(d.get('logs',[])))"
  echo "after: claimSettled=$(cast call $BV3 'claimSettled(bytes32)(bool)' $H --rpc-url $RPC)"
  echo "ClaimLapsed events: $(cast logs --rpc-url $RPC --address $BV3 'ClaimLapsed(bytes32)' $H --from-block 11622286 2>/dev/null | grep -c blockNumber)"
  echo "=== end ==="
} >> "$LOG" 2>&1
