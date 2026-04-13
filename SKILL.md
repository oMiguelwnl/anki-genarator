---
name: ankideck-generator-maintainer
description: Maintain and improve the Anki deck generator repository in this workspace. Use when Codex, Claude, or another coding agent is asked to work on deck generation quality, natural example sentences, semantic definitions, frequency-ordered word selection, provider fallback behavior, export behavior, or pytest-backed refactors in `ankideck_generator`. Trigger especially for requests about "frases naturais", "definitions", "palavras mais comuns", "remover template", "time budget", Tatoeba failures, Russian deck quality, or integrating a better external Python generator.
---

# Ankideck Generator Maintainer

## Start here

- Read `AGENTS.md` first for repo-specific commands, runtime gotchas, and behaviors to preserve.
- Read `TODO.md` and the root `alter*.md` change-notes file when the request is about deck quality, sentence quality, definition quality, or Russian generation problems.
- Run from the repo root.
- Use Python `3.11`.
- Treat `output/` and `ankideck_generator/data/{audio,cache,logs,progress}` as generated artifacts, not hand-maintained source files.

## Key files

- Use `ankideck_generator/main.py` for CLI flags, runtime wiring, and startup validation.
- Use `ankideck_generator/core/deck_builder.py` for word selection, orchestration, sentence selection, definition selection, progress handling, and export inputs.
- Use `ankideck_generator/core/providers.py` for provider fallback, HTTP calls, Tatoeba access, AI generation, and TTS.
- Use `ankideck_generator/utils/definition_tools.py` plus `definition_policy.yaml` for definition cleanup and policy-based fixes.
- Use `ankideck_generator/utils/language_tools.py` for tokenization, scoring, similarity, and frequency helpers.
- Use `ankideck_generator/tests/` as the contract for behavior.
- Inspect `vocabGenarator.py` if the request references the external Python project with better sentence or definition generation.

## Working rules

- Preserve the tested provider fallback order unless the user explicitly asks to change it.
- Keep definition providers in this order: `wiktionary -> wordnet -> dictionaryapi -> ai`.
- Keep translation providers in this order: `googletrans -> deepl -> libretranslate -> ai`.
- Keep sentence providers in this order: `tatoeba -> wordincontext -> ai`.
- Prefer policy or config edits before hardcoding cleanup logic.
- Keep AI as fallback unless the user explicitly wants a different strategy.
- Reject low-quality sentence fallbacks such as fixed templates, isolated focus words, and near-duplicate seeds.
- Prefer real corpus sentences or AI-generated natural sentences that clearly use the focus word in context.
- Prefer the primary semantic meaning of the word. Do not surface glosses like `alternative spelling of X` as the main definition when a real meaning exists.
- Use frequency-ordered word selection when the task is about "most common words". `wordfreq` is already available in `deck_builder.py`.
- Preserve export field order behavior unless the task explicitly asks to wire language-specific templates.

## Quality checklist

- Confirm the focus word appears in the sentence naturally.
- Reject sentences that are templated, too short, duplicated, or not in the target language.
- Confirm the definition is semantic, not just orthographic or morphological trivia.
- Confirm the definition language and translation align with the target word.
- Check `Run summary`, `source_mix`, and review queue output when diagnosing regressions.
- Update counters, summary fields, and tests when removing a fallback path or changing selection logic.

## Common task map

- For "remove time budget", inspect `RunConfig`, level loops, and any stop conditions that emit `stopping by time budget`.
- For "remove template fallback", inspect sentence selection and fallback stages in `deck_builder.py` and `providers.py`.
- For "bad seed sentences", inspect how sentence candidates are synthesized, rewritten, or accepted after validation.
- For "bad definitions", inspect `DefinitionSelectionCandidate`, `build_definition`, `normalize_definition`, `trim_definition_body`, and definition policy rules.
- For "most common words first", inspect the frequency pipeline and any use of `top_n_list` or related ranking helpers.
- For "duplicate or near-duplicate sentences", inspect similarity checks and sentence acceptance rules in validation and selection code.
- For "integrate better external generator", compare the external logic against current providers first, then port reusable pieces behind tests.

## Commands

- Install dependencies with `python -m pip install -r requirements.txt`.
- Run the CLI from the repo root with `python -m ankideck_generator --language es --mode build --no-resume --output output/deck.apkg`.
- Remember that `--mode build` is an alias for `full`.
- Use `python -m pytest -q` for the broad test pass.
- Use targeted tests in `ankideck_generator/tests/` when changing sentence selection, definitions, export, or CLI behavior.
