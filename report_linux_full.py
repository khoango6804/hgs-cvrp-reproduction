"""Audit the 80 full-budget Linux runs and write the per-instance report."""

import csv
import json
import math
import statistics
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from zipfile import ZipFile

from reproduce import PILOT, ROOT, read_instance, sha256, verify_solution


OUTPUT = ROOT / "results" / "linux-full"
PAPER_BEST = dict(zip(PILOT, (27591, 16876, 38684, 66209, 69230, 62238, 73396, 72678)))


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_progress(path, seed, cost, seconds):
    entries = [line.split(";") for line in path.read_text(encoding="utf-8").splitlines()]
    require(entries and all(int(entry[1]) == seed for entry in entries), f"Wrong seed in {path}")
    points = [(float(entry[3]), float(entry[2])) for entry in entries]
    require(all(a[0] <= b[0] and a[1] > b[1] for a, b in zip(points, points[1:])),
            f"Invalid convergence trace in {path}")
    require(points[-1][1] == cost and points[-1][0] <= seconds,
            f"Final convergence record does not match solution in {path}")


def main():
    require((OUTPUT / "exit_code").read_text().strip() == "0", "Benchmark did not finish successfully")
    source_dir = ROOT / "HGS-CVRP-1.0.0"
    archive_path = ROOT / "HGS-CVRP-v1.0.0.zip"
    with ZipFile(archive_path) as archive:
        commit = archive.comment.decode()
        require(commit == "35b32d8e9552074f52444d51ea1fe8aec9055467", "Unexpected source revision")
        program_files = [name for name in archive.namelist()
                         if "/Program/" in name and not name.endswith("/")]
        require(len(program_files) == 16 and all(archive.read(name) == (ROOT / name).read_bytes()
                                                 for name in program_files), "Source differs from release")
    manifest = json.loads((OUTPUT / "experiment.json").read_text())
    reference_file = ROOT / "paper_reference.csv"
    require(manifest["system"] == "Linux" and manifest["iterations"] == 20000, "Wrong benchmark settings")
    require(sha256(OUTPUT / "genvrp") == manifest["solver_sha256"], "Solver hash mismatch")
    require(sha256(reference_file) == manifest["reference_sha256"], "Reference hash mismatch")
    reference = {row["instance"]: row for row in read_csv(reference_file)}
    expected = {(name, seed) for name in PILOT for seed in range(1, 11)}
    runs = read_csv(OUTPUT / "runs.csv")
    observed = {(row["instance"], int(row["seed"])) for row in runs}
    require(len(runs) == len(expected) and observed == expected, "Wrong roster or seed count")

    instances = {}
    limits = {}
    for name in PILOT:
        path = source_dir / "Instances" / "CVRP" / f"{name}.vrp"
        require(sha256(path) == manifest["instances"][name], f"Instance hash mismatch for {name}")
        instances[name] = read_instance(path)
        limits[name] = math.ceil((len(instances[name][0]) - 1) * Fraction(12, 5))
        require(limits[name] == manifest["limits"][name], f"Wrong budget for {name}")

    costs = defaultdict(list)
    cpu_seconds = 0
    for row in runs:
        name = row["instance"]
        seed = int(row["seed"])
        solution = OUTPUT / "trials" / f"{name}-seed{seed}.sol"
        cost, route_count, seconds = verify_solution(solution, instances[name])
        bks = int(reference[name]["bks_2020"])
        require(cost == int(row["cost"]) and route_count == int(row["routes"])
                and limits[name] == int(row["time_limit_s"]) and math.isfinite(seconds)
                and seconds == float(row["solver_time_s"]) and seconds >= limits[name]
                and bks == int(row["bks_2020"])
                and math.isclose(float(row["gap_pct"]), 100 * (cost - bks) / bks),
                f"Invalid cost or budget for {name}, seed {seed}")
        verify_progress(solution.with_suffix(".sol.PG.csv"), seed, cost, seconds)
        costs[name].append(cost)
        cpu_seconds += seconds

    rows = []
    for name in PILOT:
        bks = int(reference[name]["bks_2020"])
        mean_cost = statistics.mean(costs[name])
        best = min(costs[name])
        paper_mean = float(reference[name]["paper_hgs_mean_cost"])
        rows.append((name, limits[name], bks, mean_cost, 100 * (mean_cost - bks) / bks,
                     100 * (paper_mean - bks) / bks, 100 * (mean_cost - paper_mean) / bks,
                     best, PAPER_BEST[name], costs[name].count(bks)))

    mean_gap = statistics.mean(row[4] for row in rows)
    paper_gap = statistics.mean(row[5] for row in rows)
    delta = mean_gap - paper_gap
    lines = [
        "# Kết quả tái lập HGS-CVRP trên Linux",
        "",
        f"Gap trung bình trên 8 instance là **{mean_gap:.4f}%**, so với **{paper_gap:.4f}%** của paper "
        f"trên cùng 8 instance. Chênh lệch là **{delta:+.4f} điểm phần trăm**. "
        f"Cả 80 lượt đều đạt ngân sách CPU và có nghiệm hợp lệ. Có **{sum(row[-1] > 0 for row in rows)}/8** "
        "instance đạt BKS lịch sử ở ít nhất một seed.",
        "",
        "| Instance | Giây CPU mỗi seed | BKS 2020 | Mean cost Linux | Gap Linux | Gap paper | Δ gap (đpt) | Best Linux | Best paper | Seed đạt BKS |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, limit, bks, avg, gap, reference_gap, difference, best, paper_best, matches in rows:
        lines.append(f"| {name} | {limit} | {bks} | {avg:.1f} | {gap:.4f}% | {reference_gap:.4f}% | "
                     f"{difference:+.4f} | {best} | {paper_best} | {matches}/10 |")

    lines += [
        "",
        "Gap dùng `100 × (cost − BKS) / BKS` với BKS năm 2020. Gap của paper được tính từ mean cost "
        "trong Bảng 2–4 để tránh sai số khi lấy hiệu hai giá trị gap đã làm tròn. Best paper lấy từ Bảng 5–6. "
        "Mốc 0,11% của paper là trung bình trên 100 instance. [Bảng thí nghiệm gốc](https://arxiv.org/html/2012.10384#S5)",
        "",
        f"Mỗi lượt dùng một luồng, seed 1–10 và `-it 20000`. Thời gian là `ceil(2,4 × số khách)` "
        f"vì CLI của bản phát hành nhận số giây nguyên. Tổng cộng solver dùng {cpu_seconds / 3600:.3f} giờ CPU. "
        "Benchmark dùng Ubuntu WSL 2, Core i5-12400F và GCC 15.2. Paper dùng CentOS 7.8, Xeon Gold 6148 "
        "và g++ 9.1.0. Tag `v1.0.0` chứa một bản vá nhỏ của tác giả. Seed 1–10 là lựa chọn cho lần tái lập này. "
        "[Môi trường chạy](environment.txt) · [Release của tác giả](https://github.com/vidalt/HGS-CVRP/releases/tag/v1.0.0)",
        "",
        "Verifier tính lại chi phí EUC_2D từ từng tuyến, kiểm tra khách được phục vụ đúng một lần và tải từng xe. "
        "Chi phí cuối trong log hội tụ khớp với nghiệm đã chấm. [Kết quả từng seed](runs.csv) · [Thống kê từng instance](summary.csv)",
        "",
    ]
    report = OUTPUT / "REPORT.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
