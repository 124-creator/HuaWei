# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Explicit teaching examples; not selected experiment plans or timings."""
from typing import Final

GROUPS: Final = ((0, 1), (2,), (3,), (4, 5))
OP_EDGES: Final = ((0, 1), (1, 2), (1, 3), (2, 4), (3, 4), (4, 5))
TASK_EDGES: Final = ((0, 1), (0, 2), (1, 3), (2, 3))
LEGAL_QUEUES: Final = ((0, 3), (1, 2))
CYCLIC_QUEUES: Final = ((3, 0), (1, 2))
BEFORE: Final = ("A1", "B1", "A2", "B2", "A3", "B3", "A4", "B4")
AFTER: Final = ("A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4")
FIFO_STATES: Final = (("A", "B", "C", "D"), ("B", "C", "D", "E"), ("C", "D", "E", "A"))
