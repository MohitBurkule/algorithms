"""Sorting: same output, wildly different bills depending on the machine.

  * merge_sort      -- sequential passes only; the tape/HDD champion
  * heap_sort       -- O(1) extra space but jumps all over memory
  * selection_sort  -- O(n^2) compares but only O(n) writes (SSD wear)
  * cycle_sort      -- provably minimal number of writes
  * bitonic_sort    -- O(n log^2 n) work but O(log^2 n) parallel depth
  * insertion_sort  -- the baseline
"""
import random

from hypothesis import Meter, Tape

NAME = "sort"


def insertion_sort(a: Tape, m: Meter):
    for i in range(1, len(a)):
        x = a[i]
        j = i - 1
        while j >= 0:
            m.cmp()
            y = a[j]
            if y <= x:
                break
            a[j + 1] = y
            j -= 1
        a[j + 1] = x


def merge_sort(a: Tape, m: Meter):
    """Bottom-up, ping-ponging between two tapes: purely sequential scans."""
    n = len(a)
    b = Tape([0] * n, m, device=1)  # a second tape drive
    m.space(n)
    src, dst, width = a, b, 1
    while width < n:
        for lo in range(0, n, 2 * width):
            mid, hi = min(lo + width, n), min(lo + 2 * width, n)
            i, j = lo, mid
            for k in range(lo, hi):
                if i < mid and (j >= hi or (m.cmp() or src[i] <= src[j])):
                    dst[k] = src[i]; i += 1
                else:
                    dst[k] = src[j]; j += 1
        src, dst, width = dst, src, width * 2
    if src is not a:
        for k in range(n):
            a[k] = src[k]


def heap_sort(a: Tape, m: Meter):
    n = len(a)

    def sift(i, end):
        while 2 * i + 1 < end:
            c = 2 * i + 1
            if c + 1 < end:
                m.cmp()
                if a[c + 1] > a[c]:
                    c += 1
            m.cmp()
            if a[i] >= a[c]:
                return
            a[i], a[c] = a[c], a[i]
            i = c

    for i in range(n // 2 - 1, -1, -1):
        sift(i, n)
    for end in range(n - 1, 0, -1):
        a[0], a[end] = a[end], a[0]
        sift(0, end)


def selection_sort(a: Tape, m: Meter):
    n = len(a)
    for i in range(n - 1):
        best, bv = i, a[i]
        for j in range(i + 1, n):
            m.cmp()
            v = a[j]
            if v < bv:
                best, bv = j, v
        if best != i:
            a[best], a[i] = a[i], bv


def cycle_sort(a: Tape, m: Meter):
    """Writes each element at most once into its final slot."""
    n = len(a)
    for start in range(n - 1):
        item = a[start]
        pos = start
        for i in range(start + 1, n):
            m.cmp()
            if a[i] < item:
                pos += 1
        if pos == start:
            continue
        while item == a[pos]:
            pos += 1
        a[pos], item = item, a[pos]
        while pos != start:
            pos = start
            for i in range(start + 1, n):
                m.cmp()
                if a[i] < item:
                    pos += 1
            while item == a[pos]:
                pos += 1
            a[pos], item = item, a[pos]


def bitonic_sort(a: Tape, m: Meter):
    """Sorting network: every compare-exchange in a stage is independent."""
    n = len(a)
    size = 1
    while size < n:
        size *= 2
    pad = [float("inf")] * (size - n)
    data = [a[i] for i in range(n)] + pad
    k = 2
    while k <= size:
        j = k // 2
        while j > 0:
            # size/2 independent compare-exchanges (1 compare + 2 reads each)
            # run in one parallel round. Writes are charged at write price.
            # Partners are j cells apart, so a sequential device pays a seek
            # per pair once j > 1.
            m.parallel_round(3 * (size // 2))
            if j > 1:
                m.seeks += size // 2
                m.seek_distance += size * j
            for i in range(size):
                l = i ^ j
                if l > i:
                    up = (i & k) == 0
                    if (data[i] > data[l]) == up:
                        data[i], data[l] = data[l], data[i]
                        m.writes += 2
            j //= 2
        k *= 2
    for i in range(n):
        a[i] = data[i]


SOLUTIONS = {
    "insertion": insertion_sort,
    "merge": merge_sort,
    "heap": heap_sort,
    "selection": selection_sort,
    "cycle": cycle_sort,
    "bitonic": bitonic_sort,
}


def run(solver, n=256, seed=0) -> Meter:
    rng = random.Random(seed)
    data = [rng.randrange(10 * n) for _ in range(n)]
    m = Meter()
    t = Tape(data, m)
    solver(t, m)
    assert t.data == sorted(data), solver.__name__
    return m
