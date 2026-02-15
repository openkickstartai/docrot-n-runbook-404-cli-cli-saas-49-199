# 🦷 DocRot — Documentation Rot Detection Engine

Detect stale docs before your team follows an expired Runbook at 3 AM.

DocRot scans your repo's Markdown files, finds every broken link, every reference to deleted code, and every code snippet that no longer matches reality.

## 🚀 Quick Start

```bash
pip install -e .

# Scan current repo
docrot .

# JSON output for CI
docrot . -f json

# SARIF for GitHub Code Scanning
docrot . -f sarif > docrot.sarif

# Check external URLs (Team+ feature)
docrot . --check-urls
```

## What It Detects

| Check | Description | Tier |
|-------|-------------|------|
| 🔗 Broken Links | Internal links to deleted/moved files | Free |
| 🏷️ Stale Symbols | `import` references to missing modules | Free |
| 📝 Code Drift | Code blocks referencing non-existent code | Free |
| 🌐 Dead URLs | External links returning 404 | Team |
| 📊 SARIF Output | GitHub Code Scanning integration | Free |

## 📊 Why Teams Pay For DocRot

- **$49/mo vs 2 wasted onboarding days** — one engineer's daily rate ($400+) covers a year of DocRot
- **$149/mo vs extended P1 incidents** — one wrong Runbook step at 3 AM costs more than annual subscription
- **SOC2 compliance** — auditors ask "when was this doc last reviewed?" — DocRot answers automatically
- **$49/mo is credit-card swipeable** — no procurement process needed

## 💰 Pricing

| | **Free (OSS)** | **Team $49/mo** | **Business $149/mo** | **Enterprise $499/mo** |
|---|---|---|---|---|
| Repos | 1 | 5 | 30 | Unlimited |
| Max docs | 50 | Unlimited | Unlimited | Unlimited |
| Broken links | ✅ | ✅ | ✅ | ✅ |
| Stale symbols | ✅ | ✅ | ✅ | ✅ |
| Code drift | ✅ | ✅ | ✅ | ✅ |
| External URL check | ❌ | ✅ | ✅ | ✅ |
| SARIF + JSON output | ✅ | ✅ | ✅ | ✅ |
| GitHub PR comments | ❌ | ✅ | ✅ | ✅ |
| Slack alerts | ❌ | ✅ | ✅ | ✅ |
| Auto-create issues | ❌ | ❌ | ✅ | ✅ |
| SOC2 compliance PDF | ❌ | ❌ | ✅ | ✅ |
| SSO + audit log | ❌ | ❌ | ❌ | ✅ |
| Self-hosted | ❌ | ❌ | ❌ | ✅ |

## CI Integration

```yaml
# .github/workflows/docrot.yml
name: DocRot
on: [pull_request]
jobs:
  docrot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e .
      - run: docrot . -f sarif > docrot.sarif
      - uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: docrot.sarif }
        if: always()
```

## License

MIT — free CLI forever. Paid tiers at [docrot.dev](https://docrot.dev).
