#!/usr/bin/env bash
set -euo pipefail

MAIN_LOG="${CC_MAIN_LOG:-}"
APPLY_LOG="${CC_APPLY_LOG:-}"
START_OFFSET="${CC_START_OFFSET:-1}"
LOG_HOST="${CC_LOG_HOST:-}"
LOG_USER="${CC_LOG_USER:-}"
LOG_PASS="${CC_LOG_PASS:-}"
SSH_OPTS="${CC_LOG_SSH_OPTS:-}"

if [[ -z "$MAIN_LOG" ]]; then
  echo "CC_MAIN_LOG is required" >&2
  exit 2
fi

remote_cmd() {
  local cmd="$1"
  if [[ -n "$LOG_HOST" ]]; then
    local target="$LOG_HOST"
    if [[ -n "$LOG_USER" ]]; then
      target="$LOG_USER@$LOG_HOST"
    fi
    if [[ -n "$LOG_PASS" ]] && command -v sshpass >/dev/null 2>&1; then
      sshpass -p "$LOG_PASS" ssh $SSH_OPTS "$target" "$cmd"
    else
      ssh $SSH_OPTS "$target" "$cmd"
    fi
  else
    bash -lc "$cmd"
  fi
}

tail_from_offset() {
  local file="$1"
  remote_cmd "tail -c +$START_OFFSET '$file'"
}

count_pattern() {
  local pattern="$1"
  tail_from_offset "$MAIN_LOG" | rg -c "$pattern" || true
}

echo "main_log=$MAIN_LOG"
if [[ -n "$APPLY_LOG" ]]; then
  echo "apply_log=$APPLY_LOG"
fi
echo "start_offset=$START_OFFSET"
echo

echo "-- expected recovery counts --"
for p in \
  'DEADLINE_EXCEEDED' \
  'Region event error:not_leader' \
  'Region event error:epoch_not_match' \
  'Region event error:region_not_found' \
  'Begin to re schedule region request,reason:not_leader' \
  'Begin to re schedule region request,reason:grpc_error' \
  'Begin to re schedule range request' \
  'Region is initialized' \
  '\[REAL DDL\]' \
  'Fetch data rows:[1-9]'; do
  printf '%-64s %s\n' "$p" "$(count_pattern "$p")"
done

echo
echo "-- bad marker counts --"
for p in \
  'Process event failed' \
  'ErrPrewriteNotMatch' \
  'CheckpointTs is greater than next ddl commitTs' \
  'clusterIdMismatch' \
  'duplicateRequest' \
  'matched fastFailKeywords' \
  'Try to exist with System.exit' \
  'Offer event into store failed' \
  'Fetch ddl job table meta from pd is empty' \
  'Decode fails,value length is zero' \
  'Schedule skip' \
  'Duplicate'; do
  printf '%-64s %s\n' "$p" "$(count_pattern "$p")"
done

echo
echo "-- latest metrics --"
tail_from_offset "$MAIN_LOG" | rg '\[METRICS\]' | tail -n 8 || true

echo
echo "-- latest recovery lines --"
tail_from_offset "$MAIN_LOG" | rg 'DEADLINE_EXCEEDED|not_leader|epoch_not_match|region_not_found|Begin to re schedule|Region is initialized|\[REAL DDL\]|Fetch data rows' | tail -n 120 || true

if [[ -n "$APPLY_LOG" ]]; then
  echo
  echo "-- latest apply commits --"
  remote_cmd "tail -n 120 '$APPLY_LOG'" || true
fi
