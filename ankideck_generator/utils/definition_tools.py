from __future__ import annotations

import re

POS_ALIASES = {
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
    "prepositione": "preposition",
    "preposicion": "preposition",
    "preposition": "preposition",
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
POS_LABELS = set(POS_ALIASES.values())


def normalize_definition(
    text: str,
    target_lang: str,
    pos_mode: str = "auto",
    min_words: int = 6,
    max_words: int = 10,
) -> str:
    _ = target_lang
    if not text:
        return ""

    cleaned = _strip_noise(text)
    if not cleaned:
        return ""

    pos_label, body = _extract_pos(cleaned)
    if pos_mode != "auto":
        pos_label = ""

    body = _trim_to_range(_clean_body(body), min_words, max_words)
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


def definition_has_pos(text: str) -> bool:
    pos_label, _ = _extract_pos(_strip_noise(text))
    return bool(pos_label)


def _strip_noise(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(
        r"^\s*(definition|meaning|def)\s*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.strip().strip("\"'“”")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.split("\n", 1)[0].strip()
    return cleaned


def _extract_pos(text: str) -> tuple[str, str]:
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
            pos_label = _normalize_pos(groups[1])
            body = groups[2]
        else:
            pos_label = _normalize_pos(groups[0])
            body = groups[1]
        if pos_label:
            return pos_label, body.strip()
    return "", text


def _normalize_pos(text: str) -> str:
    label = re.sub(r"\s+", " ", str(text or "").strip().lower())
    label = label.strip("()[]{}-:;,. ")
    label = (
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
    return POS_ALIASES.get(label, "")


def _clean_body(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = _lstrip_to_first_letter(cleaned)
    cleaned = re.sub(r"^[^\W\d_][^:]{0,40}:\s*", "", cleaned, count=1, flags=re.UNICODE)
    cleaned = re.sub(r"\([^()]+\)\s*[-–:]*\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -:;,")


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
