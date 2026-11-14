#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

baseline=results/linux-full
output=results/equal-budget
mkdir -p "$output"
exec 9>"$output/runner.lock"
flock -n 9 || { echo 'The equal-budget benchmark is already running.' >&2; exit 1; }
exec >>"$output/runner.log" 2>&1

rm -f -- "$output/exit_code"
trap 'status=$?; printf "%s\n" "$status" > "$output/exit_code.tmp"; mv -f -- "$output/exit_code.tmp" "$output/exit_code"' EXIT

solver="$baseline/genvrp"
cpu_list=$(sed -n 's/^Affinity: //p' "$baseline/environment.txt")
IFS=, read -r -a cpus <<< "$cpu_list"
{
    date --iso-8601=seconds
    uname -sr
    getconf GNU_LIBC_VERSION
    python3 --version
    printf 'Affinity: %s\nWorkers: %s\n' "$cpu_list" "${#cpus[@]}"
    sha256sum "$solver"
} > "$output/environment.txt"

printf '\nEqual-budget benchmark started at %s\n' "$(date --iso-8601=seconds)"
taskset -c "$cpu_list" python3 -B -u reproduce.py --solver "$solver" --time-fraction 1 \
    --reserve-seconds 1 --seeds 1 2 3 4 5 6 7 8 9 10 --jobs "${#cpus[@]}" \
    --output "$output" --resume
taskset -c "${cpus[0]}" python3 -B compare_equal_budget.py
printf 'Benchmark finished at %s\n' "$(date --iso-8601=seconds)"
