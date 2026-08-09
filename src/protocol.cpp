// SPDX-License-Identifier: Apache-2.0
#include "crshe/protocol.hpp"

#include <cstring>
#include <stdexcept>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace crshe {

namespace {
int resolve_threads(int t) {
#ifdef _OPENMP
    return t > 0 ? t : omp_get_max_threads();
#else
    (void)t;
    return 1;
#endif
}
}  // namespace

// ---------------------------------------------------------------------------
// Key wire format
// ---------------------------------------------------------------------------

namespace {
template <typename T>
void put(std::string& s, const T& v) {
    s.append((const char*)&v, sizeof(T));
}
template <typename T>
T take(const std::string& s, size_t& off) {
    if (off + sizeof(T) > s.size()) throw std::runtime_error("key blob truncated");
    T v;
    std::memcpy(&v, s.data() + off, sizeof(T));
    off += sizeof(T);
    return v;
}
}  // namespace

std::string serialize_token_key(const Token& t, uint32_t party) {
    std::string s;
    put<uint8_t>(s, t.two_party ? 1 : 0);
    if (t.two_party) {
        const Dpf2Key& k = t.k2[party];
        put<uint8_t>(s, k.party);
        put<uint32_t>(s, k.depth);
        put(s, k.seed);
        put<uint64_t>(s, k.cw_final);
        for (uint32_t i = 0; i < k.depth; ++i) {
            put(s, k.cw_seed[i]);
            put<uint8_t>(s, k.cw_tl[i]);
            put<uint8_t>(s, k.cw_tr[i]);
        }
    } else {
        const DpfNKey& k = t.kn[party];
        put<uint32_t>(s, k.party);
        put<uint32_t>(s, k.n_parties);
        put<uint64_t>(s, k.domain);
        put<uint8_t>(s, k.explicit_share ? 1 : 0);
        s.append((const char*)k.seed, 16);
        put<uint64_t>(s, (uint64_t)k.share.size());
        if (!k.share.empty())
            s.append((const char*)k.share.data(), k.share.size() * sizeof(uint64_t));
    }
    return s;
}

Token deserialize_token_key(const std::string& blob) {
    size_t off = 0;
    Token t;
    t.two_party = take<uint8_t>(blob, off) != 0;
    if (t.two_party) {
        Dpf2Key k;
        k.party = take<uint8_t>(blob, off);
        k.depth = take<uint32_t>(blob, off);
        k.seed = take<Block>(blob, off);
        k.cw_final = take<uint64_t>(blob, off);
        k.cw_seed.resize(k.depth);
        k.cw_tl.resize(k.depth);
        k.cw_tr.resize(k.depth);
        for (uint32_t i = 0; i < k.depth; ++i) {
            k.cw_seed[i] = take<Block>(blob, off);
            k.cw_tl[i] = take<uint8_t>(blob, off);
            k.cw_tr[i] = take<uint8_t>(blob, off);
        }
        if (!Dpf2::well_formed(k, k.depth))
            throw std::runtime_error("malformed DPF key rejected");
        t.k2.push_back(std::move(k));
    } else {
        DpfNKey k;
        k.party = take<uint32_t>(blob, off);
        k.n_parties = take<uint32_t>(blob, off);
        k.domain = take<uint64_t>(blob, off);
        k.explicit_share = take<uint8_t>(blob, off) != 0;
        if (off + 16 > blob.size()) throw std::runtime_error("key blob truncated");
        std::memcpy(k.seed, blob.data() + off, 16);
        off += 16;
        const uint64_t n = take<uint64_t>(blob, off);
        if (n > k.domain) throw std::runtime_error("key blob: share longer than domain");
        k.share.resize(n);
        if (n) {
            if (off + n * 8 > blob.size()) throw std::runtime_error("key blob truncated");
            std::memcpy(k.share.data(), blob.data() + off, n * 8);
        }
        t.kn.push_back(std::move(k));
    }
    return t;
}

// ---------------------------------------------------------------------------
// DpfScheme
// ---------------------------------------------------------------------------

DpfScheme::DpfScheme(Modulus mod, uint32_t n_parties, uint64_t domain,
                     bool force_nparty)
    : mod_(mod), n_parties_(n_parties), domain_(domain),
      dpf2_(mod), dpfn_(mod) {
    if (n_parties < 2) throw std::invalid_argument("n_parties >= 2 required");
    while ((1ULL << depth_) < domain_) ++depth_;
    if (depth_ == 0) depth_ = 1;
    succinct_ = (n_parties == 2) && !force_nparty;
}

void DpfScheme::gen(uint64_t alpha, uint64_t beta, Token& t) const {
    if (succinct_) {
        t.two_party = true;
        t.k2.resize(2);
        t.kn.clear();
        dpf2_.gen(alpha, beta, depth_, t.k2[0], t.k2[1]);
    } else {
        t.two_party = false;
        t.k2.clear();
        dpfn_.gen(alpha, beta, domain_, n_parties_, t.kn);
    }
}

void DpfScheme::eval_full(const Token& t, uint32_t party, uint64_t* out,
                          size_t n, int threads) const {
    if (t.two_party) dpf2_.eval_full(t.k2[party], out, n, threads);
    else dpfn_.eval_full(t.kn[party], out, n, threads);
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

const std::vector<Ct>& Provider::column_for(const Template& f, bool mac) const {
    if (f.column == Template::Column::kUnit)
        return mac ? st_.unit_mac : st_.unit;
    return mac ? st_.value_mac : st_.value;
}

AggResponse Provider::fast_agg(const uint64_t* e, const std::string& tmpl,
                               bool measure_downlink) const {
    auto it = st_.fast.find(tmpl);
    if (it == st_.fast.end())
        throw std::runtime_error("no precomputed column for template " + tmpl);
    const std::vector<uint64_t> ev(e, e + st_.n_tags);

    AggResponse r;
    r.ct = he_.inner_product(it->second.A, ev);
    r.ct_mac = he_.inner_product(it->second.A_mac, ev);
    if (measure_downlink)
        r.downlink_bytes = he_.serialize(r.ct).size() + he_.serialize(r.ct_mac).size();
    return r;
}

std::vector<uint64_t> Provider::contract_index(const uint64_t* e, int threads) const {
    if (st_.masked_index.empty())
        throw std::runtime_error(
            "the masked index I' was not built; construct the provider state "
            "with with_general = true");
    const uint64_t N = st_.n_tags;
    const uint64_t Nd = st_.n_records;
    const int nt = resolve_threads(threads);

    // Accumulate in 128 bits and reduce once per output.  Each product is
    // < p^2 < 2^74 and at most N ~ 2^14 of them are summed, so the accumulator
    // stays below 2^88 and no intermediate reduction is needed -- which is what
    // makes the inner loop a single multiply-add.
    std::vector<unsigned __int128> global(Nd, 0);

#ifdef _OPENMP
#pragma omp parallel num_threads(nt)
#endif
    {
        std::vector<unsigned __int128> local(Nd, 0);
#ifdef _OPENMP
#pragma omp for schedule(static)
#endif
        for (long long xx = 0; xx < (long long)N; ++xx) {
            const uint64_t x = (uint64_t)xx;
            const uint64_t ex = e[x];
            if (ex == 0) continue;   // only ever true for the n-party sparse case
            const uint64_t* row = st_.masked_index.data() + x * Nd;
            for (uint64_t i = 0; i < Nd; ++i)
                local[i] += (unsigned __int128)ex * row[i];
        }
#ifdef _OPENMP
#pragma omp critical
#endif
        {
            for (uint64_t i = 0; i < Nd; ++i) global[i] += local[i];
        }
    }

    std::vector<uint64_t> b(Nd);
    for (uint64_t i = 0; i < Nd; ++i) b[i] = mod_.reduce(global[i]);
    return b;
}

AggResponse Provider::gen_agg(const uint64_t* e, const Template& f,
                              bool measure_downlink, int threads) const {
    auto it = st_.gen.find(f.name);
    if (it == st_.gen.end())
        throw std::runtime_error("no correction column U_f for template " + f.name);

    const std::vector<uint64_t> b = contract_index(e, threads);

    std::vector<uint64_t> coeff(st_.n_records);
    for (uint64_t i = 0; i < st_.n_records; ++i)
        coeff[i] = mod_.mul(mod_.from_u64(f.w[i]), b[i]);

    const std::vector<uint64_t> ev(e, e + st_.n_tags);

    AggResponse r;
    r.ct = he_.sub(he_.inner_product(column_for(f, false), coeff),
                   he_.inner_product(it->second.U, ev));
    r.ct_mac = he_.sub(he_.inner_product(column_for(f, true), coeff),
                       he_.inner_product(it->second.U_mac, ev));
    if (measure_downlink)
        r.downlink_bytes = he_.serialize(r.ct).size() + he_.serialize(r.ct_mac).size();
    return r;
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

AggResult combine_dec(const HeBackend& he, Modulus mod, uint64_t delta,
                      const std::vector<AggResponse>& responses) {
    if (responses.empty()) throw std::runtime_error("no responses to combine");
    Ct acc = responses[0].ct;
    Ct acc_mac = responses[0].ct_mac;
    for (size_t j = 1; j < responses.size(); ++j) {
        acc = he.add(acc, responses[j].ct);
        acc_mac = he.add(acc_mac, responses[j].ct_mac);
    }
    AggResult res;
    res.y = he.decrypt_scalar(acc);
    const uint64_t y_mac = he.decrypt_scalar(acc_mac);
    res.mac_ok = (y_mac == mod.mul(delta, res.y));
    return res;
}

std::vector<uint32_t> combine_retrieve(
    const Owner& owner, uint64_t alpha,
    const std::vector<std::vector<uint64_t>>& shares) {
    const Modulus& mod = owner.modulus();
    const uint64_t nd = shares.at(0).size();
    std::vector<uint64_t> b(nd, 0);
    for (const auto& s : shares)
        for (uint64_t i = 0; i < nd; ++i) b[i] = mod.add(b[i], s[i]);

    std::vector<uint64_t> p(nd);
    owner.mask_row(alpha, nd, p.data());

    std::vector<uint32_t> S;
    for (uint64_t i = 0; i < nd; ++i) {
        const uint64_t v = mod.sub(b[i], p[i]);
        if (v == 1) S.push_back((uint32_t)i);
        else if (v != 0)
            throw std::runtime_error("retrieval produced a non-0/1 selection bit; "
                                     "either a provider deviated or the mask is "
                                     "out of sync");
    }
    return S;
}

uint64_t plaintext_aggregate(const Dataset& ds, const Template& f, uint64_t x,
                             Modulus mod) {
    const bool unit = f.column == Template::Column::kUnit;
    unsigned __int128 acc = 0;
    for (uint64_t k = ds.offset[x]; k < ds.offset[x + 1]; ++k) {
        const uint32_t i = ds.postings[k];
        acc += (unsigned __int128)f.w[i] * (unit ? 1u : ds.values[i]);
    }
    return mod.reduce(acc);
}

}  // namespace crshe
