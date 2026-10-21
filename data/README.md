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
| beijing | 35,162 | 420,370 | 4,624,070 | 12 / 131.5 / 102,344 |

If the counts differ, the band edges or NA handling differ from the C++ corpus builder,
so reconcile them before quoting any result.

These files could not be fetched from the environment that produced the reference
results in `results/`: the proxy blocked kaggle.com and archive.ics.uci.edu. That is why
the leakage experiments with padded and volume-hiding baselines have not been run yet.
