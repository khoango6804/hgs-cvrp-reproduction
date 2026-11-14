"""Run Vidal's HGS-CVRP release and independently verify its X-set solutions."""

import argparse
import csv
import hashlib
import json
import math
import platform
import re
import shutil
import statistics
import subprocess
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PILOT = (
    "X-n101-k25", "X-n157-k13", "X-n251-k28", "X-n401-k29",
    "X-n502-k39", "X-n627-k43", "X-n801-k40", "X-n1001-k43",
)


def read_instance(path):
    # HGS solution IDs are the original TSPLIB node IDs minus one.
    header = {}
    coordinates = {}
    demand = {}
    depot = []
    section = None
    for line in path.read_text(encoding="ascii").splitlines():
        line = line.strip()
        if not line or line == "EOF":
            continue
        if line in ("NODE_COORD_SECTION", "DEMAND_SECTION", "DEPOT_SECTION"):
            section = line
        elif section == "NODE_COORD_SECTION":
            node, x, y = map(int, line.split())
            coordinates[node - 1] = (x, y)
        elif section == "DEMAND_SECTION":
            node, quantity = map(int, line.split())
            demand[node - 1] = quantity
        elif section == "DEPOT_SECTION":
            depot.append(int(line))
        else:
            key, value = line.split(":", maxsplit=1)
            header[key.strip()] = value.strip()

    nodes = set(range(int(header["DIMENSION"])))
    if header["TYPE"] != "CVRP" or header["EDGE_WEIGHT_TYPE"] != "EUC_2D":
        raise ValueError(f"Expected CVRP with EUC_2D distances in {path}")
    if coordinates.keys() != nodes or demand.keys() != nodes or depot != [1, -1]:
        raise ValueError(f"Invalid X-set node or depot data in {path}")
    return coordinates, demand, int(header["CAPACITY"])


def verify_solution(path, instance):
    coordinates, demand, capacity = instance
    content = path.read_text(encoding="ascii")
    routes = [list(map(int, route.split())) for route in
              re.findall(r"^Route #\d+:[ \t]*(.+)$", content, re.MULTILINE)]
    cost_match = re.search(r"^Cost[ \t]+(\S+)$", content, re.MULTILINE)
    time_match = re.search(r"^Time[ \t]+(\S+)$", content, re.MULTILINE)
    if not routes or any(not route for route in routes) or not cost_match or not time_match:
        raise ValueError(f"Missing route, cost or timing in {path}")
    observed = Counter(node for route in routes for node in route)
    if observed != Counter(range(1, len(coordinates))):
        raise ValueError(f"Customer coverage mismatch in {path}")

    cost = 0
    for route in routes:
        if sum(demand[node] for node in route) > capacity:
            raise ValueError(f"Vehicle capacity exceeded in {path}")
        trip = [0, *route, 0]
        cost += sum(int(math.dist(coordinates[a], coordinates[b]) + 0.5)
                    for a, b in zip(trip, trip[1:]))
    if cost != float(cost_match[1]):
        raise ValueError(f"Reported cost {cost_match[1]} differs from verified cost {cost} in {path}")
    return cost, len(routes), float(time_match[1])


def run_trial(solver, input_path, instance, reference, seed, limit, output, resume, snapshot_trials):
    prefix = output / f"{input_path.stem}-seed{seed}"
    solution = prefix.with_suffix(".sol")
    checkpoint = prefix.with_suffix(".json")
    snapshots = Path(f"{solution}.snapshots")
    if resume and checkpoint.is_file():
        try:
            row = json.loads(checkpoint.read_text(encoding="utf-8"))
            cost, routes, solver_seconds = verify_solution(solution, instance)
            expected = (row["cost"], row["routes"], row["solver_time_s"])
            if ((cost, routes, solver_seconds) == expected and math.isfinite(solver_seconds)
                    and solver_seconds >= limit and (not snapshot_trials or any(snapshots.glob("*.sol")))):
                return row
        except (OSError, ValueError, KeyError):
            pass
    checkpoint.unlink(missing_ok=True)
    solution.unlink(missing_ok=True)
    Path(f"{solution}.PG.csv").unlink(missing_ok=True)
    if snapshot_trials and snapshots.is_dir():
        shutil.rmtree(snapshots)
    command = [str(solver), str(input_path), str(solution), "-it", "20000",
               "-t", str(limit), "-seed", str(seed)]
    started = time.perf_counter()
    with prefix.with_suffix(".log").open("w", encoding="utf-8") as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True,
                       timeout=limit * 4 + 60)
    elapsed = time.perf_counter() - started
    if not solution.is_file():
        raise RuntimeError(f"HGS did not write {solution}. See {prefix.with_suffix('.log')}")
    cost, routes, solver_seconds = verify_solution(solution, instance)
    if not math.isfinite(solver_seconds) or solver_seconds < limit:
        raise RuntimeError(f"HGS did not reach the {limit}s budget in {solution}")
    bks = int(reference["bks_2020"])
    row = dict(instance=input_path.stem, customers=len(instance[0]) - 1, seed=seed,
               time_limit_s=limit, solver_time_s=solver_seconds, wall_time_s=round(elapsed, 3),
               cost=cost, routes=routes, bks_2020=bks, gap_pct=100 * (cost - bks) / bks)
    write_json(checkpoint, row)
    return row


def write_json(path, data):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solver", type=Path, default=ROOT / "genvrp.exe")
    parser.add_argument("--instances-dir", type=Path,
                        default=ROOT / "HGS-CVRP-1.0.0" / "Instances" / "CVRP")
    parser.add_argument("--instances", nargs="+", default=list(PILOT),
                        help="X-set names, or 'all' for the full 100-instance set")
    parser.add_argument("--seeds", nargs="+", type=int, default=list(range(1, 11)))
    parser.add_argument("--time-fraction", type=float, default=0.01,
                        help="Fraction of the paper budget (2.4 seconds per customer)")
    parser.add_argument("--reserve-seconds", type=int, default=0,
                        help="Subtract this many seconds from each HGS run for post-processing")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "pilot")
    parser.add_argument("--resume", action="store_true", help="Reuse validated completed trials")
    parser.add_argument("--snapshot-trials", action="store_true",
                        help="Clean stale per-seed snapshots before retrying an unfinished trial")
    args = parser.parse_args()
    if args.jobs < 1 or not math.isfinite(args.time_fraction) or args.time_fraction <= 0 or args.reserve_seconds < 0:
        parser.error("--jobs and --time-fraction must be positive, and --reserve-seconds must be nonnegative")
    if len(set(args.seeds)) != len(args.seeds) or len(set(args.instances)) != len(args.instances):
        parser.error("Instance names and seeds must be unique")

    reference_path = ROOT / "paper_reference.csv"
    with reference_path.open(newline="", encoding="utf-8") as stream:
        references = {row["instance"]: row for row in csv.DictReader(stream)}
    names = list(references) if args.instances == ["all"] else args.instances
    for name in names:
        if name not in references:
            parser.error(f"Unknown X-set instance: {name}")
    if not args.solver.is_file():
        parser.error(f"Solver not found: {args.solver}")

    args.output.mkdir(parents=True, exist_ok=True)
    trial_dir = args.output.resolve() / "trials"
    trial_dir.mkdir(exist_ok=True)
    inputs = {name: args.instances_dir.resolve() / f"{name}.vrp" for name in names}
    instances = {name: read_instance(path) for name, path in inputs.items()}
    # The v1.0.0 CLI only accepts integer seconds. Use exact rational arithmetic.
    seconds_per_customer = Fraction(12, 5) * Fraction(str(args.time_fraction))
    limits = {name: math.ceil((len(instances[name][0]) - 1) * seconds_per_customer) - args.reserve_seconds
              for name in names}
    if not all(0 < limit < 2**31 - 1 for limit in limits.values()):
        parser.error("Each HGS time limit must fit the solver's positive finite integer range")
    solver = args.solver.resolve()
    manifest_path = args.output / "experiment.json"
    manifest = dict(system=platform.system(), machine=platform.machine(),
                    solver_sha256=sha256(solver), reference_sha256=sha256(reference_path),
                    instances={name: sha256(path) for name, path in inputs.items()},
                    seeds=sorted(args.seeds), limits=limits, iterations=20000)
    if args.resume and manifest_path.is_file():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            parser.error("Existing experiment differs from this run. Choose a new --output.")
    elif args.resume and any(trial_dir.iterdir()):
        parser.error("Existing trials have no experiment manifest. Choose a new --output.")
    else:
        # A fresh run invalidates all checkpoints before publishing its manifest.
        for checkpoint in trial_dir.glob("*.json"):
            checkpoint.unlink()
        write_json(manifest_path, manifest)
    for filename in ("runs.csv", "summary.csv"):
        (args.output / filename).unlink(missing_ok=True)
    # Start the longest jobs first to reduce idle time near the end of a batch.
    rows = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_trial, solver, inputs[name], instances[name],
                               references[name], seed, limits[name], trial_dir, args.resume, args.snapshot_trials)
                   for name in sorted(names, key=limits.__getitem__, reverse=True)
                   for seed in args.seeds]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(f"{len(rows)}/{len(futures)} {row['instance']} seed={row['seed']} "
                  f"cost={row['cost']} gap={row['gap_pct']:.3f}%", flush=True)

    order = {name: index for index, name in enumerate(names)}
    rows.sort(key=lambda row: (order[row["instance"]], row["seed"]))
    write_csv(args.output / "runs.csv", rows)
    summary = []
    trials_by_instance = {name: [] for name in names}
    for row in rows:
        trials_by_instance[row["instance"]].append(row)
    for name in names:
        trials = trials_by_instance[name]
        costs = [row["cost"] for row in trials]
        gaps = [row["gap_pct"] for row in trials]
        bks = trials[0]["bks_2020"]
        mean_cost = statistics.mean(costs)
        paper_mean_cost = float(references[name]["paper_hgs_mean_cost"])
        summary.append(dict(instance=name, customers=trials[0]["customers"],
                            seeds=len(costs), time_limit_s=limits[name],
                            bks_2020=bks, best_cost=min(costs),
                            mean_cost=mean_cost, worst_cost=max(costs),
                            mean_gap_pct=statistics.mean(gaps), best_gap_pct=min(gaps),
                            stdev_gap_pct=statistics.stdev(gaps) if len(gaps) > 1 else 0,
                            bks_matches=costs.count(bks), paper_hgs_mean_cost=paper_mean_cost,
                            paper_hgs_mean_gap_pct=references[name]["paper_hgs_mean_gap_pct"],
                            delta_mean_gap_pp=100 * (mean_cost - paper_mean_cost) / bks))
    write_csv(args.output / "summary.csv", summary)


if __name__ == "__main__":
    main()
