// SPDX-License-Identifier: Apache-2.0
//
// Shared plumbing for the benchmark binaries: argument parsing, medians over
// repeated runs, CSV output, and the environment banner that every results file
// carries so a number can never be separated from the machine it came from.

#pragma once

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sys/stat.h>
#include <functional>
#include <iostream>
#include <map>
#include <numeric>
#include <sstream>
#include <string>
#include <type_traits>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

#include "crshe/aes_prg.hpp"
#include "crshe/he_backend.hpp"

namespace crshe {

// ---------------------------------------------------------------------------
// Arguments: --key=value and --flag
// ---------------------------------------------------------------------------
class Args {
public:
    Args(int argc, char** argv) {
        for (int i = 1; i < argc; ++i) {
            std::string a = argv[i];
            if (a.rfind("--", 0) != 0) { positional_.push_back(a); continue; }
            a = a.substr(2);
            const size_t eq = a.find('=');
            if (eq == std::string::npos) kv_[a] = "1";
            else kv_[a.substr(0, eq)] = a.substr(eq + 1);
        }
    }
    bool has(const std::string& k) const { return kv_.count(k) > 0; }
    std::string str(const std::string& k, const std::string& def = "") const {
        auto it = kv_.find(k);
        return it == kv_.end() ? def : it->second;
    }
    uint64_t u64(const std::string& k, uint64_t def) const {
        auto it = kv_.find(k);
        return it == kv_.end() ? def : std::strtoull(it->second.c_str(), nullptr, 10);
    }
    int i32(const std::string& k, int def) const { return (int)u64(k, (uint64_t)def); }
    double f64(const std::string& k, double def) const {
        auto it = kv_.find(k);
        return it == kv_.end() ? def : std::strtod(it->second.c_str(), nullptr);
    }
    bool flag(const std::string& k) const { return has(k) && kv_.at(k) != "0"; }
    // Comma-separated list of integers, e.g. --nd=1000,10000,100000
    std::vector<uint64_t> list(const std::string& k,
                               const std::vector<uint64_t>& def) const {
        auto it = kv_.find(k);
        if (it == kv_.end()) return def;
        std::vector<uint64_t> out;
        std::stringstream ss(it->second);
        std::string tok;
        while (std::getline(ss, tok, ',')) if (!tok.empty())
            out.push_back(std::strtoull(tok.c_str(), nullptr, 10));
        return out;
    }
    const std::vector<std::string>& positional() const { return positional_; }

private:
    std::map<std::string, std::string> kv_;
    std::vector<std::string> positional_;
};

// ---------------------------------------------------------------------------
// Timing
// ---------------------------------------------------------------------------
inline double now_ms() {
    using clk = std::chrono::steady_clock;
    return std::chrono::duration<double, std::milli>(clk::now().time_since_epoch()).count();
}

struct Stat {
    double median = 0, min = 0, max = 0, p25 = 0, p75 = 0;
    int reps = 0;
};

// Median over `reps` runs plus `warmup` discarded runs.  The paper asks for
// medians over at least ten runs with error bars; p25/p75 are what the plots
// draw, so the raw spread is always in the CSV rather than only a mean.
inline Stat repeat(int reps, const std::function<void()>& fn, int warmup = 1) {
    for (int i = 0; i < warmup; ++i) fn();
    std::vector<double> t;
    t.reserve(reps);
    for (int i = 0; i < reps; ++i) {
        const double t0 = now_ms();
        fn();
        t.push_back(now_ms() - t0);
    }
    std::sort(t.begin(), t.end());
    Stat s;
    s.reps = reps;
    s.min = t.front();
    s.max = t.back();
    s.median = t[t.size() / 2];
    s.p25 = t[t.size() / 4];
    s.p75 = t[(3 * t.size()) / 4];
    return s;
}

// ---------------------------------------------------------------------------
// CSV
// ---------------------------------------------------------------------------
class Csv {
public:
    Csv(const std::string& path, const std::vector<std::string>& cols)
        : cols_(cols) {
        mkdir_p(path);
        os_.open(path);
        if (!os_) throw std::runtime_error("cannot write " + path);
        for (size_t i = 0; i < cols.size(); ++i)
            os_ << cols[i] << (i + 1 < cols.size() ? "," : "\n");
        std::fprintf(stderr, "[csv] %s\n", path.c_str());
    }
    template <typename... T>
    void row(T... vals) {
        write_all(std::vector<std::string>{to_s(vals)...});
    }

private:
    static std::string to_s(const std::string& s) { return s; }
    static std::string to_s(const char* s) { return s; }
    static std::string to_s(double d) {
        char buf[64];
        std::snprintf(buf, sizeof buf, "%.6g", d);
        return buf;
    }
    template <typename T,
              typename = std::enable_if_t<std::is_integral<T>::value>>
    static std::string to_s(T v) { return std::to_string(v); }

    // Create the parent directory chain so a fresh clone does not have to
    // mkdir bench/results by hand before every run.
    static void mkdir_p(const std::string& file) {
        const size_t slash = file.find_last_of('/');
        if (slash == std::string::npos) return;
        std::string dir;
        for (size_t i = 0; i <= slash; ++i) {
            if (file[i] == '/' && !dir.empty()) ::mkdir(dir.c_str(), 0755);
            dir.push_back(file[i]);
        }
        if (!dir.empty()) ::mkdir(dir.c_str(), 0755);
    }

    // RFC 4180 quoting. Several fields are free-text notes that describe a
    // baseline's leakage, and those contain commas; without quoting they would
    // silently shift every later column when the CSV is parsed.
    static std::string quote(const std::string& s) {
        if (s.find_first_of(",\"\n\r") == std::string::npos) return s;
        std::string out = "\"";
        for (char c : s) {
            if (c == '"') out += "\"\"";
            else out += c;
        }
        out += '"';
        return out;
    }

    void write_all(const std::vector<std::string>& v) {
        if (v.size() != cols_.size())
            throw std::runtime_error("CSV row/header width mismatch");
        for (size_t i = 0; i < v.size(); ++i)
            os_ << quote(v[i]) << (i + 1 < v.size() ? "," : "\n");
        os_.flush();
    }
    std::ofstream os_;
    std::vector<std::string> cols_;
};

// ---------------------------------------------------------------------------
// Provenance banner
// ---------------------------------------------------------------------------
inline int max_threads() {
#ifdef _OPENMP
    return omp_get_max_threads();
#else
    return 1;
#endif
}

inline std::string cpu_model() {
    std::ifstream f("/proc/cpuinfo");
    std::string line;
    while (std::getline(f, line)) {
        if (line.rfind("model name", 0) == 0 || line.rfind("Model name", 0) == 0) {
            const size_t c = line.find(':');
            if (c != std::string::npos) {
                std::string s = line.substr(c + 1);
                while (!s.empty() && s.front() == ' ') s.erase(s.begin());
                return s;
            }
        }
    }
    return "unknown";
}

inline void banner(const char* tool) {
    std::fprintf(stderr,
                 "== CR-SHE %s ==\n"
                 "   cpu       : %s\n"
                 "   threads   : %d\n"
                 "   aes       : %s\n",
                 tool, cpu_model().c_str(), max_threads(), aes_backend());
}

// Every benchmark takes the same HE options, and every benchmark refuses to
// report HE numbers from the plaintext stand-in unless told to.
inline std::unique_ptr<HeBackend> he_from_args(const Args& a) {
    HeParams hp;
    hp.plaintext_modulus = a.u64("p", kDefaultModulus);
    hp.ring_dim = (uint32_t)a.u64("ringdim", 0);
    hp.depth = (uint32_t)a.u64("depth", 1);
    hp.security_bits = a.i32("sec", 128);
    const std::string kind = a.str("he", openfhe_available() ? "bfv-openfhe" : "plain");
    auto be = make_he_backend(kind, hp);
    if (!be->is_secure() && !a.flag("allow-insecure-he")) {
        std::fprintf(stderr,
                     "\nREFUSING TO RUN: the HE backend is '%s', which provides no\n"
                     "confidentiality. Numbers from it must not appear in the paper.\n"
                     "Build with OpenFHE (scripts/install_openfhe.sh), or pass\n"
                     "--allow-insecure-he to run it anyway for a correctness check;\n"
                     "rows produced that way are tagged he=plain in the CSV.\n\n");
        std::exit(2);
    }
    std::fprintf(stderr, "   he        : %s\n", be->param_string().c_str());
    return be;
}

}  // namespace crshe
