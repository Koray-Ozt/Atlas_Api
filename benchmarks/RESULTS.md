# Index benchmark

- Documents: 200,000 (5,000 customers, fixed random seed)
- Query: `find(filter).sort(created_at desc, _id desc).limit(20)`, 30 timed runs after 3 warm-up runs
- MongoDB 9.0.4, pymongo 4.19.0, Python 3.12.0, Windows AMD64
- Measured: 2026-11-03 01:15 UTC

| Query | Indexes | Median | p95 | Docs examined | Keys examined |
|---|---|---:|---:|---:|---:|
| Customer's recent orders | none | 81.13 ms | 94.84 ms | 200,000 | 0 |
| Customer's recent orders | compound | 0.66 ms | 1.23 ms | 20 | 20 |
| | **speed-up (median)** | **122x** | | | |
| Newest `pending` orders | none | 101.92 ms | 132.24 ms | 200,000 | 0 |
| Newest `pending` orders | compound | 0.59 ms | 1.00 ms | 20 | 20 |
| | **speed-up (median)** | **172x** | | | |
