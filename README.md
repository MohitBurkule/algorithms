# algorithms-under-hypotheses

Textbook algorithms are tuned for time and space complexity. Real deployments
charge for other things too: seeks on a tape, write wear on an SSD, messages on
a network, parallel depth on a GPU, pointer re-links in a persistent store,
setup cost spread over many queries. This repo makes those costs explicit and
shows which algorithm wins under each one.

- **`hypothesis.py`**: the deployment model. A `Machine` gives a weight to each
  kind of event (compare, read, write, fixed seek, seek distance, message,
  item transmitted, pointer change, cores, extra space, number of queries).
  `HYPOTHESES` holds the preset machines. A `Meter` counts what an algorithm
  does, and `Meter.total_cost(machine)` turns those counts into one cost.
- **`problems/`**: each file is one problem with several solutions. Every
  solution is checked for correctness when it runs.
- **`benchmark.py`**: runs every solution on every machine and names the
  winner on each.

```
python benchmark.py            # everything
python benchmark.py lca sort   # a subset
```

## Problems

| problem | solutions | what is traded |
|---|---|---|
| `sort` | insertion, merge, heap, selection, cycle, bitonic | writes (SSD) vs seeks (tape/HDD) vs depth (parallel) vs extra space |
| `lca` | naive, binary lifting, Euler+sparse table, Farach-Colton–Bender | preprocessing vs per-query time vs space (FCB: O(n) prep, O(1) query) |
| `search` | linear, binary, Eytzinger, B-tree | seek count vs comparisons |
| `distributed_median` | gather-all, value bisection, sample+bisect | messages (latency) vs items sent (bandwidth) |
| `list_reverse` | relink, swap payloads, direction flag | pointer changes vs writes vs per-traversal overhead |

## Adding things

- New environment: add a `Machine` to `HYPOTHESES`.
- New problem: add `problems/foo.py` with `NAME`, `SOLUTIONS` and a
  `run(solution) -> Meter`, then register it in `benchmark.py`.
