"""Audit the full-budget snapshot experiment and generate a slide-ready table."""

import csv
import json
import math
import statistics
from pathlib import Path
from zipfile import ZipFile

from compare_equal_budget import BASELINE, SEEDS, audit_trials, read_runs, require
from report_linux_full import verify_progress
from reproduce import PILOT, ROOT, read_instance, sha256, verify_solution, write_csv


OUTPUT = ROOT / "results/snapshot-full"


def load_rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return {row["instance"]: row for row in csv.DictReader(stream)}


def verify_incumbents(path, instance, seed, final_seconds):
    files = sorted(Path(f"{path}.snapshots").glob("*.sol"), key=lambda item: int(item.stem))
    require(files, f"Missing snapshots for {path}")
    states = [verify_solution(item, instance) for item in files]
    require(all(a[0] > b[0] and a[2] <= b[2] for a, b in zip(states, states[1:])),
            f"Invalid incumbent sequence for {path}")
    cost, _, seconds = verify_solution(path, instance)
    require(states[-1][0] == cost and states[-1][2] <= seconds == final_seconds,
            f"Snapshot history does not end with the final solution for {path}")
    verify_progress(path.with_suffix(".sol.PG.csv"), seed, cost, seconds)
    return len(files), min(2, len(files) - 1)


def write_slide_table(rows):
    columns = ("baseline_gap_pct", "final_sp_gap_pct", "snapshot_sp_gap_pct")
    hgs_gap, final_gap, snapshot_gap = [statistics.mean(row[key] for row in rows) for key in columns]
    wins = sum(row["delta_vs_final_sp_pp"] < 0 for row in rows)
    ties = sum(row["delta_vs_final_sp_pp"] == 0 for row in rows)
    total_snapshot_cpu = sum(row["final_sp_cpu_s"] + row["snapshot_sp_cpu_s"] for row in rows)
    lines = [
        "# HGS và Set Partitioning ở ngân sách đầy đủ",
        "",
        f"Gap trung bình của nghiệm tốt nhất qua 10 seed là **{hgs_gap:.4f}%** với HGS, "
        f"**{final_gap:.4f}%** với SP từ nghiệm cuối và **{snapshot_gap:.4f}%** với SP thêm nghiệm trung gian. "
        f"So với SP từ nghiệm cuối, bản mở rộng thắng {wins}, hòa {ties}, thua {len(rows) - wins - ties} instance.",
        "",
        "| Instance | HGS best-of-10 | SP từ nghiệm cuối | SP thêm 2 nghiệm | Δ so với SP cuối (điểm %) |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(f"| {row['instance']} | {row['baseline_gap_pct']:.4f}% | {row['final_sp_gap_pct']:.4f}% | "
                     f"{row['snapshot_sp_gap_pct']:.4f}% | {row['delta_vs_final_sp_pp']:+.4f} |")
    lines += [
        f"| **Trung bình** | **{hgs_gap:.4f}%** | **{final_gap:.4f}%** | **{snapshot_gap:.4f}%** | "
        f"**{snapshot_gap - final_gap:+.4f}** |",
        "",
        "Gap dùng BKS lịch sử năm 2020. Mỗi giá trị dùng nghiệm tốt nhất của 10 seed trên từng instance. "
        "Hai nhánh SP dùng cùng các lượt HGS có lưu nghiệm, để đo riêng tác động của mở rộng tập tuyến. "
        "Nghiệm trung gian là hai incumbent ngay trước incumbent cuối, hoặc ít hơn nếu seed có ít lần cải thiện.",
        "",
        "Mỗi instance có giới hạn `10 × ceil(2,4 × số khách)` giây CPU. Baseline HGS dùng các lượt nguyên bản "
        "đã đo trên Ubuntu WSL 2. Nhánh có lưu nghiệm dành 1 giây mỗi seed cho hậu xử lý, và tính chi phí ghi "
        "nghiệm trong thời gian HGS. Baseline chạy ở đợt trước và dùng binary không có ghi snapshot. "
        "Giới hạn nguyên của CLI có thể vượt nhẹ ở lần kiểm tra thời gian cuối một vòng lặp. "
        f"Cả pipeline SP mở rộng, kể cả SP từ pool cuối để dự phòng, dùng tổng cộng {total_snapshot_cpu:.3f} giây CPU "
        "trên 8 instance và nằm trong giới hạn của từng instance.",
        "",
        "CSV ghi cả cost, CPU thực tế, kích thước pool, và kết quả SP từ nghiệm cuối của đợt đối chứng trước. "
        "Các nghiệm đầu vào và đầu ra đều được kiểm tra độc lập về tải trọng, độ phủ và chi phí EUC_2D.",
        "",
        "[CSV so sánh](comparison.csv) · [Kết quả từng seed](runs.csv) · [Môi trường Linux](environment.txt)",
        "",
    ]
    (OUTPUT / "SLIDE_TABLE.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    require((BASELINE / "exit_code").read_text().strip() == "0", "Full-budget baseline did not complete")
    baseline_manifest = json.loads((BASELINE / "experiment.json").read_text())
    manifest = json.loads((OUTPUT / "experiment.json").read_text())
    fields = ("system", "machine", "reference_sha256", "instances", "seeds", "iterations")
    require(all(manifest[key] == baseline_manifest[key] for key in fields)
            and manifest["system"] == "Linux" and manifest["seeds"] == SEEDS and manifest["iterations"] == 20000,
            "Inconsistent HGS protocol")
    references = ROOT / "paper_reference.csv"
    require(sha256(references) == manifest["reference_sha256"], "BKS reference changed")
    require(sha256(BASELINE / "genvrp") == baseline_manifest["solver_sha256"], "Baseline binary changed")
    require(sha256(OUTPUT / "genvrp-with-snapshots") == manifest["solver_sha256"], "Snapshot wrapper changed")
    require(sha256(OUTPUT / "genvrp") == (OUTPUT / "instrumented-binary.sha256").read_text().split()[0],
            "Instrumented binary changed")
    with ZipFile(ROOT / "HGS-CVRP-v1.0.0.zip") as archive:
        program = [name for name in archive.namelist() if "/Program/" in name and not name.endswith("/")]
        require(len(program) == 16 and all(archive.read(name) == (ROOT / name).read_bytes() for name in program),
                "Upstream HGS source changed")

    bks_rows = load_rows(references)
    baseline, hybrid = read_runs(BASELINE), read_runs(OUTPUT)
    pool = load_rows(OUTPUT / "pool_comparison-late.csv")
    previous = load_rows(ROOT / "results/equal-budget/comparison.csv")
    require(set(pool) == set(PILOT) and set(previous) == set(PILOT), "Incomplete SP results")
    rows = []
    for name in PILOT:
        path = ROOT / "HGS-CVRP-1.0.0/Instances/CVRP" / f"{name}.vrp"
        require(sha256(path) == manifest["instances"][name], f"Input changed for {name}")
        instance = read_instance(path)
        limit = (12 * (len(instance[0]) - 1) + 4) // 5
        require(baseline_manifest["limits"][name] == limit and manifest["limits"][name] == limit - 1,
                f"Wrong budget for {name}")
        bks = int(bks_rows[name]["bks_2020"])
        _, baseline_cost, baseline_cpu = audit_trials(BASELINE, name, baseline[name], instance, limit, bks)
        paths, short_cost, hybrid_cpu = audit_trials(OUTPUT, name, hybrid[name], instance, limit - 1, bks)
        counts = [verify_incumbents(path, instance, seed, float(hybrid[name][seed]["solver_time_s"]))
                  for path, seed in zip(paths, SEEDS)]
        old_sp = previous[name]
        row = pool[name]
        final_cost = verify_solution(OUTPUT / f"{name}-final-late.sol", instance)[0]
        snapshot_cost = verify_solution(OUTPUT / f"{name}-snapshots-late.sol", instance)[0]
        require(int(row["hgs_cost"]) == short_cost and int(row["bks_2020"]) == bks
                and int(row["final_sp_cost"]) == final_cost and int(row["snapshot_sp_cost"]) == snapshot_cost
                and snapshot_cost <= final_cost <= short_cost and int(row["snapshot_count"]) == sum(x[1] for x in counts),
                f"Incorrect SP costs or pool size for {name}")
        budget = len(SEEDS) * limit
        final_cpu = float(row["final_sp_cpu_s"])
        snapshot_cpu = float(row["snapshot_sp_cpu_s"])
        require(math.isclose(float(row["post_budget_s"]), budget - hybrid_cpu, abs_tol=0.000001)
                and 0 < final_cpu + snapshot_cpu <= budget - hybrid_cpu, f"CPU budget exceeded for {name}")
        rows.append(dict(instance=name, seeds=len(SEEDS), bks_2020=bks, cpu_budget_s=budget,
                         baseline_cpu_s=round(baseline_cpu, 6), snapshot_hgs_cpu_s=round(hybrid_cpu, 6),
                         final_sp_cpu_s=final_cpu, snapshot_sp_cpu_s=snapshot_cpu,
                         snapshot_total_cpu_s=round(hybrid_cpu + final_cpu + snapshot_cpu, 6),
                         baseline_cost=baseline_cost, snapshot_hgs_cost=short_cost,
                         final_sp_cost=final_cost, snapshot_sp_cost=snapshot_cost,
                         previous_final_sp_cost=int(old_sp["hybrid_cost"]),
                         baseline_gap_pct=100 * (baseline_cost - bks) / bks,
                         final_sp_gap_pct=100 * (final_cost - bks) / bks,
                         snapshot_sp_gap_pct=100 * (snapshot_cost - bks) / bks,
                         delta_vs_hgs_pp=100 * (snapshot_cost - baseline_cost) / bks,
                         delta_vs_final_sp_pp=100 * (snapshot_cost - final_cost) / bks,
                         final_pool_routes=row["final_pool_routes"], snapshot_pool_routes=row["snapshot_pool_routes"],
                         saved_incumbents=sum(x[0] for x in counts), selected_incumbents=sum(x[1] for x in counts),
                         snapshot_pool_optimal=row["snapshot_pool_optimal"], snapshot_timed_out=row["snapshot_timed_out"]))
    write_csv(OUTPUT / "comparison.csv", rows)
    write_slide_table(rows)
    print(f"Verified all 80 pairs and wrote {OUTPUT / 'SLIDE_TABLE.md'}")


if __name__ == "__main__":
    main()
