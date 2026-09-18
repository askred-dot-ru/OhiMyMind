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
    "sent": ("[Gmail]/Sent Mail", "[Google Mail]/Sent Mail", "[Gmail]/Отправленные"),
    "drafts": ("[Gmail]/Drafts", "[Google Mail]/Drafts", "[Gmail]/Черновики"),
    "trash": ("[Gmail]/Trash", "[Google Mail]/Trash", "[Gmail]/Bin", "[Gmail]/Корзина"),
    "spam": ("[Gmail]/Spam", "[Google Mail]/Spam", "[Gmail]/Спам"),
    "archive": (),
}

YANDEX_ALIASES = {
    "inbox": ("INBOX",),
    "sent": ("Sent", "Отправленные", "Sent Mail"),
    "drafts": ("Drafts", "Черновики"),
    "trash": ("Trash", "Удалённые", "Deleted", "Deleted Messages"),
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

# Localized Gmail virtual folders — same mail as INBOX, must not be ingested.
_GMAIL_SKIP_TAILS = {
    "all mail",
    "вся почта",
    "important",
    "важное",
    "starred",
    "помеченные",
}


def display_name(canonical: str) -> str:
    if canonical in CANONICAL_TITLES:
        return CANONICAL_TITLES[canonical]
    if canonical.startswith("user:"):
        return canonical[5:]
    return canonical


def normalize_user_canonical(imap_name: str) -> str:
    return "user:" + imap_name.strip().casefold()


def _fold_name(imap_name: str) -> str:
    return imap_name.strip().casefold().replace("\\", "/")


def is_gmail_system_folder(imap_name: str) -> bool:
    low = _fold_name(imap_name)
    return low == "inbox" or low.startswith("[gmail]/") or low.startswith("[google mail]/")


def match_canonical(provider: str, imap_name: str) -> str | None:
    low = _fold_name(imap_name)
    aliases = GMAIL_ALIASES if provider == "gmail" else YANDEX_ALIASES
    for canonical, names in aliases.items():
        for alias in names:
            alias_l = alias.casefold()
            if low == alias_l or low.endswith("/" + alias_l):
                if canonical == "inbox" and low != "inbox":
                    continue
                return canonical
    return None


def should_skip(imap_name: str) -> bool:
    low = _fold_name(imap_name)
    if low in SKIP_NAMES:
        return True
    if low.startswith("[gmail]/") or low.startswith("[google mail]/"):
        tail = low.rsplit("/", 1)[-1]
        if tail in _GMAIL_SKIP_TAILS:
            return True
    return False
