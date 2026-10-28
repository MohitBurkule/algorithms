"""Median of data spread over k machines: optimise *transmit complexity*.

  * gather_all     -- ship everything to a coordinator: k messages, n items
  * value_bisect   -- binary search on the value range; each round the
                      coordinator broadcasts a pivot and every node replies with
                      one count: O(k log U) messages, O(k log U) items
  * sample_then_bisect -- nodes send a small sample, coordinator narrows the
                      range first, then bisects: fewer rounds, a few more items
"""
import bisect
import random

from hypothesis import Meter

NAME = "distributed_median"
U = 1 << 20  # value universe


def gather_all(shards, m):
    """Centralized: send all data to one machine, sort, find median.

    Complexity: k messages (one per machine), n items transmitted, O(n log n)
    compares (sorting).

    Why: Simple and effective if you can afford the transmission. The coordinator
    sorts the full dataset and returns the median element.

    Wins on: HIGH_LATENCY network (transmit_msg = 1000 >> transmit_item = 10).
    Even though n items are sent, k messages at 1000 each can be expensive. But
    if the alternative is many rounds of messages, gather_all wins.
    Loses on: METERED_BW network (transmit_item = 100 dominates).
    """
    allv = []
    for s in shards:
        m.send(len(s)); allv.extend(s)
    allv.sort(); m.cmp(len(allv) * max(1, len(allv).bit_length()))
    return allv[(len(allv) - 1) // 2]


def _count_le(shards, x, m):
    tot = 0
    for s in shards:
        m.send(1)  # pivot broadcast
        m.send(1)  # count reply
        m.cmp(max(1, len(s).bit_length()))
        tot += bisect.bisect_right(s, x)
    return tot


def _bisect(shards, lo, hi, m):
    n = sum(map(len, shards))
    k = (n - 1) // 2 + 1  # want smallest x with count_le(x) >= k
    while lo < hi:
        mid = (lo + hi) // 2
        if _count_le(shards, mid, m) >= k:
            hi = mid
        else:
            lo = mid + 1
    return lo


def value_bisect(shards, m):
    """Binary search on the value range.

    Complexity: O(log U) rounds where U is the value universe. Each round:
    broadcast a pivot (1 message per machine = k messages), machines count
    elements <= pivot (1 message with 1 count back = k messages). Total:
    O(k log U) messages, O(k log U) items (just counts, not actual elements).

    Why: Narrow the value range by repeatedly asking "how many elements are
    <= this value?". If the answer is >= position of median, go lower. Else go
    higher. The key insight: you never send the actual elements, just counts.

    Wins on: Most machines except high-latency. Message count is O(k log U),
    which is fine. Item count is O(k log U), which is tiny (log U is at most
    20 for 1M-element universe).
    Loses on: HIGH_LATENCY (many messages at high cost per message).
    """
    return _bisect(shards, 0, U, m)


def sample_then_bisect(shards, m, per_node=16):
    """Take a small sample from each node, then binary search on a narrowed range.

    Complexity: O(k * per_node) items in sampling (k messages), then O(log range)
    rounds of value bisection. Total messages: O(k) for sample, then O(k log range)
    for verification and bisection. Total items: O(k * per_node + k log range).

    Why: Instead of bisecting on the full value range [0, U], sample the data to
    estimate a narrower range [lo, hi], then bisect within that range. This
    reduces the log factor from log U to log(U / (sample_spread)).

    Wins on: Nothing in the benchmark; the sample overhead (k * per_node items
    transmitted) is usually not worth the reduced bisection rounds. value_bisect
    is often better because the sample itself costs items, and O(log U) rounds
    of value_bisect is already cheap.
    Loses on: Everything; value_bisect dominates.
    """
    n = sum(map(len, shards))
    sample = []
    for s in shards:
        step = max(1, len(s) // per_node)
        sample.extend(s[::step]); m.send(len(s[::step]))
    sample.sort()
    # Bracket the median using sample quantiles, verify the bracket, fall back.
    q = len(sample)
    lo = sample[max(0, q // 2 - q // 8)]
    hi = sample[min(q - 1, q // 2 + q // 8)]
    k = (n - 1) // 2 + 1
    if _count_le(shards, lo - 1, m) >= k:
        lo = 0
    if _count_le(shards, hi, m) < k:
        hi = U
    return _bisect(shards, lo, hi, m)


SOLUTIONS = {"gather_all": gather_all, "value_bisect": value_bisect,
             "sample_then_bisect": sample_then_bisect}


def run(fn, n=20000, k=16, seed=0) -> Meter:
    rng = random.Random(seed)
    data = [rng.randrange(U) for _ in range(n)]
    shards = [sorted(data[i::k]) for i in range(k)]  # each node sorts locally
    m = Meter()
    got = fn(shards, m)
    assert got == sorted(data)[(n - 1) // 2], fn.__name__
    return m
