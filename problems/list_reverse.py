"""Reverse a doubly linked list: optimise *pointer-change complexity*.

When nodes live in a persistent store (on-disk records, foreign keys, objects
referenced by other systems), changing a node's address/links can be far more
expensive than rewriting its payload.

  * relink          -- classic: swap prev/next of every node, 2n pointer changes
  * swap_payloads   -- walk from both ends swapping values: 0 pointer changes,
                       n writes
  * flip_direction  -- O(1): store a 'reversed' flag and swap head/tail; costs
                       one extra branch (compare) on every later traversal step
"""
import random

from hypothesis import Meter

NAME = "list_reverse"


class Node:
    __slots__ = ("val", "prev", "next")

    def __init__(self, val):
        self.val, self.prev, self.next = val, None, None


class DList:
    def __init__(self, vals):
        self.head = self.tail = None
        self.reversed = False
        for v in vals:
            n = Node(v)
            if self.tail:
                self.tail.next, n.prev = n, self.tail
            else:
                self.head = n
            self.tail = n

    def to_list(self, m=None):
        out, cur = [], self.head
        while cur:
            out.append(cur.val)
            if m is not None and self.reversed is not None:
                m.cmp()  # cost of honoring the direction flag
            cur = cur.prev if self.reversed else cur.next
        return out


def relink(lst: DList, m: Meter):
    """Classic in-place reversal: swap prev/next pointers of every node.

    Complexity: O(n) pointer changes (2 per node), O(n) reads (read cur.prev/next),
    but 0 value writes. Space: O(1).

    Why: Traverse the list once, swapping prev and next pointers. Each swap is 2
    pointer changes. At the end, swap head and tail to point in the new direction.

    Wins on: SSD, HDD, TAPE (write cost for values is expensive; zero value writes
    beats any algorithm that must swap values). POINTER machines lose because
    pointer changes are costly, but still win over swap_payloads if writes are
    very expensive (e.g., write=400 on SSD).
    Loses on: POINTER (2n pointer changes are expensive; flip_direction wins).
    """
    cur = lst.head
    while cur:
        cur.prev, cur.next = cur.next, cur.prev
        m.relink(2)
        cur = cur.prev
    lst.head, lst.tail = lst.tail, lst.head
    m.relink(2)


def swap_payloads(lst: DList, m: Meter):
    """Reverse by swapping values, not pointers.

    Complexity: O(n/2) swaps = O(n) reads and writes to values. 0 pointer changes.
    Space: O(1).

    Why: Walk from both ends of the list (following existing pointers, which are
    never changed), and swap the values. Each swap is 1 read + 1 write per value.

    Wins on: RAM, NETWORK, PARALLEL (pointer changes are free; reads/writes are cheap).
    Also wins on POINTER machines if writes are cheaper than pointer_change.
    Loses on: SSD, HDD, TAPE (writes are expensive; relink wins despite 2n pointer
    changes, because SSD write cost >> pointer cost). Also loses on POINTER if
    pointer_change is cheap relative to writes.
    """
    a, b = lst.head, lst.tail
    i = 0
    while a is not b and a.prev is not b:
        a.val, b.val = b.val, a.val
        m.touch_write(i); m.touch_write(-i - 1)
        a, b, i = a.next, b.prev, i + 1


def flip_direction(lst: DList, m: Meter):
    """Defer cost to traversals: swap head/tail, add a reversed flag.

    Complexity: O(1) reversal time (only swap 2 pointers and 1 boolean). But
    every future traversal pays O(n) extra compares (check the flag per step).
    Space: O(1).

    Why: The reversal cost is deferred to later traversals. If you reverse but
    never traverse, you win. If you reverse and then traverse many times, you
    lose because each traversal does one extra compare per node.

    Wins on: POINTER (only 2 pointer changes, minimal cost). If you reverse but
    don't traverse (e.g., pass the reversed list to a method that doesn't care
    about direction), this is optimal.
    Loses on: Most machines after multiple traversals (the per-traversal compare
    cost adds up). In the benchmark, we do 3 traversals, so the cost is 3n
    compares, which outweighs the O(1) reversal cost.
    """
    lst.head, lst.tail = lst.tail, lst.head
    lst.reversed = not lst.reversed
    m.relink(2)


SOLUTIONS = {"relink": relink, "swap_payloads": swap_payloads, "flip_direction": flip_direction}


def run(fn, n=5000, seed=0, traversals=3) -> Meter:
    rng = random.Random(seed)
    vals = [rng.randrange(1000) for _ in range(n)]
    lst = DList(vals)
    m = Meter()
    fn(lst, m)
    # every solution pays for the same number of later traversals
    for _ in range(traversals):
        got = lst.to_list(m if fn is flip_direction else None)
    assert got == vals[::-1], fn.__name__
    return m
