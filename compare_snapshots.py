"""Measure the effect of including intermediate incumbents in the route pool."""

import csv
import json
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

from benchmark_postprocess import cpu_time
from compare_equal_budget import require
from reproduce import PILOT, ROOT, read_instance, verify_solution, write_csv
from route_pool import recombine


PILOT_DIR = ROOT / "results/snapshot-pilot"


def solve_pool(instance_path, paths, output, deadline, milp_seconds=1):
    try:
        process = subprocess.run([sys.executable, "-B", __file__, "--solve-pool", str(instance_path),
                                  str(output), str(milp_seconds), *map(str, paths)], capture_output=True, text=True,
                                 check=True, timeout=deadline)
    except subprocess.TimeoutExpired:
        return None
    return json.loads(process.stdout)


def main():
    directory = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else PILOT_DIR
    selection = sys.argv[2] if len(sys.argv) > 2 else "even"
    require(selection in ("even", "late"), "Snapshot selection must be 'even' or 'late'")
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    require(count >= 1 and (selection == "late" or count == 2), "Invalid snapshot count")
    suffix = "" if selection == "even" else "-late" if count == 2 else f"-late{count}"
    with (directory / "runs.csv").open(newline="", encoding="utf-8") as stream:
        runs = list(csv.DictReader(stream))
    seeds = sorted({int(row["seed"]) for row in runs})
    expected = {(name, seed) for name in PILOT for seed in seeds}
    require(len(runs) == len(expected) and {(r["instance"], int(r["seed"])) for r in runs} == expected,
            "Snapshot pilot is incomplete")
    rows = []
    for name in PILOT:
        instance_path = ROOT / "HGS-CVRP-1.0.0/Instances/CVRP" / f"{name}.vrp"
        instance = read_instance(instance_path)
        trials = [row for row in runs if row["instance"] == name]
        bks = int(trials[0]["bks_2020"])
        remaining = sum(int(row["time_limit_s"]) + 1 - float(row["solver_time_s"]) for row in trials)
        require(remaining > 0, f"No post-processing budget for {name}")
        finals = [directory / "trials" / f"{name}-seed{seed}.sol" for seed in seeds]
        outputs = []
        for method in ("final", "snapshots"):
            start = cpu_time()
            paths = list(finals)
            if method == "snapshots":
                for final in finals:
                    snapshots = sorted(Path(f"{final}.snapshots").glob("*.sol"))
                    require(snapshots, f"Missing snapshots for {final}")
                    snapshots.sort(key=lambda path: int(path.stem))
                    if selection == "late":
                        snapshots = snapshots[-count - 1:-1]
                    elif len(snapshots) > 2:
                        snapshots = [snapshots[i * (len(snapshots) - 1) // 3] for i in (1, 2)]
                    paths.extend(snapshots)
            output = directory / f"{name}-{method}{suffix}.sol"
            timed_out = False
            if method == "final":
                result = recombine(instance, paths, 1, output)
            else:
                deadline = remaining - outputs[0][1] - 0.25
                result = solve_pool(instance_path, paths, output, deadline) if deadline > 0 else None
                if result is None:
                    timed_out = True
                    result = dict(outputs[0][0], unique_customer_sets=None, optimal_in_pool=False)
                    shutil.copyfile(directory / f"{name}-final{suffix}.sol", output)
                elif result["recombined_cost"] > outputs[0][0]["recombined_cost"]:
                    result["recombined_cost"] = outputs[0][0]["recombined_cost"]
                    shutil.copyfile(directory / f"{name}-final{suffix}.sol", output)
            require(verify_solution(output, instance)[0] == result["recombined_cost"],
                    f"Saved cost mismatch for {name}, {method}")
            used = cpu_time() - start
            require(used <= remaining, f"{method} exceeded the CPU budget for {name}")
            outputs.append((result, used, len(paths), timed_out))
        (final, final_cpu, _, _), (snapshots, snapshot_cpu, path_count, timed_out) = outputs
        require(final_cpu + snapshot_cpu <= remaining, f"Combined snapshot pipeline exceeded budget for {name}")
        base_cost = final["best_hgs_cost"]
        final_cost = final["recombined_cost"]
        snapshot_cost = snapshots["recombined_cost"]
        row = dict(instance=name, bks_2020=bks, hgs_cost=base_cost, final_sp_cost=final_cost,
                   snapshot_sp_cost=snapshot_cost, final_pool_routes=final["unique_customer_sets"],
                   snapshot_pool_routes=snapshots["unique_customer_sets"], snapshot_count=path_count - len(seeds),
                   hgs_gap_pct=100 * (base_cost - bks) / bks,
                   final_sp_gap_pct=100 * (final_cost - bks) / bks,
                   snapshot_sp_gap_pct=100 * (snapshot_cost - bks) / bks,
                   delta_vs_final_sp_pp=100 * (snapshot_cost - final_cost) / bks,
                   final_sp_cpu_s=round(final_cpu, 6), snapshot_sp_cpu_s=round(snapshot_cpu, 6),
                   post_budget_s=round(remaining, 6), snapshot_pool_optimal=snapshots["optimal_in_pool"],
                   snapshot_timed_out=timed_out)
        rows.append(row)
        print(name, base_cost, final_cost, snapshot_cost, row["snapshot_pool_routes"], flush=True)
    write_csv(directory / f"pool_comparison{suffix}.csv", rows)
    for column in ("hgs_gap_pct", "final_sp_gap_pct", "snapshot_sp_gap_pct"):
        print(column, statistics.mean(row[column] for row in rows), flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--solve-pool":
        _, _, instance_file, output_file, milp_seconds, *solution_files = sys.argv
        print(json.dumps(recombine(read_instance(Path(instance_file)), list(map(Path, solution_files)),
                                   float(milp_seconds), Path(output_file))))
    else:
        main()
