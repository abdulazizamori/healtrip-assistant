"""Deterministic red-flag rules: no database, no LLM."""

import pytest

from app.safety import check_red_flags, detect_language, normalize

EMERGENCIES = [
    ["I have chest pain and I can't breathe"],
    ["chest pressure and I'm sweating a lot"],
    ["I have chest pain", "yes, and shortness of breath since an hour"],   # split across turns
    ["عندي ألم في صدري ومش قادر آخد نفسي"],
    ["عندي وجع في الصدر", "ودراعي الشمال بيوجعني"],
    ["this is the worst headache of my life"],
    ["my father's face is drooping and he has slurred speech"],
    ["وشي مايل وكلامي تقيل"],
    ["I'm vomiting blood"],
    ["I want to kill myself"],
    ["عايز أموت"],
]

NOT_EMERGENCIES = [
    ["I have had a mild headache for three weeks"],
    ["I'm not sure whether I should see a cardiologist or get a second opinion"],
    ["I have chest pain sometimes after eating spicy food"],  # chest pain alone -> LLM asks follow-ups
    ["عندي صداع خفيف من أسبوع"],
    ["I want a second opinion about my knee surgery"],
]


@pytest.mark.parametrize("texts", EMERGENCIES)
def test_red_flags_detected(texts):
    assert check_red_flags(texts) is not None


@pytest.mark.parametrize("texts", NOT_EMERGENCIES)
def test_no_false_alarm_on_routine_cases(texts):
    assert check_red_flags(texts) is None


def test_self_harm_is_its_own_category():
    assert check_red_flags(["I want to end my life"]).category == "mental_health"


def test_arabic_normalization():
    assert normalize("أَلَمٌ في الصدرِ") == "الم في الصدر"


@pytest.mark.parametrize("text,default,expected", [
    ("I have chest pain", "ar", "en"),
    ("عندي ألم في صدري", "en", "ar"),
    ("35", "ar", "ar"),     # no letters -> keep UI language
    ("ok", "ar", "ar"),
])
def test_language_detection(text, default, expected):
    assert detect_language(text, default) == expected
