"""Lowest common ancestor: trading preprocessing against per-query cost.

  * naive         -- no preprocessing, O(depth) per query
  * binary_lift   -- O(n log n) preprocessing/space, O(log n) per query
  * sparse_table  -- Euler tour + RMQ sparse table: O(n log n) prep, O(1) query
  * fcb           -- Farach-Colton & Bender: O(n) prep, O(1) query
                     (Euler tour has +-1 property -> blocks of size ~log n/2,
                      sparse table over block minima, in-block answers looked
                      up from a table indexed by the block's +-1 pattern)

Which wins depends on Machine.queries (how many queries amortise setup) and
Machine.extra_space (how much auxiliary memory hurts).
"""
import random

from hypothesis import Meter

NAME = "lca"


def random_tree(n, rng):
    """Deep-ish random tree: parent[i] < i."""
    return [-1] + [rng.randrange(max(0, i - 8), i) for i in range(1, n)]


def _children(parent):
    ch = [[] for _ in parent]
    for v, p in enumerate(parent):
        if p >= 0:
            ch[p].append(v)
    return ch


def _depths(parent, m):
    d = [0] * len(parent)
    for v in range(1, len(parent)):
        m.touch_read(v)
        d[v] = d[parent[v]] + 1
    return d


def _euler(parent, m):
    ch = _children(parent)
    d = _depths(parent, m)
    euler, first = [], [0] * len(parent)
    stack = [(0, 0)]
    while stack:
        v, i = stack.pop()
        if i == 0:
            first[v] = len(euler)
        euler.append(v)
        m.touch_write(len(euler))
        if i < len(ch[v]):
            stack.append((v, i + 1))
            stack.append((ch[v][i], 0))
    return euler, first, d


# ---------------------------------------------------------------- naive
class Naive:
    def __init__(self, parent, m):
        self.p = parent
        self.d = _depths(parent, m)
        m.space(len(parent))

    def query(self, u, v, m):
        p, d = self.p, self.d
        while d[u] > d[v]:
            m.touch_read(u); u = p[u]
        while d[v] > d[u]:
            m.touch_read(v); v = p[v]
        while u != v:
            m.cmp(); m.touch_read(u); m.touch_read(v)
            u, v = p[u], p[v]
        return u


# ---------------------------------------------------------------- binary lifting
class BinaryLift:
    def __init__(self, parent, m):
        n = len(parent)
        self.d = _depths(parent, m)
        self.LOG = max(1, n.bit_length())
        up = [[max(p, 0) for p in parent]]
        for _ in range(1, self.LOG):
            prev = up[-1]
            up.append([prev[prev[v]] for v in range(n)])
            m.cmp(n)
        self.up = up
        m.space(n * self.LOG)

    def query(self, u, v, m):
        d, up = self.d, self.up
        if d[u] < d[v]:
            u, v = v, u
        diff = d[u] - d[v]
        k = 0
        while diff:
            if diff & 1:
                m.touch_read(k * len(d) + u); u = up[k][u]
            diff >>= 1; k += 1
        if u == v:
            return u
        for k in range(self.LOG - 1, -1, -1):
            m.cmp()
            if up[k][u] != up[k][v]:
                u, v = up[k][u], up[k][v]
        return up[0][u]


# ---------------------------------------------------------------- sparse table
class SparseTable:
    def __init__(self, parent, m):
        self.e, self.f, self.d = _euler(parent, m)
        E = len(self.e)
        key = [self.d[v] for v in self.e]
        tbl = [list(range(E))]
        j = 1
        while (1 << j) <= E:
            prev, half = tbl[-1], 1 << (j - 1)
            row = []
            for i in range(E - (1 << j) + 1):
                a, b = prev[i], prev[i + half]
                m.cmp()
                row.append(a if key[a] <= key[b] else b)
            tbl.append(row)
            j += 1
        self.tbl, self.key = tbl, key
        m.space(sum(len(r) for r in tbl) + E)

    def query(self, u, v, m):
        l, r = sorted((self.f[u], self.f[v]))
        j = (r - l + 1).bit_length() - 1
        a, b = self.tbl[j][l], self.tbl[j][r - (1 << j) + 1]
        m.touch_read(l); m.touch_read(r); m.cmp()
        return self.e[a if self.key[a] <= self.key[b] else b]


# ---------------------------------------------------------------- Farach-Colton & Bender
class FCB:
    def __init__(self, parent, m):
        self.e, self.f, self.d = _euler(parent, m)
        key = [self.d[v] for v in self.e]
        E = len(key)
        b = max(1, E.bit_length() // 2)
        self.b, self.key = b, key
        nb = (E + b - 1) // b
        # block minima (positions)
        bmin = []
        for i in range(nb):
            lo, hi = i * b, min(E, (i + 1) * b)
            best = lo
            for k in range(lo + 1, hi):
                m.cmp()
                if key[k] < key[best]:
                    best = k
            bmin.append(best)
        # sparse table over the nb = O(n / log n) block minima -> O(n) total
        tbl = [bmin[:]]
        j = 1
        while (1 << j) <= nb:
            prev, half = tbl[-1], 1 << (j - 1)
            row = []
            for i in range(nb - (1 << j) + 1):
                x, y = prev[i], prev[i + half]
                m.cmp()
                row.append(x if key[x] <= key[y] else y)
            tbl.append(row)
            j += 1
        self.tbl = tbl
        # +-1 signature of each block; table of in-block answers per signature.
        self.sig = []
        self.inblock = {}
        for i in range(nb):
            lo, hi = i * b, min(E, (i + 1) * b)
            s = 0
            for k in range(lo + 1, hi):
                s = (s << 1) | (key[k] > key[k - 1])
            s |= (hi - lo) << b  # include length so the tail block is distinct
            self.sig.append(s)
            if s not in self.inblock:
                L = hi - lo
                ans = [[0] * L for _ in range(L)]
                for x in range(L):
                    best = x
                    for y in range(x, L):
                        m.cmp()
                        if key[lo + y] < key[lo + best]:
                            best = y
                        ans[x][y] = best
                self.inblock[s] = ans
        m.space(sum(len(r) for r in tbl) + nb
                + sum(len(t) ** 2 for t in self.inblock.values()) + E)

    def _in(self, blk, x, y, m):
        m.touch_read(blk)
        return blk * self.b + self.inblock[self.sig[blk]][x][y]

    def _better(self, a, b, m):
        m.cmp()
        return a if self.key[a] <= self.key[b] else b

    def query(self, u, v, m):
        l, r = sorted((self.f[u], self.f[v]))
        b = self.b
        bl, br = l // b, r // b
        if bl == br:
            return self.e[self._in(bl, l % b, r % b, m)]
        last_l = len(self.inblock[self.sig[bl]]) - 1
        best = self._better(self._in(bl, l % b, last_l, m), self._in(br, 0, r % b, m), m)
        if br - bl > 1:
            lo, hi = bl + 1, br - 1
            j = (hi - lo + 1).bit_length() - 1
            best = self._better(best, self._better(self.tbl[j][lo], self.tbl[j][hi - (1 << j) + 1], m), m)
        return self.e[best]


SOLUTIONS = {"naive": Naive, "binary_lift": BinaryLift, "sparse_table": SparseTable, "fcb": FCB}


def run(cls, n=2000, seed=0, nq=200) -> Meter:
    rng = random.Random(seed)
    parent = random_tree(n, rng)
    prep = Meter()
    s = cls(parent, prep)
    ref = Naive(parent, Meter())
    m = Meter(preprocess=prep)
    pairs = [(rng.randrange(n), rng.randrange(n)) for _ in range(nq)]
    for u, v in pairs:
        assert s.query(u, v, m) == ref.query(u, v, Meter()), cls.__name__
    # report per-query numbers so Machine.queries can amortise the setup
    for f in ("compares", "reads", "writes", "seeks", "seek_distance"):
        setattr(m, f, getattr(m, f) // nq)
    m.extra_space = prep.extra_space
    prep.extra_space = 0
    return m
