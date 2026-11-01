# Chunk Key Ideas Extraction Prompt (v1.0)

You are an expert educational cognitive analyst.
Extract 3 to 6 atomic, fundamental key claims from this educational text excerpt.

## Paragraph Text
"""
{paragraph_text}
"""

## Critical Rules
1. Extract 3 to 6 atomic key ideas that a student must remember and explain to demonstrate true conceptual understanding.
2. `claim`: Clear, concise statement of the atomic idea in plain language.
3. `supporting_quote`: MUST be an EXACT, VERBATIM substring of the paragraph text above. Do not alter capitalization, punctuation, or wording.
4. Output JSON only matching the schema below.

## Schema
```json
{
  "key_ideas": [
    {
      "id": "ki_1",
      "claim": "Summary of the claim",
      "supporting_quote": "exact substring from paragraph"
    }
  ]
}
```

