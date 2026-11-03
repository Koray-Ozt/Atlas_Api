"""Measure what the indexes in app/db.py buy us.

Seeds a throwaway database, then runs the two list queries the API serves most
(a customer's recent orders, and the newest orders in a status) with and without
indexes, reporting latency and how many documents MongoDB had to examine.

    python -m scripts.benchmark --docs 200000 --runs 30 --output benchmarks/RESULTS.md
"""

import argparse
import platform
import random
import statistics
import time
from datetime import UTC, datetime, timedelta

from pymongo import MongoClient

from app.config import Settings
from app.db import ORDER_INDEXES
from app.orders.repository import LIST_SORT

STATUSES = ["pending", "paid", "shipped", "cancelled"]
STATUS_WEIGHTS = [0.10, 0.25, 0.55, 0.10]
CUSTOMERS = 5_000
PAGE_SIZE = 20


def seed(collection, docs: int) -> None:
    rng = random.Random(42)  # fixed seed: every run benchmarks the same data
    start = datetime(2025, 1, 1, tzinfo=UTC)
    batch = []
    for i in range(docs):
        qty, price = rng.randint(1, 5), rng.randint(100, 20_000)
        created = start + timedelta(seconds=i * 150)
        batch.append(
            {
                "customer_email": f"customer{rng.randrange(CUSTOMERS)}@example.com",
                "items": [
                    {"sku": f"SKU-{rng.randrange(500)}", "quantity": qty, "unit_price_cents": price}
                ],
                "status": rng.choices(STATUSES, STATUS_WEIGHTS)[0],
                "total_cents": qty * price,
                "created_at": created,
                "updated_at": created,
            }
        )
        if len(batch) == 10_000:
            collection.insert_many(batch)
            batch = []
    if batch:
        collection.insert_many(batch)


def measure(collection, query: dict, runs: int) -> dict:
    def run():
        return list(collection.find(query).sort(LIST_SORT).limit(PAGE_SIZE))

    for _ in range(3):  # warm-up
        run()
    timings = []
    for _ in range(runs):
        t0 = time.perf_counter()
        run()
        timings.append((time.perf_counter() - t0) * 1000)
    stats = collection.find(query).sort(LIST_SORT).limit(PAGE_SIZE).explain()["executionStats"]
    timings.sort()
    return {
        "median_ms": statistics.median(timings),
        "p95_ms": timings[max(0, round(0.95 * len(timings)) - 1)],
        "docs_examined": stats["totalDocsExamined"],
        "keys_examined": stats["totalKeysExamined"],
    }


def render(info: dict, rows: list[tuple[str, dict, dict]]) -> str:
    lines = [
        "# Index benchmark",
        "",
        f"- Documents: {info['docs']:,} ({CUSTOMERS:,} customers, fixed random seed)",
        f"- Query: `find(filter).sort(created_at desc, _id desc).limit({PAGE_SIZE})`, "
        f"{info['runs']} timed runs after 3 warm-up runs",
        f"- MongoDB {info['mongo']}, pymongo {info['pymongo']}, "
        f"Python {platform.python_version()}, {platform.system()} {platform.machine()}",
        f"- Measured: {datetime.now(UTC):%Y-%m-%d %H:%M UTC}",
        "",
        "| Query | Indexes | Median | p95 | Docs examined | Keys examined |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name, without, with_ in rows:
        for label, r in (("none", without), ("compound", with_)):
            lines.append(
                f"| {name} | {label} | {r['median_ms']:.2f} ms | {r['p95_ms']:.2f} ms "
                f"| {r['docs_examined']:,} | {r['keys_examined']:,} |"
            )
        speedup = without["median_ms"] / with_["median_ms"]
        lines.append(f"| | **speed-up (median)** | **{speedup:.0f}x** | | | |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--docs", type=int, default=200_000)
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--output", help="also write the markdown report to this file")
    args = parser.parse_args()

    settings = Settings()
    client = MongoClient(settings.mongo_uri, tz_aware=True)
    db_name = "atlas_benchmark"
    collection = client[db_name]["orders"]
    try:
        client.drop_database(db_name)
        print(f"Seeding {args.docs:,} orders...")
        seed(collection, args.docs)

        queries = [
            ("Customer's recent orders", {"customer_email": "customer42@example.com"}),
            ("Newest `pending` orders", {"status": "pending"}),
        ]
        without = [measure(collection, q, args.runs) for _, q in queries]
        collection.create_indexes(ORDER_INDEXES)
        with_ = [measure(collection, q, args.runs) for _, q in queries]

        info = {
            "docs": args.docs,
            "runs": args.runs,
            "mongo": client.server_info()["version"],
            "pymongo": __import__("pymongo").version,
        }
        names = [name for name, _ in queries]
        report = render(info, list(zip(names, without, with_, strict=True)))
        print(report)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(report)
    finally:
        client.drop_database(db_name)
        client.close()


if __name__ == "__main__":
    main()
