"""
Real OTP delivery: SMS (Twilio or Fast2SMS) + Email (SMTP).
Set credentials in environment or backend/.env — see .env.example
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def is_demo_otp_mode() -> bool:
    return os.environ.get("NYAYAFLOW_OTP_MODE", "real").strip().lower() in (
        "demo",
        "test",
        "dev",
        "0",
        "false",
    )


def sms_provider_configured() -> bool:
    twilio = all(
        os.environ.get(k)
        for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER")
    )
    fast2 = bool(os.environ.get("FAST2SMS_API_KEY"))
    return twilio or fast2


def email_smtp_configured() -> bool:
    return all(
        os.environ.get(k)
        for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM_EMAIL")
    )


def send_sms_otp(phone_10: str, otp: str) -> tuple[bool, str]:
    """
    phone_10: 10-digit Indian mobile without country code.
    Returns (ok, error_or_empty_message).
    """
    try:
        import requests
        from requests.auth import HTTPBasicAuth
    except ImportError:
        return False, "Install requests: pip install requests"

    body = f"NyayaFlow verification OTP: {otp}. Valid for 5 minutes. Do not share."

    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    tfrom = os.environ.get("TWILIO_PHONE_NUMBER")
    if sid and token and tfrom:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        to_num = phone_10 if phone_10.startswith("+") else f"+91{phone_10}"
        r = requests.post(
            url,
            auth=HTTPBasicAuth(sid, token),
            data={"From": tfrom, "To": to_num, "Body": body},
            timeout=30,
        )
        if r.status_code >= 400:
            return False, f"Twilio error: {r.status_code} {r.text[:200]}"
        return True, ""

    fkey = os.environ.get("FAST2SMS_API_KEY")
    if fkey:
        sender = os.environ.get("FAST2SMS_SENDER_ID", "TXTIND")
        route = os.environ.get("FAST2SMS_ROUTE", "q")
        r = requests.post(
            "https://www.fast2sms.com/dev/bulkV2",
            headers={"authorization": fkey, "Content-Type": "application/json"},
            json={
                "route": route,
                "sender_id": sender,
                "message": body,
                "language": "english",
                "numbers": phone_10,
            },
            timeout=30,
        )
        try:
            data = r.json()
        except Exception:
            data = {}
        if r.status_code >= 400 or not data.get("return", True):
            return False, f"Fast2SMS error: {r.status_code} {data or r.text[:200]}"
        return True, ""

    return False, "SMS not configured (Twilio or Fast2SMS)"


def send_email_otp(to_email: str, otp: str) -> tuple[bool, str]:
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    from_addr = os.environ.get("SMTP_FROM_EMAIL", "").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    use_ssl = os.environ.get("SMTP_SSL", "").lower() in ("1", "true", "yes")

    if not all([host, user, password, from_addr]):
        return False, "Email SMTP not configured (SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL)"

    subject = "NyayaFlow — Email verification OTP"
    text = f"Your NyayaFlow verification OTP is: {otp}\n\nValid for 5 minutes. Do not share this code."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))

    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
                server.login(user, password)
                server.sendmail(from_addr, to_email, msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(user, password)
                server.sendmail(from_addr, to_email, msg.as_string())
        return True, ""
    except Exception as e:
        return False, f"SMTP send failed: {e!s}"[:300]
