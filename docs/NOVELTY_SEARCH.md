# Prior-art search for the v3 contributions

Searches run on 2026-10-25 for the two contributions added after the desk
rejection at *Internet of Things* (IOT-D-26-03923, "lack of sufficient novelty"):
oblivious range aggregation over data cubes, and the bit-packed masked index.

**The search was limited, and this note says how.** No paper was read in full. The
proxy refused arXiv, IACR ePrint, NDSS, VLDB, PETS, ScienceDirect and elsevier.com
(HTTP 403 / DNS failure for both WebFetch and curl). Everything below is
`search-summary` (a web search engine's summary) or `abstract-only` (an abstract
returned by the Consensus index). By the project's research-integrity rules,
neither counts as a reading, and no novelty claim follows from not finding
something.

## Query log

```
Query: "private information retrieval prefix sums range aggregate query multi-server"   Date: 2026-10-25
Opened: none (search-summary only)
Blocked: arxiv.org/pdf/2403.13296, ndss-symposium.org (Hafiz et al.); vldb.org, eprint.iacr.org/2024/1699 (HADES)
Stopped: no
Conclusion: summaries point to Hafiz et al. (NDSS 2024, IT-PIR aggregates) and HADES (single-server FHE, range-filtered aggregation on public data); no summary mentions a prefix-sum construction.
```

```
Query: "distributed point function range query aggregate encrypted data homomorphic encryption non-colluding servers"   Date: 2026-10-25
Opened: none (search-summary only)
Blocked: eprint.iacr.org (HADES), petsymposium.org (ARQ, PoPETs 2022)
Stopped: no
Conclusion: summaries name HADES and ARQ (structured-encryption range aggregates, single server); none combines DPFs, HE and non-colluding servers.
```

```
Query: "function secret sharing interval \"distributed comparison function\" private range sum time series aggregation"   Date: 2026-10-25
Opened: none (search-summary only)
Blocked: eprint.iacr.org (Boyle-Gilboa-Ishai FSS improvements; streaming FSS 2025/2304)
Stopped: no
Conclusion: DCF/interval FSS for private range search is known (Boyle-Gilboa-Ishai); no summary describes range aggregation over owner-encrypted data.
```

```
Query (Consensus): "private range sum query cumulative prefix sum table private information retrieval"   Date: 2026-10-25
Opened: abstracts of PRISM (ICDE 2022), Hayata et al. (IJIS 2020), Demertzis et al. (TODS 2018), Tillem et al. (2016), Youssef et al. (2026)
Blocked: full texts (proxy)
Stopped: no (two parallel Consensus queries were rate-limited and returned nothing; not re-run)
Conclusion: prefix sums for range queries appear under local differential privacy (PRISM) and SSE range aggregates (Demertzis et al., single server, with leakage); Hayata et al. give FSS-based PIR for range retrieval.
```

```
Query (Consensus): "Hafiz private aggregate queries untrusted databases multi-server IT-PIR"   Date: 2026-10-25
Opened: abstract of Hafiz et al., "Private Aggregate Queries to Untrusted Databases" (arXiv 2024 / NDSS 2024)
Blocked: full text (proxy)
Stopped: no
Conclusion: single-round aggregate queries over IT-PIR, hiding which records contribute; the abstract describes a database the PIR servers host, and says nothing on ranges or data confidentiality.
```

## Closest prior work, and the stated difference

| Work | What it does (how known) | Difference claimed for CR-SHE (bounded) |
|---|---|---|
| Hafiz et al., NDSS 2024 | Single-round aggregate queries via IT-PIR; servers host the database (`abstract-only`) | Owner-encrypted data the servers cannot read; t = n−1; multi-dimensional box aggregates. Whether their framework supports ranges is **not known**, since the full text was not read |
| HADES, VLDB 2025 | Single-server FHE range-filtered aggregation on public data (`search-summary`) | Two or more servers, data encrypted, symmetric-key selection; no FHE comparison |
| ARQ, PoPETs 2022; Demertzis et al., TODS 2018 | Range aggregates over encrypted data, single server, structured/searchable encryption with leakage (`search-summary` / `abstract-only`) | No access-pattern or result-size leakage to a coalition of n−1 |
| Hayata et al., IJIS 2020 | FSS-based PIR for range *retrieval*, constant rounds (`abstract-only`) | Aggregation without returning records; one round; data encrypted |
| Splinter, NSDI 2017 | FSS queries with SUM/COUNT on public data (cited in the manuscript; not re-read here) | Data encrypted at rest under the owner's key |
| Prefix-sum data cubes (OLAP), PRISM (ICDE 2022) | Range sums from constant numbers of prefix sums (`abstract-only` for PRISM) | We use the classical structure; the contribution is composing it with oblivious homomorphic aggregation, not the structure |

## What may be said in the manuscript

> Searches of web indexes and the Consensus paper index found no earlier
> description of multi-dimensional range aggregation over owner-encrypted,
> replicated data that hides the range from a coalition of n−1 non-interacting
> providers. The full texts of the closest works (Hafiz et al., HADES, ARQ, and
> Hayata et al.) could not be opened, so this is not a claim of priority.

Do not write "first" or "novel" without this qualification. The prefix-sum (summed-area)
structure itself is old and must be credited. Bit-packing the masked index is an
engineering optimisation, not a research contribution.

## Before submission

Open and read the full texts of Hafiz et al. (NDSS 2024), HADES (VLDB 2025),
ARQ (PoPETs 2022) and Hayata et al. (IJIS 2020) from a network that can reach them.
Then update the table above. If any of them already does box aggregation over
encrypted data at t = n−1 without interaction, the range contribution must be
re-scoped.
