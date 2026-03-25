from ankideck_generator.utils.definition_tools import (
    definition_has_pos,
    normalize_definition,
)


def test_normalize_definition_reorders_pos_from_parentheses() -> None:
    value = normalize_definition(
        "Early morning: (feminine noun) The part of the night before dawn.",
        "en",
        min_words=4,
        max_words=12,
    )
    assert value == "feminine noun: the part of the night before dawn."


def test_normalize_definition_keeps_extended_pos_labels() -> None:
    value = normalize_definition(
        "determiner: used before nouns to specify or identify them",
        "en",
        min_words=4,
        max_words=12,
    )
    assert value.startswith("determiner:")
    assert definition_has_pos(value) is True


def test_normalize_definition_maps_spanish_pos_aliases() -> None:
    value = normalize_definition(
        "Hay: (sustantivo) Hierba seca para alimentar a los animales.",
        "es",
        min_words=4,
        max_words=12,
    )
    assert value == "noun: hierba seca para alimentar a los animales."


def test_normalize_definition_keeps_cyrillic_body() -> None:
    value = normalize_definition(
        "noun: важное понятие в обычной жизни",
        "ru",
        min_words=2,
        max_words=12,
    )
    assert value.startswith("noun:")
    assert "важное понятие" in value
