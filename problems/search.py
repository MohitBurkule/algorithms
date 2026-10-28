"""Membership search in a static sorted set.

  * linear      -- sequential scan; zero seeks, great on tape for 1 query
  * binary      -- O(log n) reads but each probe is a far seek
  * eytzinger   -- BFS layout: probes cluster at the front (cache/disk friendly)
  * b_tree      -- fan-out B: O(log_B n) seeks, each followed by B sequential reads
"""
import bisect
import random

from hypothesis import Meter

NAME = "search"
B = 64


def linear(arr, x, m, _aux=None):
    """Linear scan: O(n) reads, O(n) compares in worst case.

    Why: Just scan from left to right, compare each element, stop when found.
    Worst case: element is at the end or not in the array.

    Wins on: Nothing (binary and variants always beat it for sorted arrays).
    """
    for i, v in enumerate(arr):
        m.touch_read(i); m.cmp()
        if v >= x:
            return v == x
    return False


def binary(arr, x, m, _aux=None):
    """Binary search: O(log n) reads and compares, but random access.

    Why: Each mid calculation is at a new, unpredictable address. Even though
    we only do log n probes (cutting the search space in half each time), each
    probe is a seek away from the last one.

    Complexity: O(log n) compares, reads, and seeks (each read is far from the
    last, so each is counted as a seek).

    Wins on: Nothing in this benchmark (eytzinger beats it by improving locality).
    """
    lo, hi = 0, len(arr)
    while lo < hi:
        mid = (lo + hi) // 2
        m.touch_read(mid); m.cmp()
        if arr[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return lo < len(arr) and arr[lo] == x


def build_eytzinger(arr):
    out = [0] * (len(arr) + 1)
    it = iter(arr)

    def fill(k):
        if k <= len(arr):
            fill(2 * k); out[k] = next(it); fill(2 * k + 1)

    fill(1)
    return out


def eytzinger(arr, x, m, ey):
    """Breadth-first tree layout: O(log n) seeks, but cache-friendly.

    Why: Layout the binary search tree in breadth-first order. Element at index i
    has children at 2i and 2i+1. When we read element i and it's not the target,
    we either go left (2i) or right (2i+1). Both children are close together in
    memory (within a cache line or disk block), so we're likely to hit the same
    block on the next read.

    Complexity: O(log n) compares and reads (same as binary search), but with
    better cache locality. However, in seek count, it's the same: O(log n) reads
    that are far apart.

    Wins on: RAM, NETWORK, PARALLEL (the cache clustering effect reduces the
    cost per read, even though seek count is the same).
    Loses on: HDD, TAPE (fixed seek cost per probe defeats the clustering).
    """
    k = 1
    while k < len(ey):
        m.touch_read(k); m.cmp()
        if ey[k] == x:
            return True
        k = 2 * k + (ey[k] < x)
    return False


def build_btree(arr):
    """Levels of separator keys, each level stored contiguously."""
    levels = [arr]
    while len(levels[-1]) > B:
        levels.append(levels[-1][::B])
    return levels[::-1]


def b_tree(arr, x, m, levels):
    """B-tree: O(log_B n) seeks, each followed by B sequential reads.

    Why: A B-tree with branching factor B has O(log_B n) levels. At each level,
    you compare against B separators (log B comparisons via binary search), then
    read B elements sequentially from that block. The key insight: one fixed seek
    cost to get to the block, then B elements read for cheap (sequential I/O).
    This amortizes the seek cost over B elements.

    Complexity: O(log_B n) seeks, O(log_B n * B) = O(log n / log B) reads,
    O(log B * log_B n) = O(log n) compares.

    For B = 64 (typical disk block size), a 1 million element array has
    log_64(1M) ≈ 3 levels. Three seeks is far fewer than log(1M) = 20 seeks
    for binary search, even though you read more elements per seek.

    Wins on: HDD, TAPE (seeks dominate; fewer seeks beats fewer reads).
    Loses on: RAM (the indirection and repeated binary search on B separators
    is slower than a tight binary search loop on the full array).
    """
    base, idx = 0, 0
    for lv in levels:
        lo = idx * B if lv is not levels[0] else 0
        hi = min(len(lv), lo + B)
        for i in range(lo, hi):  # one seek, then a sequential block read
            m.touch_read(base + i)
        m.cmp(max(1, (hi - lo).bit_length()))
        pos = bisect.bisect_right(lv, x, lo, hi) - 1
        if lv is levels[-1]:
            return pos >= lo and lv[pos] == x
        idx = max(pos, lo)
        base += len(lv) * 4  # next level lives elsewhere on disk
    return False


SOLUTIONS = {"linear": linear, "binary": binary, "eytzinger": eytzinger, "b_tree": b_tree}
BUILD = {"eytzinger": build_eytzinger, "b_tree": build_btree}


def run(fn, n=1 << 14, seed=0, nq=50) -> Meter:
    rng = random.Random(seed)
    arr = sorted(rng.sample(range(10 * n), n))
    name = next(k for k, v in SOLUTIONS.items() if v is fn)
    aux = BUILD[name](arr) if name in BUILD else None
    s = set(arr)
    m = Meter()
    for _ in range(nq):
        x = rng.choice(arr) if rng.random() < 0.5 else rng.randrange(10 * n)
        m.reset_heads()  # each query starts from a cold head position
        assert fn(arr, x, m, aux) == (x in s), name
    for f in ("compares", "reads", "seeks", "seek_distance"):
        setattr(m, f, getattr(m, f) // nq)
    return m
