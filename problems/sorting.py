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
    """Insert each element into its sorted position in a[0..i-1].

    Complexity: O(n²) compares, O(n²) seeks in the worst case (each comparison
    and shift jumps to a different part of the array), O(n) to O(n²) writes
    depending on data (in random data, element i is written on average i/2 times).

    Why: For each element a[i], we compare it against a[0..i-1] to find where to
    insert it, then shift all larger elements right. This creates O(n²) reads and
    writes. Each access is a separate seek.

    Wins on: TAPE for small arrays (O(n²) seeks but each element touched only a
    constant number of times, vs merge sort's O(n log n) sequential passes).
    """
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
    """Bottom-up merge sort using two tapes: purely sequential I/O.

    Complexity: O(n log n) compares and reads/writes, but purely sequential
    (seek distance is O(n log n) cells, spread over O(log n) passes, so
    amortized ~O(n) seeks total across the entire sort). Space: O(n).

    Why: Divide and conquer. Merge two sorted arrays by comparing and copying
    elements in order. Each pass through the array does one round of merges:
    merge [0..1], [2..3], [4..5], etc., then merge [0..3], [4..7], etc.
    The key insight: every comparison results in one write, and writes are
    sequential within each merge region.

    Wins on: TAPE (purely sequential access pattern minimizes head movement).
    Also wins on RAM and most machines because O(n log n) is optimal for
    comparison sorts, and the sequential I/O is cache-friendly.
    """
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
    """Build a heap, then repeatedly pop the root and re-heapify.

    Complexity: O(n log n) compares, O(n log n) reads/writes, O(n log n) seeks
    (because heap is a binary tree laid out linearly, and parent-child pointers
    are far apart). Space: O(1).

    Why: A complete binary tree with n nodes has depth O(log n). Building a
    heap takes O(n) sift operations of O(log n) each, for O(n log n) total.
    Then n extractions, each an O(log n) sift-down. But in a linear array,
    element at index i has children at 2i and 2i+1, which are far away.

    Wins on: TINY_MEM (uses O(1) extra space; merge sort needs O(n)).
    Loses on: tape/HDD/SSD (random access pattern causes many seeks).
    """
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
    """Repeatedly find the minimum and swap it to its final position.

    Complexity: O(n²) compares (for each position i, scan the rest to find min).
    O(n) writes (each element is written exactly once to its final position, or
    swapped in place). O(n²) seeks and reads (scan the array n times).

    Why: For position i, scan from i to n to find the minimum. When found,
    swap it into position i. Repeat for i = 0..n-1. This is O(n²) comparisons
    but only O(n) writes (an element at position j is swapped once, then never
    written again, unless it's involved in a future swap as the min for some i > j).

    Wins on: SSD and HDD (write cost dominates; O(n) writes beats merge sort's
    O(n log n) writes, and selection's O(n²) seeks/reads are spread over fewer
    expensive write operations).
    """
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
    """Provably minimal write sort: each element is written exactly once.

    Complexity: O(n²) compares (find position of each element), O(n) writes
    (each element written to its final position, plus a few duplicates in
    cycles), O(n²) seeks and reads.

    Why: For each starting position, place the element in its correct sorted
    position, which displaces the element that was there. Continue placing the
    displaced element until we cycle back. The key insight: if an element has
    k elements smaller than it, it belongs at position k. We find k by counting
    comparisons, then write the element there. The next element written is the
    one displaced. This guarantees each element is written O(1) times on average.

    Wins on: SSD with very expensive writes (cycle sort writes are minimal, even
    though it has O(n²) compares like selection sort, the write count is proven
    minimal for any comparison-based sort).
    """
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
    """Bitonic sorting network: O(log² n) parallel depth, all steps independent.

    Complexity: O(n log² n) compares and writes (log n stages, each stage is a
    bitonic merge of size increasing from 2 to n; stage k has 2^k layers, each
    layer does n/2 compare-exchanges). O(log² n) parallel depth (can execute
    all independent steps in one round). O(n log² n) seeks (at layer j, partners
    are j cells apart, and there are n/2 pairs per layer).

    Why: Batcher's bitonic sort is a sorting network (a fixed pattern of
    comparisons regardless of the data). Build a bitonic sequence of size 2,
    then merge two size-2 bitonics, then merge two size-4 bitonics, etc.
    The key insight: at each stage/layer pair, all comparisons are independent
    and can run in parallel. Stage k has log k layers, and there are log n stages,
    for O(log² n) depth. Total work is O(n log² n) because summing over all
    (stage, layer) pairs gives sum of n/2 (per pair) * log² n pairs = O(n log² n).

    Wins on: PARALLEL (1024-core machine; depth is O(log² n) vs O(n log n) work
    for merge, so with 1024 cores you can do most of the n log n work in
    parallel, paying O(log² n) time = O(log² n * compare) cost, which is tiny).
    """
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
