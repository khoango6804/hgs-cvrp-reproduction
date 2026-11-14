"""Compare two SP pools built from the same instrumented HGS runs."""

import argparse
import csv
import math
import shutil
import statistics
from fractions import Fraction
from pathlib import Path

from benchmark_postprocess import cpu_time
from compare_equal_budget import require
from compare_snapshots import solve_pool
from reproduce import ROOT, read_instance, verify_solution, write_csv


OUTPUT = ROOT / "results/population-pool"
INSTANCES = ("X-n627-k43", "X-n1001-k43")
SEEDS = tuple(range(21, 26))
POST_WALL_LIMIT = 10
MILP_LIMIT = 5


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--late-stages", type=int, choices=range(1, 6), default=2)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--fraction", type=Fraction, default=Fraction(1, 10))
    parser.add_argument("--seeds", type=int, nargs="+", default=SEEDS)
    args = parser.parse_args()
    directory = args.output.resolve()
    seeds = args.seeds
    require(args.fraction > 0 and len(set(seeds)) == len(seeds), "Invalid fraction or seed list")
    with (directory / "runs.csv").open(newline="", encoding="utf-8") as stream:
        runs = list(csv.DictReader(stream))
    expected = {(name, seed) for name in INSTANCES for seed in seeds}
    require(len(runs) == len(expected) and {(r["instance"], int(r["seed"])) for r in runs} == expected,
            "Incomplete or duplicate HGS trials")
    rows = []
    for name in INSTANCES:
        instance_path = ROOT / "HGS-CVRP-1.0.0/Instances/CVRP" / f"{name}.vrp"
        instance = read_instance(instance_path)
        hgs_cap = math.ceil((len(instance[0]) - 1) * Fraction(12, 5) * args.fraction)
        trials = {int(row["seed"]): row for row in runs if row["instance"] == name}
        bks = int(trials[seeds[0]]["bks_2020"])
        finals = [directory / "trials" / f"{name}-seed{seed}.sol" for seed in seeds]
        samples = []
        hgs_cpu = 0
        non_incumbent_samples = 0
        for seed, final in zip(seeds, finals):
            cost, routes, seconds = verify_solution(final, instance)
            row = trials[seed]
            require(cost == int(row["cost"]) and routes == int(row["routes"])
                    and seconds == float(row["solver_time_s"]) and seconds >= hgs_cap - 3
                    and int(row["time_limit_s"]) == hgs_cap - 3 and int(row["bks_2020"]) == bks,
                    f"Trial mismatch for {name}, seed {seed}")
            hgs_cpu += seconds
            seed_samples = sorted(Path(f"{final}.snapshots").glob("*.sol"))
            require(len(seed_samples) == 15, f"Incomplete feasible-population samples for {final}")
            for sample in seed_samples:
                sample_cost, _, sampled_at = verify_solution(sample, instance)
                require(sampled_at <= seconds, f"Sample timestamp exceeds HGS time for {sample}")
                if int(sample.stem.split("-", maxsplit=1)[0]) >= 5 - args.late_stages:
                    samples.append(sample)
                    non_incumbent_samples += sample_cost > cost

        budget = len(seeds) * hgs_cap
        cap = min(POST_WALL_LIMIT, budget - hgs_cpu - 0.5)
        require(cap > 0, f"No CPU budget for SP on {name}")
        results = []
        population_timed_out = False
        for label, pool in (("final", finals), ("population", finals + samples)):
            output = directory / f"{name}-{label}-{args.late_stages}stages.sol"
            started = cpu_time()
            result = solve_pool(instance_path, pool, output, cap, min(MILP_LIMIT, cap / 2))
            if result is None:
                require(label == "population", f"{name} final SP exceeded shared wall-time cap")
                population_timed_out = True
                final_cost, _, final_sp = results[0]
                shutil.copyfile(directory / f"{name}-final-{args.late_stages}stages.sol", output)
                result = dict(final_sp, recombined_cost=final_cost, optimal_in_pool=False,
                              unique_customer_sets=None)
            cost = verify_solution(output, instance)[0]
            used = cpu_time() - started
            require(used + hgs_cpu <= budget and cost == result["recombined_cost"],
                    f"{name} {label} invalid cost or CPU accounting")
            results.append((cost, used, result))

        final_cost, final_cpu, final_sp = results[0]
        pool_cost, pool_cpu, population_sp = results[1]
        rows.append(dict(instance=name, bks_2020=bks, seeds=len(seeds), late_stages=args.late_stages, samples=len(samples),
                         samples_above_seed_final=non_incumbent_samples,
                         hgs_best_cost=final_sp["best_hgs_cost"], final_sp_cost=final_cost,
                         population_sp_cost=pool_cost, final_sp_gap_pct=100 * (final_cost - bks) / bks,
                         population_sp_gap_pct=100 * (pool_cost - bks) / bks,
                         delta_gap_pp=100 * (pool_cost - final_cost) / bks,
                         cpu_budget_s=budget, hgs_cpu_s=round(hgs_cpu, 6),
                         final_sp_cpu_s=round(final_cpu, 6), population_sp_cpu_s=round(pool_cpu, 6),
                         sp_wall_cap_s=cap, milp_cap_s=min(MILP_LIMIT, cap / 2),
                         final_pool_routes=final_sp["unique_customer_sets"],
                         population_pool_routes=population_sp["unique_customer_sets"],
                         final_pool_optimal=final_sp["optimal_in_pool"],
                         population_pool_optimal=population_sp["optimal_in_pool"],
                         population_timed_out=population_timed_out))
        print(rows[-1], flush=True)

    write_csv(directory / f"comparison-{args.late_stages}stages.csv", rows)
    for key in ("final_sp_gap_pct", "population_sp_gap_pct", "delta_gap_pp"):
        print(key, statistics.mean(row[key] for row in rows), flush=True)


if __name__ == "__main__":
    main()
