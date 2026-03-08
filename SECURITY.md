# Security Design Document

This document describes the security architecture of mcp-feed-reader-crunchtools.

## 1. Threat Model

### 1.1 Assets to Protect

| Asset | Sensitivity | Impact if Compromised |
|-------|-------------|----------------------|
| SQLite Database | Medium | Feed subscriptions, read state exposed |
| Feed Content | Low | Publicly available RSS/Atom content |
| OPML Files | Low | Feed subscription list exposed |

### 1.2 Threat Actors

| Actor | Capability | Motivation |
|-------|------------|------------|
| Malicious AI Agent | Can craft tool inputs | Data exfiltration, path traversal |
| Local Attacker | Access to filesystem | Database tampering |
| Malicious Feed | Crafted RSS/XML content | XXE injection, content injection |

### 1.3 Attack Vectors

| Vector | Description | Mitigation |
|--------|-------------|------------|
| **Path Traversal** | Manipulated file paths in OPML import | Input validation |
| **XXE Injection** | Crafted XML in RSS feeds | feedparser handles safely |
| **SQL Injection** | Crafted tool inputs | Parameterized queries only |
| **Denial of Service** | Fetch extremely large feeds | Response size limits (10MB) |
| **SSRF** | Feed URL pointing to internal services | User-initiated only |
| **Content Injection** | Malicious HTML in feed content | Content stored as-is, rendering is client responsibility |

## 2. Security Architecture

### 2.1 Defense in Depth Layers

```
+---------------------------------------------------------+
| Layer 1: Input Validation                                |
| - Pydantic models for all tool inputs                   |
| - Reject unexpected fields (extra="forbid")             |
| - Field length limits                                    |
+---------------------------------------------------------+
| Layer 2: Database Security                               |
| - Parameterized queries only (no string formatting)     |
| - WAL mode for concurrent safety                        |
| - Foreign keys enforced                                  |
+---------------------------------------------------------+
| Layer 3: Network Hardening                               |
| - httpx with timeout enforcement (30s)                  |
| - Response size limits (10MB)                            |
| - Follow redirects (max 5)                               |
| - Custom User-Agent for feed fetching                    |
+---------------------------------------------------------+
| Layer 4: Runtime Protection                              |
| - No shell execution (subprocess)                        |
| - No dynamic code evaluation (eval/exec)                |
| - Type-safe with Pydantic                                |
| - SQLite FTS5 for search (no raw SQL from user input)   |
+---------------------------------------------------------+
| Layer 5: Supply Chain Security                           |
| - Automated CVE scanning via GitHub Actions             |
| - Container built on Hummingbird for minimal CVEs       |
| - Weekly dependency audits                               |
+---------------------------------------------------------+
```

### 2.2 No Credentials

This server has no API tokens or credentials. It fetches publicly available RSS/Atom feeds over HTTP/HTTPS. The primary security concern is input validation and safe XML parsing.

### 2.3 Input Validation Rules

All inputs are validated:

- **URLs**: Must be valid HTTP/HTTPS URLs
- **Feed IDs**: Integer only
- **Entry IDs**: Integer only
- **Search queries**: FTS5 syntax (safe by design)
- **OPML paths**: Filesystem paths (validated by OS)
- **Limits**: Bounded 1-500
- **Extra Fields**: Rejected (Pydantic extra="forbid")

## 3. Supply Chain Security

### 3.1 Automated CVE Scanning

This project uses GitHub Actions to automatically scan for CVEs:

1. **Weekly Scheduled Scans**: Every Monday at 9 AM UTC
2. **PR Checks**: Every pull request is scanned before merge
3. **Dependabot**: Enabled for automatic security updates

### 3.2 Container Security

The container image is built on **[Hummingbird Python](https://quay.io/repository/hummingbird/python)** from [Project Hummingbird](https://github.com/hummingbird-project):

| Advantage | Description |
|-----------|-------------|
| **Minimal CVE Count** | Dramatically reduced attack surface |
| **Rapid Security Updates** | Security patches applied promptly |
| **Python Optimized** | Pre-configured with uv package manager |
| **Non-Root Default** | Runs as non-root user |
| **Production Ready** | Proper signal handling, minimal footprint |

## 4. Security Checklist

Before each release:

- [ ] All inputs validated through Pydantic models
- [ ] No filesystem operations beyond SQLite database
- [ ] No shell execution
- [ ] No eval/exec
- [ ] Error messages don't leak internals
- [ ] Dependencies scanned for CVEs
- [ ] Container rebuilt with latest Hummingbird base

## 5. Reporting Security Issues

Report security vulnerabilities using [GitHub's private security advisory](https://github.com/crunchtools/mcp-feed-reader/security/advisories/new). This creates a private channel visible only to maintainers.

Do NOT open public issues for security vulnerabilities.
