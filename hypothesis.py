"""
hypothesis.py -- the "world" an algorithm is deployed into.

Classic analysis only counts abstract steps (time) and cells (space). Real
machines charge very differently for different things:

  * a tape charges by how far the head moves (seek distance)
  * a hard disk charges a big constant for any non-sequential access
  * an SSD reads cheaply but writes are expensive and wear the device out
  * RAM is roughly uniform, but cache misses still punish random access
  * a network charges per message (latency) and per byte (bandwidth)
  * a CPU with P cores rewards algorithms with low *depth* (span)
  * some structures (on-disk linked lists, persistent memory, DB rows with
    foreign keys) make *changing an address / pointer* the costly operation

Every algorithm in this repo runs against an instrumented `Meter`. The meter
counts raw events; a `Machine` turns those counts into a single cost by
weighting them. Changing the Machine changes which algorithm "wins" -- that is
the whole point of the repo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Storage(Enum):
    RAM = "ram"
    SSD = "ssd"
    HDD = "hdd"
    TAPE = "tape"


@dataclass(frozen=True)
class Machine:
    """Weights for each kind of event. All costs are in arbitrary 'units'."""

    name: str
    storage: Storage = Storage.RAM
    compare: float = 1.0          # one CPU comparison / arithmetic step
    read: float = 1.0             # read one cell
    write: float = 1.0            # write one cell
    seek_fixed: float = 0.0       # paid on every non-sequential access (HDD)
    seek_per_cell: float = 0.0    # paid per cell of head movement (TAPE)
    transmit_msg: float = 0.0     # per message sent between nodes (latency)
    transmit_item: float = 0.0    # per item carried in a message (bandwidth)
    pointer_change: float = 1.0   # re-linking / changing an address
    cores: int = 1                # how many operations can run in one parallel round
    extra_space: float = 0.0      # penalty per cell of auxiliary memory used
    preprocess_weight: float = 1.0  # how much we care about one-off setup cost
    queries: int = 1              # how many queries amortise the setup

    def describe(self) -> str:
        return f"{self.name} ({self.storage.value}, {self.cores} cores)"


# --------------------------------------------------------------------------
# Preset hypotheses about the deployment environment.
# --------------------------------------------------------------------------
HYPOTHESES: dict[str, Machine] = {
    "ram": Machine("RAM workstation"),
    "ssd": Machine("SSD, write-limited", Storage.SSD, read=2, write=400),
    "hdd": Machine("Spinning disk", Storage.HDD, read=1, write=1, seek_fixed=500),
    "tape": Machine("Tape drive", Storage.TAPE, read=1, write=1, seek_per_cell=5),
    "network": Machine("Cluster, high latency", transmit_msg=1000, transmit_item=10),
    "metered_bw": Machine("Metered bandwidth link", transmit_msg=10, transmit_item=100),
    "parallel": Machine("1024-core GPU-ish", cores=1024),
    "pointer": Machine("Persistent store, costly relinks", pointer_change=200, write=5),
    "tiny_mem": Machine("Microcontroller, tight RAM", extra_space=50),
    "many_queries": Machine("Query-heavy service", queries=1_000_000, preprocess_weight=1),
    "one_query": Machine("One-shot script", queries=1, preprocess_weight=1),
}


# --------------------------------------------------------------------------
# The meter: algorithms report what they do, never how much it costs.
# --------------------------------------------------------------------------
@dataclass
class Meter:
    compares: int = 0
    reads: int = 0
    writes: int = 0
    seeks: int = 0               # non-sequential accesses
    seek_distance: int = 0       # total head movement
    messages: int = 0
    items_sent: int = 0
    pointer_changes: int = 0
    rounds: int = 0              # parallel depth, if the algorithm reports it
    work_in_rounds: int = 0      # total work done inside reported rounds
    extra_space: int = 0         # peak auxiliary cells
    preprocess: "Meter | None" = None
    _heads: dict = field(default_factory=dict, repr=False)  # device -> head pos

    # --- memory access -----------------------------------------------------
    def _move(self, addr: int, dev: int) -> None:
        head = self._heads.get(dev, 0)
        if addr != head and addr != head + 1:
            self.seeks += 1
        self.seek_distance += abs(addr - head)
        self._heads[dev] = addr

    def reset_heads(self) -> None:
        self._heads.clear()

    def touch_read(self, addr: int, dev: int = 0) -> None:
        self._move(addr, dev)
        self.reads += 1

    def touch_write(self, addr: int, dev: int = 0) -> None:
        self._move(addr, dev)
        self.writes += 1

    def cmp(self, n: int = 1) -> None:
        self.compares += n

    def send(self, items: int) -> None:
        self.messages += 1
        self.items_sent += items

    def relink(self, n: int = 1) -> None:
        self.pointer_changes += n

    def parallel_round(self, work: int) -> None:
        """Report one round of `work` independent operations."""
        self.rounds += 1
        self.work_in_rounds += work

    def space(self, cells: int) -> None:
        self.extra_space = max(self.extra_space, cells)

    # --- pricing -----------------------------------------------------------
    def cost(self, m: Machine) -> float:
        c = (
            self.compares * m.compare
            + self.reads * m.read
            + self.writes * m.write
            + self.seeks * m.seek_fixed
            + self.seek_distance * m.seek_per_cell
            + self.messages * m.transmit_msg
            + self.items_sent * m.transmit_item
            + self.pointer_changes * m.pointer_change
            + self.extra_space * m.extra_space
        )
        if self.rounds:
            # Work inside rounds is executed `cores` at a time (Brent's theorem).
            # Work reported in rounds is charged here, not via `compares`.
            c += max(self.rounds, self.work_in_rounds / m.cores) * m.compare
        return c

    def total_cost(self, m: Machine) -> float:
        """Per-query cost with preprocessing amortised over `m.queries`."""
        q = self.cost(m)
        if self.preprocess is not None:
            q += self.preprocess.cost(m) * m.preprocess_weight / m.queries
        return q


class Tape:
    """A list whose every access is reported to a Meter (address = index).

    `device` identifies the physical medium: two Tapes on different devices
    have independent heads (e.g. two tape drives), on the same device they
    share one head.
    """

    def __init__(self, data, meter: Meter, base: int = 0, device: int = 0):
        self.data = list(data)
        self.m = meter
        self.base = base
        self.dev = device

    def __len__(self):
        return len(self.data)

    def __getitem__(self, i):
        self.m.touch_read(self.base + i, self.dev)
        return self.data[i]

    def __setitem__(self, i, v):
        self.m.touch_write(self.base + i, self.dev)
        self.data[i] = v
