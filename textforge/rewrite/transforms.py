"""Transformation classes for text rewriting."""

from __future__ import annotations

from abc import ABC, abstractmethod

from textforge.models import RewriteContext, TransformationResult
from textforge.provenance.hashing import sha256_hash
from textforge.providers.base import RewriteProvider


class TextTransformation(ABC):
    name: str

    @abstractmethod
    async def apply(
        self,
        text: str,
        context: RewriteContext,
    ) -> TransformationResult: ...

    def _make_result(
        self,
        text: str,
        output: str,
        **params: str | int | float | bool | None,
    ) -> TransformationResult:
        return TransformationResult(
            text=output,
            transformation_name=self.name,
            input_hash=sha256_hash(text),
            output_hash=sha256_hash(output),
            parameters=params,
        )


class LLMTransformation(TextTransformation):
    """Base for transformations that delegate to an LLM."""

    def __init__(self, provider: RewriteProvider, model: str | None = None):
        self._provider = provider
        self._model = model

    async def _rewrite_with_instruction(
        self,
        text: str,
        instruction: str,
    ) -> str:
        system = f"You are a text editor. {instruction}\n\nReturn ONLY the modified text."
        response = await self._provider.rewrite(text, system, model=self._model, temperature=0.3)
        return response.text.strip()


class SentenceRestructure(LLMTransformation):
    name = "sentence_restructure"

    async def apply(self, text: str, context: RewriteContext) -> TransformationResult:
        output = await self._rewrite_with_instruction(
            text,
            "Restructure sentences for improved clarity and flow. "
            "Do not change meaning. Preserve all <TF_PROTECTED_XXXX> placeholders exactly.",
        )
        return self._make_result(text, output)


class SentenceSplit(LLMTransformation):
    name = "sentence_split"

    async def apply(self, text: str, context: RewriteContext) -> TransformationResult:
        if not context.allow_sentence_split:
            return self._make_result(text, text)
        output = await self._rewrite_with_instruction(
            text,
            "Split long or complex sentences into shorter, clearer ones. "
            "Preserve meaning and all <TF_PROTECTED_XXXX> placeholders exactly.",
        )
        return self._make_result(text, output)


class SentenceMerge(LLMTransformation):
    name = "sentence_merge"

    async def apply(self, text: str, context: RewriteContext) -> TransformationResult:
        if not context.allow_sentence_merge:
            return self._make_result(text, text)
        output = await self._rewrite_with_instruction(
            text,
            "Merge short, related sentences for better flow. "
            "Preserve meaning and all <TF_PROTECTED_XXXX> placeholders exactly.",
        )
        return self._make_result(text, output)


class ParagraphRestructure(LLMTransformation):
    name = "paragraph_restructure"

    async def apply(self, text: str, context: RewriteContext) -> TransformationResult:
        output = await self._rewrite_with_instruction(
            text,
            "Restructure paragraphs for improved organization and logical flow. "
            "Preserve meaning, paragraph count, and all <TF_PROTECTED_XXXX> placeholders exactly.",
        )
        return self._make_result(text, output)


class ConciseRewrite(LLMTransformation):
    name = "concise_rewrite"

    async def apply(self, text: str, context: RewriteContext) -> TransformationResult:
        output = await self._rewrite_with_instruction(
            text,
            "Make the text more concise. Remove redundancy and verbosity while "
            "preserving all key information and <TF_PROTECTED_XXXX> placeholders.",
        )
        return self._make_result(text, output)


class ExpansionRewrite(LLMTransformation):
    name = "expansion_rewrite"

    async def apply(self, text: str, context: RewriteContext) -> TransformationResult:
        output = await self._rewrite_with_instruction(
            text,
            "Expand terse or unclear passages. Add clarifying language without "
            "introducing new facts. Preserve all <TF_PROTECTED_XXXX> placeholders.",
        )
        return self._make_result(text, output)


class ToneNormalize(LLMTransformation):
    name = "tone_normalize"

    async def apply(self, text: str, context: RewriteContext) -> TransformationResult:
        output = await self._rewrite_with_instruction(
            text,
            "Normalize the tone to be consistent and even. Remove emotional "
            "or informal language while preserving meaning and placeholders.",
        )
        return self._make_result(text, output)


class RegisterShift(LLMTransformation):
    name = "register_shift"

    async def apply(self, text: str, context: RewriteContext) -> TransformationResult:
        if context.preserve_register:
            return self._make_result(text, text)
        output = await self._rewrite_with_instruction(
            text,
            f"Shift the register of this text to match the {context.profile_name} style. "
            "Preserve meaning and all <TF_PROTECTED_XXXX> placeholders.",
        )
        return self._make_result(text, output)


class TerminologyNormalize(LLMTransformation):
    name = "terminology_normalize"

    async def apply(self, text: str, context: RewriteContext) -> TransformationResult:
        if context.preserve_technical_terms:
            return self._make_result(text, text)
        output = await self._rewrite_with_instruction(
            text,
            "Normalize terminology to use standard, widely-accepted terms. "
            "Preserve meaning and all <TF_PROTECTED_XXXX> placeholders.",
        )
        return self._make_result(text, output)


class DiscourseRewrite(LLMTransformation):
    name = "discourse_rewrite"

    async def apply(self, text: str, context: RewriteContext) -> TransformationResult:
        output = await self._rewrite_with_instruction(
            text,
            "Improve the discourse structure: transitions, cohesion, and argument flow. "
            "Preserve meaning and all <TF_PROTECTED_XXXX> placeholders.",
        )
        return self._make_result(text, output)
