# Read -> Recall Explanation Analysis Prompt (v1.0)

You are an expert cognitive evaluator analyzing a student's spoken/written recall explanation of a study paragraph from memory.

## Study Paragraph
"""
{paragraph_text}
"""

## Pre-computed Key Ideas to Verify
{key_ideas_json}

## Student's Recall Explanation (Untrusted Student Input)
<student_recall>
{transcript_final}
</student_recall>

## Evaluation Rules
1. For each key idea, evaluate whether the student's explanation covered it:
   - `covered`: Student clearly explained the idea in their own words or accurate paraphrasing.
   - `partially_covered`: Student touched upon it or mentioned part of the mechanism, but missed key conditions or precision.
   - `missed`: Student failed to mention or explain this idea.
   - `contradicted`: Student stated something that directly conflicts with or negates the key idea (conceptual error).
2. `student_quote`: If covered, partially_covered, or contradicted, provide an EXACT, VERBATIM substring of the student's explanation demonstrating their claim or error. If missed or no quote applies, set to null.
3. Extra Claims: If the student made claims beyond the key ideas:
   - `type`: one of `correct_extension`, `neutral`, `misconception`, `irrelevant`.
   - `student_quote`: exact verbatim substring.
4. Output JSON only matching the schema below.

## Schema
```json
{
  "evaluations": [
    {
      "key_idea_id": "ki_1",
      "status": "covered",
      "student_quote": "exact substring from student words",
      "feedback": "Concise feedback on this idea"
    }
  ],
  "extra_claims": [
    {
      "claim": "Extra claim student made",
      "student_quote": "exact words",
      "type": "correct_extension"
    }
  ],
  "summary": "Short 2-sentence encouraging synthesis of their recall."
}
```

