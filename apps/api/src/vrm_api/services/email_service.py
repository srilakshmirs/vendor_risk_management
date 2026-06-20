"""Email notification service — sends alerts for CRITICAL/HIGH risk issues and resolutions.

Supports two modes:
  - **smtp**: Real email via smtplib (Gmail, SendGrid, AWS SES, etc.)
  - **console**: Logs the email to stdout/structlog (for testing/demos without SMTP credentials)

All sends run in background threads via ``asyncio.to_thread`` so they never block
the API event loop. Failures are logged but never propagated — the scoring pipeline
is never disrupted by email issues.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from ..config import get_settings
from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..models import Alert, Vendor
    from ..scoring.engine import ScoredVendor

log = get_logger(__name__)

# Severity thresholds that trigger emails
_EMAIL_SEVERITIES = {"CRITICAL", "HIGH"}


# ── Low-level SMTP sender ────────────────────────────────────────────

def _send_smtp(to: list[str], subject: str, html_body: str) -> None:
    """Send an HTML email via SMTP. Runs synchronously — call from a thread."""
    s = get_settings()

    msg = MIMEMultipart("alternative")
    msg["From"] = s.email_from
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if s.smtp_use_tls:
            ctx = ssl.create_default_context()
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as srv:
                srv.starttls(context=ctx)
                if s.smtp_user and s.smtp_password:
                    srv.login(s.smtp_user, s.smtp_password)
                srv.sendmail(s.email_from, to, msg.as_string())
        else:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as srv:
                if s.smtp_user and s.smtp_password:
                    srv.login(s.smtp_user, s.smtp_password)
                srv.sendmail(s.email_from, to, msg.as_string())
        log.info("email_sent", to=to, subject=subject)
    except Exception as exc:  # noqa: BLE001
        log.error("email_send_failed", to=to, subject=subject, error=str(exc))


def _send_console(to: list[str], subject: str, html_body: str) -> None:
    """Mock sender — logs the email to console for testing."""
    log.info(
        "email_console_mock",
        to=to,
        subject=subject,
        body_preview=html_body[:500].replace("\n", " "),
    )
    print(f"\n{'='*70}")
    print(f"📧 EMAIL NOTIFICATION (console mock)")
    print(f"{'='*70}")
    print(f"  To:      {', '.join(to)}")
    print(f"  Subject: {subject}")
    print(f"{'─'*70}")
    # Strip HTML tags for a rough console preview
    import re
    text = re.sub(r'<[^>]+>', ' ', html_body)
    text = re.sub(r'\s+', ' ', text).strip()
    print(f"  {text[:1000]}")
    print(f"{'='*70}\n")


def send_email(to: list[str], subject: str, html_body: str) -> None:
    """Route to SMTP or console depending on config."""
    s = get_settings()
    if not s.email_enabled:
        return
    if not to:
        log.warning("email_no_recipients", subject=subject)
        return

    if s.email_mode == "console":
        _send_console(to, subject, html_body)
    else:
        _send_smtp(to, subject, html_body)


async def send_email_async(to: list[str], subject: str, html_body: str) -> None:
    """Non-blocking wrapper — dispatches to a thread."""
    await asyncio.to_thread(send_email, to, subject, html_body)


def send_email_fire_and_forget(to: list[str], subject: str, html_body: str) -> None:
    """Best-effort send from sync code (scheduler jobs, CLI). Uses a new event loop if needed."""
    s = get_settings()
    if not s.email_enabled or not to:
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(send_email_async(to, subject, html_body))
    except RuntimeError:
        # No running loop — just send synchronously (scheduler jobs are already in threads)
        send_email(to, subject, html_body)


# ── Recipient resolution ─────────────────────────────────────────────

def _resolve_recipients(vendor: Vendor | None = None) -> list[str]:
    """Build recipient list from admin list + optional vendor contact."""
    s = get_settings()
    recipients = list(s.email_admin_recipients)
    if s.email_send_to_vendor_contact and vendor and vendor.primary_contact_email:
        if vendor.primary_contact_email not in recipients:
            recipients.append(vendor.primary_contact_email)
    return recipients


# ── HTML Template Helpers ─────────────────────────────────────────────

_SEVERITY_COLORS = {
    "CRITICAL": ("#DC2626", "🔴"),
    "HIGH": ("#EA580C", "🟠"),
    "MEDIUM": ("#CA8A04", "🟡"),
    "LOW": ("#2563EB", "🔵"),
    "NONE": ("#16A34A", "🟢"),
}

_TRAFFIC_LIGHT_COLORS = {
    "Red": "#DC2626",
    "Yellow": "#CA8A04",
    "Green": "#16A34A",
}


def _base_html(title_icon: str, title_text: str, title_color: str, body_rows: str) -> str:
    """Shared HTML email skeleton."""
    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
  <!-- Header -->
  <tr>
    <td style="background:{title_color};padding:24px 32px;">
      <span style="font-size:28px;vertical-align:middle;">{title_icon}</span>
      <span style="color:#ffffff;font-size:20px;font-weight:700;vertical-align:middle;margin-left:12px;">{title_text}</span>
    </td>
  </tr>
  <!-- Body -->
  <tr>
    <td style="padding:32px;">
      {body_rows}
    </td>
  </tr>
  <!-- Footer -->
  <tr>
    <td style="background:#f8fafc;padding:16px 32px;border-top:1px solid #e2e8f0;">
      <p style="margin:0;color:#94a3b8;font-size:12px;">
        VRM Intelligence &mdash; Société Générale TPRM Hackathon<br>
        Sent at {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
      </p>
    </td>
  </tr>
</table>
</td></tr></table>
</body>
</html>"""


def _info_row(label: str, value: str, color: str | None = None) -> str:
    val_style = f"color:{color};font-weight:700;" if color else "color:#1e293b;"
    return f"""\
    <tr>
      <td style="padding:6px 0;color:#64748b;font-size:14px;width:180px;vertical-align:top;">{label}</td>
      <td style="padding:6px 0;font-size:14px;{val_style}">{value}</td>
    </tr>"""


def _section_divider() -> str:
    return '<tr><td colspan="2" style="padding:12px 0;"><hr style="border:none;border-top:1px solid #e2e8f0;"></td></tr>'


# ── Escalation Email (CRITICAL/HIGH detected) ────────────────────────

def build_risk_alert_html(scored: ScoredVendor, vendor: Vendor) -> str:
    """Build rich HTML email for a CRITICAL/HIGH risk detection."""
    sev_color, sev_icon = _SEVERITY_COLORS.get(scored.severity, ("#64748b", "⚪"))
    tl_color = _TRAFFIC_LIGHT_COLORS.get(scored.traffic_light, "#64748b")

    rows = f'<table width="100%" cellpadding="0" cellspacing="0">'

    # Vendor info
    rows += _info_row("Vendor", f"{vendor.name} ({vendor.vendor_id})")
    rows += _info_row("Criticality", vendor.criticality)
    rows += _info_row("Severity", f"{sev_icon} {scored.severity}", sev_color)
    rows += _info_row("Risk Score", f"<span style='font-size:24px;font-weight:800;color:{tl_color};'>{scored.score}/100</span>")
    if scored.anomaly_type and scored.anomaly_type != "NONE":
        rows += _info_row("Anomaly Type", scored.anomaly_type)

    # Component breakdown
    rows += _section_divider()
    rows += '<tr><td colspan="2" style="padding:8px 0;font-size:16px;font-weight:700;color:#1e293b;">Risk Component Breakdown</td></tr>'
    for comp_name, raw_val in scored.components.items():
        weighted_val = scored.weighted_components.get(comp_name, 0)
        bar_width = min(raw_val, 100)
        bar_color = "#DC2626" if raw_val >= 70 else "#CA8A04" if raw_val >= 40 else "#16A34A"
        rows += f"""\
    <tr>
      <td style="padding:4px 0;color:#64748b;font-size:13px;text-transform:capitalize;">{comp_name.replace('_', ' ')}</td>
      <td style="padding:4px 0;">
        <div style="display:inline-block;width:120px;height:8px;background:#e2e8f0;border-radius:4px;vertical-align:middle;">
          <div style="width:{bar_width}%;height:8px;background:{bar_color};border-radius:4px;"></div>
        </div>
        <span style="font-size:13px;color:#475569;margin-left:8px;">{raw_val} (wt: {weighted_val})</span>
      </td>
    </tr>"""

    # Triggered rules
    if scored.rule_hits:
        rows += _section_divider()
        rows += '<tr><td colspan="2" style="padding:8px 0;font-size:16px;font-weight:700;color:#1e293b;">Triggered Rules</td></tr>'
        for hit in scored.rule_hits:
            rows += f"""\
    <tr>
      <td style="padding:4px 0;color:#64748b;font-size:13px;">{hit.get('rule_id', '')}</td>
      <td style="padding:4px 0;font-size:13px;color:#1e293b;">{hit.get('rationale', '')}</td>
    </tr>"""

    # Narrative / recommended action
    if scored.narrative:
        rows += _section_divider()
        rows += f"""\
    <tr>
      <td colspan="2" style="padding:8px 0;">
        <div style="background:#fef2f2;border-left:4px solid {sev_color};padding:12px 16px;border-radius:4px;">
          <strong style="color:{sev_color};">Recommended Action</strong>
          <p style="margin:8px 0 0;color:#1e293b;font-size:14px;line-height:1.5;">{scored.narrative}</p>
        </div>
      </td>
    </tr>"""

    # Dashboard link
    rows += f"""\
    <tr>
      <td colspan="2" style="padding:20px 0 0;">
        <a href="http://localhost:3001/vendors/{vendor.vendor_id}" 
           style="display:inline-block;background:{sev_color};color:#fff;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">
          View in Dashboard →
        </a>
      </td>
    </tr>"""

    rows += "</table>"

    return _base_html(
        "⚠️", f"VRM RISK ALERT — {scored.severity}",
        sev_color, rows,
    )


def build_resolution_html(
    vendor: Vendor,
    previous_severity: str,
    new_severity: str,
    new_score: int | None = None,
    previous_score: int | None = None,
    reason: str = "Risk severity downgraded following re-scoring.",
) -> str:
    """Build HTML email for a resolved risk (severity dropped from CRITICAL/HIGH)."""
    prev_color, prev_icon = _SEVERITY_COLORS.get(previous_severity, ("#64748b", "⚪"))
    new_color, new_icon = _SEVERITY_COLORS.get(new_severity, ("#16A34A", "🟢"))

    rows = f'<table width="100%" cellpadding="0" cellspacing="0">'
    rows += _info_row("Vendor", f"{vendor.name} ({vendor.vendor_id})")
    rows += _info_row("Previous Severity", f"{prev_icon} {previous_severity}", prev_color)
    rows += _info_row("Current Severity", f"{new_icon} {new_severity}", new_color)
    rows += _info_row("Resolved At", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

    if new_score is not None:
        score_text = f"{new_score}/100"
        if previous_score is not None:
            score_text += f" (was {previous_score})"
        rows += _info_row("Updated Risk Score", score_text)

    rows += _section_divider()
    rows += f"""\
    <tr>
      <td colspan="2" style="padding:8px 0;">
        <div style="background:#f0fdf4;border-left:4px solid #16A34A;padding:12px 16px;border-radius:4px;">
          <strong style="color:#16A34A;">Resolution Summary</strong>
          <p style="margin:8px 0 0;color:#1e293b;font-size:14px;line-height:1.5;">{reason}</p>
        </div>
      </td>
    </tr>"""

    rows += f"""\
    <tr>
      <td colspan="2" style="padding:20px 0 0;">
        <a href="http://localhost:3001/vendors/{vendor.vendor_id}" 
           style="display:inline-block;background:#16A34A;color:#fff;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">
          View in Dashboard →
        </a>
      </td>
    </tr>"""
    rows += "</table>"

    return _base_html("✅", "VRM RISK RESOLVED", "#16A34A", rows)


def build_alert_resolved_html(alert: Alert, vendor: Vendor) -> str:
    """Build HTML for when an alert is manually marked resolved."""
    sev_color, sev_icon = _SEVERITY_COLORS.get(alert.severity, ("#64748b", "⚪"))

    rows = f'<table width="100%" cellpadding="0" cellspacing="0">'
    rows += _info_row("Vendor", f"{vendor.name} ({vendor.vendor_id})")
    rows += _info_row("Alert Type", alert.alert_type)
    rows += _info_row("Original Severity", f"{sev_icon} {alert.severity}", sev_color)
    rows += _info_row("Resolved At", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

    rows += _section_divider()
    rows += f"""\
    <tr>
      <td colspan="2" style="padding:8px 0;">
        <div style="background:#f0fdf4;border-left:4px solid #16A34A;padding:12px 16px;border-radius:4px;">
          <strong style="color:#16A34A;">Alert Resolved</strong>
          <p style="margin:8px 0 0;color:#1e293b;font-size:14px;line-height:1.5;">
            Alert &ldquo;{alert.alert_type}&rdquo; (ID #{alert.id}) has been manually resolved by an operator.<br>
            Original message: {alert.message}
          </p>
        </div>
      </td>
    </tr>"""

    rows += f"""\
    <tr>
      <td colspan="2" style="padding:20px 0 0;">
        <a href="http://localhost:3001/vendors/{vendor.vendor_id}" 
           style="display:inline-block;background:#16A34A;color:#fff;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">
          View in Dashboard →
        </a>
      </td>
    </tr>"""
    rows += "</table>"

    return _base_html("✅", "VRM ALERT RESOLVED", "#16A34A", rows)


# ── High-level orchestrators ─────────────────────────────────────────

def notify_critical_high(scored: ScoredVendor, vendor: Vendor) -> None:
    """Send an escalation email if severity is CRITICAL or HIGH.
    
    Safe to call from sync code (scheduler, CLI, etc.) — handles event loop detection.
    """
    s = get_settings()
    if not s.email_enabled:
        return
    if scored.severity not in _EMAIL_SEVERITIES:
        return

    recipients = _resolve_recipients(vendor)
    if not recipients:
        return

    subject = f"[VRM {scored.severity}] {vendor.name} ({vendor.vendor_id}) — Risk Score {scored.score}/100"
    html = build_risk_alert_html(scored, vendor)
    send_email_fire_and_forget(recipients, subject, html)
    log.info("notify_critical_high_dispatched", vendor=vendor.vendor_id, severity=scored.severity, to=recipients)


def notify_resolution(
    vendor: Vendor,
    previous_severity: str,
    new_severity: str,
    new_score: int | None = None,
    previous_score: int | None = None,
) -> None:
    """Send a resolution email when severity drops from CRITICAL/HIGH to lower.
    
    Safe to call from sync code.
    """
    s = get_settings()
    if not s.email_enabled:
        return
    if previous_severity not in _EMAIL_SEVERITIES:
        return
    if new_severity in _EMAIL_SEVERITIES:
        return  # Still critical/high — no resolution yet

    recipients = _resolve_recipients(vendor)
    if not recipients:
        return

    reason = (
        f"Risk severity has been downgraded from {previous_severity} to {new_severity} "
        f"following re-assessment. The vendor's risk profile has improved."
    )
    subject = f"[VRM RESOLVED] {vendor.name} ({vendor.vendor_id}) — {previous_severity} → {new_severity}"
    html = build_resolution_html(vendor, previous_severity, new_severity, new_score, previous_score, reason)
    send_email_fire_and_forget(recipients, subject, html)
    log.info("notify_resolution_dispatched", vendor=vendor.vendor_id, from_sev=previous_severity, to_sev=new_severity, to=recipients)


def notify_alert_resolved(alert: Alert, vendor: Vendor) -> None:
    """Send resolution email when an alert is manually marked as resolved.
    
    Only fires for CRITICAL/HIGH alerts. Safe to call from sync code.
    """
    s = get_settings()
    if not s.email_enabled:
        return
    if alert.severity not in _EMAIL_SEVERITIES:
        return

    recipients = _resolve_recipients(vendor)
    if not recipients:
        return

    subject = f"[VRM RESOLVED] Alert #{alert.id} — {alert.alert_type} for {vendor.name} ({vendor.vendor_id})"
    html = build_alert_resolved_html(alert, vendor)
    send_email_fire_and_forget(recipients, subject, html)
    log.info("notify_alert_resolved_dispatched", alert_id=alert.id, vendor=vendor.vendor_id, to=recipients)


def get_email_status() -> dict:
    """Return email service health/config info for the /alerts/email-status endpoint."""
    s = get_settings()
    return {
        "enabled": s.email_enabled,
        "mode": s.email_mode,
        "smtp_host": s.smtp_host if s.email_mode == "smtp" else None,
        "smtp_port": s.smtp_port if s.email_mode == "smtp" else None,
        "from": s.email_from,
        "admin_recipients": s.email_admin_recipients,
        "send_to_vendor_contact": s.email_send_to_vendor_contact,
    }
