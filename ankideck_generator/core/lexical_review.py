from __future__ import annotations

from .models import LexicalReviewRequest, LexicalReviewResult


class LexicalReviewService:
    def __init__(self, providers) -> None:
        self.providers = providers

    def review(self, request: LexicalReviewRequest) -> LexicalReviewResult:
        transport = getattr(self.providers, "lexical_review", None)
        provider_result = transport(request) if callable(transport) else None
        base = provider_result.review if provider_result and provider_result.review else None

        winning_sense, reason = self._resolve_winning_sense(request, base)
        reason_codes = list(dict.fromkeys((list(base.reason_codes) if base else []) + ([] if winning_sense else ["lexical_review_unresolved_ambiguity"])))

        if winning_sense is None:
            selection_reasons = dict(request.selection_reasons)
            if base:
                selection_reasons.update(base.selection_reasons)
            if reason:
                selection_reasons.setdefault("winning_sense", reason)
            return LexicalReviewResult(
                verdict="reject",
                focus_word=request.focus_word,
                language=request.language,
                target_translation_language=request.target_translation_language,
                accepted_sentence=request.accepted_sentence,
                current_definition=request.current_definition,
                current_translation=request.current_translation,
                source_definition=request.source_definition,
                candidate_senses=list(request.candidate_senses),
                winning_sense=None,
                losing_sense_candidates=list(request.candidate_senses),
                reason_codes=reason_codes,
                confidence=(base.confidence if base else request.confidence),
                before=dict(request.before),
                after=dict(request.after),
                selection_reasons=selection_reasons,
            )

        losing = [sense for sense in request.candidate_senses if sense != winning_sense]
        corrected_definition = None
        corrected_translation = base.corrected_translation if base else None
        if base and base.corrected_definition:
            corrected_definition = base.corrected_definition
        elif request.current_definition.strip() != winning_sense.strip():
            corrected_definition = winning_sense

        verdict = "correct" if corrected_definition or corrected_translation else "accept"
        before = dict(request.before) or {
            "definition": request.current_definition,
            "translation": request.current_translation,
        }
        after = dict(request.after)
        if corrected_definition:
            after.setdefault("definition", corrected_definition)
        if corrected_translation:
            after.setdefault("translation", corrected_translation)

        selection_reasons = dict(request.selection_reasons)
        if base:
            selection_reasons.update(base.selection_reasons)
        if reason and not selection_reasons.get("winning_sense"):
            selection_reasons["winning_sense"] = reason

        return LexicalReviewResult(
            verdict=verdict,
            focus_word=request.focus_word,
            language=request.language,
            target_translation_language=request.target_translation_language,
            accepted_sentence=request.accepted_sentence,
            current_definition=request.current_definition,
            current_translation=request.current_translation,
            source_definition=request.source_definition,
            candidate_senses=list(request.candidate_senses),
            winning_sense=winning_sense,
            losing_sense_candidates=losing,
            corrected_definition=corrected_definition,
            corrected_translation=corrected_translation,
            reason_codes=reason_codes,
            confidence=(base.confidence if base else request.confidence),
            before=before,
            after=after,
            selection_reasons=selection_reasons,
        )

    def _resolve_winning_sense(
        self,
        request: LexicalReviewRequest,
        base: LexicalReviewResult | None,
    ) -> tuple[str | None, str | None]:
        if base and base.winning_sense:
            return base.winning_sense, base.selection_reasons.get("winning_sense")
        if request.winning_sense:
            return request.winning_sense, request.selection_reasons.get("winning_sense")
        if len(request.candidate_senses) == 1:
            return request.candidate_senses[0], "single_candidate"

        source_definition = request.source_definition.strip().casefold()
        if source_definition:
            matches = [
                sense for sense in request.candidate_senses if sense.strip().casefold() == source_definition
            ]
            if len(matches) == 1:
                return matches[0], "matched_source_definition"

        return None, None
