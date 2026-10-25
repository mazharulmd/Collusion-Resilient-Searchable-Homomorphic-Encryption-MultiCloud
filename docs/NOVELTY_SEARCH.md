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


## Second round (v4), 2026-10-25

Searched for the two mechanisms added in v4 (the session-keyed check and role-scoped access) and,
again, for close work on oblivious aggregation. A retry of arXiv, IACR ePrint, NDSS, PETS,
Semantic Scholar and OpenAlex failed at the proxy for every host (no HTTP response), so everything
below is again `abstract-only` from the Consensus index.

```
Query (Consensus): "verifiable function secret sharing distributed point function malicious server integrity check"   Date: 2026-10-25
Opened: abstracts of de Castro & Polychroniadou (Eurocrypt 2022; ePrint 2021), Boyle-Gilboa-Ishai (CCS 2016), Xu et al. VeHSS (2024, 2025), Choudhuri et al. ve-HSS (2024), Kruglik et al. (2024)
Blocked: full texts (proxy)
Stopped: no (a parallel query on "secret random scaling" was rate-limited and not re-run)
Conclusion: verifiable DPF checks that KEYS are well formed (client-side malice); verifiable HSS checks server evaluation. The BGI16 abstract states FSS for decision trees "towards FSS for multi-dimensional intervals".
```

```
Query (Consensus): "information-theoretic MAC on homomorphic computation result client-chosen key detect malicious cloud aggregation"   Date: 2026-10-25
Opened: abstracts of Gupta et al. "Obscure" (PVLDB 2019), Li et al. PVODTE (TDSC 2026), Bottoni et al. (2025), Li et al. (TSC 2024)
Blocked: full texts (proxy)
Stopped: no
Conclusion: MAC-based verification of non-interactive two-server computation exists (PVODTE, HSS). Obscure gives oblivious, verifiable aggregation over secret-shared data.
```

```
Query (Consensus): "oblivious range aggregation queries over secret-shared outsourced data multiple non-colluding clouds hiding access patterns"   Date: 2026-10-25
Opened: abstracts of Gupta et al. "Obscure" (TKDE 2020), Qiu et al. Doquet (PVLDB 2023), Wang et al. (TIFS 2025), Yang et al. TRQED (TKDE 2022), Chang et al. (TKDE 2021), Zhang et al. BRASP (arXiv 2026), Nie et al. VPRQ (2024)
Blocked: full texts (proxy)
Stopped: no
Conclusion: Obscure (TKDE 2020) states aggregation queries with conjunctive or disjunctive predicates over secret-shared data, hiding access and query patterns, with NO server-to-server communication and optional result verification. This is the closest work found to CR-SHE's keyword and flexible paths. Its collusion threshold and range support are not stated in the abstract.
```

```
Query (Consensus): "private access control lists function secret sharing PACL authorization of hidden queries"   Date: 2026-10-25
Opened: abstracts of Servan-Schreiber et al. PACL (S&P 2023), Abdolmaleki et al. (2025), Ji et al. (ePrint 2023), Kamal et al. (2025)
Blocked: full texts (proxy)
Stopped: no
Conclusion: access control for FSS checks that the key-holder is authorised for the shared function (evaluator-side proof). Ji et al. report the PACL DPF scheme ignored beta and give attribute-based constraints on alpha.
```

### What changes in the manuscript because of this round

* **Obscure** must be cited as the closest work on oblivious, verifiable, non-interactive
  aggregation. CR-SHE's distinction becomes narrower: owner-encrypted replicas (no re-dealing),
  a collusion bound of n−1 (Obscure's threshold unknown to us), and one-round range aggregates
  over registered cubes. The v3 sentence "none of them gives analytics ... without inter-provider
  communication" is withdrawn from every file.
* The **session-keyed check** is an information-theoretic MAC whose key the client picks per
  query and hides in DPF outputs. MAC-based verification of non-interactive multi-server
  computation is known (PVODTE, verifiable HSS). We claim its use here, not the technique.
* **Role-scoped access** restricts which data a query can reach (role-filtered columns and
  role-keyed masks), unlike PACL and Ji et al., which restrict which keys are accepted. We do not
  claim it is new; it costs storage per role and trusts providers to apply the policy.
* "FSS for multi-dimensional intervals" exists (BGI16, abstract): our prefix-sum design is
  one choice among others, not forced.

## Before submission

Open and read the full texts of Hafiz et al. (NDSS 2024), HADES (VLDB 2025),
ARQ (PoPETs 2022), Hayata et al. (IJIS 2020), **Obscure (PVLDB 2019, TKDE 2020)** and
PVODTE (TDSC 2026) from a network that can reach them.
Then update the table above. If any of them already does box aggregation over
encrypted data at t = n−1 without interaction, the range contribution must be
re-scoped.
