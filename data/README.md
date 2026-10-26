# Datasets

The raw files are public but not redistributed here. Put them under `data/raw/`
(ignored by git):

| Corpus | Source | Expected layout |
|---|---|---|
| Environmental Sensor Telemetry (Stafford, 2020), 405,184 rows, 3 devices | Kaggle, "Environmental Sensor Telemetry Data" (`iot_telemetry_data.csv`) | `data/raw/iot_telemetry_data.csv` |
| Beijing Multi-Site Air-Quality (Zhang et al., 2017), 420,768 rows, 12 sites | UCI ML Repository, dataset 501 | `data/raw/beijing/PRSA_Data_*_20130301-20170228.csv` (12 files) |

The loaders in `crshe/corpus.py` rebuild the tag universe that the manuscript
describes. When the rebuild is right, `python bench/corpus_stats.py` should report:

| | N (tags) | N_d (records) | postings | median / mean / max posting length |
|---|---:|---:|---:|---|
| telemetry | 11,580 | 405,184 | 3,646,656 | 35 / 314.9 / 404,702 |
| beijing | 35,162 | 420,370 | 4,624,070 | 12 / 131.5 / 102,344 (C++ builder); **98,878** (this loader) |

N, N_d and the posting total hold for any band rule (every record gets one tag per family),
so matching them does not show that the band edges agree. The maximum posting length and the
largest single-tag aggregate do: on the first real run (2026-10-26) the telemetry corpus matched
the C++ builder on both, while Beijing gave a maximum of 98,878 against 102,344 and a largest
aggregate of 676,076,034 against 698,963,226. The two builders therefore assign some Beijing band
edges differently; `bench/dump_lengths.py` writes per-tag lengths so they can be compared tag by
tag. `scripts/run_server_experiments.sh` now checks all five values.

These files cannot be fetched from the environment that produced the synthetic-data results
in `results/` (the proxy blocks kaggle.com and archive.ics.uci.edu). The real-corpus results
(`corpus_stats.json`, `correctness_{telemetry,beijing}.json`, `leakage_{telemetry,beijing}.json`,
`range_real_{telemetry,beijing_day}.json`) were produced by the authors on their own server with
`scripts/run_server_experiments.sh`; its logs are in `results/server_logs_20261026/`.
