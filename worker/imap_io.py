from __future__ import annotations

import base64
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from imapclient import IMAPClient

from app.config import settings
from app.models import MailAccount
from app.store_mail import html_to_text

log = logging.getLogger("ohimymind.imap")


def google_access_token(refresh_token: str) -> str:
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
    )
    creds.refresh(Request())
    if not creds.token:
        raise RuntimeError("gmail_token_refresh_failed")
    return creds.token


def imap_connect(account: MailAccount, secret: dict) -> IMAPClient:
    client = IMAPClient(account.imap_host, port=account.imap_port, ssl=account.use_ssl, timeout=60)
    if secret.get("kind") == "oauth":
        token = google_access_token(secret["refresh_token"])
        client.oauth2_login(account.email, token)
    else:
        client.login(account.email, secret["password"])
    return client


def smtp_connect(account: MailAccount, secret: dict) -> smtplib.SMTP:
    smtp = smtplib.SMTP_SSL(account.smtp_host, account.smtp_port, timeout=60)
    smtp.ehlo()
    if secret.get("kind") == "oauth":
        token = google_access_token(secret["refresh_token"])
        auth = f"user={account.email}\x01auth=Bearer {token}\x01\x01"
        code, _ = smtp.docmd("AUTH", "XOAUTH2 " + base64.b64encode(auth.encode()).decode())
        if code != 235:
            raise RuntimeError("smtp_oauth_failed")
    else:
        smtp.login(account.email, secret["password"])
    return smtp


def build_outgoing(
    *,
    from_addr: str,
    to_addrs: list[str],
    cc_addrs: list[str],
    subject: str,
    body_html: str,
    in_reply_to: str,
    references: str,
) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    if in_reply_to:
        msg["In-Reply-To"] = f"<{in_reply_to.strip('<>')}>"
    if references:
        msg["References"] = references
    plain = html_to_text(body_html) or body_html
    msg.set_content(plain)
    if body_html:
        msg.add_alternative(body_html, subtype="html")
    return msg
