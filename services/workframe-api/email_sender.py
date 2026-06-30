"""
Email sender module for Workframe API.
Sends OTP verification emails via SMTP (env or stack_config).
"""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import stack_config

APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:18644").rstrip("/")


def _tls_flags(cfg: dict[str, Any]) -> tuple[bool, bool]:
    port = int(cfg.get("port") or 587)
    secure = stack_config.normalize_smtp_secure(port, str(cfg.get("secure") or ""))
    use_ssl = secure == "ssl"
    use_tls = secure == "starttls"
    return use_ssl, use_tls


def _smtp_send(msg: MIMEMultipart, to_email: str, cfg: dict[str, Any]) -> None:
    host = str(cfg.get("host") or "").strip()
    if not host:
        raise RuntimeError("SMTP_HOST not configured")
    port = int(cfg.get("port") or 587)
    user = str(cfg.get("user") or "").strip()
    password = str(cfg.get("password") or "").strip().replace(" ", "")
    from_addr = str(cfg.get("from") or user or "").strip()
    if not from_addr:
        raise RuntimeError("SMTP from address not configured")
    if user and not password:
        raise RuntimeError("SMTP password is required when SMTP user is set")
    msg["From"] = from_addr
    use_ssl, use_tls = _tls_flags(cfg)
    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
        with server:
            server.ehlo()
            if use_tls and not use_ssl:
                server.starttls()
                server.ehlo()
            if user:
                server.login(user, password)
            server.sendmail(from_addr, [to_email], msg.as_string())
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(f"SMTP login failed: {exc}") from exc
    except smtplib.SMTPSenderRefused as exc:
        sender = str(getattr(exc, "sender", "") or from_addr)
        if user and sender.lower() != user.lower():
            raise RuntimeError(
                f"SMTP rejected From address {sender!r} for login {user!r}"
            ) from exc
        raise RuntimeError(f"SMTP error: {exc}") from exc
    except smtplib.SMTPException as exc:
        raise RuntimeError(f"SMTP error: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Network error sending email: {exc}") from exc


def _active_smtp() -> dict[str, Any]:
    cfg = stack_config.resolved_smtp()
    if cfg.get("source") == "none":
        return {}
    return cfg


def send_email_with_config(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str = "",
    cfg: dict[str, Any] | None = None,
) -> None:
    smtp = cfg or _active_smtp()
    if not smtp.get("host"):
        raise RuntimeError("SMTP_HOST not configured")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["To"] = to_email
    msg.attach(MIMEText(body_text, "plain"))
    if body_html:
        msg.attach(MIMEText(body_html, "html"))
    _smtp_send(msg, to_email, smtp)


def _branded_html(
    *,
    brand: str,
    headline: str,
    intro: str,
    body_html: str,
    logo_url: str = "",
    footer: str = "If you didn't request this, you can safely ignore this email.",
) -> str:
    logo_block = (
        f'<img src="{logo_url}" alt="" style="height:40px;margin-bottom:12px;" />'
        if logo_url
        else ""
    )
    return f"""\
<html>
<body style="margin:0; background:#f6f7fb; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color:#1d2340;">
  <div style="max-width:560px; margin:0 auto; padding:32px 20px;">
    <div style="background:#ffffff; border:1px solid #e4e7f2; border-radius:20px; padding:32px; box-shadow:0 24px 64px rgba(14,20,49,0.08);">
      {logo_block}
      <div style="font-size:12px; font-weight:700; letter-spacing:0.14em; text-transform:uppercase; color:#6c5ce7; margin-bottom:12px;">{brand}</div>
      <h1 style="margin:0 0 12px; font-size:28px; line-height:1.2;">{headline}</h1>
      <p style="margin:0 0 24px; color:#4f5878; font-size:16px; line-height:1.6;">{intro}</p>
      {body_html}
      <p style="margin:24px 0 0; color:#7b849d; font-size:12px; line-height:1.6;">{footer}</p>
    </div>
  </div>
</body>
</html>
"""


def _code_block_html(code: str) -> str:
    return f"""\
<div style="background:linear-gradient(180deg, #f5f7ff 0%, #eef1ff 100%); border:1px solid #d9defa; border-radius:16px; padding:18px 20px; text-align:center; margin-bottom:20px;">
  <div style="font-size:12px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:#6b7280; margin-bottom:10px;">Verification code</div>
  <div style="font-size:34px; font-weight:800; letter-spacing:10px; color:#111827; font-variant-numeric:tabular-nums;">{code}</div>
</div>
<p style="margin:0 0 20px; color:#4f5878; font-size:14px; line-height:1.6;">This code expires in 10 minutes.</p>
"""


def _cta_button_html(url: str, label: str) -> str:
    return (
        f'<a href="{url}" style="display:inline-block; padding:12px 20px; background:#6c5ce7; '
        f'color:#ffffff; text-decoration:none; border-radius:10px; font-weight:700;">{label}</a>'
    )


def _build_verification_email(
    to_email: str,
    code: str,
    verification_url: str,
    workspace_name: str = "Workframe",
    logo_url: str = "",
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    brand = workspace_name or "Workframe"
    msg["Subject"] = f"Your {brand} sign-in code"
    msg["To"] = to_email
    text_body = f"""\
{brand} sign-in code

Your verification code is:

{code}

This code expires in 10 minutes.

Or click the link to verify:
{verification_url}

If you didn't request this, ignore this email.
"""
    body_html = _code_block_html(code) + _cta_button_html(verification_url, "Verify now")
    html_body = _branded_html(
        brand=brand,
        headline="Sign in with your code",
        intro="Use this one-time code to finish signing in to Workframe.",
        body_html=body_html,
        logo_url=logo_url,
    )
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    return msg


def send_verification_email(
    to_email: str,
    code: str,
    verification_url: str,
    workspace_name: str = "",
    logo_url: str = "",
) -> None:
    msg = _build_verification_email(to_email, code, verification_url, workspace_name, logo_url)
    _smtp_send(msg, to_email, _active_smtp())


def send_email(to_email: str, subject: str, body_text: str, body_html: str = "") -> None:
    send_email_with_config(to_email, subject, body_text, body_html)


def send_branded_invite_email(
    to_email: str,
    workspace_name: str,
    invite_url: str,
    logo_url: str = "",
) -> None:
    brand = workspace_name or "Workframe"
    subject = f"Join {brand} on Workframe"
    text = f"You were invited to {brand}.\n\nAccept: {invite_url}\n"
    body_html = _cta_button_html(invite_url, "Accept invite")
    html = _branded_html(
        brand=brand,
        headline=f"Join {brand}",
        intro="You were invited to collaborate on Workframe.",
        body_html=body_html,
        logo_url=logo_url,
        footer="If you weren't expecting this invite, you can ignore this email.",
    )
    send_email_with_config(to_email, subject, text, html)


if __name__ == "__main__":
    html = _build_verification_email("test@example.com", "123456", "http://127.0.0.1:18644/?code=123456").as_string()
    assert "Verification code" in html and "Verify now" in html
