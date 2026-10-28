# Algorithm Analysis: Complexity Under Different Hypotheses

This document explains the complexity of every algorithm in the repo and why it performs differently on different machines.

## How to Read This

Each algorithm has:
- **What it does**: high-level strategy
- **Complexity**: theoretical complexity and why
- **Why it wins/loses**: which machines prefer it and why

---

## Sorting

All six algorithms solve the same problem (sort n elements) but charge very differently depending on the machine.

### insertion_sort: O(n²) compares, O(n²) moves, but optimal writes for small data

```
for i in 1..n:
    find position of a[i] in a[0..i-1]
    shift elements right, write a[i]
```

**Complexity:**
- **Compares:** O(n²) in the worst case (each element compared against all earlier ones)
- **Writes:** O(n) to O(n²) depending on data (one write per shifted element)
- **Seeks:** O(n²) (each insertion jumps to a different location)

**Why:**
- For random data, on average an element is compared against n/4 prior elements
- Each comparison or write jumps the head, so seeks pile up
- But each element is written only a small constant number of times

**Wins on:**
- **Tape:** O(n²) seeks but O(n²) elements touched only once each; better than merge sort's sequential scans for very small n

**Loses on:**
- **SSD:** writes are expensive (even if total is low, n² compares still hurt)
- **HDD:** O(n²) seeks with fixed seek cost kills it
- **RAM:** merge sort does fewer compares

---

### merge_sort: O(n log n) compares, purely sequential, uses 2x memory

```
split array in half recursively
merge sorted halves by scanning from left and comparing
```

**Complexity:**
- **Compares:** O(n log n) (each element is compared O(log n) times)
- **Reads:** O(n log n) (read each element in each of log n passes)
- **Writes:** O(n log n) (write each element in each of log n passes)
- **Seeks:** O(log n) total across the entire sort (only seek between the two input arrays per merge pass)
- **Space:** O(n) (needs a second tape/buffer)

**Why:**
- Divide and conquer: split into halves → merge (the key insight)
- Merging two sorted arrays of size n is linear with only one comparison per element on average
- Each level of the tree does n comparisons total (across all merges at that level)
- The two arrays (source and destination) are disjoint in memory, so only one seek per merge phase

**Wins on:**
- **Tape:** purely sequential access pattern (one scan left-to-right per pass) minimizes head movement
- **RAM:** O(n log n) is optimal for comparison sorts, and the sequential access wins in practice
- **HDD:** slightly worse than selection sort because of fixed seek cost

**Loses on:**
- **SSD:** write cost (O(n log n) writes) is expensive compared to selection sort (O(n) writes)
- **Parallel:** sequential nature means low parallelism; bitonic sort wins

---

### heap_sort: O(n log n) compares, O(1) extra space, but random access pattern

```
build a heap from the array
repeatedly extract the min and sift-down
```

**Complexity:**
- **Compares:** O(n log n) (build heap in O(n), then n extractions of O(log n) each)
- **Reads:** O(n log n) (sift operations follow pointers down the tree)
- **Writes:** O(n log n) (elements move during sift-downs and extractions)
- **Seeks:** O(n log n) (each parent-child comparison is a far jump in a linear array)
- **Space:** O(1) (in-place sorting)

**Why:**
- Heap is a complete binary tree represented as an array
- Child of element i is at 2i or 2i+1, which is far away in the array
- Sift operations follow parent → child → grandchild chains, each a far seek
- Building the heap: push each element up O(log n) comparisons
- Extraction: pop root, move last element to root, sift down O(log n) steps

**Wins on:**
- **Tiny memory:** only O(1) extra space (merge sort needs O(n))
- **RAM:** despite poor cache locality, O(n log n) with O(1) space is still competitive

**Loses on:**
- **Tape/HDD/SSD:** random access pattern (parent-child jumps) causes many seeks

---

### selection_sort: O(n²) compares, **O(n) writes**, terrible seek pattern

```
for i in 0..n-1:
    find minimum in a[i..n-1]
    if it's not a[i], swap with a[i]
```

**Complexity:**
- **Compares:** O(n²) (find min is O(n), do it n times)
- **Reads:** O(n²) (scan to find each min)
- **Writes:** O(n) (only n elements ever written to)
- **Seeks:** O(n²) (one seek per comparison in the scan)

**Why:**
- Literally find and place each element in its final position
- Each iteration scans the remaining elements (no smart reuse of comparisons)
- Key insight: we only care about writes; we ignore the cost of reads for finding

**Wins on:**
- **SSD:** write cost is dominant; O(n) writes beats other sorts' O(n log n) writes
- **HDD:** O(n) writes beats merge sort's O(n log n) writes, and seeks are paid per-element anyway

**Loses on:**
- **RAM:** O(n²) compares is terrible; merge sort does O(n log n)
- **Tape:** O(n²) seeks are awful

---

### cycle_sort: O(n²) compares, **provably minimal writes O(n)**, also a terrible seeker

```
for each starting position:
    rotate element into its final place
    recursively rotate the displaced element
```

**Complexity:**
- **Compares:** O(n²) (similar to selection sort, find position via comparisons)
- **Writes:** O(n) guaranteed; provably minimal for any comparison sort
- **Seeks:** O(n²)

**Why:**
- Each element is written exactly once into its final position (except for one extra)
- To find the correct position for an element, you compare it against all others that haven't been placed
- After placing element x at position p, the element that was at p becomes the new x to place
- This continues until we cycle back to the start

**Wins on:**
- **SSD with many distinct writes:** write count is proven minimal; even better than selection sort if you count every write as expensive

**Loses on:**
- Most machines that care about compares or seeks

---

### bitonic_sort: O(n log² n) compares, O(log² n) parallel depth, random access

```
sorting network: stages of bitonic merges
at each stage, pairs of elements are far apart
every pair can be compared in parallel
```

**Complexity:**
- **Compares:** O(n log² n) (log n stages, each stage compares n/2 pairs)
- **Writes:** O(n log² n) (one write per compare that swaps)
- **Seeks:** O(n log² n) (partners are j = 2^0, 2^1, ..., 2^(log n-1) apart)
- **Parallel depth:** O(log² n) (log n stages of log n steps each; every compare-exchange in a step is independent)

**Why:**
- Builds on Batcher's bitonic sort: a sorting network (fixed comparison pattern)
- Stage k has 2^k levels; level j has bitonic merges of size 2^j
- At level j, compared elements are j cells apart (so a sequential head must seek j cells)
- The magic: all n/2 pairs in a level are independent, can run in parallel in one round
- Total work: sum over all (stage, level) pairs of n/2 comparisons = n log² n / 2

**Wins on:**
- **Parallel (1024 cores):** O(log² n) depth is tiny compared to O(n log n) sequential steps; time to sort is dominated by depth, not total work

**Loses on:**
- **SSD/HDD:** O(n log² n) writes and seeks dominate
- **Tape:** seek_distance is n log² n * j, where j gets large

---

## Lowest Common Ancestor (LCA)

Given a tree and pairs of nodes (u, v), find their lowest common ancestor. We benchmark preprocessing cost amortized over multiple queries.

### naive: O(1) preprocessing, O(depth) per query

```
preprocessing: compute depth of each node
query(u, v):
    bring both to same depth by walking up from the deeper one
    walk both up in sync until they meet
```

**Complexity:**
- **Preprocessing:** O(n) reads (compute depth of each node via DFS)
- **Per-query compares:** O(log n) (tree is random, depth is ~log n)
- **Per-query reads:** O(log n) (read parent pointers while walking up)

**Why:**
- Depth computation is one DFS pass: read each node once
- Query walks up two paths; in a tree of depth h, this is O(h) steps
- For a balanced random tree, h = O(log n)

**Wins on:**
- **One-shot query:** no preprocessing, so just the query cost O(log n)
- **RAM/Network/Parallel:** low extra space, so amortized cost is low
- **Tape:** reads are sequential along parent chains (mostly; depth is shallow)

**Loses on:**
- Many queries on a deep tree (unbalanced case)

---

### binary_lift: O(n log n) preprocessing and space, O(log n) per query

```
preprocessing: build a table up[v][k] = 2^k-th ancestor of v
query(u, v):
    lift both to same depth using the table
    binary search on the table to find LCA
```

**Complexity:**
- **Preprocessing:** O(n log n) compares (build the table by doubling: up[v][0] = parent[v], then up[v][k] = up[up[v][k-1]][k-1])
- **Space:** O(n log n) (table has one row per node, log n columns)
- **Per-query reads:** O(log n) (read from table)
- **Per-query compares:** O(log n) (binary search on the ancestors)

**Why:**
- Precompute 2^k-th ancestor for each node and each k
- To lift a node up d steps, write d in binary and use the precomputed jumps
- Finding LCA: both nodes are at the same depth; binary search to find the last point where they have different ancestors
- Each query does O(log n) table lookups

**Wins on:**
- **Many queries:** preprocessing cost amortized well

**Loses on:**
- **One-shot query:** preprocessing cost is expensive and wasted
- **SSD:** O(n log n) reads during preprocessing and per query reads are scattered
- **Tape:** building the table does random accesses to parent pointers

---

### sparse_table (Euler tour + RMQ): O(n log n) preprocessing and space, O(1) query

```
preprocessing:
    1. DFS to build Euler tour (list of nodes and depths in DFS order)
    2. for each node, record its position in the tour
    3. build sparse table: ST[i][k] = minimum depth in tour[i..i+2^k-1]
query(u, v):
    1. get positions in Euler tour
    2. query sparse table for min depth in that range
    3. return the node at that position
```

**Complexity:**
- **Preprocessing:** O(n log n) compares (DFS for tour, then build sparse table with log n levels)
- **Preprocessing reads:** O(n log n) (read each element in the tour log n times to build the table)
- **Preprocessing space:** O(n log n) (the tour is O(n), the table is O(n log n))
- **Per-query reads:** O(log n) (two table lookups for the two positions)
- **Per-query compares:** O(1) (just compare two pre-computed values)

**Why:**
- Euler tour: DFS visits nodes; record the depth at each visit
- The LCA of u and v is the node at the minimum depth between the first visit to u and the first visit to v (in Euler order)
- RMQ (range minimum query) sparse table: ST[i][k] precomputes the min in every range of size 2^k starting at i
- Query: find the two positions, query the overlapping ranges, answer in O(1)

**Wins on:**
- **Many queries and high CPU cost:** O(1) per-query time is unbeatable

**Loses on:**
- **SSD:** O(n log n) space is expensive (extra_space penalty); reads are scattered
- **One-shot query:** preprocessing dominates

---

### fcb (Farach-Colton & Bender): O(n) preprocessing, O(1) query, clever

```
preprocessing:
    1. Euler tour + depths (like sparse_table)
    2. divide into blocks of size B = log(n)/2
    3. RMQ sparse table over block minima (O(n/B) blocks)
    4. precompute in-block RMQ for each block signature
       (±1 pattern: at each step, depth goes up or down by 1)
query(u, v):
    1. positions in Euler tour
    2. if both in same block: lookup in-block table
    3. otherwise: query block minima table + in-block tables at boundaries
```

**Complexity:**
- **Preprocessing:** O(n) total (Euler tour O(n), block minima table O(n/B log(n/B)) = O(n), in-block tables: O(B²) per signature, but there are only 2^B signatures and each ±1 block has sum O(B²) precomputation, total O(n))
- **Space:** O(n) (Euler tour O(n), sparse table O(n/B log(n/B)) = O(n), in-block tables O(n) total)
- **Per-query reads:** O(1) (at most 3 table lookups, all O(1) size)
- **Per-query compares:** O(1)

**Why:**
- The trick: ±1 constraint on Euler tour (depth changes by 1 at each step)
- For each ±1 pattern (signature), precompute the answer for every in-block query
- Only 2^(log n / 2) ≈ sqrt(n) distinct ±1 patterns, so precomputation is O(n log n) but amortized to O(n)
- Query reduces to at most 3 small table lookups

**Wins on:**
- **Many queries with tight memory:** O(n) space is tight; O(1) query time is best

**Loses on:**
- **One-shot query:** O(n log n) preprocessing overhead (even though it's O(n) in theory, practice is slower)

---

## Sorted Search

Given a sorted array of n elements and a query element x, return true if x is in the array.

### linear: O(n) reads, purely sequential

```
for each element in the array:
    compare with x
    if found, return true
```

**Complexity:**
- **Reads:** O(n) in the worst case (scan the whole array)
- **Compares:** O(n)
- **Seeks:** O(n) (each element might be far from the last, depending on layout)

**Why:**
- Simple linear scan; worst case is when the element is not in the array or is at the end

**Wins on:**
- Nothing in this benchmark (binary search and others are strictly better)

---

### binary: O(log n) reads, but random access

```
search for x in array[lo..hi]:
    mid = (lo + hi) / 2
    if array[mid] == x: found
    if array[mid] < x: search array[mid+1..hi]
    else: search array[lo..mid-1]
```

**Complexity:**
- **Reads:** O(log n) (each step cuts the search space in half)
- **Compares:** O(log n)
- **Seeks:** O(log n) (each probe is a random location, typically far from the last)

**Why:**
- Each mid calculation is at a new, unpredictable address
- log n probes mean log n seeks

**Wins on:**
- Nothing (eytzinger beats it on every machine)

---

### eytzinger: O(log n) reads, cache-friendly layout

```
Layout array in breadth-first order (BFS tree layout):
    array[1] = root
    array[2i] = left child of array[i]
    array[2i+1] = right child of array[i]
Search by following parent/child pointers in this layout
```

**Complexity:**
- **Reads:** O(log n)
- **Compares:** O(log n)
- **Seeks:** O(log n) (like binary search, but the BFS layout clusters nodes near each other in memory)

**Why:**
- Breadth-first tree layout puts all nodes at depth d close together in the array
- When you probe a node and its children, they're likely to be in the same cache line or disk block
- One seek takes you to the root and its two children (three cache-friendly probes)

**Wins on:**
- **RAM/Network/Parallel:** seeks are the same count as binary, but reads are clustered, so the effective cost is lower

**Loses on:**
- **HDD:** fixed seek cost per probe defeats the clustering advantage
- **Tape:** still needs random access

---

### b_tree: O(log_B n) seeks, each seek followed by B sequential reads

```
Multi-level tree with fan-out B:
    inner nodes store B separators
    leaves store B elements
Search: find which child to descend into (compare against B separators),
    then sequentially read B elements at that level
```

**Complexity:**
- **Seeks:** O(log_B n) (tree height)
- **Reads:** O(log_B n * B) = O((log n) / (log B)) (each of log_B n levels reads B elements sequentially)
- **Compares:** O(log B) per level (binary search within the B separators)

**Why:**
- For disk access, you pay a fixed seek cost but then can read sequentially for cheap
- Reading B elements sequentially after one seek amortizes the seek cost
- With B = 64 (typical SSD block size), a 20 MB array needs only 2-3 seeks to search

**Wins on:**
- **HDD:** fixed seek cost makes fewer seeks worth the sequential block reads
- **Tape:** definitely beats binary search because of fewer seeks

**Loses on:**
- **RAM:** the indirection and B-way search on comparisons is slower than binary's tight inner loop

---

## Distributed Median

Given n elements split across k machines, find the median. We count message-passing complexity.

### gather_all: Send all data to one machine, sort, find median

```
coordinator broadcasts a request
each machine sends all its data
coordinator sorts and finds median
```

**Complexity:**
- **Messages:** k (one message per node to coordinator)
- **Items sent:** n (every element is transmitted once)

**Why:**
- Straightforward: ship all the data and solve locally

**Wins on:**
- **High latency, low bandwidth:** transmit_msg >> transmit_item (e.g., network = 1000 per message, 10 per item; 300k items = 300M cost but 16 messages = 16k cost, so gather wins only when latency is cheap relative to bandwidth)
- Actually, gather wins on the "network" machine (high latency) because 1 message of 20k items costs 20k + 20k messages = 1M, while value_bisect costs 10+ rounds of 16 messages = lots of rounds

**Loses on:**
- **Metered bandwidth:** pay 100 per item; 20k items = 2M, which is expensive

---

### value_bisect: Binary search on the value range

```
lo, hi = min_value, max_value
while lo < hi:
    mid = (lo + hi) / 2
    coordinator broadcasts mid
    each machine counts how many elements <= mid
    coordinator collects counts
    if total <= position: lo = mid + 1
    else: hi = mid
```

**Complexity:**
- **Rounds:** O(log U) where U is the value range
- **Messages per round:** k+1 (broadcast pivot, then k counts back)
- **Items per round:** k (just one count per machine)
- **Total messages:** O(k log U)
- **Total items:** O(k log U)

**Why:**
- Pivot binary search: narrow the value range until you have the exact median value
- Each round, one machine sends one count (a single number), not a whole dataset
- Only O(log U) rounds needed because the value range shrinks exponentially

**Wins on:**
- **Metered bandwidth:** items sent is low (just counts), so pay O(k log U) per item
- **All machines except high-latency network:** the low item count beats gather_all

**Loses on:**
- **High-latency network:** O(k log U) messages at 1000 cost each is expensive

---

### sample_then_bisect: Take a sample first, then bisect

```
preprocessing:
    each machine sends a small sample (every B-th element) to coordinator
    coordinator estimates the median range from the sample
main:
    coordinator broadcasts the narrowed range
    machines count again to verify the range is correct
    coordinator binary searches within the range
```

**Complexity:**
- **Messages:** k (sample) + O(log range) rounds (verify + bisect)
- **Items:** k * (n/k / B) (sample size) + O(k log U) (bisect)

**Why:**
- Sampling narrows the search space before bisecting
- Instead of bisecting on the full value range [0, U], you bisect on a smaller range [lo, hi] determined by the sample

**Wins on:**
- Nothing in the benchmark; value_bisect is usually better because the sample overhead isn't worth it

---

## List Reversal

Given a doubly linked list, reverse it in-place. We count pointer changes (re-linking), writes, and per-traversal overhead.

### relink: Classic in-place reversal

```
for each node:
    swap prev and next pointers
after: swap head and tail
```

**Complexity:**
- **Pointer changes:** 2n (every node's prev and next are swapped)
- **Space:** O(1)
- **Reads:** 0 (don't need to read values)
- **Writes:** 0 (don't change values, only pointers)

**Why:**
- Each pointer is changed once
- After reversal, next points to the previous node

**Wins on:**
- **Pointer-heavy machine:** pointer_change cost dominates; 2n changes is unavoidable
- **SSD/HDD/Tape:** writes are expensive, so avoiding them wins

**Loses on:**
- **Persistent store where relinking is expensive:** pointer_change=200 makes 2n changes very costly

---

### swap_payloads: Walk from both ends, swap values

```
a = head, b = tail
while a != b and a.prev != b:
    swap a.value and b.value
    a = a.next
    b = b.prev
```

**Complexity:**
- **Pointer changes:** 0 (never re-link, only follow existing pointers)
- **Writes:** n/2 to n (write values when swapping; we count this as 2 writes per swap)
- **Reads:** n/2 to n (read values when swapping)

**Why:**
- No pointers are changed; we only read and write values
- Trade off pointer-changing for value-swapping

**Wins on:**
- **RAM:** reads and writes are cheap; pointer changes don't exist
- **Pointer-heavy store with expensive writes:** no pointer changes, but writes are paid; if write < pointer_change, this wins

**Loses on:**
- **SSD/HDD/Tape:** writes are very expensive (100-1000x pointer changes)

---

### flip_direction: Store a "reversed" flag, swap head/tail

```
reverse:
    swap head and tail
    flip reversed_flag
traversal:
    if reversed_flag: go backwards (follow prev instead of next)
    else: go forwards
```

**Complexity:**
- **Pointer changes:** 2 (swap head and tail pointers, done)
- **Space:** O(1) (just one boolean flag)
- **Per-traversal overhead:** one extra compare per step (check the flag)
- **Reads:** 0 during reversal

**Why:**
- Defers the cost of reversal to future traversals
- Each traversal pays one extra compare per node
- If you reverse but never traverse, you win. If you traverse many times, you lose.

**Wins on:**
- **Pointer-heavy store:** only 2 pointer changes beats 2n of relink

**Loses on:**
- **Most machines:** per-traversal cost of a compare per node adds up (3 traversals means n/2 compares, which is n/2 costs; might exceed the cost of swapping)

---

## Summary Table: Why Each Algorithm Wins

| Problem | Algorithm | Wins On | Why |
|---|---|---|---|
| **sort** | selection | SSD, HDD | O(n) writes beats other sorts' O(n log n) |
| | merge | RAM, tape | O(n log n) compares, purely sequential |
| | heap | tiny_mem | O(1) extra space |
| | bitonic | parallel | O(log² n) depth on 1024 cores |
| | insertion | tape (edge case) | Small problem size, few seeks per element |
| **lca** | naive | one_query, most machines | No preprocessing cost |
| | binary_lift | few machines | Middle ground: some preprocessing, ok queries |
| | sparse_table | many_queries (many bytes) | O(1) queries but high space |
| | fcb | many_queries, pointer, HDD | O(n) preprocessing, O(1) queries, tight space |
| **search** | eytzinger | RAM, network, parallel | Cache-friendly layout, same seek count as binary |
| | b_tree | HDD, tape | Amortizes fixed seek cost with sequential reads |
| **median** | gather_all | network (high latency) | Few messages beat many messages, even with n items |
| | value_bisect | most machines | Low item count, few messages |
| **reverse** | relink | SSD, HDD, tape | 0 writes beats swapping values |
| | swap_payloads | RAM, parallel, network | 0 pointer changes, writes are cheap |
| | flip_direction | pointer | Only 2 pointer changes, future cost amortized |
