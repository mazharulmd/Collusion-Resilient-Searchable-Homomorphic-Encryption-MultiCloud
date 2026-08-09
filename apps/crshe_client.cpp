// SPDX-License-Identifier: Apache-2.0
//
// E3: end-to-end query latency across a real multi-cloud deployment,
// decomposed into provider compute, wide-area transport, and client
// combine/decrypt.
//
//   build/crshe_client --bundle=deploy \
//                      --providers=aws-eu.example:9101,gcp-us.example:9101 \
//                      --queries=100 --out=bench/results/e3_wan.csv
//
// The decomposition is: the provider reports its own compute time inside the
// response, the client measures wall-clock round-trip, and transport is the
// difference.  Providers are queried in parallel, so the query's provider-side
// cost is the slowest one, not the sum -- reporting the sum would misstate a
// deployment that is genuinely parallel.
//
// Bare round-trip time to each provider is measured separately with a ping
// frame and recorded, so a reader can tell transport from compute without
// trusting the subtraction.

#include <algorithm>
#include <cstdio>
#include <fstream>
#include <future>
#include <random>
#include <sstream>
#include <vector>

#include "crshe/bench_util.hpp"
#include "crshe/net.hpp"
#include "crshe/protocol.hpp"

using namespace crshe;

namespace {

std::string read_file(const std::string& path) {
    std::ifstream is(path, std::ios::binary);
    if (!is) throw std::runtime_error("cannot open " + path);
    std::ostringstream ss;
    ss << is.rdbuf();
    return ss.str();
}

std::map<std::string, std::string> read_meta(const std::string& path) {
    std::map<std::string, std::string> m;
    std::ifstream is(path);
    std::string line;
    while (std::getline(is, line)) {
        const size_t eq = line.find('=');
        if (eq != std::string::npos) m[line.substr(0, eq)] = line.substr(eq + 1);
    }
    return m;
}

std::vector<std::string> split(const std::string& s, char c) {
    std::vector<std::string> out;
    std::stringstream ss(s);
    std::string tok;
    while (std::getline(ss, tok, c)) if (!tok.empty()) out.push_back(tok);
    return out;
}

struct Endpoint {
    std::string host;
    uint16_t port;
    int fd = -1;
};

double median(std::vector<double> v) {
    if (v.empty()) return 0;
    std::sort(v.begin(), v.end());
    return v[v.size() / 2];
}
double pct(std::vector<double> v, double q) {
    if (v.empty()) return 0;
    std::sort(v.begin(), v.end());
    return v[std::min(v.size() - 1, (size_t)(q * v.size()))];
}

}  // namespace

int main(int argc, char** argv) {
    Args args(argc, argv);
    banner("crshe_client (E3)");

    const std::string bundle = args.str("bundle", "deploy");
    const std::string tmpl = args.str("template", "sum");
    const int queries = args.i32("queries", 100);
    const std::string out = args.str("out", "bench/results/e3_wan.csv");
    const std::string label = args.str("label", "unlabelled-deployment");

    const auto meta = read_meta(bundle + "/public/meta.txt");
    const std::string kind = meta.count("he_kind") ? meta.at("he_kind") : "bfv-openfhe";
    auto he = load_he_backend(kind, read_file(bundle + "/public/he_public.bin"),
                              read_file(bundle + "/secret/he_secret.bin"));
    Modulus mod(he->plaintext_modulus());
    const uint64_t n_tags = std::strtoull(meta.at("n_tags").c_str(), nullptr, 10);

    uint64_t delta = 0;
    for (const auto& kv : read_meta(bundle + "/secret/owner.txt"))
        if (kv.first == "delta") delta = std::strtoull(kv.second.c_str(), nullptr, 10);

    std::vector<Endpoint> eps;
    for (const auto& s : split(args.str("providers", "127.0.0.1:9101,127.0.0.1:9102"),
                               ',')) {
        const size_t c = s.rfind(':');
        eps.push_back({s.substr(0, c), (uint16_t)std::stoi(s.substr(c + 1))});
    }
    const uint32_t n = (uint32_t)eps.size();
    for (auto& e : eps) {
        e.fd = tcp_connect(e.host, e.port);
        std::fprintf(stderr, "   connected to %s:%u\n", e.host.c_str(), e.port);
    }

    // Bare round-trip time per provider, measured before any query so that
    // transport is not inferred solely by subtraction.
    std::vector<double> rtt(n, 0);
    for (uint32_t j = 0; j < n; ++j) {
        std::vector<double> samples;
        for (int i = 0; i < 20; ++i) {
            const double t0 = now_ms();
            send_msg(eps[j].fd, "ping");
            (void)recv_msg(eps[j].fd);
            samples.push_back(now_ms() - t0);
        }
        rtt[j] = median(samples);
        std::fprintf(stderr, "   rtt to %s:%u = %.3f ms\n", eps[j].host.c_str(),
                     eps[j].port, rtt[j]);
    }

    Csv csv(out, {"deployment", "n_providers", "N", "template", "query_index",
                  "end_to_end_ms", "provider_compute_ms_max", "transport_ms",
                  "client_combine_decrypt_ms", "uplink_bytes_total",
                  "downlink_bytes_total", "mac_ok", "he_params", "provider_list",
                  "rtt_ms_max"});

    DpfScheme scheme(mod, n, n_tags);
    std::mt19937_64 rng(9);
    std::vector<double> e2e, comp, trans, comb;

    for (int q = 0; q < queries; ++q) {
        Token tok;
        const double tgen = now_ms();
        scheme.gen(rng() % n_tags, 1, tok);
        (void)tgen;

        size_t uplink = 0;
        const double t0 = now_ms();
        std::vector<std::future<std::pair<double, std::pair<std::string, std::string>>>>
            futs;
        for (uint32_t j = 0; j < n; ++j) {
            const std::string blob = serialize_token_key(tok, j);
            uplink += blob.size();
            futs.push_back(std::async(std::launch::async, [fd = eps[j].fd, &tmpl, j,
                                                           blob] {
                send_msg(fd, "agg");
                send_msg(fd, tmpl);
                send_msg(fd, std::to_string(j));
                send_msg(fd, blob);
                const double ms = std::strtod(recv_msg(fd).c_str(), nullptr);
                std::string a = recv_msg(fd);
                std::string b = recv_msg(fd);
                return std::make_pair(ms, std::make_pair(std::move(a), std::move(b)));
            }));
        }

        double compute_max = 0;
        size_t downlink = 0;
        std::vector<AggResponse> resp;
        for (auto& f : futs) {
            auto r = f.get();
            compute_max = std::max(compute_max, r.first);
            downlink += r.second.first.size() + r.second.second.size();
            AggResponse ar;
            ar.ct = he->deserialize(r.second.first);
            ar.ct_mac = he->deserialize(r.second.second);
            resp.push_back(ar);
        }
        const double t_net = now_ms() - t0;

        const double t1 = now_ms();
        const AggResult res = combine_dec(*he, mod, delta, resp);
        const double t_comb = now_ms() - t1;

        const double total = t_net + t_comb;
        const double transport = std::max(0.0, t_net - compute_max);

        e2e.push_back(total);
        comp.push_back(compute_max);
        trans.push_back(transport);
        comb.push_back(t_comb);

        csv.row(label, (uint64_t)n, n_tags, tmpl, (uint64_t)q, total, compute_max,
                transport, t_comb, (uint64_t)uplink, (uint64_t)downlink,
                res.mac_ok ? "true" : "false", he->param_string(),
                args.str("providers", ""), *std::max_element(rtt.begin(), rtt.end()));
    }

    std::fprintf(stderr,
                 "\n%s, n=%u providers, %d queries\n"
                 "  end-to-end        median %8.2f ms  [p25 %.2f, p75 %.2f]\n"
                 "  provider compute  median %8.2f ms  (slowest provider)\n"
                 "  wide-area transport median %6.2f ms\n"
                 "  client combine+decrypt   %8.2f ms\n",
                 label.c_str(), n, queries, median(e2e), pct(e2e, 0.25),
                 pct(e2e, 0.75), median(comp), median(trans), median(comb));

    for (auto& e : eps) ::close(e.fd);
    return 0;
}
