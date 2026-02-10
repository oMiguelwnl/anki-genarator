from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from wordfreq import zipf_frequency

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


@dataclass
class DifficultyScore:
    average_zipf: float
    tokens: list[str]


def tokenize(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


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
    if focus.lower() not in sentence.lower():
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


def filter_frequent_words(words: Iterable[str], language: str, min_length: int = 3) -> list[str]:
    stopwords = STOPWORDS.get(language, set())
    result: list[str] = []
    for word in words:
        lower = word.lower()
        if len(lower) < min_length:
            continue
        if not lower.isalpha():
            continue
        if lower in stopwords:
            continue
        result.append(lower)
    return result


def score_sentence(sentence: str, focus: str, language: str) -> float:
    if not sentence:
        return 0.0
    tokens = tokenize(sentence)
    word_count = len(tokens)
    if word_count < 5 or word_count > 25:
        return 0.0
    if focus.lower() not in sentence.lower():
        return 0.0
    score = 1.0
    # Prefer medium length
    score += 1.0 - abs(12 - word_count) / 12
    # Prefer mid-frequency words
    diff = difficulty(sentence, language)
    if diff.tokens:
        score += max(0.0, min(1.0, (diff.average_zipf - 2.5) / 2.5))
    # Penalize excessive punctuation
    punctuation = sum(1 for ch in sentence if ch in {",", ";", ":", "(", ")", "\"", "“", "”"})
    score -= min(0.5, punctuation * 0.1)
    return score
