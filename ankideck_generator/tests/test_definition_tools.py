from ankideck_generator.utils.definition_tools import (
    compact_meta_note,
    compose_resolved_meta_definition,
    definition_has_pos,
    extract_meta_definition,
    normalize_definition,
    strip_definition_usage_notes,
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


def test_normalize_definition_strips_wiktionary_markup_noise() -> None:
    value = normalize_definition(
        "particle: there is not, there are no .mw-parser-output .object-usage-tag{font-style:italic}.mw-parser-output .deprecated{color:var} [ with genitive",
        "en",
        min_words=4,
        max_words=12,
    )
    assert value == "particle: there is not, there are no."


def test_normalize_definition_normalizes_list_spacing() -> None:
    value = normalize_definition(
        "adverb: maybe , perhaps , possibly",
        "en",
        min_words=2,
        max_words=12,
    )
    assert value == "adverb: maybe, perhaps, possibly."


def test_extract_meta_definition_builds_compact_verb_note() -> None:
    meta = extract_meta_definition(
        "verb: masculine singular past indicative imperfective of говори́ть"
    )
    assert meta is not None
    assert meta.lemma == "говори́ть"
    assert compact_meta_note(meta) == "past tense, imperfective"


def test_compose_resolved_meta_definition_omits_noun_case_note() -> None:
    meta = extract_meta_definition("noun: genitive singular of управление")
    assert meta is not None

    value = compose_resolved_meta_definition(
        "noun: control, administration",
        meta,
    )

    assert value == "noun: control, administration"


def test_strip_definition_usage_notes_removes_case_hints() -> None:
    value = strip_definition_usage_notes(
        "to buy, to purchase [with accusative 'something']"
    )
    assert "with accusative" not in value
