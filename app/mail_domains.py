from __future__ import annotations

import re

_HOST = re.compile(r"[^a-z0-9.-]+")


def normalize_sender_domain(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value.startswith("@"):
        value = value[1:]
    if "@" in value:
        value = value.rsplit("@", 1)[-1]
    value = _HOST.sub("", value).strip(".")
    return value


def merge_domains(raw: list[str] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in raw or []:
        domain = normalize_sender_domain(item)
        if not domain or domain in seen:
            continue
        seen.add(domain)
        out.append(domain)
    out.sort()
    return out
