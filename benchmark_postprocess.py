"""Compare route post-processors using the existing equal-budget HGS seeds on Linux."""

import csv
import resource
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from compare_equal_budget import audit_trials, BASELINE, OUTPUT, read_runs, require
from reproduce import PILOT, ROOT, read_instance, verify_solution, write_csv
from route_pool import recombine


DEST = ROOT / "results/postprocess"
METHODS = ("HGS best-of-10", "Set Partitioning", "Local Search", "Ruin-and-Recreate",
           "SP + Local Search", "Ruin-and-Recreate + SP")


def cpu_time():
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time() + children.ru_utime + children.ru_stime


def generate(instance_file, method, paths, prefix, seconds):
    subprocess.run([str(DEST / "improve_hgs"), str(instance_file), method, str(seconds), "1",
                    str(prefix), *map(str, paths)], check=True, stdout=subprocess.DEVNULL, timeout=30)
    return [*paths, *sorted(prefix.parent.glob(f"{prefix.name}*.sol"))]


def select_best(instance, candidates, output):
    best = min(candidates, key=lambda path: verify_solution(path, instance)[0])
    shutil.copyfile(best, output)


def evaluate(name, group, seeds, base_rows, short_rows, reference, directory):
    instance_file = ROOT / "HGS-CVRP-1.0.0/Instances/CVRP" / f"{name}.vrp"
    instance = read_instance(instance_file)
    limit = int(reference["cpu_budget_s"]) // 10
    bks = int(reference["bks_2020"])
    _, baseline, baseline_cpu = audit_trials(BASELINE, name, base_rows, instance, limit, bks, seeds)
    paths, short_cost, hgs_cpu = audit_trials(OUTPUT, name, short_rows, instance, limit - 1, bks, seeds)
    budget = len(seeds) * limit
    # A half-seed-pool uses proportionally less CPU, including in post-processing.
    search_limit = len(seeds) * 0.35
    milp_limit = len(seeds) * 0.20
    prefix = f"{name}-{group}"
    results = [(METHODS[0], baseline, 0, baseline_cpu, 0)]

    def record(method, output, start, columns=0, prior=0):
        cost, _, _ = verify_solution(output, instance)
        used = cpu_time() - start + prior
        require(hgs_cpu + used <= budget, f"{method} exceeded CPU budget for {prefix}")
        require(cost <= short_cost, f"{method} lost the short-HGS incumbent for {prefix}")
        results.append((method, cost, used, hgs_cpu + used, columns))
        return used

    start = cpu_time()
    sp_path = directory / f"{prefix}-sp.sol"
    sp = recombine(instance, paths, milp_limit, sp_path)
    sp_cpu = record(METHODS[1], sp_path, start, sp["unique_customer_sets"])

    start = cpu_time()
    ls_path = directory / f"{prefix}-ls.sol"
    ls = generate(instance_file, "local-search", paths, directory / "ls-candidate-", search_limit)
    select_best(instance, ls, ls_path)
    record(METHODS[2], ls_path, start)

    start = cpu_time()
    rr_path = directory / f"{prefix}-rr.sol"
    rr = generate(instance_file, "ruin-recreate", paths, directory / "rr-candidate-", search_limit)
    rr_generation_cpu = cpu_time() - start
    select_best(instance, rr, rr_path)
    record(METHODS[3], rr_path, start)

    start = cpu_time()
    sp_ls_path = directory / f"{prefix}-sp-ls.sol"
    sp_ls = generate(instance_file, "local-search", [sp_path], directory / "sp-ls-candidate-", search_limit)
    select_best(instance, sp_ls, sp_ls_path)
    record(METHODS[4], sp_ls_path, start, prior=sp_cpu)

    start = cpu_time()
    rr_sp_path = directory / f"{prefix}-rr-sp.sol"
    rr_sp = recombine(instance, rr, milp_limit, rr_sp_path)
    record(METHODS[5], rr_sp_path, start, rr_sp["unique_customer_sets"], prior=rr_generation_cpu)

    if group == "all":
        for solution in (sp_path, ls_path, rr_path, sp_ls_path, rr_sp_path):
            shutil.copyfile(solution, DEST / solution.name)
    return [dict(instance=name, group=group, seeds=" ".join(map(str, seeds)), method=method,
                 bks_2020=bks, baseline_cost=baseline, short_hgs_cost=short_cost, cost=cost,
                 gap_pct=100 * (cost - bks) / bks, delta_vs_hgs_pp=100 * (cost - baseline) / bks,
                 cpu_budget_s=budget, post_cpu_s=round(post_cpu, 6), total_cpu_s=round(total_cpu, 6),
                 unique_customer_sets=columns)
            for method, cost, post_cpu, total_cpu, columns in results]


def main():
    DEST.mkdir(exist_ok=True)
    baseline, short = read_runs(BASELINE), read_runs(OUTPUT)
    with (OUTPUT / "comparison.csv").open(newline="", encoding="utf-8") as stream:
        reference = {row["instance"]: row for row in csv.DictReader(stream)}
    rows = []
    for group, seeds in (("all", list(range(1, 11))), ("seeds-1-5", list(range(1, 6))),
                         ("seeds-6-10", list(range(6, 11)))):
        for name in PILOT:
            with tempfile.TemporaryDirectory(prefix="hgs-post-") as directory:
                trials = evaluate(name, group, seeds, baseline[name], short[name], reference[name], Path(directory))
            rows.extend(trials)
            print(name, group, [trial["cost"] for trial in trials], flush=True)
    write_csv(DEST / "comparison.csv", rows)
    summary = []
    for group in ("all", "seeds-1-5", "seeds-6-10"):
        for method in METHODS:
            selected = [row for row in rows if row["group"] == group and row["method"] == method]
            deltas = [row["delta_vs_hgs_pp"] for row in selected]
            summary.append(dict(group=group, method=method, mean_gap_pct=statistics.mean(row["gap_pct"] for row in selected),
                                mean_delta_pp=statistics.mean(deltas), wins=sum(delta < 0 for delta in deltas),
                                ties=deltas.count(0), losses=sum(delta > 0 for delta in deltas),
                                total_post_cpu_s=sum(row["post_cpu_s"] for row in selected)))
    write_csv(DEST / "summary.csv", summary)


if __name__ == "__main__":
    main()
