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
    for i, v in enumerate(arr):
        m.touch_read(i); m.cmp()
        if v >= x:
            return v == x
    return False


def binary(arr, x, m, _aux=None):
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
