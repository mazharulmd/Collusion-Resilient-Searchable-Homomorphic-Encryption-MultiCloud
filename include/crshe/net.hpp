// SPDX-License-Identifier: Apache-2.0
//
// Minimal length-prefixed TCP framing for the multi-cloud deployment.
//
// Deliberately plain sockets and no TLS: the paper's channel assumption is that
// links are authenticated and confidential, and adding a TLS handshake here
// would fold session setup into every latency measurement. Wrap these
// processes in a TLS terminator (or a WireGuard tunnel) for anything other
// than benchmarking, and say which was used when reporting numbers.

#pragma once

#include <arpa/inet.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace crshe {

inline void send_all(int fd, const void* buf, size_t n) {
    const char* p = (const char*)buf;
    while (n) {
        const ssize_t k = ::send(fd, p, n, MSG_NOSIGNAL);
        if (k <= 0) throw std::runtime_error("send failed");
        p += k;
        n -= (size_t)k;
    }
}

inline void recv_all(int fd, void* buf, size_t n) {
    char* p = (char*)buf;
    while (n) {
        const ssize_t k = ::recv(fd, p, n, 0);
        if (k <= 0) throw std::runtime_error("connection closed");
        p += k;
        n -= (size_t)k;
    }
}

inline void send_msg(int fd, const std::string& s) {
    // One write, not two.  Sending the 8-byte length prefix separately from the
    // payload interacts with Nagle and delayed ACK and adds tens of
    // milliseconds per frame on an otherwise idle link -- which would show up
    // in E3 as wide-area transport that is really a local stack artefact.
    std::string frame;
    frame.reserve(8 + s.size());
    const uint64_t len = s.size();
    frame.append((const char*)&len, 8);
    frame.append(s);
    send_all(fd, frame.data(), frame.size());
}

inline std::string recv_msg(int fd) {
    uint64_t len = 0;
    recv_all(fd, &len, 8);
    if (len > (1ULL << 32)) throw std::runtime_error("message too large");
    std::string s(len, '\0');
    if (len) recv_all(fd, &s[0], len);
    return s;
}

inline int tcp_listen(uint16_t port) {
    const int fd = ::socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) throw std::runtime_error("socket failed");
    int one = 1;
    ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    sockaddr_in a{};
    a.sin_family = AF_INET;
    a.sin_addr.s_addr = INADDR_ANY;
    a.sin_port = htons(port);
    if (::bind(fd, (sockaddr*)&a, sizeof a) < 0)
        throw std::runtime_error("bind failed on port " + std::to_string(port));
    if (::listen(fd, 16) < 0) throw std::runtime_error("listen failed");
    return fd;
}

inline int tcp_accept(int listen_fd) {
    const int fd = ::accept(listen_fd, nullptr, nullptr);
    if (fd < 0) return fd;
    int one = 1;
    ::setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
    return fd;
}

inline int tcp_connect(const std::string& host, uint16_t port) {
    addrinfo hints{}, *res = nullptr;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    const std::string p = std::to_string(port);
    if (::getaddrinfo(host.c_str(), p.c_str(), &hints, &res) != 0)
        throw std::runtime_error("cannot resolve " + host);
    const int fd = ::socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (fd < 0) { ::freeaddrinfo(res); throw std::runtime_error("socket failed"); }
    if (::connect(fd, res->ai_addr, res->ai_addrlen) < 0) {
        ::freeaddrinfo(res);
        ::close(fd);
        throw std::runtime_error("cannot connect to " + host + ":" + p);
    }
    ::freeaddrinfo(res);
    int one = 1;
    ::setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
    return fd;
}

}  // namespace crshe
