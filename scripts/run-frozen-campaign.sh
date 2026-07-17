#!/bin/zsh

# Supervise one immutable, resumable campaign command.
# This script never changes a manifest or constructs a new experiment.

set -u

usage() {
  print -u2 "usage: $0 CAMPAIGN [--max-restarts N] -- COMMAND [ARG ...]"
  exit 2
}

[[ $# -ge 3 ]] || usage
campaign=$1
shift
[[ $campaign =~ '^[A-Za-z0-9._-]+$' ]] || {
  print -u2 "campaign must contain only letters, numbers, dot, underscore, or dash"
  exit 2
}

max_restarts=2
if [[ ${1:-} == "--max-restarts" ]]; then
  [[ $# -ge 3 ]] || usage
  max_restarts=$2
  shift 2
fi
[[ $max_restarts == <0-> ]] || {
  print -u2 "--max-restarts must be a non-negative integer"
  exit 2
}
[[ ${1:-} == "--" ]] || usage
shift
[[ $# -gt 0 ]] || usage

repo=${FROZEN_CAMPAIGN_REPO:-${0:A:h:h}}
runtime_root=${FROZEN_CAMPAIGN_RUNTIME_ROOT:-$repo/autoresearch-results/runtime}
heartbeat_seconds=${FROZEN_CAMPAIGN_HEARTBEAT_SECONDS:-60}
retry_seconds=${FROZEN_CAMPAIGN_RETRY_SECONDS:-15}
[[ $heartbeat_seconds == <1-> && $retry_seconds == <0-> ]] || {
  print -u2 "heartbeat seconds must be positive and retry seconds non-negative"
  exit 2
}
runtime_dir=$runtime_root/$campaign
lock_dir=$runtime_dir/active.lock
mkdir -p "$runtime_dir"
cd "$repo" || {
  print -u2 "campaign repository is unavailable: $repo"
  exit 2
}

if ! mkdir "$lock_dir" 2>/dev/null; then
  prior_pid=""
  [[ -f $lock_dir/supervisor.pid ]] && prior_pid=$(<$lock_dir/supervisor.pid)
  if [[ $prior_pid == <1-> ]] && kill -0 "$prior_pid" 2>/dev/null; then
    print -u2 "campaign '$campaign' is already supervised by PID $prior_pid"
    exit 3
  fi
  stale="$runtime_dir/stale-lock-$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$lock_dir" "$stale"
  mkdir "$lock_dir" || exit 3
fi

print -r -- $$ > "$lock_dir/supervisor.pid"
print -r -- $$ > "$runtime_dir/supervisor.pid"
printf '%q ' "$@" > "$runtime_dir/command.txt"
print >> "$runtime_dir/command.txt"

started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
child_pid=0
attempt=0
last_exit="null"
state="starting"

write_status() {
  local heartbeat tmp
  heartbeat=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  tmp="$runtime_dir/status.json.tmp.$$"
  print -r -- "{\"campaign\":\"$campaign\",\"status\":\"$state\",\"supervisor_pid\":$$,\"child_pid\":$child_pid,\"attempt\":$attempt,\"max_restarts\":$max_restarts,\"started_at\":\"$started_at\",\"heartbeat\":\"$heartbeat\",\"last_exit_code\":$last_exit}" > "$tmp"
  mv "$tmp" "$runtime_dir/status.json"
}

release_lock() {
  rm -f "$lock_dir/supervisor.pid"
  rmdir "$lock_dir" 2>/dev/null || true
}

terminate_tree() {
  local root_pid=$1 descendant
  for descendant in $(pgrep -P "$root_pid" 2>/dev/null); do
    terminate_tree "$descendant"
  done
  kill -TERM "$root_pid" 2>/dev/null || true
}

interrupt() {
  state="interrupted"
  last_exit=130
  write_status
  if [[ $child_pid == <1-> ]] && kill -0 "$child_pid" 2>/dev/null; then
    terminate_tree "$child_pid"
    wait "$child_pid" 2>/dev/null || true
  fi
  exit 130
}

trap release_lock EXIT
trap interrupt INT TERM

while (( attempt <= max_restarts )); do
  attempt=$((attempt + 1))
  state="running"
  last_exit="null"
  print -r -- "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] attempt $attempt" >> "$runtime_dir/run.log"
  "$@" >> "$runtime_dir/run.log" 2>&1 &
  child_pid=$!
  print -r -- "$child_pid" > "$runtime_dir/child.pid"
  write_status

  while kill -0 "$child_pid" 2>/dev/null; do
    write_status
    sleep "$heartbeat_seconds"
  done

  wait "$child_pid"
  last_exit=$?
  child_pid=0
  if (( last_exit == 0 )); then
    state="complete"
    write_status
    exit 0
  fi

  state="retry_wait"
  write_status
  if (( attempt > max_restarts )); then
    break
  fi
  sleep "$retry_seconds"
done

state="failed"
write_status
exit "$last_exit"
