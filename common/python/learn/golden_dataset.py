"""Golden Evaluation Dataset for Preppy Misconception Analysis (§6.4).

Contains 12 curated benchmark student responses covering all error types:
- conceptual_misunderstanding (2)
- calculation_error (2)
- knowledge_gap (2)
- careless_mistake (2)
- incomplete_reasoning (2)
- uncertain (2)
"""

from typing import Any, Dict, List
from .schemas import ErrorType

GOLDEN_TEST_CASES: List[Dict[str, Any]] = [
    # 1. Conceptual Misunderstanding (Newton's 2nd Law)
    {
        "id": "gold_1",
        "concept": "Newton's Second Law",
        "question": "What happens to the acceleration of an object if the applied net force doubles at constant mass?",
        "correct_answer": "Acceleration doubles",
        "student_answer": "Acceleration remains unchanged",
        "reasoning": "Mass has not changed so nothing changes in the object.",
        "distractor_hint": "Believes acceleration depends strictly on mass alone",
        "confidence": 3,
        "time_ms": 12000,
        "prior_mastery": 0.50,
        "expected_error_type": ErrorType.conceptual_misunderstanding,
        "expected_quote_sub": "mass has not changed so nothing changes",
    },
    # 2. Conceptual Misunderstanding (Free Fall & Gravity)
    {
        "id": "gold_2",
        "concept": "Gravitational Acceleration",
        "question": "In a vacuum, which hits the ground first: a 10kg iron ball or a 1kg wooden ball dropped from the same height?",
        "correct_answer": "Both hit at the same time",
        "student_answer": "The 10kg iron ball hits first",
        "reasoning": "Heavier objects are pulled harder by gravity so they fall faster.",
        "distractor_hint": "Believes heavier objects fall with greater acceleration in vacuum",
        "confidence": 3,
        "time_ms": 9500,
        "prior_mastery": 0.45,
        "expected_error_type": ErrorType.conceptual_misunderstanding,
        "expected_quote_sub": "heavier objects are pulled harder by gravity",
    },
    # 3. Calculation Error (Kinetic Energy)
    {
        "id": "gold_3",
        "concept": "Kinetic Energy",
        "question": "Calculate the kinetic energy of a 2 kg cart moving at 3 m/s.",
        "correct_answer": "9 Joules",
        "student_answer": "18 Joules",
        "reasoning": "KE = 1/2 m v^2. m is 2 and v^2 is 9, so 2 * 9 = 18.",
        "distractor_hint": None,
        "confidence": 2,
        "time_ms": 18000,
        "prior_mastery": 0.65,
        "expected_error_type": ErrorType.calculation_error,
        "expected_quote_sub": "2 * 9 = 18",
    },
    # 4. Calculation Error (Ohm's Law)
    {
        "id": "gold_4",
        "concept": "Ohm's Law",
        "question": "What is the voltage across a 5 Ohm resistor carrying 2 Amperes of current?",
        "correct_answer": "10 Volts",
        "student_answer": "7 Volts",
        "reasoning": "V = I * R. 5 plus 2 is 7.",
        "distractor_hint": None,
        "confidence": 2,
        "time_ms": 11000,
        "prior_mastery": 0.60,
        "expected_error_type": ErrorType.calculation_error,
        "expected_quote_sub": "5 plus 2 is 7",
    },
    # 5. Knowledge Gap (Entropy definition)
    {
        "id": "gold_5",
        "concept": "Second Law of Thermodynamics",
        "question": "What does entropy measure in an isolated thermodynamic system?",
        "correct_answer": "The degree of disorder or multiplicity of microstates",
        "student_answer": "How hot something gets",
        "reasoning": "Entropy is just temperature in Kelvin.",
        "distractor_hint": "Lacks definition of statistical thermodynamic microstates",
        "confidence": 1,
        "time_ms": 15000,
        "prior_mastery": 0.30,
        "expected_error_type": ErrorType.knowledge_gap,
        "expected_quote_sub": "entropy is just temperature",
    },
    # 6. Knowledge Gap (Inertial Reference Frames)
    {
        "id": "gold_6",
        "concept": "Reference Frames",
        "question": "Which of the following constitutes an inertial frame of reference?",
        "correct_answer": "A train moving at constant velocity on a straight track",
        "student_answer": "An elevator accelerating upward",
        "reasoning": "Any elevator with people inside counts as reference frame.",
        "distractor_hint": "Unaware that accelerating frames are non-inertial",
        "confidence": 1,
        "time_ms": 14000,
        "prior_mastery": 0.25,
        "expected_error_type": ErrorType.knowledge_gap,
        "expected_quote_sub": "any elevator with people inside",
    },
    # 7. Careless Mistake (Quick vector sign flip)
    {
        "id": "gold_7",
        "concept": "Displacement Vectors",
        "question": "If north is positive, what is the net displacement after moving 10m north then 15m south?",
        "correct_answer": "-5 meters",
        "student_answer": "+5 meters",
        "reasoning": "15 - 10 = 5.",
        "distractor_hint": None,
        "confidence": 3,
        "time_ms": 1800,  # Fast under 3.5s
        "prior_mastery": 0.88,  # High prior mastery
        "expected_error_type": ErrorType.careless_mistake,
        "expected_quote_sub": None,
    },
    # 8. Careless Mistake (Fast units slip)
    {
        "id": "gold_8",
        "concept": "Acceleration Units",
        "question": "What is the SI unit of acceleration?",
        "correct_answer": "m/s^2",
        "student_answer": "m/s",
        "reasoning": "Speed per second.",
        "distractor_hint": None,
        "confidence": 3,
        "time_ms": 1200,  # Fast under 3.5s
        "prior_mastery": 0.92,  # Very high mastery
        "expected_error_type": ErrorType.careless_mistake,
        "expected_quote_sub": None,
    },
    # 9. Incomplete Reasoning (Work by friction)
    {
        "id": "gold_9",
        "concept": "Work-Energy Theorem",
        "question": "Does kinetic friction perform positive, negative, or zero work on a sliding box?",
        "correct_answer": "Negative work",
        "student_answer": "It performs work",
        "reasoning": "Friction exerts a force on the box as it moves over distance.",
        "distractor_hint": None,
        "confidence": 2,
        "time_ms": 16000,
        "prior_mastery": 0.55,
        "expected_error_type": ErrorType.incomplete_reasoning,
        "expected_quote_sub": "friction exerts a force",
    },
    # 10. Incomplete Reasoning (Momentum conservation)
    {
        "id": "gold_10",
        "concept": "Conservation of Momentum",
        "question": "Is total momentum conserved in an inelastic collision when no external forces act?",
        "correct_answer": "Yes, total momentum is conserved",
        "student_answer": "Only kinetic energy changes",
        "reasoning": "The kinetic energy turns into heat so it is not completely conserved.",
        "distractor_hint": None,
        "confidence": 2,
        "time_ms": 17000,
        "prior_mastery": 0.50,
        "expected_error_type": ErrorType.incomplete_reasoning,
        "expected_quote_sub": "kinetic energy turns into heat",
    },
    # 11. Uncertain (Vague unassertive guess)
    {
        "id": "gold_11",
        "concept": "Simple Harmonic Motion",
        "question": "Where is the acceleration greatest in a simple pendulum?",
        "correct_answer": "At the maximum displacement extremes",
        "student_answer": "At the equilibrium midpoint",
        "reasoning": "I honestly have no clue, just picked randomly.",
        "distractor_hint": None,
        "confidence": 1,
        "time_ms": 6000,
        "prior_mastery": 0.35,
        "expected_error_type": ErrorType.uncertain,
        "expected_quote_sub": None,
    },
    # 12. Uncertain (Conflicting fabricated quote)
    {
        "id": "gold_12",
        "concept": "Doppler Effect",
        "question": "What happens to the observed pitch as a siren moves away?",
        "correct_answer": "The pitch decreases",
        "student_answer": "The pitch increases",
        "reasoning": "Sound waves.",
        "distractor_hint": None,
        "confidence": 1,
        "time_ms": 4000,
        "prior_mastery": 0.40,
        "expected_error_type": ErrorType.uncertain,
        "expected_quote_sub": None,
    },
]

