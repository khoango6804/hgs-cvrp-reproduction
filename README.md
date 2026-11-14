# HGS-CVRP reproduction and route recombination

This project reproduces Vidal's HGS-CVRP v1.0.0 on eight CVRPLIB X instances and evaluates Set Partitioning on feasible routes collected across seeds. It includes the official C++ release and its MIT license, the Python experiment runners, and the historical BKS reference used for scoring.

## Run on Linux

Use GCC with C++11 support and Python 3.9 or newer. Install NumPy and SciPy (1.9 or newer) for the Set Partitioning experiments. The batch launchers use `taskset` and `flock`. Launchers with a fixed CPU affinity use logical CPUs `0,2,4,6,8,10` from the original six-core test host. Adjust that affinity for your machine if those IDs are unavailable.

```bash
python3 -m pip install numpy 'scipy>=1.9'
bash run_linux_full.sh
python3 report_linux_full.py
bash run_equal_budget.sh
```

The first launcher builds the solver and runs 10 seeds on the eight instances at the paper's CPU budget. The second experiment reserves one second per seed for post-processing and compares final-route Set Partitioning with the HGS baseline at the same total CPU limit. Both commands write results under `results/`.

## Other experiments

```bash
# Compare final-route and intermediate-incumbent pools at full budget.
HGS_SNAPSHOT_OUTPUT=results/snapshot-full HGS_SNAPSHOT_FRACTION=1 \
  HGS_SNAPSHOT_SELECTION=late bash run_snapshot_pilot.sh {1..10}

# Sample feasible survivors at full and double budget on two large instances.
HGS_POPULATION_OUTPUT=results/population-pool-full HGS_POPULATION_FRACTION=1 \
  bash run_population_pool.sh {1..10}
HGS_POPULATION_OUTPUT=results/population-pool-2x HGS_POPULATION_FRACTION=2 \
  bash run_population_pool.sh {1..10}
python3 merge_population_budgets.py
```

`route_pool.py` implements route recombination. `benchmark_postprocess.py` and `exact_route_sp.py` contain additional comparisons. `REPORT.md` records the initial pilot. The upstream ZIP is included because the audit scripts compare the checked-in solver sources byte for byte with that archive.

## References

- [Vidal (2022), Hybrid Genetic Search for the CVRP](https://doi.org/10.1016/j.cor.2021.105643)
- [HGS-CVRP v1.0.0 and MIT license](https://github.com/vidalt/HGS-CVRP/tree/v1.0.0)
- [CVRPLIB](https://galgos.inf.puc-rio.br/cvrplib/)
