#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

output=results/linux-full
mkdir -p "$output"
exec 9>"$output/runner.lock"
flock -n 9 || { echo 'The Linux benchmark is already running.' >&2; exit 1; }
exec >>"$output/runner.log" 2>&1

rm -f -- "$output/exit_code"
trap 'status=$?; printf "%s\n" "$status" > "$output/exit_code.tmp"; mv -f -- "$output/exit_code.tmp" "$output/exit_code"' EXIT

solver="$output/genvrp"
if [[ ! -x "$solver" ]]; then
    g++ -O3 -Wall -std=c++11 HGS-CVRP-1.0.0/Program/*.cpp -o "$solver"
fi

# Take one available logical CPU per physical core, up to six cores.
cpu_list=$(python3 - <<'PY'
import os
import subprocess

allowed = os.sched_getaffinity(0)
cores = {}
for line in subprocess.check_output(['lscpu', '-p=CPU,CORE,SOCKET'], text=True).splitlines():
    if line.startswith('#'):
        continue
    cpu, core, socket = map(int, line.split(','))
    if cpu in allowed:
        cores.setdefault((socket, core), cpu)
print(','.join(map(str, list(cores.values())[:6])))
PY
)
IFS=, read -r -a cpus <<< "$cpu_list"

{
    date --iso-8601=seconds
    uname -sr
    cat /etc/os-release
    g++ --version
    getconf GNU_LIBC_VERSION
    python3 --version
    lscpu -e=CPU,CORE,SOCKET
    printf 'Affinity: %s\nWorkers: %s\n' "$cpu_list" "${#cpus[@]}"
    sha256sum "$solver"
} > "$output/environment.txt"

printf '\nFull-budget benchmark started at %s\n' "$(date --iso-8601=seconds)"
taskset -c "$cpu_list" python3 -B -u reproduce.py --solver "$solver" --time-fraction 1 \
    --seeds 1 2 3 4 5 6 7 8 9 10 --jobs "${#cpus[@]}" --output "$output" --resume
printf 'Benchmark finished at %s\n' "$(date --iso-8601=seconds)"
