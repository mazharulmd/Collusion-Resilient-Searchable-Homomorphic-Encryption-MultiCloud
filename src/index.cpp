// SPDX-License-Identifier: Apache-2.0
#include "crshe/index.hpp"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <sstream>
#include <stdexcept>
#include <unistd.h>

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

uint64_t available_ram_bytes() {
#if defined(_SC_AVPHYS_PAGES) && defined(_SC_PAGESIZE)
    const long pages = sysconf(_SC_AVPHYS_PAGES);
    const long page = sysconf(_SC_PAGESIZE);
    if (pages > 0 && page > 0) return (uint64_t)pages * (uint64_t)page;
#endif
    return 0;
}

// ---------------------------------------------------------------------------
// Owner
// ---------------------------------------------------------------------------

Owner::Owner(const Dataset& ds, Modulus mod, uint64_t seed)
    : ds_(ds), mod_(mod) {
    std::mt19937_64 rng(seed);
    for (int b = 0; b < 16; b += 8) {
        uint64_t r = rng();
        std::memcpy(k_ + b, &r, 8);
        r = rng();
        std::memcpy(kp_ + b, &r, 8);
    }
    delta_ = 1 + rng() % (mod_.value() - 1);
    mask_prf_ = std::make_unique<CtrPrf>(kp_);
}

uint64_t Owner::address(const std::string& tag) const {
    // F_K(tag) truncated to the tag domain. Collisions are the Q^2/2^lambda
    // term of Theorem 3; the corpus builder assigns distinct addresses, so
    // this path exists for ad-hoc keyword lookups.
    CtrPrf prf(k_);
    uint64_t h = 1469598103934665603ULL;
    for (unsigned char c : tag) { h ^= c; h *= 1099511628211ULL; }
    uint64_t out[2];
    prf.stream(h & ~1ULL, out, 2);
    return out[0] % ds_.n_tags;
}

void Owner::mask_row(uint64_t x, uint64_t nd, uint64_t* out) const {
    // P[x][i] = F'_{K'}(x*Nd + i). The counter is injective in (x, i) because
    // it is taken over the *full* record count, not the subsampled one.
    mask_prf_->stream(x * ds_.n_records, out, nd);
    for (uint64_t i = 0; i < nd; ++i) out[i] = mod_.from_u64(out[i]);
}

std::vector<uint64_t> Owner::build_masked_index(uint64_t nd, int threads) const {
    const unsigned __int128 bytes = masked_index_bytes(ds_.n_tags, nd);
    const uint64_t avail = available_ram_bytes();
    if (bytes > (unsigned __int128)UINT64_MAX ||
        (avail && (uint64_t)bytes > avail)) {
        std::ostringstream os;
        os << "masked index of " << ds_.n_tags << " x " << nd << " Z_p words needs "
           << (double)bytes / 1e9 << " GB but only " << (double)avail / 1e9
           << " GB is available. This is the real storage cost of the general "
              "path and is itself a result: subsample records with --nd, or run "
              "the fast path, which does not store I' at all.";
        throw std::runtime_error(os.str());
    }
    std::vector<uint64_t> I(ds_.n_tags * nd);
    const int nt = resolve_threads(threads);

#ifdef _OPENMP
#pragma omp parallel for schedule(static) num_threads(nt)
#endif
    for (long long xx = 0; xx < (long long)ds_.n_tags; ++xx) {
        const uint64_t x = (uint64_t)xx;
        uint64_t* row = I.data() + x * nd;
        mask_row(x, nd, row);
        for (uint64_t k = ds_.offset[x]; k < ds_.offset[x + 1]; ++k) {
            const uint32_t i = ds_.postings[k];
            if (i < nd) row[i] = mod_.add(row[i], 1);
        }
    }
    (void)nt;
    return I;
}

std::vector<uint64_t> Owner::compute_A(const Template& f) const {
    std::vector<uint64_t> A(ds_.n_tags, 0);
    const bool unit = f.column == Template::Column::kUnit;
#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic, 64)
#endif
    for (long long xx = 0; xx < (long long)ds_.n_tags; ++xx) {
        const uint64_t x = (uint64_t)xx;
        unsigned __int128 acc = 0;
        for (uint64_t k = ds_.offset[x]; k < ds_.offset[x + 1]; ++k) {
            const uint32_t i = ds_.postings[k];
            const uint64_t v = unit ? 1u : ds_.values[i];
            acc += (unsigned __int128)f.w[i] * v;
            if (acc >> 100) acc = mod_.reduce(acc);   // keep well clear of 2^128
        }
        A[x] = mod_.reduce(acc);
    }
    return A;
}

std::vector<uint64_t> Owner::compute_U(const Template& f, uint64_t nd,
                                       int threads) const {
    // U_f[x] = sum_i P[x][i] * w_f[i] * v_i.  Theta(N * nd) multiply-adds, and
    // the dominant one-off cost of setup.
    std::vector<uint64_t> U(ds_.n_tags, 0);
    const bool unit = f.column == Template::Column::kUnit;
    const int nt = resolve_threads(threads);

    // Fold w_f[i]*v_i once; the inner loop then costs one multiply-add.
    std::vector<uint64_t> wv(nd);
    for (uint64_t i = 0; i < nd; ++i)
        wv[i] = mod_.mul(f.w[i], unit ? 1u : mod_.from_u64(ds_.values[i]));

#ifdef _OPENMP
#pragma omp parallel num_threads(nt)
#endif
    {
        std::vector<uint64_t> row(nd);
#ifdef _OPENMP
#pragma omp for schedule(static)
#endif
        for (long long xx = 0; xx < (long long)ds_.n_tags; ++xx) {
            const uint64_t x = (uint64_t)xx;
            mask_row(x, nd, row.data());
            unsigned __int128 acc = 0;
            for (uint64_t i = 0; i < nd; ++i) {
                acc += (unsigned __int128)row[i] * wv[i];
                if (acc >> 120) acc = mod_.reduce(acc);
            }
            U[x] = mod_.reduce(acc);
        }
    }
    (void)nt;
    return U;
}

std::vector<uint64_t> Owner::scale(const std::vector<uint64_t>& v,
                                   uint64_t c) const {
    std::vector<uint64_t> out(v.size());
    for (size_t i = 0; i < v.size(); ++i) out[i] = mod_.mul(v[i], c);
    return out;
}

// ---------------------------------------------------------------------------
// Templates
// ---------------------------------------------------------------------------

std::vector<Template> default_templates(const Dataset& ds, uint64_t seed) {
    std::vector<Template> ts;
    const uint64_t nd = ds.n_records;

    Template count;
    count.name = "count";
    count.column = Template::Column::kUnit;
    count.w.assign(nd, 1);
    ts.push_back(count);

    Template sum;
    sum.name = "sum";
    sum.column = Template::Column::kValue;
    sum.w.assign(nd, 1);
    ts.push_back(sum);

    // A per-sensor-band sum: records whose value falls in the upper half of the
    // observed range contribute, the rest do not.  A fixed 0/1 plaintext weight
    // vector, registered at setup exactly as the paper describes.
    uint64_t lo = UINT64_MAX, hi = 0;
    for (uint64_t v : ds.values) { lo = std::min(lo, v); hi = std::max(hi, v); }
    const uint64_t mid = ds.values.empty() ? 0 : lo + (hi - lo) / 2;
    Template band;
    band.name = "band_sum";
    band.column = Template::Column::kValue;
    band.w.resize(nd);
    for (uint64_t i = 0; i < nd; ++i) band.w[i] = ds.values[i] >= mid ? 1u : 0u;
    ts.push_back(band);

    // A fixed plaintext-weighted inner product.
    std::mt19937_64 rng(seed);
    Template wsum;
    wsum.name = "wsum";
    wsum.column = Template::Column::kValue;
    wsum.w.resize(nd);
    for (uint64_t i = 0; i < nd; ++i) wsum.w[i] = 1 + rng() % 8;
    ts.push_back(wsum);

    return ts;
}

// ---------------------------------------------------------------------------
// Provider state
// ---------------------------------------------------------------------------

ProviderState build_provider_state(const Owner& owner, const HeBackend& he,
                                   const std::vector<Template>& templates,
                                   bool with_general, int threads) {
    const Dataset& ds = owner.dataset();
    const Modulus& mod = owner.modulus();
    ProviderState st;
    st.n_tags = ds.n_tags;
    st.n_records = ds.n_records;

    // Encrypted record columns.
    std::vector<uint64_t> mvals(st.n_records), mmac(st.n_records);
    std::vector<uint64_t> ones(st.n_records, 1), onemac(st.n_records, owner.delta());
    for (uint64_t i = 0; i < st.n_records; ++i) {
        mvals[i] = mod.from_u64(ds.values[i]);
        mmac[i] = mod.mul(mvals[i], owner.delta());
    }
    st.value = he.encrypt_vector(mvals);
    st.value_mac = he.encrypt_vector(mmac);
    st.unit = he.encrypt_vector(ones);
    st.unit_mac = he.encrypt_vector(onemac);

    for (const auto& f : templates) {
        FastColumns fc;
        const std::vector<uint64_t> A = owner.compute_A(f);
        fc.A = he.encrypt_vector(A);
        fc.A_mac = he.encrypt_vector(owner.scale(A, owner.delta()));
        st.fast[f.name] = std::move(fc);

        if (with_general) {
            GenColumns gc;
            const std::vector<uint64_t> U = owner.compute_U(f, st.n_records, threads);
            gc.U = he.encrypt_vector(U);
            gc.U_mac = he.encrypt_vector(owner.scale(U, owner.delta()));
            st.gen[f.name] = std::move(gc);
        }
    }

    if (with_general) st.masked_index = owner.build_masked_index(st.n_records, threads);
    return st;
}

}  // namespace crshe
