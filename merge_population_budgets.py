"""Select the best verified CVRP solutions across the 1× and 2× experiments."""

import argparse
import csv
import shutil
import time
from pathlib import Path

from benchmark_postprocess import cpu_time
from compare_equal_budget import require
from compare_population_pool import INSTANCES
from compare_snapshots import solve_pool
from reproduce import ROOT, read_instance, verify_solution, write_csv


RESULTS = ROOT / "results"
REFERENCE = RESULTS / "population-pool-full"
EXTENDED = RESULTS / "population-pool-2x"


def read_rows(directory, filename):
    with (directory / filename).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--one-budget", action="store_true", help="Evaluate the 1× pool independently")
    args = parser.parse_args()
    directories = [REFERENCE] if args.one_budget else [REFERENCE, EXTENDED]
    destination = directories[-1] / "merged"
    destination.mkdir(exist_ok=True)
    for directory in directories:
        require((directory / "exit_code").read_text().strip() == "0", f"Experiment incomplete: {directory}")
    comparisons = [{row["instance"]: row for row in read_rows(directory, "comparison-2stages.csv")}
                   for directory in directories]
    full_runs = [read_rows(directory, "runs.csv") for directory in directories]
    rows = []
    for name in INSTANCES:
        started = cpu_time()
        instance_path = ROOT / "HGS-CVRP-1.0.0/Instances/CVRP" / f"{name}.vrp"
        instance = read_instance(instance_path)
        finals = []
        samples = []
        for directory, runs in zip(directories, full_runs):
            trials = [row for row in runs if row["instance"] == name]
            require(len(trials) == 10 and {int(row["seed"]) for row in trials} == set(range(1, 11)),
                    f"Unexpected roster for {name} in {directory}")
            for trial in trials:
                path = directory / "trials" / f"{name}-seed{trial['seed']}.sol"
                require(verify_solution(path, instance)[0] == int(trial["cost"]), f"Invalid trial: {path}")
                finals.append(path)
                sampled = Path(f"{path}.snapshots")
                samples.extend(sampled / f"{stage}-{rank}.sol" for stage in (3, 4) for rank in (0, 1, 4))

        references = [data[name] for data in comparisons]
        bks = int(references[0]["bks_2020"])
        require(all(int(row["bks_2020"]) == bks for row in references), f"BKS changed for {name}")
        incumbents = [directory / f"{name}-{kind}-2stages.sol"
                      for directory in directories for kind in ("final", "population")]
        best = min(incumbents, key=lambda path: verify_solution(path, instance)[0])
        status = {}
        for kind, pool, milp_limit in (("final", finals, 5), ("population", finals + samples, 12)):
            output = destination / f"{name}-{kind}.sol"
            result = solve_pool(instance_path, pool + incumbents, output, milp_limit + 8, milp_limit)
            status[kind] = result is not None and result["optimal_in_pool"]
            if result is not None and verify_solution(output, instance)[0] < verify_solution(best, instance)[0]:
                best = output

        result_path = destination / f"{name}-best.sol"
        shutil.copyfile(best, result_path)
        cost = verify_solution(result_path, instance)[0]
        original = min(int(references[0][key]) for key in ("final_sp_cost", "population_sp_cost"))
        latest = min(int(references[-1][key]) for key in ("final_sp_cost", "population_sp_cost"))
        require(cost <= min(original, latest), f"Lost the incumbent for {name}")
        rows.append(dict(instance=name, bks_2020=bks, cost_1x=original, latest_cost=latest, best_cost=cost,
                         gap_1x_pct=100 * (original - bks) / bks, latest_gap_pct=100 * (latest - bks) / bks,
                         best_gap_pct=100 * (cost - bks) / bks, delta_vs_1x_pp=100 * (cost - original) / bks,
                         winning_source=str(best.relative_to(RESULTS)),
                         final_pool_optimal=status["final"], population_pool_optimal=status["population"],
                         merge_cpu_s=round(cpu_time() - started, 6),
                         hgs_cpu_s_across_budgets=round(sum(float(row["hgs_cpu_s"]) for row in references), 6)))
        print(rows[-1], flush=True)
    write_csv(destination / "comparison.csv", rows)


if __name__ == "__main__":
    main()
