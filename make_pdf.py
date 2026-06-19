from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", size=12)
pdf.multi_cell(0, 10, """Master Services Agreement between Société Générale and CloudCorp.

Data Access:
CloudCorp shall have access to PII and Financial data only in the staging environment.

Compliance:
Vendor must maintain SOC 2 Type II and ISO 27001 certifications.

SLA:
The guaranteed uptime is 99.99%.

Term:
This agreement renews on 2025-08-15.

Termination:
Either party may terminate with 30 days written notice.
""")
pdf.output("mock_contract.pdf")
