// SPDX-License-Identifier: Apache-2.0
//
// The comparison points of Section VIII-E.  Each one is a real implementation
// measured on the same corpus and the same machine as CR-SHE, and each one
// carries its leakage in its own comment so a table entry can never drift from
// what the code actually does.
//
//   PlaintextScan  no privacy at all; lower-bounds achievable latency.
//   SseIndex       single-server searchable encryption. Leaks the search
//                  pattern, the access pattern and |S|.
//   PathOram       oblivious RAM over the record store. Hides the access
//                  pattern from one server, at O(log^2 N_d) blocks per access
//                  and with |S| accesses per keyword.
//   DoryStyle      distributed-trust search only: the same DPF selection
//                  CR-SHE uses, stopping at the selection vector with no
//                  aggregation. Isolates the cost of adding oblivious
//                  analytics to oblivious selection.

#pragma once

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <map>
#include <random>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "crshe/aes_prg.hpp"
#include "crshe/dataset.hpp"
#include "crshe/zp.hpp"

namespace crshe {

// ---------------------------------------------------------------------------
// (i) Plaintext linear scan
// ---------------------------------------------------------------------------
class PlaintextScan {
public:
    explicit PlaintextScan(const Dataset& ds) : ds_(ds) {}
    // Sum of the computable field over the posting list of tag x. The server
    // sees the tag, the matched set, and the answer.
    uint64_t aggregate(uint64_t x) const {
        uint64_t s = 0;
        for (uint64_t k = ds_.offset[x]; k < ds_.offset[x + 1]; ++k)
            s += ds_.values[ds_.postings[k]];
        return s;
    }
    // A true linear scan over every record, for the case where the index is
    // not available and the filter must be evaluated per record.
    uint64_t scan_all(uint64_t needle) const {
        uint64_t s = 0;
        for (uint64_t i = 0; i < ds_.n_records; ++i)
            if (ds_.values[i] == needle) s += ds_.values[i];
        return s;
    }

private:
    const Dataset& ds_;
};

// ---------------------------------------------------------------------------
// (ii) Single-server searchable encryption
// ---------------------------------------------------------------------------
// Inverted index keyed by a PRF token; each posting list is encrypted under
// AES-CTR with a per-tag key derived from the token. The server matches the
// token against a hash table and returns the ciphertext blob, learning the
// search pattern (repeated tokens), the access pattern (which blob) and |S|
// (the blob length). This is the leakage the leakage-abuse literature attacks
// and the reason CR-SHE masks its index.
class SseIndex {
public:
    SseIndex(const Dataset& ds, const uint8_t key[16]) : ds_(ds) {
        std::memcpy(key_, key, 16);
        CtrPrf prf(key_);
        blobs_.resize(ds.n_tags);
        tokens_.resize(ds.n_tags);
        for (uint64_t x = 0; x < ds.n_tags; ++x) {
            uint64_t t[2];
            prf.stream(2 * x, t, 2);
            tokens_[x] = t[0];
            const uint64_t len = ds.posting_len(x);
            // Each posting is (record id, value), encrypted with a keystream
            // derived from the token.
            std::vector<uint64_t> plain(2 * len);
            for (uint64_t k = 0; k < len; ++k) {
                const uint32_t i = ds.postings[ds.offset[x] + k];
                plain[2 * k] = i;
                plain[2 * k + 1] = ds.values[i];
            }
            uint8_t list_key[16];
            std::memcpy(list_key, &t[0], 8);
            std::memcpy(list_key + 8, &t[1], 8);
            CtrPrf lk(list_key);
            std::vector<uint64_t> ks(plain.size());
            lk.stream(0, ks.data(), ks.size());
            for (size_t j = 0; j < plain.size(); ++j) plain[j] ^= ks[j];
            blobs_[x] = std::move(plain);
            table_[tokens_[x]] = x;
        }
    }

    uint64_t token(uint64_t x) const { return tokens_[x]; }

    // Server side: hash-table lookup plus the copy of the blob onto the wire.
    const std::vector<uint64_t>& search(uint64_t token) const {
        auto it = table_.find(token);
        if (it == table_.end()) throw std::runtime_error("SSE: unknown token");
        return blobs_[it->second];
    }

    // Client side: decrypt and aggregate. Charged to the client, as it must be.
    uint64_t decrypt_and_sum(uint64_t x, const std::vector<uint64_t>& blob) const {
        CtrPrf prf(key_);
        uint64_t t[2];
        prf.stream(2 * x, t, 2);
        uint8_t list_key[16];
        std::memcpy(list_key, &t[0], 8);
        std::memcpy(list_key + 8, &t[1], 8);
        CtrPrf lk(list_key);
        std::vector<uint64_t> ks(blob.size());
        lk.stream(0, ks.data(), ks.size());
        uint64_t s = 0;
        for (size_t j = 1; j < blob.size(); j += 2) s += (blob[j] ^ ks[j]);
        return s;
    }

    size_t blob_bytes(uint64_t x) const { return blobs_[x].size() * sizeof(uint64_t); }

private:
    const Dataset& ds_;
    uint8_t key_[16];
    std::vector<uint64_t> tokens_;
    std::vector<std::vector<uint64_t>> blobs_;
    std::unordered_map<uint64_t, uint64_t> table_;
};

// ---------------------------------------------------------------------------
// (iii) Path ORAM
// ---------------------------------------------------------------------------
// Non-recursive Path ORAM (Stefanov et al.): bucket size Z = 4, client-side
// position map and stash. Hides the access pattern from a single server at the
// cost of reading and writing a whole root-to-leaf path per access. A keyword
// query touching |S| records costs |S| accesses, which is where the comparison
// against CR-SHE's single fixed-size response is decided.
class PathOram {
public:
    static constexpr size_t kZ = 4;

    PathOram(uint64_t n_blocks, size_t block_words, uint64_t seed)
        : n_(n_blocks), bw_(block_words), rng_(seed) {
        levels_ = 1;
        while ((1ULL << levels_) < n_) ++levels_;
        n_leaves_ = 1ULL << levels_;
        n_buckets_ = 2 * n_leaves_;             // 1-indexed heap
        storage_.assign(n_buckets_ * kZ, Block_{});
        for (auto& b : storage_) b.data.assign(bw_, 0);
        pos_.resize(n_);
        for (uint64_t i = 0; i < n_; ++i) pos_[i] = rng_() % n_leaves_;
    }

    void write(uint64_t id, const std::vector<uint64_t>& data) { access(id, &data); }
    std::vector<uint64_t> read(uint64_t id) { return access(id, nullptr); }

    size_t stash_size() const { return stash_.size(); }
    uint64_t levels() const { return levels_; }
    // Bytes moved between client and server per access, both directions.
    size_t bytes_per_access() const {
        return 2 * (levels_ + 1) * kZ * (bw_ * sizeof(uint64_t) + sizeof(uint64_t));
    }

private:
    struct Block_ {
        bool valid = false;
        uint64_t id = 0;
        std::vector<uint64_t> data;
    };

    static uint64_t bucket_on_path(uint64_t leaf, uint64_t level, uint64_t levels) {
        // Heap index of the level-`level` ancestor of `leaf`.
        return ((leaf + (1ULL << levels)) >> (levels - level));
    }

    std::vector<uint64_t> access(uint64_t id, const std::vector<uint64_t>* wdata) {
        const uint64_t leaf = pos_[id];
        pos_[id] = rng_() % n_leaves_;           // remap before touching the path

        // Read the whole path into the stash.
        for (uint64_t l = 0; l <= levels_; ++l) {
            const uint64_t b = bucket_on_path(leaf, l, levels_);
            for (size_t s = 0; s < kZ; ++s) {
                Block_& blk = storage_[b * kZ + s];
                if (blk.valid) { stash_.push_back(blk); blk.valid = false; }
            }
        }

        std::vector<uint64_t> out(bw_, 0);
        bool found = false;
        for (auto& blk : stash_) {
            if (blk.valid && blk.id == id) {
                out = blk.data;
                if (wdata) blk.data = *wdata;
                found = true;
                break;
            }
        }
        if (!found) {
            Block_ nb;
            nb.valid = true;
            nb.id = id;
            nb.data = wdata ? *wdata : std::vector<uint64_t>(bw_, 0);
            stash_.push_back(nb);
        }

        // Write the path back, greedily pushing blocks as deep as they can go.
        for (int l = (int)levels_; l >= 0; --l) {
            const uint64_t b = bucket_on_path(leaf, (uint64_t)l, levels_);
            size_t placed = 0;
            for (auto& blk : stash_) {
                if (!blk.valid || placed == kZ) continue;
                if (bucket_on_path(pos_[blk.id], (uint64_t)l, levels_) != b) continue;
                storage_[b * kZ + placed] = blk;
                blk.valid = false;
                ++placed;
            }
        }
        stash_.erase(std::remove_if(stash_.begin(), stash_.end(),
                                    [](const Block_& b) { return !b.valid; }),
                     stash_.end());
        return out;
    }

    uint64_t n_, bw_;
    uint64_t levels_ = 0, n_leaves_ = 0, n_buckets_ = 0;
    std::vector<Block_> storage_;
    std::vector<Block_> stash_;
    std::vector<uint64_t> pos_;
    std::mt19937_64 rng_;
};

}  // namespace crshe
