from __future__ import annotations

import re

POS_LABELS = {"noun", "verb", "adjective", "adverb"}


def normalize_definition(
    text: str,
    target_lang: str,
    pos_mode: str = "auto",
    min_words: int = 6,
    max_words: int = 10,
) -> str:
    if not text:
        return ""

    cleaned = _strip_noise(text)
    if not cleaned:
        return ""

    pos_label, body = _extract_pos(cleaned)
    if pos_mode != "auto":
        pos_label = ""

    body = _trim_to_range(body, min_words, max_words)
    if not body:
        return ""

    if pos_label:
        body = _capitalize_after_colon(body)
        result = f"{pos_label}: {body}"
    else:
        result = _capitalize_sentence(body)

    if not result.endswith("."):
        result += "."

    return result


def _strip_noise(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\s*(definition|meaning|def)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip().strip("\"'“”")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.split("\n", 1)[0].strip()
    return cleaned


def _extract_pos(text: str) -> tuple[str, str]:
    match = re.match(r"^\s*([A-Za-z]+)\s*:\s*(.+)$", text)
    if not match:
        return "", text
    label = match.group(1).lower()
    if label not in POS_LABELS:
        return "", text
    return label, match.group(2).strip()


def _trim_to_range(text: str, min_words: int, max_words: int) -> str:
    words = text.split()
    if len(words) == 0:
        return ""
    if len(words) > max_words:
        words = words[:max_words]
    return " ".join(words)


def _capitalize_sentence(text: str) -> str:
    if not text:
        return ""
    return text[0].upper() + text[1:]


def _capitalize_after_colon(text: str) -> str:
    if not text:
        return ""
    return text[0].lower() + text[1:]
