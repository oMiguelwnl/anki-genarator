from __future__ import annotations

import copy
import re
import unicodedata
from dataclasses import dataclass
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
    "num\u00e9ral": "numeral",
    "numerale": "numeral",
    "numeral": "numeral",
    "particle": "particle",
    "particula": "particle",
    "particule": "particle",
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
    "sostantivo": "noun",
    "substantif": "noun",
    "sustantivo": "noun",
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

MORPHOLOGICAL_CASE_LABELS = {
    "ablative",
    "accusative",
    "dative",
    "genitive",
    "instrumental",
    "locative",
    "nominative",
    "prepositional",
    "vocative",
}
ORTHOGRAPHIC_META_TAGS = {
    "alternative form",
    "alternative spelling",
    "dated spelling",
    "misspelling",
    "nonstandard spelling",
    "obsolete spelling",
    "spelling variant",
    "variant",
}
_GRAMMATICAL_USAGE_PATTERN = (
    r"(?:accusative|ablative|dative|genitive|instrumental|locative|nominative|"
    r"prepositional|vocative)"
)
_META_LEMMA_FIELD_NAMES = (
    "altOf",
    "formOf",
    "form_of",
    "headword",
    "lemma",
    "term",
    "title",
    "word",
)
_MORPHOLOGY_TAG_PATTERNS: list[tuple[str, str]] = [
    ("past participle", r"\bpast participle\b"),
    ("present participle", r"\bpresent participle\b"),
    ("simple past", r"\bsimple past\b"),
    ("first person", r"\bfirst(?:[\s-]+person)?\b"),
    ("second person", r"\bsecond(?:[\s-]+person)?\b"),
    ("third person", r"\bthird(?:[\s-]+person)?\b"),
    ("imperative", r"\bimperative\b"),
    ("indicative", r"\bindicative\b"),
    ("subjunctive", r"\bsubjunctive\b"),
    ("infinitive", r"\binfinitive\b"),
    ("participle", r"\bparticiple\b"),
    ("past", r"\bpast\b"),
    ("present", r"\bpresent\b"),
    ("future", r"\bfuture\b"),
    ("perfective", r"\bperfective\b"),
    ("imperfective", r"\bimperfective\b"),
    ("masculine", r"\bmasculine\b"),
    ("feminine", r"\bfeminine\b"),
    ("neuter", r"\bneuter\b"),
    ("singular", r"\bsingular\b"),
    ("plural", r"\bplural\b"),
    ("form", r"\bform\b"),
    ("inflection", r"\binflection\b"),
    ("alternative spelling", r"\balternative\s+spelling\b"),
    ("alternative form", r"\balternative(?:\s+case)?\s+form\b"),
    ("variant", r"\bvariant\b"),
    ("spelling variant", r"\bspelling\s+variant\b"),
    ("dated spelling", r"\bdated\s+spelling\b"),
    ("obsolete spelling", r"\bobsolete\s+spelling\b"),
    ("nonstandard spelling", r"\bnonstandard\s+spelling\b"),
    ("misspelling", r"\bmisspelling\b"),
]
_MORPHOLOGY_TAG_PATTERNS.extend(
    (label, rf"\b{label}\b") for label in sorted(MORPHOLOGICAL_CASE_LABELS)
)


@dataclass(frozen=True)
class MetaDefinition:
    pos_label: str
    lemma: str
    tags: tuple[str, ...]
    raw_body: str

    @property
    def is_verb(self) -> bool:
        label = self.pos_label.strip().lower()
        return label == "verb" or label.endswith(" verb")


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


def extract_meta_definition(
    text: str,
    *,
    policy: dict[str, Any] | None = None,
) -> MetaDefinition | None:
    resolved_policy = _resolve_policy(policy)
    cleaned = _strip_noise(text, resolved_policy)
    if not cleaned:
        return None

    pos_label, body = _extract_pos(cleaned, resolved_policy)
    raw_body = _clean_body(body, resolved_policy).strip()
    if not raw_body:
        return None

    lemma = ""
    raw_feature_text = raw_body
    lemma_match = re.search(r"\bof\b\s+(.+)$", raw_body, flags=re.IGNORECASE)
    if lemma_match:
        raw_feature_text = raw_body[: lemma_match.start()].strip()
        lemma = _strip_noise(lemma_match.group(1), resolved_policy).strip(
            " .,:;()[]{}\"'"
        )

    normalized = _normalize_meta_text(raw_feature_text)
    if not normalized:
        return None

    tags = _collect_morphology_tags(normalized)
    if not tags:
        return None

    tokens = re.findall(r"[a-z]+", normalized)
    if tokens:
        tagged_tokens = {token for tag in tags for token in tag.split()}
        token_hits = sum(1 for token in tokens if token in tagged_tokens)
        has_meta_marker = bool(lemma) or any(
            marker in normalized
            for marker in (
                "alternative",
                "form",
                "inflection",
                "imperative",
                "misspelling",
                "participle",
                "spelling",
                "variant",
            )
        )
        if not has_meta_marker and token_hits < max(2, len(tokens) - 1):
            return None

    return MetaDefinition(
        pos_label=pos_label,
        lemma=lemma,
        tags=tuple(tags),
        raw_body=raw_body,
    )


def extract_meta_lemma(
    payload: object,
    *,
    policy: dict[str, Any] | None = None,
) -> str:
    resolved_policy = _resolve_policy(policy)

    def cleaned_string(value: object) -> str:
        if isinstance(value, str):
            return _strip_noise(value, resolved_policy).strip(" .,:;()[]{}\"'")
        return ""

    def search(value: object, *, allow_raw: bool = False) -> str:
        if isinstance(value, dict):
            for key in _META_LEMMA_FIELD_NAMES:
                if key in value:
                    found = search(value.get(key), allow_raw=True)
                    if found:
                        return found
            for item in value.values():
                found = search(item, allow_raw=False)
                if found:
                    return found
            return ""
        if isinstance(value, (list, tuple)):
            for item in value:
                found = search(item, allow_raw=allow_raw)
                if found:
                    return found
            return ""

        direct = cleaned_string(value)
        if not direct:
            return ""
        meta = extract_meta_definition(direct, policy=resolved_policy)
        if meta is not None and meta.lemma:
            return meta.lemma
        return direct if allow_raw else ""

    return search(payload)


def compact_meta_note(meta: MetaDefinition) -> str:
    tags = set(meta.tags)
    parts: list[str] = []

    if "past participle" in tags:
        parts.append("past participle")
    elif "present participle" in tags:
        parts.append("present participle")
    elif "simple past" in tags or "past" in tags:
        parts.append("past tense")
    elif "present" in tags:
        parts.append("present tense")
    elif "future" in tags:
        parts.append("future tense")

    if "imperative" in tags:
        parts.append("imperative")
    elif "subjunctive" in tags:
        parts.append("subjunctive")
    elif "infinitive" in tags:
        parts.append("infinitive")
    elif "participle" in tags and not any("participle" in item for item in parts):
        parts.append("participle")

    if "perfective" in tags:
        parts.append("perfective")
    elif "imperfective" in tags:
        parts.append("imperfective")

    if not parts and any(tag not in ORTHOGRAPHIC_META_TAGS for tag in tags):
        parts.append("inflected form")
    return ", ".join(dict.fromkeys(parts))


def compose_resolved_meta_definition(
    semantic_definition: str,
    meta: MetaDefinition,
    *,
    policy: dict[str, Any] | None = None,
) -> str:
    resolved_policy = _resolve_policy(policy)
    normalized = normalize_definition(
        semantic_definition,
        "en",
        min_words=1,
        max_words=12,
        policy=resolved_policy,
    )
    if not normalized or extract_meta_definition(normalized, policy=resolved_policy):
        return ""

    semantic_pos, semantic_body = _extract_pos(
        _strip_noise(normalized, resolved_policy),
        resolved_policy,
    )
    pos_label = meta.pos_label or semantic_pos
    body = semantic_body.strip().rstrip(".")
    if not body:
        return ""

    if meta.is_verb:
        note = compact_meta_note(meta)
        if note:
            body = f"{body}, {note}"
        pos_label = pos_label or "verb"

    result = f"{pos_label}: {body}" if pos_label else body
    return _normalize_spacing(result, resolved_policy).rstrip(".")


def strip_definition_usage_notes(text: str) -> str:
    cleaned = str(text or "")
    if not cleaned:
        return ""
    patterns = [
        rf"\[[^\]]*\bwith\s+{_GRAMMATICAL_USAGE_PATTERN}\b[^\]]*\]",
        rf"\([^)]*\bwith\s+{_GRAMMATICAL_USAGE_PATTERN}\b[^)]*\)",
        rf"[,;]?\s*\bwith\s+{_GRAMMATICAL_USAGE_PATTERN}\b[^.;)]*",
        rf"[,;]?\s*\btaking\s+the\s+{_GRAMMATICAL_USAGE_PATTERN}\b[^.;)]*",
        r"\s+[\"'`][^\"'`]+[\"'`]\s*$",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    return cleaned


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
    label = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    label = "".join(char for char in label if not unicodedata.combining(char))
    label = re.sub(r"\s+", " ", label)
    return label.strip("()[]{}-:;,. ")


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
    cleaned = strip_definition_usage_notes(cleaned)
    if cleanup_cfg.get("strip_quotes", True):
        cleaned = cleaned.strip().strip("\"\u201c\u201d'")
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    cleaned = _normalize_spacing(cleaned, policy)
    if cleanup_cfg.get("collapse_whitespace", True):
        cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _extract_pos(text: str, policy: dict[str, Any]) -> tuple[str, str]:
    patterns = [
        re.compile(r"^\s*([^:]+):\s*\(([^()]+)\)\s*[-\u2013\u2014:]*\s*(.+)$"),
        re.compile(r"^\s*\(([^()]+)\)\s*[-\u2013\u2014:]*\s*(.+)$"),
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
    cleaned = re.sub(r"\([^()]+\)\s*[-\u2013\u2014:]*\s*", "", cleaned)
    cleaned = re.sub(r"\[[^\]]+\]", " ", cleaned)
    cleaned = re.sub(r"\[[^\]]*$", " ", cleaned)
    cleaned = strip_definition_usage_notes(cleaned)
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


def _normalize_meta_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or "").lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[\/\-\u2013\u2014]+", " ", normalized)
    normalized = re.sub(r"[^a-z\s]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _collect_morphology_tags(text: str) -> list[str]:
    normalized = _normalize_meta_text(text)
    tags: list[str] = []
    for tag, pattern in _MORPHOLOGY_TAG_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            tags.append(tag)
    return list(dict.fromkeys(tags))


set_default_definition_policy()
