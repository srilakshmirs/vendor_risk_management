---
marp: true
theme: default
paginate: true
backgroundColor: '#fafafa'
header: '**VRM Intelligence** · Société Générale TPRM · Option A'
footer: 'Hackathon Submission · 2026'
style: |
  section {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    color: #18181b;
    padding: 60px 70px;
  }
  section.lead {
    background: linear-gradient(135deg, #fafafa 0%, #fff7ed 60%, #fef2f2 100%);
  }
  h1 {
    color: #dc2626;
    border-bottom: 3px solid #dc2626;
    padding-bottom: 6px;
    font-weight: 700;
  }
  h2 {
    color: #18181b;
    border-bottom: 1px solid #e4e4e7;
    padding-bottom: 4px;
    font-weight: 600;
  }
  strong { color: #dc2626; }
  code {
    background: #f4f4f5;
    color: #be123c;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.85em;
  }
  table { font-size: 0.85em; border-collapse: collapse; margin: 16px 0; }
  table th { background: #f4f4f5; color: #3f3f46; font-weight: 600; text-align: left; }
  table th, table td { border: 1px solid #e4e4e7; padding: 8px 12px; }
  blockquote {
    border-left: 4px solid #dc2626;
    background: #fff;
    padding: 12px 18px;
    font-style: italic;
    color: #52525b;
  }
  .kpi {
    display: inline-block;
    padding: 14px 22px;
    margin: 6px;
    border-radius: 12px;
    background: linear-gradient(135deg, #dc2626, #f59e0b);
    color: white;
    font-weight: 600;
    font-size: 1.1em;
  }
  .pass { color: #059669; font-weight: 700; }
  .fail { color: #dc2626; font-weight: 700; }
  .muted { color: #71717a; font-size: 0.85em; }
  header { color: #71717a; font-size: 0.7em; }
  footer { color: #a1a1aa; font-size: 0.7em; }
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _header: '' -->

# VRM Intelligence

## AI-Powered Third-Party Vendor Risk Management

**Société Générale TPRM Hackathon — Option A**

<br/>

400 vendors · continuous scoring · LLM-driven analyst
streaming Q&A · auto-generated audit packs

<br/>

<span class="muted">Solo submission · all 5 rubric metrics measured & passing</span>

<!--
Open with confidence. The hook: "5 out of 5 rubric metrics passing — and I'll show you the numbers." Don't apologize for anything. This is a 3-minute pitch, every second counts.
-->

---

# The problem

> *"60% of data breaches involve third parties."*

Société Générale tracks **1,000+ vendors** today — cloud providers, contractors, SaaS, integration partners, payment processors. The current state:

- 📊 Risk lives in **spreadsheets** — inconsistent, outdated, no shared truth
- 🚨 No **standardized scoring** — every analyst makes their own call
- ⏰ Quarterly manual reviews **don't scale** to a 1,000-vendor portfolio
- 🔍 Auditors ask *"is vendor X compliant?"* — answer takes **days**, not minutes
- 📑 **GDPR Art 28/33**, **NIST SP 800-53 SA-9**, **SOX 404** all demand evidence that's hard to produce

**Real-world incidents from the brief:**
- Vendor breach with no PII notification due to unclear contracts
- Contractor access never revoked post-project; data sold to competitor
- Payment processor downgraded security, exposed during PCI-DSS audit

<!--
The 60% stat is from the brief itself. Mention it. Make the pain concrete with the real-world incidents — judges (especially the SocGen TPRM team) will recognize all of these as things they've actually seen. Don't dwell here — 30 seconds max.
-->

---

# The solution — VRM Intelligence

| Capability | What it does |
|---|---|
| **Risk scoring engine** | 5-component composite + 7-rule classifier, deterministic, sub-millisecond per vendor |
| **Continuous monitoring** | 5 scheduled jobs: cert/contract expiry, breach feed, financial scrape, SOC2 verify, daily rescore |
| **LLM contract intelligence** | Upload a PDF → structured data access, SLA, renewal date, termination clauses |
| **Streaming Q&A** | *"Which vendors have CRITICAL risk and handle PII?"* — answers with clickable `[V0276]` citations |
| **AI risk narratives** | LLM-rewritten with specific dates + GDPR/NIST/SOX references |
| **One-click audit pack** | 2-page styled PDF per vendor — covers every signal an auditor asks for |

**Differentiator:** every LLM feature works on **local Ollama (free) or Anthropic Claude (production)** — single env-var toggle. Provider-agnostic.

<!--
This is the "what's in the box" slide. Don't read it word-for-word — point at the table, say "every Option A capability from the brief, plus the AI features that make it more than a dashboard." Move quickly to the rubric.
-->

---

# The rubric — **5 / 5 measured**

| Rubric metric | Target | **Measured** |
|---|---|---|
| Vendor coverage | ≥ 95% | <span class="pass">100% (400 / 400)</span> |
| Risk-assessment accuracy | ≥ 80% | <span class="pass">90% anomaly · 100% CRITICAL recall · 100% HIGH recall · F1 1.000</span> |
| Alert lead time | ≥ 30 days | <span class="pass">60 / 30 / 7-day cascade (APScheduler)</span> |
| Q&A response time | ≤ 5 min | <span class="pass">~3 s on Ollama · ~1 s on Claude Haiku</span> |
| Audit report generation | ≤ 15 min | <span class="pass">~250 ms per PDF (reportlab)</span> |

> Reproducible: `make eval` runs the full harness against the provided `vendor_labels.csv` and prints PASS/FAIL per gate. Regression-gated in CI.

**The judging line that matters**: *"Recall on CRITICAL/HIGH matters more than overall precision."* We hit **100%** on both — every breached high-access vendor is caught.

<!--
This is the headline. Slow down here. Pause after each row. Say "all measured, all reproducible — you can run `make eval` and see the same numbers." The 100% CRITICAL recall is the bullet that wins the rubric.
-->

---

# Architecture

```
Browser ─→ Next.js 16 ─REST+SSE─→ FastAPI ─→ Postgres 16 + pgvector
                                     │                  ↑ HNSW cosine
                                     ├─→ Scoring engine (5 components + 7 rules)
                                     ├─→ RAG pipeline ─→ fastembed (384-dim ONNX)
                                     ├─→ Audit PDF (reportlab)
                                     └─→ APScheduler ─→ 5 jobs
                                              │       expiry · breach · financial
                                              │       cert-verify · daily rescore
                                              └─→ LLM (provider-switchable)
                                                  Ollama llama3.2 / Claude / mock
```

| Layer | Choice | Why |
|---|---|---|
| **Web** | Next.js 16 · React 19 · Tailwind 4 · framer-motion · SWR · recharts | Fast iteration, polished motion, type-safe end-to-end |
| **API** | FastAPI · SQLAlchemy 2.0 · structlog · `uv` | Auto OpenAPI, JSON-structured logs, fast Python deps |
| **DB** | Postgres 16 + **pgvector** (HNSW) | Single store for relational + vector — no two-DB tax |
| **Embeddings** | `fastembed` BAAI/bge-small-en-v1.5 | Local, deterministic, zero external services |
| **LLM** | Env-switchable: Ollama · Claude · mock | Demo runs free locally, prod runs on Claude — single env var |
| **PDF** | reportlab | Pure Python, no Cairo/Pango install pain |

<!--
The ASCII diagram renders consistently across PDF/HTML/PPTX without depending on plugins. Point at the box, say "every dependency is justified — no fashion choices. Single Postgres instance for both relational and vector data, single LLM abstraction, single scheduler in the FastAPI lifespan."
-->

---

# Live demo — 90 seconds

**Pre-baked dataset**: `make demo-reset` (one command, ~14s) → 400 vendors, 95 alerts, 2 CRITICAL stories planted

1. **Portfolio overview** — *"All 5 rubric gates green, donut shows severity distribution"*
2. **Click "Poll breach feed"** in `/alerts` — *"watch the topbar pulse, two new CRITICAL alerts appear, affected vendor scores auto-rescore"*
3. **Ask the analyst** — type *"Which vendors are CRITICAL and handle PII?"* — *"tokens stream in real-time, every vendor reference is a clickable citation"*
4. **Drill into V0276** (the ransomware vendor) — *"risk gauge sweeps to 85, AI-enhanced narrative mentions the June 8 breach + GDPR Art 33 72-hour clock"*
5. **Upload `sample-msa.pdf`** on the vendor page — *"LLM extracts 99.95% SLA, renewal date, termination clauses in ~10 seconds"*
6. **Export Audit Pack** — *"2-page styled PDF in under 300ms — every signal an auditor needs"*

> **Hero vendors are pre-enhanced** with AI narratives, so the first click already shows the LLM output with no wait.

<!--
This is the script for the live demo if you do one. Memorize the order. The "Poll breach feed" → CRITICAL pulse is the single most memorable visual — make sure judges see it. The contract upload is the AI wow moment.
-->

---

# Why we win

**Coverage:** 5 / 5 rubric metrics passing — **measured**, not estimated. Zero gaps from the Option A spec.

**Engineering quality:**
- 9 SQLAlchemy tables, 11 pytest tests, structured JSON logs, append-only `audit_logs` (SOX 404)
- Type-checked Next.js + Pydantic v2 throughout
- Regression-gated: CI fails if any rubric metric drops
- `make demo-reset` — one command rebuilds the demo dataset in 14 seconds

**AI surface area (5 features):**
1. LLM contract extraction (`/contracts/extract`)
2. LLM-enhanced risk narratives (`/risk/score/{id}/enhance`)
3. Streaming RAG Q&A (`/ask/stream` with pgvector retrieval)
4. Embedded vendor profiles (400 chunks, HNSW cosine top-K)
5. Automated breach + cert + financial-health re-evaluation

**Production-grade thinking:** provider abstraction · scheduler in lifespan · idempotent pollers · dedupe windows · graceful fallback when LLM fails · `WARMUP_ON_STARTUP` for cold-start kill · light/dark mode · loading skeletons.

> **GitHub:** _link goes here_  ·  **Live demo:** _URL goes here_  ·  **Video:** _Loom link goes here_

<!--
The closer. Don't be modest. Lead with "5 of 5 rubric metrics passing, measured." Then enumerate the AI features (count them on your fingers — 1, 2, 3, 4, 5 — judges remember concrete numbers). End with the GitHub link. Total pitch should land at 2:45 — leave 15 seconds for the obvious question: "show me the code."
-->
