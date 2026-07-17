#!/bin/zsh

# Detach run-frozen-campaign.sh so the batch survives the invoking session.

set -u

[[ $# -ge 3 ]] || {
  print -u2 "usage: $0 CAMPAIGN [--max-restarts N] -- COMMAND [ARG ...]"
  exit 2
}

campaign=$1
[[ $campaign =~ '^[A-Za-z0-9._-]+$' ]] || {
  print -u2 "invalid campaign name"
  exit 2
}

repo=${FROZEN_CAMPAIGN_REPO:-${0:A:h:h}}
runtime_root=${FROZEN_CAMPAIGN_RUNTIME_ROOT:-$repo/autoresearch-results/runtime}
runtime_dir=$runtime_root/$campaign
mkdir -p "$runtime_dir"

if [[ -x /usr/bin/screen ]]; then
  screen_session="viennaps-$campaign"
  /usr/bin/screen -dmS "$screen_session" \
    "$repo/scripts/run-frozen-campaign.sh" "$@"
  print -r -- "$screen_session" > "$runtime_dir/screen.session"
  print "launched $campaign in detached screen session $screen_session"
else
  nohup "$repo/scripts/run-frozen-campaign.sh" "$@" \
    >> "$runtime_dir/launcher.log" 2>&1 < /dev/null &
  launcher_pid=$!
  print -r -- "$launcher_pid" > "$runtime_dir/launcher.pid"
  print "launched $campaign supervisor PID $launcher_pid"
fi
print "status: $runtime_dir/status.json"
print "log:    $runtime_dir/run.log"
