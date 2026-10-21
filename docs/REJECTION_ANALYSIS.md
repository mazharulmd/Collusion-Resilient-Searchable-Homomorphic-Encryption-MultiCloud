# FGCS-D-26-05016: why it was rejected, and what the revision changes

**Decision (27 Sep 2026):** reject, no reconsideration. Editor's summary:
*"The research results reported are too premature for publication. More work is
needed to substantiate the conclusions."* The individual reviewer reports were not
available when this was written. Fill them in under
[Reviewer comments](#reviewer-comments) once you have them from Editorial Manager.

This note reads the submitted manuscript (`paper/fgcs-2026-submission/CRSHE_FGCS.tex`)
the way a referee would. It lists what most plausibly led to "premature" and
"conclusions not substantiated", and says what has been fixed in this repository and
what is still the authors' to do.

---

## 1. Technical errors a referee could find

### 1.1 Section 6.2 is wrong: an (n,n)-shared store cannot answer DPF queries locally

The submitted text says: *"If the DO instead dealt an (n,n) additive sharing of each
column A_f over Z_p, every provider could answer a DPF query over its share in the clear,
giving t=n-1 privacy with no homomorphic encryption."* Table 1 lists that design as
supporting oblivious analytics with no server channel.

That is false. With e = Σ_j e_j (DPF shares) and S = Σ_k S_k (data shares), the answer
⟨e, S⟩ = Σ_j Σ_k ⟨e_j, S_k⟩ includes cross terms j ≠ k that no single provider holds.
Each local answer ⟨e_j, S_j⟩ sums to the wrong value. `tests/test_primitives.py::test_nn_shared_store_cannot_answer_locally`
demonstrates this, and `crshe/baselines.py::nn_shared_local_answers` computes what the
local answers actually add up to.

This matters beyond one paragraph. The submission then concedes that the shared design
"is the better design" wherever durability comes from elsewhere. A referee who knows
FSS reads that as the authors not knowing why their own homomorphic layer exists. The
correct statement is stronger: the design requires three things together, namely
(a) t = n-1 collusion, (b) no server-to-server interaction, and (c) data hidden from the
providers. With all three, each provider must answer what amounts to a single-server
PIR query over data it cannot read. That needs a computational, homomorphic-style
primitive (Kushilevitz–Ostrovsky 1997; Di Crescenzo–Malkin–Ostrovsky 2000). So the HE
layer is a necessity, not a durability trade-off.

**Fixed in the revision:** Section 6.2 is rewritten as "Why the homomorphic layer is
necessary", with a proposition and proof for the linear case. Table 1 is corrected.

### 1.2 The general path cannot serve ad-hoc weights, though the paper says it does

The submitted general path cancels the index mask with an encrypted correction column
U_f[x] = Σ_i w_f[i] P[x][i] m_i. The owner must precompute that column for each weight
vector w_f. Yet Section 6.5, the Discussion and Algorithm 2 (`GenAgg ... ad-hoc w_f`) say ad-hoc
weights and conjunctions "fall back to the general path". They cannot. For a registered
w_f, the general path computes exactly what the fast path computes, only more slowly.
For an unregistered one, no correction column exists. Conjunctions are not linear in
the selection vector at all.

**Fixed in the revision:** the general path is replaced by a two-round *flexible
path*:

1. Retrieval. Providers return b_j. The user subtracts the mask row P[α], which it
   derives from K', and obtains S. This step is unchanged.
2. Contraction. The user forms any selection vector it likes (conjunctions,
   disjunctions, ad-hoc weights), v = w ∘ 1_S. It deals fresh additive shares of v (one
   16-byte PRF seed per light provider, one explicit vector) and each provider contracts
   its share against the encrypted record column. The response is one ciphertext.

A coalition of n-1 providers sees uniform shares in round 2, so the security proof
extends by one hybrid. The correction columns U_f and G_f, and the original Remark 1, are no longer
needed. The claim of Remark 3 that "two rounds admit no simulator" holds only when S is
sent in the clear, and the revision says so. Implemented in `crshe/protocol.py`
(`DataUser.deal_selection`, `Provider.contract`) and tested with conjunctions,
disjunctions and ad-hoc weights in `tests/test_protocol.py`.

### 1.3 The fast path was never compared with the obvious single-server alternative

The headline result (39 ms per aggregate) is a two-server PIR query into an
owner-encrypted table A_f. One server holding the same encrypted A_f can answer the same
query with **no non-collusion assumption**. The user sends an encrypted one-hot vector,
and the server contracts ciphertext by ciphertext at the same depth-1 parameters.
The submission notes this alternative in Related Work and dismisses it because it
"forgoes the durability that replication provides". A single-server scheme can be
replicated for durability just as well. The comparison the paper actually ran was
against a homomorphic equality scan (617×), which is a much weaker baseline. A referee
will ask what the non-collusion assumption buys.

**Measured in the revision** (`bench/bench_response.py`, `results/response_and_single_server.json`;
same implementation, same machine, one thread):

| N (tags) | CR-SHE fast path, packed (provider) | single-server (server) | uplink CR-SHE | uplink single-server |
|---:|---:|---:|---:|---:|
| 11,580 | 23.5 ms | 42.6 ms | 260 B | 789,033 B |
| 35,162 | 31.4 ms | 92.5 ms | 294 B | 2,367,099 B |

The honest answer: on the fast path, the trust split buys 1.8–2.9× in server compute,
3,000–8,000× in uplink, and 27–108× in client-side query cost (0.54–0.62 ms of DPF key
generation against 14.6–67.5 ms of query encryption). On retrieval, a single server must
multiply an encrypted N-vector by the N × N_d index: at least ⌈N·N_d/ℓ⌉
plaintext-ciphertext products before any rotation. With the measured per-product cost,
that lower bound is 2.6–3.4× CR-SHE's measured retrieval in the same implementation
(`results/ops_and_retrieval_bound.json`). Both sides are Θ(N·N_d), so this is a
constant factor too, not an asymptotic gap.

So the non-collusion assumption buys a small constant factor in server work and large
factors at the client and on the link. That is a legitimate argument for thin,
metered IoT clients, but it is not the orders-of-magnitude server win the submission
implied. The revised abstract, Related Work, Section 8 and Discussion now say exactly
this. A referee will respect the honest framing far more than discovering the
comparison themselves.

### 1.4 Smaller correctness points

* Theorem 1 (and with it Theorem 3) carried a statistical term N·N_d·2⁻⁶⁴ ≈ 2⁻³¹·⁹ from reducing 64-bit words
  mod p. Rejection sampling removes it exactly. The reference implementation does this
  (`crshe/prg.py::uniform_zp`), and the theorem and proof are tightened to match.
* Remark 2 (per-row MAC keys) was "not implemented or measured". It is now both
  (`bench/bench_mac.py`, `results/mac_detection.json`).

## 2. "Premature": the paper lists its own missing evaluation

The submitted Limitations section and the sections before it say outright that the
following are missing:

| Gap stated in the submission | Status after this revision |
|---|---|
| Response is 2 BFV ciphertexts (526 kB) for one scalar; 8,191 of 8,192 slots unused; "standard reductions we have not applied" | **Done.** Value and MAC share one ciphertext (the two BFV rows), several templates share it in slot segments, and the response is compressed to one RNS tower: **132 kB for four templates**, against 2.1 MB in the submitted layout. Provider time for one template halves. |
| Per-row MAC keys "not implemented or measured" | **Done.** Implemented and measured; catches the consistent linear substitution that the global MAC misses. |
| Statistical term in Theorem 1 | **Done** (rejection sampling). |
| No comparison with a padded / volume-hiding index | **Code ready, run pending.** `crshe/attack.py` adds both baselines. It needs the two corpora, which this environment could not download (see `data/README.md`). |
| Single-host deployment only; no wide-area latency | **Authors.** Needs providers in distinct cloud regions. Provider compute and response size are now smaller, and they determine most of the WAN cost. |
| n > 2 uses a non-succinct sharing (heavy key 8N bytes) | **Open.** The BGI15 succinct p-party DPF outputs XOR shares, which do not convert linearly to additive Z_p shares. Keep key-size claims to n = 2, as the submission already does. |
| Per-user authorisation not met | **Open.** Unchanged; state as a requirement. |
| Ingest: new-keyword insertion and per-tier re-keying not implemented | **Authors.** |
| No gateway-class measurement | **Authors.** The user's work is one DPF key generation, n-1 additions and one decryption (about 1–1.6 ms on a server). |

A referee who reads a Limitations section this long, followed by "Future work will
pursue...", reasonably concludes the evaluation is not finished. The revision closes the
items that need no new hardware and turns the rest into a shorter, precise list.

## 3. Presentation and process issues

* **No artefact.** The submission removed its data-availability statement and every
  repository link. The public GitHub repository at the time contained an older Paillier
  prototype that did not implement the paper. It also had defects: 64-bucket results,
  colliding keyword rows, a strawman baseline it lost to, and a README naming a
  different venue and title. A referee who found it would have weighed it against the
  paper. **Fixed:** the old code is in `legacy/` with its defects listed, the
  reference implementation is in `crshe/`, and the revised manuscript has a data and
  code availability statement.
* **The C++ prototype the paper measures is not public.** The paper's tables come from
  a C++17/OpenFHE build that is not in any repository. Publish it alongside `crshe/`.
  Otherwise the reference implementation here is the only artefact, and its latencies
  are a Python driver's, not the paper's.
* **Generative-AI declaration.** The submitted declaration says AI tools were used only
  for "routine language and grammar checking". `paper/fgcs-2026-submission/README_conversion.md`
  describes much more: the abstract was rewritten, the title changed, the class
  converted, every em dash rewritten, and Figure 1 redrawn by a tool. Elsevier and most
  publishers require the declaration to be accurate. Revise it so it describes what was
  actually done before any resubmission. The revised manuscript has a placeholder
  comment there.
* **Headline baseline.** "617× less work than a homomorphic equality scan" compares a
  two-server design with a one-server design that pays for a depth-17 circuit. Keep
  it in the table, but do not lead with it.
* **Mixed provenance of numbers.** The revised manuscript keeps the C++/EPYC numbers
  where the measured quantity did not change. It reports the new experiments from the
  reference implementation in a separate, machine-stamped table. It marks the places
  where the C++ numbers must be re-measured with `\authorcheck{...}` (red in the PDF).
  Remove every marker before submitting.

## 4. Where to submit next

FGCS will not reconsider. Reasonable targets for the revised paper, roughly in order of
fit:

1. **IEEE Transactions on Cloud Computing.** Multi-cloud trust split, systems
   evaluation.
2. **Proceedings on Privacy Enhancing Technologies (PoPETs).** The FSS/PIR community
   that will judge the cryptography fairly. Needs the WAN evaluation and the published
   C++ artefact.
3. **IEEE Internet of Things Journal.** The manuscript was originally prepared for it.
   Strengthen the IoT angle with a gateway measurement of the client side.
4. **Computers & Security** or **Journal of Information Security and Applications.**
   Lower bar, faster turnaround.

Before submitting anywhere: finish the WAN run, publish the C++ code, run
`bench/bench_leakage.py` on both corpora, re-measure the `\authorcheck` items, and fix
the AI declaration.

## Reviewer comments

*(Paste the reviewer reports from Editorial Manager here and map each point to a
change.)*
