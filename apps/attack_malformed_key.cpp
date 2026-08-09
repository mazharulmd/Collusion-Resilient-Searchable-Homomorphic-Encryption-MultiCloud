// SPDX-License-Identifier: Apache-2.0
//
// The attack of Section VI-F, made concrete.
//
// A client is supposed to submit DPF keys for a *point* function.  Nothing in
// a single BGI16 key distinguishes one from a key for an arbitrary function --
// the correction words are pseudorandom either way -- so a provider that only
// checks the key's shape will happily evaluate whatever it is given.  A client
// that submits shares of an arbitrary vector v instead of a point function
// receives sum_x v[x] * I'[x], i.e. an arbitrary linear combination of the
// masked index rows.  With N such queries the client recovers I' entirely, and
// since it also holds K' it recovers I.
//
// This binary mounts that attack against our own provider and reports how many
// queries full recovery takes, so the paper can state the cost of *not* having
// a well-formedness check rather than asserting that one exists.
//
//   build/attack_malformed_key --ntags=256 --nd=512 \
//                              --out=bench/results/e12_malformed_key.csv

#include <cstdio>
#include <random>
#include <vector>

#include "crshe/bench_util.hpp"
#include "crshe/dataset.hpp"
#include "crshe/index.hpp"
#include "crshe/protocol.hpp"

using namespace crshe;

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("attack_malformed_key (Section VI-F)");

    const uint64_t ntags = args.u64("ntags", 256);
    const uint64_t nd = args.u64("nd", 512);
    const std::string out = args.str("out", "bench/results/e12_malformed_key.csv");

    auto he = he_from_args(args);
    Modulus mod(he->plaintext_modulus());

    Dataset ds = Dataset::synthetic(ntags, nd, 1.1, 17);
    Owner owner(ds, mod, 1234);
    const auto templates = default_templates(ds, 7);
    ProviderState st = build_provider_state(owner, *he, templates, true);
    Provider prov(*he, st, mod);

    Csv csv(out, {"N", "Nd", "queries_issued", "index_rows_recovered",
                  "membership_bits_recovered", "recovery_rate_pct", "note"});

    std::mt19937_64 rng(31);
    std::vector<uint64_t> recovered(ntags * nd, 0);
    uint64_t queries = 0;

    // The malformed "keys": instead of shares of e_alpha, the client sends
    // shares of the standard basis vector e_x for x = 0..N-1 -- which is what
    // an honest client would send -- but also, crucially, could send shares of
    // *any* vector. We use the basis directly, which is the cheapest possible
    // full extraction: N queries, one row each.
    for (uint64_t x = 0; x < ntags; ++x) {
        std::vector<uint64_t> e_a(ntags), e_b(ntags);
        for (uint64_t i = 0; i < ntags; ++i) {
            e_a[i] = rng() % mod.value();
            e_b[i] = mod.sub(i == x ? 1u : 0u, e_a[i]);
        }
        // Each share is individually uniform, so neither provider can tell this
        // from an honest query: the attack is invisible per provider, and the
        // shape check in Dpf2::well_formed does not apply because the client
        // never has to produce a tree-shaped key at all.
        const auto ba = prov.contract_index(e_a.data());
        const auto bb = prov.contract_index(e_b.data());
        queries += 2;
        for (uint64_t i = 0; i < nd; ++i)
            recovered[x * nd + i] = mod.add(ba[i], bb[i]);
    }

    // The client holds K', so it strips the mask and reads off membership.
    uint64_t bits_ok = 0, rows_ok = 0;
    std::vector<uint64_t> p(nd);
    for (uint64_t x = 0; x < ntags; ++x) {
        owner.mask_row(x, nd, p.data());
        bool row_ok = true;
        for (uint64_t i = 0; i < nd; ++i) {
            const uint64_t bit = mod.sub(recovered[x * nd + i], p[i]);
            uint64_t want = 0;
            for (uint64_t k = ds.offset[x]; k < ds.offset[x + 1]; ++k)
                if (ds.postings[k] == i) want = 1;
            if (bit == want) ++bits_ok;
            else row_ok = false;
        }
        if (row_ok) ++rows_ok;
    }

    const double rate = 100.0 * (double)bits_ok / (double)(ntags * nd);
    csv.row(ntags, nd, queries, rows_ok, bits_ok, rate,
            "malformed-key extraction against a provider with no well-formedness "
            "check; 2N queries recover the whole index");
    std::fprintf(stderr,
                 "\nRecovered %llu/%llu index rows and %.1f%% of membership bits "
                 "in %llu queries.\n"
                 "This is what an unauthenticated client can do today. The shape\n"
                 "check in Dpf2::well_formed does NOT prevent it -- closing it\n"
                 "requires a verifiable DPF or a PACL-style authorisation proof,\n"
                 "which this artefact does not implement. Report it as an open\n"
                 "requirement, not as a solved problem.\n",
                 (unsigned long long)rows_ok, (unsigned long long)ntags, rate,
                 (unsigned long long)queries);
    return 0;
}
