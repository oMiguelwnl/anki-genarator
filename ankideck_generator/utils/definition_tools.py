from __future__ import annotations

import copy
import re
from typing import Any

BUILTIN_POS_ALIASES = {
    "adj": "adjective",
    "adjective": "adjective",
    "adjectif": "adjective",
    "adjetivo": "adjective",
    "adv": "adverb",
    "adverb": "adverb",
    "adverbe": "adverb",
    "adverbio": "adverb",
    "article": "article",
    "article defini": "article",
    "articulo": "article",
    "aux": "auxiliary verb",
    "auxiliary": "auxiliary verb",
    "auxiliary verb": "auxiliary verb",
    "auxiliar": "auxiliary verb",
    "conjunction": "conjunction",
    "conjonction": "conjunction",
    "conjuncion": "conjunction",
    "determiner": "determiner",
    "determinante": "determiner",
    "determinant": "determiner",
    "expression": "expression",
    "expression idiomatique": "expression",
    "feminine noun": "feminine noun",
    "masculine noun": "masculine noun",
    "plural noun": "plural noun",
    "interjection": "interjection",
    "interjeccion": "interjection",
    "noun": "noun",
    "nom": "noun",
    "nome": "noun",
    "nombre": "noun",
    "sostantivo": "noun",
    "substantif": "noun",
    "sustantivo": "noun",
    "numeral": "numeral",
    "numeralе": "numeral",
    "numerale": "numeral",
    "numéral": "numeral",
    "particle": "particle",
    "particule": "particle",
    "particula": "particle",
    "phrase": "phrase",
    "prep": "preposition",
    "preposition": "preposition",
    "prepositione": "preposition",
    "preposicion": "preposition",
    "pronom": "pronoun",
    "pronombre": "pronoun",
    "pronoun": "pronoun",
    "proper noun": "proper noun",
    "nom propre": "proper noun",
    "nome proprio": "proper noun",
    "nombre propio": "proper noun",
    "verb": "verb",
    "verbe": "verb",
    "verbo": "verb",
}

BUILTIN_DEFINITION_POLICY = {
    "cleanup": {
        "collapse_whitespace": True,
        "strip_bracket_notes": True,
        "strip_css_markup": True,
        "strip_html": True,
        "strip_quotes": True,
        "normalize_punctuation_spacing": True,
    },
    "noise_patterns": [
        r"\.mw-parser-output(?:\s+\.[A-Za-z0-9_-]+(?:\{[^{}]*\})?)*",
        r"\.[A-Za-z0-9_-]+\{[^{}]*\}",
        r"__TOC__",
    ],
    "spacing_replacements": [
        [r"\s+,", ","],
        [r"\s+\.", "."],
        [r"\s+;", ";"],
        [r"\s+:", ":"],
        [r"\(\s+", "("],
        [r"\s+\)", ")"],
        [r",(?=\S)", ", "],
        [r";(?=\S)", "; "],
    ],
    "pos_aliases": BUILTIN_POS_ALIASES,
}

_DEFAULT_DEFINITION_POLICY: dict[str, Any] = {}


def build_definition_policy(policy: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = copy.deepcopy(BUILTIN_DEFINITION_POLICY)
    if isinstance(policy, dict):
        merged = _deep_merge(merged, policy)
        if isinstance(policy.get("noise_patterns"), list):
            merged["noise_patterns"] = [
                *BUILTIN_DEFINITION_POLICY.get("noise_patterns", []),
                *policy.get("noise_patterns", []),
            ]
        if isinstance(policy.get("spacing_replacements"), list):
            merged["spacing_replacements"] = [
                *BUILTIN_DEFINITION_POLICY.get("spacing_replacements", []),
                *policy.get("spacing_replacements", []),
            ]

    aliases = dict(BUILTIN_POS_ALIASES)
    override_aliases = merged.get("pos_aliases")
    if isinstance(override_aliases, dict):
        for raw_key, raw_value in override_aliases.items():
            key = _normalize_alias_key(raw_key)
            value = str(raw_value or "").strip()
            if key and value:
                aliases[key] = value
    merged["pos_aliases"] = aliases
    merged["cleanup"] = dict(merged.get("cleanup") or {})
    merged["noise_patterns"] = [
        str(item).strip()
        for item in (merged.get("noise_patterns") or [])
        if str(item).strip()
    ]
    merged["spacing_replacements"] = [
        item
        for item in (merged.get("spacing_replacements") or [])
        if isinstance(item, (list, tuple)) and len(item) == 2
    ]
    merged["_built"] = True
    return merged


def set_default_definition_policy(policy: dict[str, Any] | None = None) -> None:
    global _DEFAULT_DEFINITION_POLICY
    _DEFAULT_DEFINITION_POLICY = build_definition_policy(policy)


def normalize_definition(
    text: str,
    target_lang: str,
    pos_mode: str = "auto",
    min_words: int = 6,
    max_words: int = 10,
    *,
    policy: dict[str, Any] | None = None,
) -> str:
    _ = target_lang
    resolved_policy = _resolve_policy(policy)
    if not text:
        return ""

    cleaned = _strip_noise(text, resolved_policy)
    if not cleaned:
        return ""

    pos_label, body = _extract_pos(cleaned, resolved_policy)
    if pos_mode != "auto":
        pos_label = ""

    body = _trim_to_range(
        _clean_body(body, resolved_policy),
        min_words,
        max_words,
    )
    if not body:
        return ""

    if pos_label:
        body = _capitalize_after_colon(body)
        result = f"{pos_label}: {body}"
    else:
        result = _capitalize_sentence(body)

    result = _normalize_spacing(result, resolved_policy)
    if not result.endswith("."):
        result += "."
    return result


def definition_has_pos(
    text: str,
    *,
    policy: dict[str, Any] | None = None,
) -> bool:
    resolved_policy = _resolve_policy(policy)
    pos_label, _ = _extract_pos(_strip_noise(text, resolved_policy), resolved_policy)
    return bool(pos_label)


def _resolve_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    if policy is None:
        return _DEFAULT_DEFINITION_POLICY
    if bool(policy.get("_built")):
        return policy
    return build_definition_policy(policy)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _normalize_alias_key(value: object) -> str:
    label = re.sub(r"\s+", " ", str(value or "").strip().lower())
    label = label.strip("()[]{}-:;,. ")
    return (
        label.replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ã", "a")
        .replace("ä", "a")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("ë", "e")
        .replace("í", "i")
        .replace("ì", "i")
        .replace("î", "i")
        .replace("ï", "i")
        .replace("ó", "o")
        .replace("ò", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ö", "o")
        .replace("ú", "u")
        .replace("ù", "u")
        .replace("û", "u")
        .replace("ü", "u")
        .replace("ç", "c")
    )


def _strip_noise(text: str, policy: dict[str, Any]) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    cleanup_cfg = policy.get("cleanup") or {}
    if cleanup_cfg.get("strip_html", True):
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    if cleanup_cfg.get("strip_css_markup", True):
        for pattern in policy.get("noise_patterns") or []:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"^\s*(definitions?|meaning|def)\s*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    if cleanup_cfg.get("strip_bracket_notes", True):
        cleaned = re.sub(r"\[[^\]]+\]", " ", cleaned)
        cleaned = re.sub(r"\[[^\]]*$", " ", cleaned)
    if cleanup_cfg.get("strip_quotes", True):
        cleaned = cleaned.strip().strip("\"'“”")
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    cleaned = _normalize_spacing(cleaned, policy)
    if cleanup_cfg.get("collapse_whitespace", True):
        cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _extract_pos(text: str, policy: dict[str, Any]) -> tuple[str, str]:
    patterns = [
        re.compile(r"^\s*([^:]+):\s*\(([^()]+)\)\s*[-–:]*\s*(.+)$"),
        re.compile(r"^\s*\(([^()]+)\)\s*[-–:]*\s*(.+)$"),
        re.compile(r"^\s*([^\W\d_][^:\-]{0,48})\s*[:\-]\s*(.+)$", flags=re.UNICODE),
    ]
    for pattern in patterns:
        match = pattern.match(text)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 3:
            pos_label = _normalize_pos(groups[1], policy)
            body = groups[2]
        else:
            pos_label = _normalize_pos(groups[0], policy)
            body = groups[1]
        if pos_label:
            return pos_label, body.strip()
    return "", text


def _normalize_pos(text: str, policy: dict[str, Any]) -> str:
    label = _normalize_alias_key(text)
    return (policy.get("pos_aliases") or {}).get(label, "")


def _clean_body(text: str, policy: dict[str, Any]) -> str:
    cleaned = str(text or "").strip()
    cleaned = _lstrip_to_first_letter(cleaned)
    cleaned = re.sub(r"^[^\W\d_][^:]{0,40}:\s*", "", cleaned, count=1, flags=re.UNICODE)
    cleaned = re.sub(r"\([^()]+\)\s*[-–:]*\s*", "", cleaned)
    cleaned = re.sub(r"\[[^\]]+\]", " ", cleaned)
    cleaned = re.sub(r"\[[^\]]*$", " ", cleaned)
    cleaned = _normalize_spacing(cleaned, policy)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" -:;,")
    cleaned = re.sub(r"\s*;\s*$", "", cleaned)
    return cleaned


def _normalize_spacing(text: str, policy: dict[str, Any]) -> str:
    cleaned = str(text or "")
    cleanup_cfg = policy.get("cleanup") or {}
    if cleanup_cfg.get("normalize_punctuation_spacing", True):
        for pattern, replacement in policy.get("spacing_replacements") or []:
            cleaned = re.sub(str(pattern), str(replacement), cleaned)
    return cleaned.strip()


def _lstrip_to_first_letter(text: str) -> str:
    for index, char in enumerate(text):
        if char.isalpha():
            return text[index:]
    return ""


def _trim_to_range(text: str, min_words: int, max_words: int) -> str:
    words = text.split()
    if len(words) < max(1, min_words):
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


set_default_definition_policy()
