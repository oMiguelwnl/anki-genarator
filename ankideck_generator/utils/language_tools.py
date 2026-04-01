from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable

from wordfreq import zipf_frequency

try:
    from langdetect import DetectorFactory, detect_langs
except Exception:  # pragma: no cover - optional
    DetectorFactory = None
    detect_langs = None

if DetectorFactory is not None:  # pragma: no branch - deterministic language detection
    DetectorFactory.seed = 0

LANG_CODE_TO_NAME = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "de": "German",
    "ru": "Russian",
}

SENTENCE_TEMPLATES = {
    "en": [
        "I saw the {focus} today at the market.",
        "The {focus} is important for my daily routine.",
        "We talked about the {focus} in class this morning.",
        "She uses the {focus} every day at work.",
    ],
    "es": [
        "Vi la {focus} hoy en el mercado de la ciudad.",
        "La {focus} es importante para mi rutina diaria.",
        "Hablamos de la {focus} en clase esta manana.",
        "Ella usa la {focus} cada dia en el trabajo.",
    ],
    "fr": [
        "J'ai vu le {focus} aujourd'hui au marche.",
        "Le {focus} est important pour ma routine quotidienne.",
        "Nous avons parle du {focus} en classe ce matin.",
        "Elle utilise le {focus} chaque jour au travail.",
    ],
    "it": [
        "Ho visto il {focus} oggi al mercato.",
        "Il {focus} e importante per la mia routine quotidiana.",
        "Abbiamo parlato del {focus} in classe questa mattina.",
        "Lei usa il {focus} ogni giorno al lavoro.",
    ],
    "de": [
        "Ich habe das {focus} heute auf dem Markt gesehen.",
        "Das {focus} ist wichtig fur meine tagliche Routine.",
        "Wir haben uber das {focus} im Kurs heute Morgen gesprochen.",
        "Sie benutzt das {focus} jeden Tag bei der Arbeit.",
    ],
    "ru": [
        "Ya videl {focus} segodnya na rynke.",
        "{focus} vazhno dlya moei ezhednevnoi rutiny.",
        "My govorili o {focus} na uroke segodnya utrom.",
        "Ona ispolzuet {focus} kazhdyi den na rabote.",
    ],
}

WORD_RE = re.compile(r"[\w'-]+", re.UNICODE)
META_DEFINITION_PATTERNS = [
    re.compile(
        r"\b(?:inflection|form|imperative|participle|plural|singular)\s+of\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:simple past|past participle|present participle)\s+of\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:genitive|accusative|dative|prepositional|instrumental|locative|ablative|nominative|vocative)\b.*\bof\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bthe word\b.+\bnot a\b.+\bword\b", re.IGNORECASE),
    re.compile(r"\bused as a greeting or farewell\b", re.IGNORECASE),
    re.compile(r"\bdialects?\s+of\b", re.IGNORECASE),
    re.compile(r"\bdepending on the context\b", re.IGNORECASE),
]

STOPWORDS = {
    "en": {
        "the", "a", "an", "and", "or", "but", "if", "then", "than", "that", "this", "these", "those",
        "is", "are", "was", "were", "be", "been", "being", "to", "of", "in", "on", "at", "for", "from",
        "with", "without", "as", "by", "about", "into", "over", "under", "after", "before", "between",
        "it", "its", "he", "she", "they", "we", "you", "i", "me", "him", "her", "them", "us", "my",
        "your", "his", "their", "our", "not", "no", "yes", "do", "does", "did", "so",
    },
    "es": {
        "el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "pero", "si", "que", "como",
        "de", "del", "al", "a", "en", "por", "para", "con", "sin", "sobre", "entre", "desde", "hasta",
        "es", "son", "era", "eran", "ser", "estar", "esta", "este", "estos", "estas", "eso", "esa",
        "yo", "tu", "el", "ella", "nosotros", "vosotros", "ellos", "ellas", "me", "te", "se", "lo",
        "la", "le", "les", "mi", "mis", "tu", "tus", "su", "sus", "no", "si", "ya",
    },
    "fr": {
        "le", "la", "les", "un", "une", "des", "et", "ou", "mais", "si", "que", "quoi", "comme",
        "de", "du", "au", "aux", "a", "en", "pour", "par", "avec", "sans", "sur", "entre", "depuis",
        "est", "sont", "etait", "etaient", "etre", "avoir", "ce", "cet", "cette", "ces", "je", "tu",
        "il", "elle", "nous", "vous", "ils", "elles", "me", "te", "se", "mon", "ma", "mes", "ton",
        "ta", "tes", "son", "sa", "ses", "pas", "non",
    },
    "it": {
        "il", "lo", "la", "i", "gli", "le", "un", "una", "uno", "e", "o", "ma", "se", "che", "come",
        "di", "del", "della", "dello", "dei", "degli", "delle", "a", "in", "per", "con", "senza",
        "su", "tra", "fra", "e", "da", "al", "allo", "alla", "ai", "agli", "alle", "sono", "e",
        "era", "erano", "essere", "avere", "questo", "questa", "questi", "queste", "io", "tu", "lui",
        "lei", "noi", "voi", "loro", "mi", "ti", "si", "mio", "mia", "miei", "mie", "tuo", "tua",
        "tuoi", "tue", "suo", "sua", "suoi", "sue", "non",
    },
    "de": {
        "der", "die", "das", "ein", "eine", "und", "oder", "aber", "wenn", "dass", "wie", "zu", "von",
        "für", "mit", "ohne", "auf", "an", "in", "im", "am", "aus", "bei", "über", "unter", "zwischen",
        "ist", "sind", "war", "waren", "sein", "haben", "ich", "du", "er", "sie", "es", "wir", "ihr",
        "sie", "mich", "dich", "sich", "mein", "dein", "sein", "ihr", "unser", "euer", "kein", "nicht",
    },
    "ru": {
        "и", "а", "но", "или", "что", "как", "в", "на", "к", "с", "со", "по", "за", "от", "до", "без",
        "из", "у", "о", "об", "для", "при", "про", "над", "под", "между", "это", "тот", "та", "то",
        "эти", "этот", "эта", "там", "тут", "он", "она", "они", "мы", "вы", "я", "ты", "его", "ее",
        "их", "мой", "твой", "наш", "ваш", "есть", "был", "были", "не",
    },
}


CLOSED_CLASS_WORDS: dict[str, set[str]] = {
    "en": {
        "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by", "for",
        "from", "had", "has", "have", "he", "her", "hers", "him", "his", "i", "if", "in",
        "into", "is", "it", "its", "me", "my", "of", "on", "or", "our", "ours", "she",
        "that", "the", "their", "theirs", "them", "they", "this", "those", "to", "us",
        "we", "were", "what", "which", "who", "whom", "with", "you", "your", "yours",
    },
    "es": {
        "a", "al", "con", "de", "del", "el", "ella", "ellas", "ellos", "en", "la", "las",
        "le", "les", "lo", "los", "me", "mi", "mis", "nos", "nosotros", "o", "para", "por",
        "que", "se", "si", "sin", "su", "sus", "te", "tu", "tus", "un", "una", "uno", "unos", "y",
    },
    "fr": {
        "a", "au", "aux", "avec", "ce", "ces", "dans", "de", "des", "du", "elle", "elles",
        "en", "et", "il", "ils", "je", "la", "le", "les", "leur", "leurs", "lui", "ma", "mes",
        "moi", "mon", "nous", "ou", "par", "pas", "pour", "que", "qui", "sa", "se", "ses",
        "son", "sur", "ta", "te", "tes", "toi", "tu", "un", "une", "vous", "y",
    },
    "it": {
        "a", "al", "alla", "alle", "allo", "che", "con", "da", "dal", "dalla", "dalle", "dello",
        "dei", "del", "della", "di", "e", "gli", "ha", "i", "il", "in", "io", "la", "le", "lo",
        "lui", "ma", "mi", "ne", "noi", "o", "per", "quale", "quali", "se", "si", "su", "sua",
        "sue", "sul", "sulla", "te", "ti", "tra", "tu", "un", "una", "uno", "voi",
    },
    "de": {
        "aber", "als", "am", "an", "auch", "auf", "aus", "bei", "bis", "da", "das", "dass",
        "dein", "dem", "den", "der", "des", "die", "du", "ein", "eine", "einem", "einen",
        "einer", "es", "für", "hat", "ich", "ihr", "im", "in", "ist", "mit", "nach", "nicht",
        "oder", "sein", "seine", "sich", "sie", "und", "uns", "vom", "von", "war", "wir", "zu",
    },
    "ru": {
        "\u0430", "\u0431\u0435\u0437", "\u0431\u044b", "\u0432", "\u0432\u0430\u0441", "\u0432\u0430\u043c",
        "\u0432\u0430\u0448", "\u0432\u0430\u0448\u0430", "\u0432\u0430\u0448\u0435", "\u0432\u0430\u0448\u0438",
        "\u0432\u0430\u0448\u0435\u0433\u043e", "\u0432\u0430\u0448\u0435\u043c\u0443", "\u0432\u0430\u0448\u0438\u0445",
        "\u0432\u0441\u0435", "\u0432\u0441\u0435\u0445", "\u0432\u0441\u0435\u043c", "\u0432\u044b", "\u0433\u0434\u0435",
        "\u0434\u0430", "\u0434\u043b\u044f", "\u0435\u0433\u043e", "\u0435\u0435", "\u0435\u0451", "\u0438",
        "\u0438\u043b\u0438", "\u0438\u043c", "\u0438\u043c\u0438", "\u0438\u0445", "\u043a", "\u043a\u0430\u043a",
        "\u043a\u0442\u043e", "\u043c\u0435\u043d\u044f", "\u043c\u043d\u0435", "\u043c\u043e\u0439", "\u043c\u044b",
        "\u043d\u0430", "\u043d\u0430\u0441", "\u043d\u0435", "\u043d\u0435\u0433\u043e", "\u043d\u0435\u0439",
        "\u043d\u0438\u0445", "\u043d\u043e", "\u043e", "\u043e\u043d", "\u043e\u043d\u0430", "\u043e\u043d\u0438",
        "\u043e\u0442", "\u043f\u043e", "\u043f\u043e\u0442\u043e\u043c\u0443", "\u043f\u043e\u0447\u0435\u043c\u0443",
        "\u043f\u0440\u0438", "\u0441", "\u0441\u0435\u0431\u044f", "\u0442\u0430\u043a", "\u0442\u0435\u0431\u0435",
        "\u0442\u044b", "\u0443", "\u0447\u0435\u0433\u043e", "\u0447\u0442\u043e", "\u044d\u0442\u043e",
        "\u044d\u0442\u043e\u043c", "\u044f",
    },
}


@dataclass
class DifficultyScore:
    average_zipf: float
    tokens: list[str]


def tokenize(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def _normalize_focus_token(value: str) -> str:
    return str(value or "").strip().lower().replace("’", "'")


def text_contains_focus(text: str, focus: str) -> bool:
    focus_tokens = [_normalize_focus_token(token) for token in tokenize(focus)]
    sentence_tokens = [_normalize_focus_token(token) for token in tokenize(text)]
    if not focus_tokens or not sentence_tokens:
        return False
    if len(focus_tokens) == 1:
        return focus_tokens[0] in sentence_tokens
    window = len(focus_tokens)
    for index in range(0, len(sentence_tokens) - window + 1):
        if sentence_tokens[index : index + window] == focus_tokens:
            return True
    return False


def valid_focus_characters(text: str) -> bool:
    for char in text:
        if char.isalpha() or char in {"-", "'", "’"}:
            continue
        return False
    return True


def valid_sentence_characters(text: str) -> bool:
    for char in text:
        if char.isalpha() or char.isdigit() or char.isspace():
            continue
        if char in {"-", "—", "–", "'", "’", "\"", "“", "”", ",", ".", "!", "?", "¿", "¡", ":", ";", "(", ")", "…"}:
            continue
        return False
    return True


def sentence_from_templates(focus: str, language: str) -> str:
    templates = SENTENCE_TEMPLATES.get(language) or SENTENCE_TEMPLATES["en"]
    template = templates[hash(focus) % len(templates)]
    return template.format(focus=focus)


def sentence_is_acceptable(sentence: str, focus: str, min_len: int, max_len: int) -> bool:
    word_count = len(sentence.split())
    if not (min_len <= word_count <= max_len):
        return False
    if not text_contains_focus(sentence, focus):
        return False
    return True


def difficulty(sentence: str, language: str) -> DifficultyScore:
    tokens = [token for token in tokenize(sentence) if token.isalpha()]
    if not tokens:
        return DifficultyScore(average_zipf=0.0, tokens=[])
    scores = [zipf_frequency(token, language) for token in tokens]
    average = sum(scores) / len(scores)
    return DifficultyScore(average_zipf=average, tokens=tokens)


def unique_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def is_closed_class_word(word: str, language: str) -> bool:
    language_code = normalize_language_code(language)
    lexicon = CLOSED_CLASS_WORDS.get(language_code, set())
    return word.lower() in lexicon


def filter_frequent_words(
    words: Iterable[str],
    language: str,
    min_length: int = 3,
    *,
    exclude_closed_class_words: bool = True,
) -> list[str]:
    stopwords = CLOSED_CLASS_WORDS.get(normalize_language_code(language), set())
    result: list[str] = []
    for word in words:
        lower = word.lower()
        if len(lower) < min_length:
            continue
        if not lower.isalpha():
            continue
        if exclude_closed_class_words and lower in stopwords:
            continue
        result.append(lower)
    return result


def score_sentence(
    sentence: str,
    focus: str,
    language: str,
    *,
    min_words: int = 5,
    max_words: int = 25,
) -> float:
    if not sentence:
        return 0.0
    tokens = tokenize(sentence)
    word_count = len(tokens)
    if word_count < min_words or word_count > max_words:
        return 0.0
    if not text_contains_focus(sentence, focus):
        return 0.0
    score = 1.0
    score += 1.0 - abs(12 - word_count) / 12
    diff = difficulty(sentence, language)
    if diff.tokens:
        score += max(0.0, min(1.0, (diff.average_zipf - 2.5) / 2.5))
    punctuation = sum(1 for ch in sentence if ch in {",", ";", ":", "(", ")", "\"", "“", "”"})
    score -= min(0.5, punctuation * 0.1)
    return score


def normalize_language_code(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip().lower()
    if "-" in text:
        text = text.split("-", 1)[0]
    return text


def text_language_score(text: str, expected_language: str) -> float:
    language = normalize_language_code(expected_language)
    tokens = [token for token in tokenize(text) if any(ch.isalpha() for ch in token)]
    if not language or not tokens:
        return 0.0

    stopwords = STOPWORDS.get(language, set()) | CLOSED_CLASS_WORDS.get(language, set())
    stopword_hits = sum(1 for token in tokens if token in stopwords)
    stopword_score = stopword_hits / len(tokens)

    detect_score = 0.0
    if detect_langs is not None and len(" ".join(tokens)) >= 8:
        try:
            matches = detect_langs(text)
        except Exception:  # pragma: no cover - optional
            matches = []
        for match in matches:
            if normalize_language_code(getattr(match, "lang", "")) == language:
                detect_score = max(detect_score, float(getattr(match, "prob", 0.0)))

    return max(detect_score, min(1.0, stopword_score * 2.5))


def text_matches_language(
    text: str,
    expected_language: str,
    *,
    min_score: float = 0.55,
    min_tokens: int = 2,
) -> bool:
    tokens = [token for token in tokenize(text) if any(ch.isalpha() for ch in token)]
    if len(tokens) < min_tokens:
        return False
    return text_language_score(text, expected_language) >= min_score


def semantic_definition_reason(text: str, focus: str = "") -> str | None:
    cleaned = (text or "").strip()
    if not cleaned:
        return "definition_missing"

    alpha_tokens = [token for token in tokenize(cleaned) if token.isalpha()]
    if len(alpha_tokens) < 3:
        return "definition_too_short"

    for pattern in META_DEFINITION_PATTERNS:
        if pattern.search(cleaned):
            return "definition_nonsemantic"

    if focus:
        lower = cleaned.lower()
        quoted_focus = f'"{focus.lower()}"'
        if quoted_focus in lower or f"'{focus.lower()}'" in lower:
            return "definition_nonsemantic"

    language_names = {name.lower() for name in LANG_CODE_TO_NAME.values()}
    lower_tokens = {token.lower() for token in alpha_tokens}
    if lower_tokens.intersection(language_names):
        return "definition_mentions_other_language"

    return None


def is_semantic_definition(text: str, focus: str = "") -> bool:
    return semantic_definition_reason(text, focus) is None


def compact_audio_basename(
    language: str,
    kind: str,
    text: str,
    *,
    slug_words: int = 4,
    extra: str = "",
) -> str:
    slug_tokens = tokenize(text)[: max(1, slug_words)]
    slug = "-".join(slug_tokens).lower()
    slug = re.sub(r"[^a-z0-9\-]+", "", slug)
    slug = slug[:24].strip("-") or kind
    digest_input = f"{language}|{kind}|{text}|{extra}".encode("utf-8")
    digest = hashlib.sha1(digest_input).hexdigest()[:8]
    return f"{language}_{kind}_{slug}_{digest}"
