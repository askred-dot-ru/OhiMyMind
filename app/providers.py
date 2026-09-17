from __future__ import annotations

CANONICAL_ORDER = ("inbox", "sent", "drafts", "trash", "archive", "spam")

CANONICAL_TITLES = {
    "inbox": "Входящие",
    "sent": "Отправленные",
    "drafts": "Черновики",
    "trash": "Корзина",
    "archive": "Архив",
    "spam": "Спам",
}

PROVIDER_DEFAULTS = {
    "gmail": {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 465,
    },
    "yandex": {
        "imap_host": "imap.yandex.ru",
        "imap_port": 993,
        "smtp_host": "smtp.yandex.ru",
        "smtp_port": 465,
    },
}

GMAIL_ALIASES = {
    "inbox": ("INBOX",),
    "sent": ("[Gmail]/Sent Mail", "[Google Mail]/Sent Mail"),
    "drafts": ("[Gmail]/Drafts", "[Google Mail]/Drafts"),
    "trash": ("[Gmail]/Trash", "[Google Mail]/Trash", "[Gmail]/Bin"),
    "spam": ("[Gmail]/Spam", "[Google Mail]/Spam"),
    "archive": (),
}

YANDEX_ALIASES = {
    "inbox": ("INBOX",),
    "sent": ("Sent", "Отправленные", "Sent Mail"),
    "drafts": ("Drafts", "Черновики"),
    "trash": ("Trash", "Удалённые", "Deleted"),
    "spam": ("Spam", "Спам"),
    "archive": ("Archive", "Архив"),
}

SKIP_NAMES = {
    "[gmail]",
    "[google mail]",
    "[gmail]/all mail",
    "[google mail]/all mail",
    "[gmail]/important",
    "[gmail]/starred",
}


def display_name(canonical: str) -> str:
    if canonical in CANONICAL_TITLES:
        return CANONICAL_TITLES[canonical]
    if canonical.startswith("user:"):
        return canonical[5:]
    return canonical


def normalize_user_canonical(imap_name: str) -> str:
    return "user:" + imap_name.strip().casefold()


def match_canonical(provider: str, imap_name: str) -> str | None:
    low = imap_name.strip()
    aliases = GMAIL_ALIASES if provider == "gmail" else YANDEX_ALIASES
    for canonical, names in aliases.items():
        for alias in names:
            if low.casefold() == alias.casefold() or alias.casefold() in low.casefold():
                if canonical == "inbox" and low.casefold() != "inbox":
                    continue
                return canonical
    return None


def should_skip(imap_name: str) -> bool:
    return imap_name.strip().casefold() in SKIP_NAMES
