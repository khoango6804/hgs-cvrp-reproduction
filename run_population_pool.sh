#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

out=${HGS_POPULATION_OUTPUT:-results/population-pool}
fraction=${HGS_POPULATION_FRACTION:-0.1}
if (( $# == 0 )); then set -- 21 22 23 24 25; fi
mkdir -p "$out"
exec 9>"$out/runner.lock"
flock -n 9
exec >>"$out/runner.log" 2>&1
rm -f -- "$out/exit_code"
build=$(mktemp -d)
trap 'status=$?; rm -r -- "$build"; printf "%s\n" "$status" > "$out/exit_code"' EXIT
cp HGS-CVRP-1.0.0/Program/*.{cpp,h} "$build"
python3 - "$build" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])


def patch(name, anchor, replacement):
    path = root / name
    source = path.read_text()
    assert source.count(anchor) == 1, (name, anchor)
    path.write_text(source.replace(anchor, replacement))


anchor = 'void exportSearchProgress(std::string fileName, std::string instanceName, int seedRNG);'
patch('Population.h', anchor, anchor + '\n   void exportFeasibleSample(const std::string& prefix);')
with (root / 'Population.cpp').open('a') as source:
    source.write('''
void Population::exportFeasibleSample(const std::string& prefix)
{
    // Sample low-cost survivors and a deeper-ranked survivor without consuming RNG.
    for (int rank : {0, 1, 4}) {
        if (rank < static_cast<int>(feasibleSubpopulation.size()))
            feasibleSubpopulation[rank]->exportCVRPLibFormat(prefix + std::to_string(rank) + ".sol");
    }
}
''')
patch('Genetic.cpp', '#include "Genetic.h"', '#include "Genetic.h"\n#include <cstdlib>')
patch('Genetic.cpp', 'int nbIterNonProd = 1;', '''int nbIterNonProd = 1;
    const char* samplePrefix = std::getenv("HGS_SAMPLE_PREFIX");
    const double sampleFractions[] = {0.50, 0.70, 0.85, 0.95, 0.99};
    int sample = 0;''')
anchor = '\t\t/* TRACKING THE NUMBER OF ITERATIONS SINCE LAST SOLUTION IMPROVEMENT */'
patch('Genetic.cpp', anchor, '''        if (samplePrefix && sample < 5 &&
            static_cast<double>(clock()) / CLOCKS_PER_SEC >= timeLimit * sampleFractions[sample]) {
            population->exportFeasibleSample(std::string(samplePrefix) + std::to_string(sample) + "-");
            ++sample;
        }

''' + anchor)
PY
g++ -O3 -Wall -std=c++11 "$build"/*.cpp -o "$out/genvrp"

cat > "$out/genvrp-with-population" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
directory="$2.snapshots"
mkdir -p "$directory"
export HGS_SAMPLE_PREFIX="$directory/"
exec "$(dirname -- "$0")/genvrp" "$@"
SH
if [[ ! -x "$out/genvrp-with-population" ]]; then
    chmod +x "$out/genvrp-with-population"
fi
{
    uname -sr
    g++ --version | head -1
    sha256sum "$out/genvrp" "$out/genvrp-with-population"
} > "$out/environment.txt"
taskset -c 0,2,4,6,8,10 python3 -B -u reproduce.py --solver "$out/genvrp-with-population" \
    --instances X-n627-k43 X-n1001-k43 --time-fraction "$fraction" --reserve-seconds 3 \
    --seeds "$@" --jobs 6 --output "$out" --resume --snapshot-trials
taskset -c 0 python3 -B -u compare_population_pool.py --output "$out" --fraction "$fraction" --seeds "$@"
