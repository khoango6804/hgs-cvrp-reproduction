"""Recombine feasible HGS routes by solving a restricted set-partitioning model."""

import argparse
import math
import re
import time
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_array

from reproduce import PILOT, ROOT, read_instance, verify_solution, write_csv


def route_cost(route, coordinates):
    trip = (0, *route, 0)
    return sum(int(math.dist(coordinates[a], coordinates[b]) + 0.5)
               for a, b in zip(trip, trip[1:]))


def recombine(instance, solutions, time_limit, output, transform_routes=None):
    coordinates, _, _ = instance
    customer_count = len(coordinates) - 1
    start = time.perf_counter()
    by_customers = {}
    best_seed_cost = math.inf
    for path in solutions:
        cost, _, _ = verify_solution(path, instance)
        if cost < best_seed_cost:
            best_seed_cost, incumbent = cost, path
        for text in re.findall(r"^Route #\d+:[ \t]*(.+)$", path.read_text(), re.MULTILINE):
            route = tuple(map(int, text.split()))
            key = tuple(sorted(route))
            candidate = (route_cost(route, coordinates), min(route, route[::-1]))
            if key not in by_customers or candidate < by_customers[key]:
                by_customers[key] = candidate

    routes = list(by_customers.values())
    if transform_routes is not None:
        routes = transform_routes(routes)
    indices = [node - 1 for _, route in routes for node in route]
    pointers = np.cumsum([0, *(len(route) for _, route in routes)])
    matrix = csc_array((np.ones(len(indices)), indices, pointers),
                       shape=(customer_count, len(routes)))
    model = milp(c=np.array([cost for cost, _ in routes]), integrality=np.ones(len(routes)),
                 bounds=Bounds(0, 1), constraints=LinearConstraint(matrix, 1, 1),
                 options={"time_limit": time_limit, "mip_rel_gap": 0.0})
    if model.status not in (0, 1) or (model.status == 0 and model.x is None):
        raise RuntimeError(f"Set partitioning failed: {model.message}")
    elapsed = time.perf_counter() - start
    output.write_bytes(incumbent.read_bytes())
    if model.x is not None:
        selected = [route for value, (_, route) in zip(model.x, routes) if value > 0.5]
        candidate_cost = sum(route_cost(route, coordinates) for route in selected)
        if candidate_cost < best_seed_cost:
            candidate = output.with_suffix(".candidate")
            lines = [f"Route #{i}: {' '.join(map(str, route))}" for i, route in enumerate(selected, 1)]
            # Time is the route-pool post-processing duration, in wall-clock seconds.
            candidate.write_text("\n".join([*lines, f"Cost {candidate_cost}", f"Time {elapsed:.6f}", ""]))
            verify_solution(candidate, instance)
            candidate.replace(output)

    new_cost, _, _ = verify_solution(output, instance)
    return dict(seeds=len(solutions), unique_customer_sets=len(routes), best_hgs_cost=best_seed_cost,
                recombined_cost=new_cost, cost_saved=best_seed_cost - new_cost,
                wall_time_s=round(elapsed, 6), optimal_in_pool=model.status == 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=Path, default=ROOT / "results/linux-full/trials")
    parser.add_argument("--output", type=Path, default=ROOT / "results/route-pool")
    parser.add_argument("--seconds", type=float, default=5)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error("--seconds must be finite and positive")
    args.output.mkdir(parents=True, exist_ok=True)

    rows = []
    instances = ROOT / "HGS-CVRP-1.0.0/Instances/CVRP"
    for name in PILOT:
        paths = [args.trials / f"{name}-seed{seed}.sol" for seed in range(1, 11)]
        row = recombine(read_instance(instances / f"{name}.vrp"), paths, args.seconds,
                        args.output / f"{name}.sol")
        rows.append(dict(instance=name, **row))
        print(f"{name}: {row['best_hgs_cost']} -> {row['recombined_cost']} "
              f"({row['unique_customer_sets']} columns, {row['wall_time_s']:.3f}s)")
    write_csv(args.output / "summary.csv", rows)


if __name__ == "__main__":
    main()
