"""TEMPORARY done-action (2026-09-17).

«Выполнить» forwards the invoked message to a hardcoded mailbox, then archives the whole thread.
Replace with a real distribution route later. Do not add env or UI settings for this.
"""

from __future__ import annotations

import base64
import html
import logging
import re
from pathlib import Path

from app.config import settings
from app.models import MailAttachment, MailMessage

log = logging.getLogger("ohimymind.done")

# TEMPORARY hardcoded recipient — not a setting.
DONE_RECIPIENT = "robr@askred.ru"

_MAX_INLINE = 3_000_000
_ATT_SRC = re.compile(
    r"""src=(['"])(?:https?://[^'"]+)?/api/v1/mail/attachments/([0-9a-fA-F-]{36})\1""",
    re.I,
)


def done_subject(subject: str) -> str:
    text = (subject or "").strip() or "(без темы)"
    if text.lower().startswith("fwd:"):
        return text
    return f"Fwd: {text}"


def build_done_html(msg: MailMessage, attachments: list[MailAttachment]) -> str:
    quoted = msg.body_html.strip() if msg.body_html else f"<pre>{html.escape(msg.body_text or '')}</pre>"
    quoted = _inline_local_images(quoted, attachments)
    return (
        "<p>Выполнено</p>"
        f"<p>От: {html.escape(msg.from_addr)}<br>Тема: {html.escape(msg.subject or '')}</p>"
        f"<blockquote>{quoted}</blockquote>"
    )


def _inline_local_images(body: str, attachments: list[MailAttachment]) -> str:
    by_id = {str(att.id).lower(): att for att in attachments}
    root = Path(settings.attachments_dir).resolve()

    def repl(match: re.Match[str]) -> str:
        att = by_id.get(match.group(2).lower())
        if att is None or not (att.mime or "").lower().startswith("image/"):
            return match.group(0)
        path = (root / att.storage_path).resolve()
        if root not in path.parents and path != root:
            return match.group(0)
        try:
            data = path.read_bytes()
        except OSError:
            log.info("done inline miss attachment_id=%s", att.id)
            return match.group(0)
        if len(data) > _MAX_INLINE:
            return match.group(0)
        b64 = base64.b64encode(data).decode("ascii")
        return f'src="data:{att.mime};base64,{b64}"'

    return _ATT_SRC.sub(repl, body)
