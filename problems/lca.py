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
    """Naive walk-up: O(depth) per query, O(n) preprocessing.

    Preprocessing: O(n) to compute depths via DFS. Storage: O(n).

    Query: Bring both nodes to the same depth (O(depth)), then walk both up
    in sync until they meet (O(depth)). For a random tree, depth is O(log n).

    Why: Simple and minimal preprocessing. Works by observing that the LCA of
    (u, v) is the first common ancestor when walking up from both nodes.
    Equalize depths first so both pointers move up together.

    Wins on: ONE_QUERY (no expensive preprocessing), RAM, NETWORK, PARALLEL
    (low auxiliary space and simple reads). Also wins on TAPE (depths are
    computed in one DFS pass, then queries walk up parent chains).
    """
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
    """Precompute 2^k-th ancestors: O(n log n) preprocessing, O(log n) query.

    Preprocessing: Build a table up[v][k] where up[v][k] = 2^k-th ancestor of v.
    up[v][0] = parent[v]. up[v][k] = up[up[v][k-1]][k-1] (jump 2^(k-1) twice).
    This takes O(n log n) space and O(n log n) time. Storage: O(n log n).

    Query: Bring both to the same depth using binary lifting (write diff in binary,
    use precomputed jumps). Then binary search on ancestors: for k from log n down
    to 0, if up[k][u] != up[k][v], jump both up by 2^k. This takes O(log n) reads.

    Why: Precomputed ancestors allow O(log n) queries. The trade-off is the
    O(n log n) space for the table.

    Wins on: MANY_QUERIES with moderate space constraints.
    Loses on: ONE_QUERY (preprocessing wasted), SSD (O(n log n) reads scatter).
    """
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
    """Euler tour + RMQ sparse table: O(n log n) preprocessing, O(1) query.

    Preprocessing:
    1. DFS to build Euler tour (O(n)): record each node and its depth at each
       visit (and visit on the way back up). The tour is 2n-1 elements.
    2. For each node, record its first position in the tour (O(n)).
    3. Build RMQ sparse table: ST[i][j] = index of min depth in tour[i..i+2^j-1].
       This is O(n log n) time and space.

    Query: Find positions of u and v in the tour. The LCA is the node with
    minimum depth in tour[l..r]. Use the sparse table to answer this in O(1):
    find the largest power of 2 that fits in [l, r], query two overlapping
    ranges, and return the one with smaller depth.

    Why: Euler tour + RMQ is the classic trick. The depth constraint (±1 per
    step) is not exploited here, unlike FCB.

    Wins on: MANY_QUERIES with no extra space constraints.
    Loses on: SSD (O(n log n) space penalty), ONE_QUERY (preprocessing overhead).
    """
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
    """Farach-Colton & Bender: O(n) preprocessing, O(1) query (tight space!).

    The trick: Euler tour depths follow a ±1 pattern (depth changes by ±1 at
    each step). This means there are only 2^(log n / 2) = sqrt(n) distinct
    ±1 patterns. Precompute answers for every query within each pattern block.

    Preprocessing:
    1. Euler tour (O(n)): like sparse table.
    2. Divide into blocks of size B = log n / 2.
    3. Build sparse table over block minima (O(n/B * log(n/B)) = O(n)).
    4. For each ±1 signature: precompute in-block RMQ (O(B²) per signature,
       but sum over all signatures = O(n)).

    Query: At most 3 table lookups:
      - If both in the same block: in-block lookup.
      - Otherwise: query block minima for the middle, then in-block for edges.

    Why: The ±1 constraint is the key. Without exploiting it, FCB is no better
    than sparse table. With it, preprocessing is O(n) instead of O(n log n).

    Wins on: MANY_QUERIES + tight space (O(n) vs O(n log n)), HDD (seeks),
    or POINTER heavy (the O(n) space is tight).
    Loses on: ONE_QUERY (preprocessing overhead), SSD (O(n) is still expensive).
    """
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
