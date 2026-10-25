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
    cur = lst.head
    while cur:
        cur.prev, cur.next = cur.next, cur.prev
        m.relink(2)
        cur = cur.prev
    lst.head, lst.tail = lst.tail, lst.head
    m.relink(2)


def swap_payloads(lst: DList, m: Meter):
    a, b = lst.head, lst.tail
    i = 0
    while a is not b and a.prev is not b:
        a.val, b.val = b.val, a.val
        m.touch_write(i); m.touch_write(-i - 1)
        a, b, i = a.next, b.prev, i + 1


def flip_direction(lst: DList, m: Meter):
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
