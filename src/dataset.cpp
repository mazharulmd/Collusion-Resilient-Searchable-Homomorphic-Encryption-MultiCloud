// SPDX-License-Identifier: Apache-2.0
#include "crshe/dataset.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <random>
#include <set>
#include <stdexcept>

namespace crshe {

namespace {
constexpr char kMagic[8] = {'C', 'R', 'S', 'H', 'E', 'D', 'S', '1'};

template <typename T>
void write_pod(std::ostream& os, const T& v) {
    os.write((const char*)&v, sizeof(T));
}
template <typename T>
void read_pod(std::istream& is, T& v) {
    is.read((char*)&v, sizeof(T));
    if (!is) throw std::runtime_error("dataset: truncated file");
}
template <typename T>
void write_vec(std::ostream& os, const std::vector<T>& v) {
    write_pod<uint64_t>(os, v.size());
    if (!v.empty()) os.write((const char*)v.data(), v.size() * sizeof(T));
}
template <typename T>
void read_vec(std::istream& is, std::vector<T>& v) {
    uint64_t n = 0;
    read_pod(is, n);
    v.resize(n);
    if (n) {
        is.read((char*)v.data(), n * sizeof(T));
        if (!is) throw std::runtime_error("dataset: truncated file");
    }
}
}  // namespace

void Dataset::validate() const {
    // A posting list must be sorted and free of duplicates: I[x][i] is a
    // membership bit, and a repeated record id would push it out of {0,1},
    // silently breaking retrieval and making every aggregate double-count.
    for (uint64_t x = 0; x < n_tags; ++x) {
        if (offset[x] > offset[x + 1] || offset[x + 1] > postings.size())
            throw std::runtime_error("dataset: posting offsets out of range at tag " +
                                     std::to_string(x));
        for (uint64_t k = offset[x]; k + 1 < offset[x + 1]; ++k)
            if (postings[k] >= postings[k + 1])
                throw std::runtime_error(
                    "dataset: posting list of tag " + std::to_string(x) +
                    " is not strictly increasing (duplicate or unsorted record id)");
        if (offset[x + 1] > offset[x] && postings[offset[x + 1] - 1] >= n_records)
            throw std::runtime_error("dataset: record id out of range at tag " +
                                     std::to_string(x));
    }
}

uint64_t Dataset::max_posting_len() const {
    uint64_t m = 0;
    for (uint64_t x = 0; x < n_tags; ++x) m = std::max(m, posting_len(x));
    return m;
}

uint64_t Dataset::max_aggregate(const std::vector<uint64_t>& w) const {
    uint64_t worst = 0;
    for (uint64_t x = 0; x < n_tags; ++x) {
        unsigned __int128 s = 0;
        for (uint64_t k = offset[x]; k < offset[x + 1]; ++k) {
            const uint32_t i = postings[k];
            s += (unsigned __int128)w[i] * values[i];
        }
        if (s > (unsigned __int128)UINT64_MAX) return UINT64_MAX;
        worst = std::max(worst, (uint64_t)s);
    }
    return worst;
}

void Dataset::save(const std::string& path) const {
    std::ofstream os(path, std::ios::binary);
    if (!os) throw std::runtime_error("cannot write " + path);
    os.write(kMagic, 8);
    write_pod(os, n_records);
    write_pod(os, n_tags);
    write_vec(os, values);
    write_vec(os, offset);
    write_vec(os, postings);
    write_pod<uint64_t>(os, source.size());
    os.write(source.data(), source.size());
    write_pod<uint64_t>(os, tag_names.size());
    for (const auto& t : tag_names) {
        write_pod<uint32_t>(os, (uint32_t)t.size());
        os.write(t.data(), t.size());
    }
}

Dataset Dataset::load(const std::string& path) {
    std::ifstream is(path, std::ios::binary);
    if (!is) throw std::runtime_error("cannot open dataset " + path +
                                      " (run python/prepare_dataset.py first)");
    char magic[8];
    is.read(magic, 8);
    if (std::memcmp(magic, kMagic, 8) != 0)
        throw std::runtime_error("not a CR-SHE dataset file: " + path);
    Dataset d;
    read_pod(is, d.n_records);
    read_pod(is, d.n_tags);
    read_vec(is, d.values);
    read_vec(is, d.offset);
    read_vec(is, d.postings);
    uint64_t slen = 0;
    read_pod(is, slen);
    d.source.resize(slen);
    if (slen) is.read(&d.source[0], slen);
    uint64_t ntags = 0;
    read_pod(is, ntags);
    d.tag_names.resize(ntags);
    for (uint64_t i = 0; i < ntags; ++i) {
        uint32_t l = 0;
        read_pod(is, l);
        d.tag_names[i].resize(l);
        if (l) is.read(&d.tag_names[i][0], l);
    }
    if (d.offset.size() != d.n_tags + 1)
        throw std::runtime_error("dataset: offset array inconsistent with n_tags");
    if (d.values.size() != d.n_records)
        throw std::runtime_error("dataset: value array inconsistent with n_records");
    d.validate();
    return d;
}

Dataset Dataset::synthetic(uint64_t n_tags, uint64_t n_records, double zipf,
                           uint64_t seed) {
    Dataset d;
    d.n_tags = n_tags;
    d.n_records = n_records;
    d.source = "synthetic(zipf=" + std::to_string(zipf) + ")";
    std::mt19937_64 rng(seed);

    d.values.resize(n_records);
    // Values in the range of the primary corpus: temperature in hundredths of
    // a degree, roughly 1000..3500.
    for (uint64_t i = 0; i < n_records; ++i) d.values[i] = 1000 + rng() % 2500;

    // Zipf-ish posting lengths: tag x gets about n_records / (x+1)^zipf
    // records, floored at 1 and capped at n_records.
    d.offset.resize(n_tags + 1, 0);
    std::vector<uint64_t> len(n_tags);
    for (uint64_t x = 0; x < n_tags; ++x) {
        const double l = (double)n_records / std::pow((double)(x + 1), zipf);
        uint64_t li = (uint64_t)std::max(1.0, l);
        len[x] = std::min(li, n_records);
    }
    for (uint64_t x = 0; x < n_tags; ++x) d.offset[x + 1] = d.offset[x] + len[x];
    d.postings.resize(d.offset[n_tags]);
    for (uint64_t x = 0; x < n_tags; ++x) {
        // Distinct, sorted record ids -- a posting list must never repeat a
        // record, or I[x][i] leaves {0,1} and retrieval stops being a
        // membership test.  Floyd's algorithm samples k distinct values from
        // [0, n) in O(k) without materialising the population.
        std::vector<uint32_t> ids;
        ids.reserve(len[x]);
        std::set<uint32_t> chosen;
        for (uint64_t j = n_records - len[x]; j < n_records; ++j) {
            uint32_t t = (uint32_t)(rng() % (j + 1));
            if (chosen.count(t)) t = (uint32_t)j;
            chosen.insert(t);
        }
        ids.assign(chosen.begin(), chosen.end());
        std::sort(ids.begin(), ids.end());
        std::copy(ids.begin(), ids.end(), d.postings.begin() + d.offset[x]);
    }
    d.tag_names.resize(n_tags);
    for (uint64_t x = 0; x < n_tags; ++x) d.tag_names[x] = "syn" + std::to_string(x);
    return d;
}

Dataset Dataset::subsample_records(uint64_t nd) const {
    if (nd >= n_records) return *this;
    Dataset d;
    d.n_tags = n_tags;
    d.n_records = nd;
    d.source = source + "|subsample(Nd=" + std::to_string(nd) + ")";
    d.values.assign(values.begin(), values.begin() + nd);
    d.tag_names = tag_names;
    d.offset.assign(n_tags + 1, 0);
    for (uint64_t x = 0; x < n_tags; ++x) {
        uint64_t kept = 0;
        for (uint64_t k = offset[x]; k < offset[x + 1]; ++k)
            if (postings[k] < nd) ++kept;
        d.offset[x + 1] = d.offset[x] + kept;
    }
    d.postings.resize(d.offset[n_tags]);
    uint64_t w = 0;
    for (uint64_t x = 0; x < n_tags; ++x)
        for (uint64_t k = offset[x]; k < offset[x + 1]; ++k)
            if (postings[k] < nd) d.postings[w++] = postings[k];
    return d;
}

}  // namespace crshe
