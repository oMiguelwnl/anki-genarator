from ankideck_generator.utils.cache_refresh import refresh_russian_caches


def test_refresh_russian_caches_repairs_definitions_and_removes_bad_translations() -> None:
    definitions = {
        "управления::ru::v3": "noun: genitive singular.",
        "управления::en::v3": "noun: genitive singular.",
        "купить::en::v3": "verb: to buy , to purchase [ with accusative",
    }
    translations = {
        "Это автомобиль с системой автоматического управления.::ru->en::v3": (
            "This sentence uses a word that means genitive singular."
        )
    }
    sentences = {
        "управления::lvl2::4-10::v3": "Это автомобиль с системой автоматического управления."
    }

    def resolve_definition(word: str, sentence: str | None) -> str | None:
        if word == "управления":
            assert sentence == "Это автомобиль с системой автоматического управления."
            return "noun: control, administration"
        return None

    stats = refresh_russian_caches(
        definitions,
        translations,
        sentences,
        resolve_definition=resolve_definition,
        resolve_translation=lambda _sentence: None,
    )

    assert definitions["управления::en::v3"] == "noun: control, administration"
    assert "управления::ru::v3" not in definitions
    assert definitions["купить::en::v3"] == "verb: to buy, to purchase"
    assert translations == {}
    assert stats.definitions_refreshed == 1
    assert stats.definition_entries_removed == 1
    assert stats.definitions_normalized == 1
    assert stats.translations_removed == 1


def test_refresh_russian_caches_replaces_synthetic_translation_when_real_one_exists() -> None:
    definitions: dict[str, str] = {}
    translations = {
        "Он говорил спокойно.::ru->en::v3": (
            "This sentence uses a word that means past tense."
        )
    }
    sentences: dict[str, str] = {}

    stats = refresh_russian_caches(
        definitions,
        translations,
        sentences,
        resolve_definition=lambda _word, _sentence: None,
        resolve_translation=lambda sentence: "He spoke calmly." if sentence == "Он говорил спокойно." else None,
    )

    assert translations["Он говорил спокойно.::ru->en::v3"] == "He spoke calmly."
    assert stats.translations_refreshed == 1
    assert stats.translations_removed == 0


def test_refresh_russian_caches_removes_unresolved_bad_definitions() -> None:
    definitions = {
        "управления::ru::v3": "noun: genitive singular.",
        "управления::en::v3": "noun: genitive singular.",
    }

    stats = refresh_russian_caches(
        definitions,
        translations={},
        sentences={},
        resolve_definition=lambda _word, _sentence: None,
        resolve_translation=lambda _sentence: None,
    )

    assert definitions == {}
    assert stats.definition_entries_removed == 2
