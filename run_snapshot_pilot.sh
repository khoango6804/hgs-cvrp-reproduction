#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

out=${HGS_SNAPSHOT_OUTPUT:-results/snapshot-pilot}
time_fraction=${HGS_SNAPSHOT_FRACTION:-0.03}
selection=${HGS_SNAPSHOT_SELECTION:-even}
if (( $# == 0 )); then set -- 11 12 13 14 15; fi
mkdir -p "$out"
exec 9>"$out/runner.lock"
flock -n 9 || exit 1
exec >>"$out/runner.log" 2>&1
rm -f -- "$out/exit_code"
trap 'printf "%s\n" "$?" > "$out/exit_code"' EXIT

build=$(mktemp -d)
trap 'status=$?; rm -r -- "$build"; printf "%s\n" "$status" > "$out/exit_code"' EXIT
cp HGS-CVRP-1.0.0/Program/*.{cpp,h} "$build"
python3 - "$build/Population.cpp" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()
anchor = 'bestSolutionOverall = *indiv;'
assert text.count(anchor) == 1
path.write_text('#include <cstdlib>\n' + text.replace(anchor, anchor + '''
            if (const char* prefix = std::getenv("HGS_SNAPSHOT_PREFIX")) {
                auto stamp = clock();
                bestSolutionOverall.exportCVRPLibFormat(std::string(prefix) + std::to_string(stamp) + ".sol");
            }'''))
PY
g++ -O3 -std=c++11 "$build"/*.cpp -o "$out/genvrp"

# The wrapper assigns each trial its own snapshot prefix. The released source stays intact.
cat > "$out/genvrp-with-snapshots" <<'SH'
#!/usr/bin/env bash
set -eu
directory="$2.snapshots"
mkdir -p "$directory"
export HGS_SNAPSHOT_PREFIX="$directory/"
exec "$(dirname -- "$0")/genvrp" "$@"
SH
chmod +x "$out/genvrp-with-snapshots"
{
    date --iso-8601=seconds
    uname -sr
    cat /etc/os-release
    g++ --version | head -1
    getconf GNU_LIBC_VERSION
    printf 'Affinity: 0,2,4,6,8,10\nWorkers: 6\n'
    sha256sum "$out/genvrp" "$out/genvrp-with-snapshots"
} > "$out/environment.txt"
sha256sum "$out/genvrp" > "$out/instrumented-binary.sha256"
taskset -c 0,2,4,6,8,10 python3 -B -u reproduce.py --solver "$out/genvrp-with-snapshots" \
    --time-fraction "$time_fraction" --reserve-seconds 1 --seeds "$@" --jobs 6 --output "$out" \
    --resume --snapshot-trials
taskset -c 0 python3 -B -u compare_snapshots.py "$out" "$selection"
if [[ "$out" == results/snapshot-full ]]; then
    taskset -c 0 python3 -B -u report_snapshot_full.py
fi
