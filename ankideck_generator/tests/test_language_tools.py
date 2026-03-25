from ankideck_generator.utils.language_tools import (
    filter_frequent_words,
    semantic_definition_reason,
)


def test_filter_frequent_words_excludes_closed_class_words_all_languages() -> None:
    samples = {
        "en": ["the", "market", "you", "garden"],
        "es": ["el", "mercado", "ella", "jardin"],
        "fr": ["vous", "marche", "table", "qui"],
        "it": ["voi", "mercato", "casa", "che"],
        "de": ["und", "markt", "haus", "sie"],
        "ru": ["\u0432\u0430\u0441", "\u0440\u044b\u043d\u043e\u043a", "\u0434\u043e\u043c", "\u043c\u043d\u0435"],
    }

    for language, words in samples.items():
        filtered = filter_frequent_words(words, language, min_length=2)
        assert len(filtered) == 2


def test_filter_frequent_words_can_include_closed_class_words_when_disabled() -> None:
    words = ["the", "market", "you"]
    filtered = filter_frequent_words(
        words,
        "en",
        min_length=2,
        exclude_closed_class_words=False,
    )
    assert filtered == ["the", "market", "you"]


def test_semantic_definition_reason_rejects_case_form_definitions() -> None:
    reason = semantic_definition_reason(
        "pronoun: genitive / accusative / prepositional of you.",
        "vas",
    )
    assert reason == "definition_nonsemantic"
