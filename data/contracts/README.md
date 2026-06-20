# Sample contract PDFs (demo data)

Two pre-generated PDFs you can drop into the **Upload PDF** widget on any vendor
detail page (`/vendors/Vxxxx`) to demo the `/contracts/extract` endpoint live.

| File | Purpose |
|---|---|
| `sample-msa.pdf` | Well-drafted Master Services Agreement. Every field the LLM extracts is explicitly present — judges see a clean, structured extraction. |
| `sample-msa-risky.pdf` | Intentionally vague contract. Several fields are missing or hedged — judges see the LLM correctly return `null` instead of hallucinating. |

## Expected extraction (good contract)

| Field | Value the LLM should return |
|---|---|
| `data_access_permissions` | PII, Financial transaction records, Internal metadata; Read + Write access |
| `compliance_obligations` | SOC 2 Type II, ISO/IEC 27001:2022, PCI-DSS v4.0, GDPR Art 28, NIST SP 800-53 SA-9, SOX 404 |
| `sla_uptime_percentage` | 99.95 |
| `renewal_date` | 2028-01-14 (auto-renewing) |
| `termination_conditions` | 30-day cure for material breach; immediate termination on cert loss, security incident, or insolvency; 30-day data return/destruction |

## Expected extraction (risky contract)

Most fields should come back `null` or empty list — the LLM is instructed not to
hallucinate. That's the demo beat: **"see how it refuses to invent terms that
aren't there."**

## Regenerate

```bash
make sample-contracts
```

Both files are produced by `generate_sample_contracts.py` (PEP-723 inline-deps
script, runs via `uv run`). Edit the script to add more samples or change the
fictional party names.
