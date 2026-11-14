"""Try exact visit ordering for short routes before set partitioning."""

import csv
import math
import time
from functools import lru_cache

from reproduce import PILOT, ROOT, read_instance, verify_solution, write_csv
from route_pool import recombine


def exact_order(route, distance):
    n = len(route)
    full = (1 << n) - 1

    @lru_cache(maxsize=None)
    def visit(mask, previous):
        if not mask:
            return distance(previous, 0), -1
        remaining = mask
        best = (math.inf, -1)
        while remaining:
            bit = remaining & -remaining
            position = bit.bit_length() - 1
            node = route[position]
            best = min(best, (distance(previous, node) + visit(mask ^ bit, node)[0], position))
            remaining ^= bit
        return best

    remaining = full
    previous = 0
    ordered = []
    cost = visit(remaining, previous)[0]
    while remaining:
        _, position = visit(remaining, previous)
        previous = route[position]
        ordered.append(previous)
        remaining ^= 1 << position
    visit.cache_clear()
    return cost, tuple(ordered)


def main():
    source = ROOT / "results/snapshot-full"
    destination = ROOT / "results/exact-route-sp"
    destination.mkdir(exist_ok=True)
    with (source / "comparison.csv").open(newline="", encoding="utf-8") as stream:
        reference = {row["instance"]: row for row in csv.DictReader(stream)}
    rows = []
    for name in PILOT:
        row = reference[name]
        instance = read_instance(ROOT / "HGS-CVRP-1.0.0/Instances/CVRP" / f"{name}.vrp")
        coordinates = instance[0]
        finals = [source / "trials" / f"{name}-seed{seed}.sol" for seed in range(1, 11)]
        original = source / f"{name}-final-late.sol"
        sp_cost = verify_solution(original, instance)[0]
        available = int(row["cpu_budget_s"]) - float(row["snapshot_hgs_cpu_s"])
        started = time.process_time()
        processed = improved = 0

        @lru_cache(maxsize=None)
        def distance(a, b):
            return int(math.dist(coordinates[a], coordinates[b]) + 0.5)

        def polish(routes):
            nonlocal processed, improved
            result = []
            for cost, route in sorted(routes, key=lambda entry: len(entry[1])):
                if 4 <= len(route) <= 10 and time.process_time() - started < min(4, available / 2):
                    candidate = exact_order(route, distance)
                    if candidate[0] > cost:
                        raise ValueError("Exact route ordering returned a higher cost")
                    processed += 1
                    improved += candidate[0] < cost
                    if candidate[0] < cost:
                        cost, route = candidate
                result.append((cost, route))
            return result

        output = destination / f"{name}.sol"
        result = recombine(instance, finals, 1, output, transform_routes=polish)
        used = time.process_time() - started
        new_cost = verify_solution(output, instance)[0]
        if new_cost > sp_cost or used > available or new_cost != result["recombined_cost"]:
            raise ValueError(f"Invalid comparison for {name}")
        bks = int(row["bks_2020"])
        rows.append(dict(instance=name, sp_cost=sp_cost, exact_sp_cost=new_cost,
                         exact_gap_pct=100 * (new_cost - bks) / bks,
                         delta_gap_pp=100 * (new_cost - sp_cost) / bks,
                         routes_processed=processed, routes_improved=improved,
                         cpu_s=round(used, 6), budget_left_s=round(available, 6)))
        print(rows[-1], flush=True)
    write_csv(destination / "comparison.csv", rows)


if __name__ == "__main__":
    main()
