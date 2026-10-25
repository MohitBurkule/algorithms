"""Run every problem's solutions under every hypothesis; show who wins where.

    python benchmark.py               # all problems, all machines
    python benchmark.py sort lca      # a subset of problems
"""
import sys

from hypothesis import HYPOTHESES
from problems import distributed_median, lca, list_reverse, search, sorting

PROBLEMS = {p.NAME: p for p in (sorting, lca, search, distributed_median, list_reverse)}


def fmt(x):
    for unit, d in (("G", 1e9), ("M", 1e6), ("k", 1e3)):
        if x >= d:
            return f"{x / d:.1f}{unit}"
    return f"{x:.0f}"


def bench(problem):
    meters = {name: problem.run(sol) for name, sol in problem.SOLUTIONS.items()}
    names = list(meters)
    w = max(map(len, names)) + 2
    print(f"\n=== {problem.NAME} ===")
    print("machine".ljust(14) + "".join(n.rjust(w) for n in names) + "   winner")
    for key, mach in HYPOTHESES.items():
        costs = {n: meters[n].total_cost(mach) for n in names}
        best = min(costs, key=costs.get)
        row = "".join(fmt(costs[n]).rjust(w) for n in names)
        print(key.ljust(14) + row + f"   {best}")


if __name__ == "__main__":
    for name in sys.argv[1:] or PROBLEMS:
        bench(PROBLEMS[name])
