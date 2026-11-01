from pathlib import Path
from learn.schemas import (
    ErrorType,
    MaterialKind,
    QuestionType,
    MisconceptionState,
    MasteryBand,
)


def test_schema_drift_enums():
    """
    Guards against schema drift between Python schemas.py and TypeScript types.ts (§11).
    Validates that every enum value in Python exists verbatim in the TypeScript definition.
    """
    ts_file = Path("common/frontend/src/learn/types.ts")
    assert ts_file.exists(), "TypeScript types file common/frontend/src/learn/types.ts does not exist"

    ts_content = ts_file.read_text(encoding="utf-8")

    # Check ErrorType
    for e in ErrorType:
        assert f"'{e.value}'" in ts_content, f"ErrorType '{e.value}' missing from TS types.ts"

    # Check MaterialKind
    for m in MaterialKind:
        assert f"'{m.value}'" in ts_content, f"MaterialKind '{m.value}' missing from TS types.ts"

    # Check QuestionType
    for q in QuestionType:
        assert f"'{q.value}'" in ts_content, f"QuestionType '{q.value}' missing from TS types.ts"

    # Check MisconceptionState
    for s in MisconceptionState:
        assert f"'{s.value}'" in ts_content, f"MisconceptionState '{s.value}' missing from TS types.ts"

    # Check MasteryBand
    for b in MasteryBand:
        assert f"'{b.value}'" in ts_content, f"MasteryBand '{b.value}' missing from TS types.ts"

