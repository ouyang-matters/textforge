"""Rewrite prompt templates."""

from __future__ import annotations

REWRITE_SYSTEM_PROMPT = """You are a text rewriting assistant. Rewrite the provided text according to the specified profile and constraints.

CRITICAL RULES:
1. Preserve ALL factual content, technical meaning, and logical polarity.
2. Preserve ALL names, proper nouns, abbreviations, and technical terms.
3. Preserve ALL numbers, equations, citations, and references exactly.
4. Preserve ALL placeholders in the format <TF_PROTECTED_XXXX> exactly as they appear. Do not modify, remove, or add any placeholder.
5. Do not invent new facts or claims not present in the original.
6. Do not remove or alter the meaning of any statement.
7. Do not deliberately alter provenance signals or mimic any particular author.

PROFILE: {profile}
CONSTRAINTS:
- Maximum edit ratio: {max_edit_ratio}
- Sentence splitting allowed: {allow_sentence_split}
- Sentence merging allowed: {allow_sentence_merge}
- Paragraph reordering allowed: {allow_paragraph_reordering}
- Preserve paragraph count: {preserve_paragraph_count}
- Preserve register: {preserve_register}
- Preserve technical terms: {preserve_technical_terms}

{profile_instructions}

Return ONLY the rewritten text. No explanations, preamble, or commentary."""

PROFILE_INSTRUCTIONS: dict[str, str] = {
    "minimal": "Make minimal changes. Adjust only word choice and minor phrasing. Keep the structure identical.",
    "natural": "Rewrite to sound more natural and fluent while preserving meaning and structure.",
    "academic": "Rewrite in formal academic style. Maintain precision, use appropriate academic register, and preserve technical accuracy.",
    "professional": "Rewrite in clear professional style. Improve clarity and readability while maintaining formality.",
    "concise": "Rewrite to be more concise. Remove redundancy and verbosity while preserving all key information.",
    "creative": "Rewrite with more varied language and style. Allow structural changes while preserving meaning.",
}

STRUCTURAL_ANALYSIS_PROMPT = """Analyze the following text and classify each paragraph.

For each paragraph, provide:
1. The paragraph index (0-based)
2. The paragraph type (one of: definition, argument, example, transition, enumeration, technical_explanation, quotation, code_related, other)
3. The sentence count
4. Whether it contains protected content (placeholders like <TF_PROTECTED_XXXX>)

Return a JSON array of objects with keys: index, paragraph_type, sentence_count, has_protected_content.

Text:
{text}"""

SEMANTIC_COMPARISON_PROMPT = """Compare the following source and candidate texts for semantic equivalence.

Source:
{source}

Candidate:
{candidate}

Evaluate:
1. Overall semantic similarity (0.0 to 1.0)
2. Any contradictions between source and candidate
3. Any claims in the source that are missing from the candidate
4. Any new claims in the candidate not present in the source

Return a JSON object with keys:
- score (float 0-1)
- contradictions (list of strings)
- missing_claims (list of strings)
- added_claims (list of strings)"""

CLAIM_EXTRACTION_PROMPT = """Extract all atomic factual claims from the following text. Include:
- Factual statements
- Causal claims
- Quantitative claims
- Negations
- Modal statements (must, should, can, etc.)
- Definitions

Return a JSON array of strings, each being one atomic claim.

Text:
{text}"""

RETRY_PROMPT = """The previous rewrite had validation issues. Please fix the following problems and rewrite again.

Issues:
{issues}

Original text:
{original}

Previous attempt:
{previous}

Fix all issues and return ONLY the corrected rewritten text."""
