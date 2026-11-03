"""MongoDB index definitions.

Both indexes end with `_id` because list queries sort by (created_at desc, _id desc):
the `_id` tie-breaker keeps pagination stable and lets MongoDB return the sort order
straight from the index instead of sorting in memory.
"""

from pymongo import ASCENDING, DESCENDING, IndexModel

ORDER_INDEXES = [
    IndexModel(
        [("customer_email", ASCENDING), ("created_at", DESCENDING), ("_id", DESCENDING)],
        name="customer_email_created_at",
    ),
    IndexModel(
        [("status", ASCENDING), ("created_at", DESCENDING), ("_id", DESCENDING)],
        name="status_created_at",
    ),
]
