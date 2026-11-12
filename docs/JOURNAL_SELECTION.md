# Where to send the manuscript next

Written 2026-11-12, after three rejections (see
[`REJECTION_ANALYSIS.md`](REJECTION_ANALYSIS.md)). This note says how each candidate
journal was checked, what could not be checked, and which one is recommended.

**How the journals were checked, and the limit of that check.** The journals' own pages
could not be opened from the build environment: `www.sciencedirect.com`,
`www.computer.org` and `petsymposium.org` are outside the session's allowed network
(DNS failure). Everything below marked *summary* is a web-search summary of those pages
or of third-party aggregators, not a reading. Impact factors differ between aggregators;
the figure given is the one a publisher page or two sources agreed on. **Before
submitting, open the journal's own Guide for Authors and confirm the scope sentence, the
length rules and the fee.**

## Search log

```
Query: "Journal of Information Security and Applications" aims and scope, topics, metrics   Date: 2026-11-12
Opened: none (search summaries of the ScienceDirect journal, insights and guide pages)
Blocked: www.sciencedirect.com (aims-and-scope page, guide for authors)
Stopped: no
Conclusion: scope is original research and practice-driven applications in information security;
            listed topics include authentication and access control, anonymity and privacy, and
            cryptography; purely mathematical work without a demonstrated application is not
            considered; single anonymized review; Impact Factor 3.7, CiteScore 10.0; open access
            optional (USD 2,970).
```

```
Query: Computers & Security aims and scope, cryptography   Date: 2026-11-12
Opened: none (search summary of the Elsevier listing)
Blocked: www.sciencedirect.com
Stopped: no
Conclusion: the listing says the journal's scope has excluded cryptology since 2006. Not a target.
```

```
Query: IEEE TDSC / IEEE TCC / IEEE TSC / IEEE TIFS scope, page limits, metrics   Date: 2026-11-12
Opened: none (search summaries of IEEE Computer Society author pages and aggregators)
Blocked: www.computer.org (TDSC author information)
Stopped: no
Conclusion: Computer Society Transactions: regular papers 12 two-column pages including references
            and biographies, USD 220 per page beyond that, appendices as supplemental material.
            Impact factors: TDSC 7.5, TCC 5.3, TSC 5.8, TIFS 8 (aggregators; TCC also on its own page).
```

```
Query: PoPETs 2027 call for papers   Date: 2026-11-12
Opened: none (search summary of petsymposium.org/cfp27.php)
Blocked: petsymposium.org
Stopped: no
Conclusion: deadlines 30 Nov 2026 and 28 Feb 2027; 12-page main body; mandatory open-science and
            AI-use sections; no fee. Indexing and impact factor were not found.
```

```
Query: Journal of Network and Computer Applications metrics; Journal of Systems Architecture scope   Date: 2026-11-12
Opened: none (aggregators)
Blocked: www.sciencedirect.com
Stopped: no
Conclusion: JNCA Impact Factor 8.0 (JCR, Q1), about 120 days to a first decision (aggregator).
            JSA's stated scope is embedded systems and architecture; security is not a core aim.
```

One more piece of evidence is `read-directly`: the papers closest to CR-SHE that were
read on 2026-10-26 (Splinter, DORY, Boyle–Gilboa–Ishai, ARQ, PVODTE, Obscure, Hafiz et
al., HADES; `docs/NOVELTY_SEARCH.md`) appeared, in that order, in NSDI, OSDI, ACM CCS, PoPETs,
IEEE TDSC, PVLDB and IEEE TKDE, NDSS, and PVLDB. None of them appeared in an Internet of Things or
general networking journal. PVODTE, the closest precursor of the tamper check, is in IEEE
TDSC 23(4), 2026.

## What the manuscript is

An applied-cryptography systems paper: a protocol built from distributed point functions
and lattice-based homomorphic encryption, with security proofs, a reference
implementation and measurements on two public IoT datasets. The IoT part is the
application and the datasets. The contribution is a security protocol for outsourced
data. A journal whose editors and reviewers work on security and applied cryptography
will judge it on its own terms; an IoT or networking journal sees one more "searchable
encryption for IoT" title, which is how two of the three rejections read.

## Candidates

| Journal | Scope fit | Metrics (*summary*) | Length and format | Cost | Assessment |
|---|---|---|---|---|---|
| **Journal of Information Security and Applications** (Elsevier) | **Direct.** Cryptography, privacy and access control with a demonstrated application | IF 3.7, CiteScore 10.0; Scopus Q1 (aggregators); JCR Q2 in 2023 (Peeref) | Elsevier format, Word or LaTeX, single anonymized. The existing Word pipeline applies unchanged | None (subscription); open access optional | **Recommended.** Best match between what the paper is and what the journal says it wants |
| **IEEE Transactions on Dependable and Secure Computing** | **Direct.** PVODTE appeared here | IF 7.5, JCR Q1 | 12 two-column pages, IEEE template, proofs as supplemental material | USD 220 per page over 12 | **Reach.** Right readership, but expect requests for a native implementation and a wide-area deployment |
| **IEEE Transactions on Cloud Computing** | Good: cloud storage, security and privacy | IF 5.3, Scopus Q1 | As above | As above | **Alternative** if a JCR Q1 IEEE Transactions is required; same evaluation risk as TDSC, somewhat lower bar |
| IEEE Transactions on Services Computing | Fair | IF 5.8 | As above | As above | Possible; weaker fit than TCC |
| IEEE Transactions on Information Forensics and Security | Good | IF 8 | IEEE | Page charges | Higher bar than TDSC for the cryptography; not advised |
| **Journal of Network and Computer Applications** (Elsevier) | Partial: networked applications, cloud, IoT | IF 8.0, JCR Q1 | Package already built (`paper/jnca/submission/`) | None | **Risky.** Same profile as the two journals that desk-rejected: broad, high volume, IoT/network editors |
| PoPETs | **Direct** (ARQ appeared here) | Not a JCR journal; indexing not confirmed | 12 pages, double-blind, open-science section | None | Right community, but it expects a public artefact, and the authors do not want to publish the code yet |
| Computers & Security | **Out of scope** (cryptology excluded) | | | | Do not submit |
| Journal of Systems Architecture | Weak | IF 4.1, Q1 | Elsevier | None | Not advised |
| IEEE IoT Journal, FGCS, Internet of Things | Already rejected | | | | FGCS said it will not reconsider |

Not checked in this round, named from general knowledge only: *International Journal of
Information Security* (Springer) and *Cluster Computing* (Springer) as lower-tier
fallbacks; *Journal of Cloud Computing* (open access, fee).

## Recommendation

1. **Submit to the Journal of Information Security and Applications.** Its stated scope
   names cryptography, privacy and access control and asks for a practical application,
   which is the shape of this paper. It charges nothing, takes Word, and uses the Elsevier
   format the package is already in. It is Q1 in Scopus; if the authors' institution
   counts only JCR quartiles, note that the 2023 JCR quartile found was Q2.
2. **If a JCR Q1 title is required, choose IEEE TDSC or IEEE TCC** and accept a longer
   review and a likely major revision asking for more evaluation. The manuscript then has
   to be reset in the IEEE two-column template and cut to about 12 pages, with the proofs
   as supplemental material.
3. **Do not send it to another IoT or general networking journal first.** The JNCA
   package stays in the repository and can still be used, but the three decisions so far
   point away from that kind of venue.

These are judgements about fit, not predictions of acceptance. No journal's acceptance
rate was found in a source that could be opened.

## What changed in the manuscript for this target

See `docs/REJECTION_ANALYSIS.md` (section "Third round") and
`docs/JISA_SUBMISSION.md`.
