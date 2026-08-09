// SPDX-License-Identifier: Apache-2.0
//
// The corpus, in the form the protocol needs it: a tag -> record-id posting
// list (CSR) plus one integer computable field per record.
//
// python/prepare_dataset.py turns the raw CSVs into this format so that no
// benchmark ever pays CSV parsing, and so that the C++ and the Python leakage
// attack read byte-identical inputs.

#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace crshe {

struct Dataset {
    uint64_t n_records = 0;
    uint64_t n_tags = 0;
    // Computable field m_i, already scaled to an integer (e.g. temperature in
    // hundredths of a degree). Must satisfy the Lemma 1 magnitude bound.
    std::vector<uint64_t> values;
    // Postings in CSR form: tag x owns postings[offset[x] .. offset[x+1]).
    std::vector<uint64_t> offset;
    std::vector<uint32_t> postings;
    // Human-readable tag names, used only by the leakage-abuse attack.
    std::vector<std::string> tag_names;
    std::string source = "unknown";

    // Throws if the posting lists are not strictly increasing or ids are out
    // of range; called on every load so bad input fails at the door.
    void validate() const;

    uint64_t postings_total() const { return postings.empty() ? 0 : postings.size(); }
    uint64_t posting_len(uint64_t x) const { return offset[x + 1] - offset[x]; }
    uint64_t max_posting_len() const;
    // Largest value of sum_i w[i] m[i] over any single tag, i.e. the quantity
    // Lemma 1 requires to stay below p.
    uint64_t max_aggregate(const std::vector<uint64_t>& w) const;

    static Dataset load(const std::string& path);
    void save(const std::string& path) const;

    // Deterministic synthetic corpus with Zipf-distributed posting lengths.
    // Used so that the whole harness runs before the real data is downloaded,
    // and for the scaling sweeps that go past the real corpus size.
    static Dataset synthetic(uint64_t n_tags, uint64_t n_records, double zipf,
                             uint64_t seed);

    // Keep the first `nd` records and drop the rest from every posting list.
    // This is how the general-path sweep reaches N_d = 1e3 .. 1e5 without
    // materialising the full N x N_d index.
    Dataset subsample_records(uint64_t nd) const;
};

}  // namespace crshe
