"""Verify the paired HGS runs and write a slide table for the equal-budget comparison."""

import csv
import json
import math
import statistics
import time
from collections import defaultdict

from reproduce import PILOT, ROOT, read_instance, sha256, verify_solution, write_csv
from route_pool import recombine


BASELINE = ROOT / "results/linux-full"
OUTPUT = ROOT / "results/equal-budget"
SEEDS = list(range(1, 11))
RESERVE_PER_SEED = 1
MILP_WALL_LIMIT = 5


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_runs(folder):
    with (folder / "runs.csv").open(newline="", encoding="utf-8") as stream:
        runs = defaultdict(dict)
        for row in csv.DictReader(stream):
            seed = int(row["seed"])
            require(seed not in runs[row["instance"]], f"Duplicate seed in {folder}")
            runs[row["instance"]][seed] = row
    require(set(runs) == set(PILOT) and all(sorted(rows) == SEEDS for rows in runs.values()),
            f"Expected the same eight instances and ten seeds in {folder}")
    return runs


def audit_trials(folder, name, rows, instance, expected_limit, bks, seeds=SEEDS):
    paths = []
    costs = []
    times = []
    for seed in seeds:
        row = rows[seed]
        solution = folder / "trials" / f"{name}-seed{seed}.sol"
        cost, routes, seconds = verify_solution(solution, instance)
        require(cost == int(row["cost"]) and routes == int(row["routes"])
                and math.isfinite(seconds) and seconds >= expected_limit
                and seconds == float(row["solver_time_s"])
                and int(row["time_limit_s"]) == expected_limit and int(row["bks_2020"]) == bks,
                f"Invalid trial or CPU accounting for {solution}")
        paths.append(solution)
        costs.append(cost)
        times.append(seconds)
    return paths, min(costs), sum(times)


def render_report(rows):
    baseline_mean = statistics.mean(row["gap_hgs_pct"] for row in rows)
    hybrid_mean = statistics.mean(row["gap_hybrid_pct"] for row in rows)
    wins = sum(row["delta_gap_pp"] < 0 for row in rows)
    ties = sum(row["delta_gap_pp"] == 0 for row in rows)
    lines = [
        "# HGS và Set Partitioning dưới cùng ngân sách CPU",
        "",
        f"Trên 8 instance, gap của nghiệm tốt nhất qua 10 seed trung bình là {baseline_mean:.4f}% với HGS "
        f"và {hybrid_mean:.4f}% với HGS + Set Partitioning. Bản hybrid thắng {wins}, hòa {ties} "
        f"và thua {len(rows) - wins - ties} instance.",
        "",
        "| Instance | Ngân sách CPU (giây) | Gap HGS best-of-10 | Gap HGS + SP | Δ gap (điểm %) |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(f"| {row['instance']} | {row['cpu_budget_s']:,} | {row['gap_hgs_pct']:.4f}% | "
                     f"{row['gap_hybrid_pct']:.4f}% | {row['delta_gap_pp']:+.4f} |")
    lines.extend([
        f"| **Trung bình** | | **{baseline_mean:.4f}%** | **{hybrid_mean:.4f}%** | "
        f"**{hybrid_mean - baseline_mean:+.4f}** |",
        "",
        "Δ gap = gap HGS + SP trừ gap HGS. Giá trị âm là cải thiện. Hai nhánh dùng cùng BKS năm 2020.",
        "",
        "Baseline dùng 10 lượt HGS đã hoàn tất trên cùng máy WSL. Với mỗi instance, ngân sách là `10 × T`, "
        "với `T = ceil(2,4 × số khách)`. Bản hybrid chạy lại cùng binary và seed 1–10 với `T − 1` giây CPU "
        "mỗi seed. Ngân sách còn lại dành cho đọc và kiểm tra nghiệm, gom tuyến và giải MILP trên một CPU logic. "
        "Mỗi seed và cả hai nghiệm cuối đều được kiểm tra độc lập. Ngân sách là giới hạn tối đa, nên hybrid "
        "có thể kết thúc sớm khi MILP giải xong. Hai nhánh chạy ở hai thời điểm khác nhau.",
        "",
        f"Hậu xử lý tốn {sum(row['post_cpu_s'] for row in rows):.3f} giây CPU trên cả 8 instance. "
        "Cột `delta_gap_sp_only_pp` trong CSV đo riêng lợi ích MILP trên đúng pool HGS rút ngắn, "
        "giúp phân biệt hiệu ứng ghép tuyến với biến động do giới hạn thời gian HGS.",
        "",
        "[Số liệu đầy đủ](comparison.csv) · [Baseline](../linux-full/REPORT.md) · "
        "[Cấu hình môi trường](environment.txt)",
        "",
    ])
    (OUTPUT / "SLIDE_TABLE.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    require((BASELINE / "exit_code").read_text().strip() == "0", "Baseline did not complete")
    baseline = json.loads((BASELINE / "experiment.json").read_text())
    hybrid = json.loads((OUTPUT / "experiment.json").read_text())
    fields = ("system", "machine", "solver_sha256", "reference_sha256", "instances", "seeds", "iterations")
    require(all(baseline[field] == hybrid[field] for field in fields), "Different experimental inputs")
    require(hybrid["system"] == "Linux" and hybrid["seeds"] == SEEDS and hybrid["iterations"] == 20000,
            "Unexpected experimental settings")
    reference_file = ROOT / "paper_reference.csv"
    require(sha256(reference_file) == hybrid["reference_sha256"], "BKS reference changed")
    require(sha256(BASELINE / "genvrp") == hybrid["solver_sha256"], "Solver changed")
    with reference_file.open(newline="", encoding="utf-8") as stream:
        bks_by_name = {row["instance"]: int(row["bks_2020"]) for row in csv.DictReader(stream)}

    baseline_runs, hybrid_runs = read_runs(BASELINE), read_runs(OUTPUT)
    solution_dir = OUTPUT / "solutions"
    solution_dir.mkdir(exist_ok=True)
    comparison = []
    for name in PILOT:
        path = ROOT / "HGS-CVRP-1.0.0/Instances/CVRP" / f"{name}.vrp"
        require(sha256(path) == hybrid["instances"][name], f"Instance changed for {name}")
        instance = read_instance(path)
        limit = (12 * (len(instance[0]) - 1) + 4) // 5
        hybrid_limit = limit - RESERVE_PER_SEED
        require(baseline["limits"][name] == limit and hybrid["limits"][name] == hybrid_limit,
                f"Incorrect HGS time limits for {name}")
        bks = bks_by_name[name]
        _, baseline_cost, baseline_cpu = audit_trials(BASELINE, name, baseline_runs[name], instance, limit, bks)
        paths, short_cost, hgs_cpu = audit_trials(OUTPUT, name, hybrid_runs[name], instance, hybrid_limit, bks)
        budget = len(SEEDS) * limit
        remaining = budget - hgs_cpu
        require(remaining > 0, f"No CPU time left for post-processing {name}")

        start_cpu = time.process_time()
        result = recombine(instance, paths, min(MILP_WALL_LIMIT, remaining / 2), solution_dir / f"{name}.sol")
        post_cpu = time.process_time() - start_cpu
        require(hgs_cpu + post_cpu <= budget, f"Hybrid exceeded the CPU budget on {name}")
        cost = result["recombined_cost"]
        require(result["best_hgs_cost"] == short_cost and cost <= short_cost,
                f"Invalid set-partitioning result for {name}")
        comparison.append(dict(instance=name, bks_2020=bks, seeds=len(SEEDS), cpu_budget_s=budget,
                               baseline_hgs_cpu_s=round(baseline_cpu, 4), hybrid_hgs_cpu_s=round(hgs_cpu, 4),
                               post_cpu_s=round(post_cpu, 6), hybrid_total_cpu_s=round(hgs_cpu + post_cpu, 6),
                               best_hgs_cost=baseline_cost, short_hgs_cost=short_cost, hybrid_cost=cost,
                               gap_hgs_pct=100 * (baseline_cost - bks) / bks,
                               gap_hybrid_pct=100 * (cost - bks) / bks,
                               delta_gap_pp=100 * (cost - baseline_cost) / bks,
                               delta_gap_sp_only_pp=100 * (cost - short_cost) / bks,
                               unique_customer_sets=result["unique_customer_sets"],
                               optimal_in_pool=result["optimal_in_pool"]))
        print(f"{name}: {baseline_cost} (full HGS), {short_cost} (short HGS), {cost} (short HGS + SP), "
              f"{hgs_cpu + post_cpu:.3f}/{budget}s CPU", flush=True)

    write_csv(OUTPUT / "comparison.csv", comparison)
    render_report(comparison)


if __name__ == "__main__":
    main()
