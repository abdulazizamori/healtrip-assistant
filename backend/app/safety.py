"""Deterministic safety layer.

Runs on EVERY turn, BEFORE the LLM, over everything the patient has said in the session.
If a red flag matches, the LLM is not consulted at all: the system answers with an emergency
response. This keeps working even if the LLM provider is down (graceful degradation).

IMPORTANT (prototype assumption): this list was written by an engineer from public
first-aid guidance. In production it must be written/approved by clinicians, and the
system should be tuned to over-triage (false alarms) rather than under-triage (missed emergencies).
"""

import re
from dataclasses import dataclass

# ------------------------------------------------------------------ normalization

_AR_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")


def normalize(text: str) -> str:
    """Lowercase, strip Arabic diacritics/tatweel, unify common Arabic letter variants."""
    t = _AR_DIACRITICS.sub("", text.lower())
    t = re.sub("[إأآٱ]", "ا", t)
    t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return re.sub(r"\s+", " ", t)


def detect_language(text: str, default: str = "en") -> str:
    """Reply in the language the patient writes in; fall back to the UI language (e.g. for '35' or 'ok')."""
    arabic = len(re.findall(r"[؀-ۿ]", text))
    latin = len(re.findall(r"[a-zA-Z]", text))
    if arabic == latin or (arabic + latin) < 3:
        return default
    return "ar" if arabic > latin else "en"


# ------------------------------------------------------------------ rules

@dataclass(frozen=True)
class RedFlagRule:
    id: str
    category: str  # "medical" | "mental_health"
    all_of: tuple[str, ...]  # every regex group must match (AND). Each regex is an OR of variants.


def _p(*alternatives: str) -> str:
    return "(" + "|".join(alternatives) + ")"


CHEST = _p(r"chest (pain|pressure|tightness|hurts?)", r"pain in (my )?chest",
           r"(الم|وجع|ضغط|ضيق|تقل|ثقل)\s*(في\s*)?(ال)?صدر", r"صدري\s*(بيوجعني|واجعني|يوجعني)")
BREATH = _p(r"(can'?t|cannot|can not|hard to|trouble|difficult(y)?|struggling to) (breathe|breath|breathing)",
            r"short(ness)? of breath", r"out of breath", r"breathless",
            r"(مش قادر|مقدرش|ما اقدر|لا استطيع|صعوبه في|ضيق في?|ضيق) ?(اخد|اخذ|اتنفس|التنفس|النفس|نفس|تنفس)",
            r"نفسي (مقطوع|بيتقطع)", r"اختناق|بتخنق|مخنوق")
CARDIAC_COMPANION = _p(r"sweat", r"left arm", r"arm pain", r"jaw", r"faint", r"dizz", r"nause",
                       r"عرق", r"دراعي|ذراعي|الدراع|الذراع", r"فكي|الفك", r"دوخه|دايخ|اغمي|اغماء", r"غثيان|عايز ارجع")

RULES: tuple[RedFlagRule, ...] = (
    RedFlagRule("chest_pain_with_breathing_difficulty", "medical", (CHEST, BREATH)),
    RedFlagRule("chest_pain_with_cardiac_signs", "medical", (CHEST, CARDIAC_COMPANION)),
    RedFlagRule("severe_breathing_difficulty", "medical", (_p(
        r"can'?t breathe", r"cannot breathe", r"not breathing", r"choking", r"lips (are )?(blue|turning blue)",
        r"مش قادر (اتنفس|اخد نفسي|اخذ نفسي)", r"لا استطيع التنفس", r"شفايفي (زرقا|ازرقت)"),)),
    RedFlagRule("stroke_signs", "medical", (_p(
        r"face (is )?droop", r"slurred speech", r"can'?t (speak|talk) (properly|clearly)",
        r"(weak|numb)(ness)? (on|in) (one|the (left|right)) side", r"one side of (my|his|her) (body|face)",
        r"sudden(ly)? confus", r"can'?t move (my )?(arm|leg)",
        r"وشي (مايل|اتعوج)", r"وجهي (مايل|مائل)", r"كلامي (تقيل|ثقيل|متلخبط)", r"مش قادر اتكلم",
        r"(تنميل|خدر|ضعف) (في )?(نص|نصف|جانب|ناحيه)", r"مش قادر احرك (ايدي|رجلي|دراعي)"),)),
    RedFlagRule("thunderclap_headache", "medical", (_p(
        r"worst headache", r"sudden(ly)? (severe|terrible|extreme) headache", r"thunderclap",
        r"headache .{0,40}(stiff neck|after (a|hitting my) head|passed out|faint)",
        r"اسوا صداع", r"صداع (مفاجي|فجاه|جامد فجاه|شديد فجاه)", r"صداع .{0,30}(رقبتي ناشفه|تيبس|بعد خبطه|اغمي)"),)),
    RedFlagRule("loss_of_consciousness_or_seizure", "medical", (_p(
        r"passed out", r"unconscious", r"fainted", r"seizure", r"convuls", r"not responding",
        r"اغمي عليه|اغمي علي|فقد الوعي|فاقد الوعي|تشنج|نوبه صرع|مش بيرد"),)),
    RedFlagRule("severe_bleeding", "medical", (_p(
        r"(heavy|severe|won'?t stop|can'?t stop) bleeding", r"bleeding (heavily|a lot|won'?t stop)",
        r"(vomiting|coughing( up)?|throwing up) blood",
        r"نزيف (شديد|جامد|مش بيقف|لا يتوقف)", r"(بترجع|برجع|بكح|كحه|قيء|استفراغ) (فيه |فيها )?دم"),)),
    RedFlagRule("anaphylaxis", "medical", (_p(
        r"throat (is )?(closing|swelling)", r"(tongue|lips|face) (is |are )?swell.{0,30}(breath|allerg)",
        r"زوري (بيقفل|ورم)", r"(لساني|شفايفي) (ورم|وارم).{0,20}(نفس|حساسيه)"),)),
    RedFlagRule("self_harm", "mental_health", (_p(
        r"kill (my ?self|myself)", r"suicid", r"want to die", r"end my life", r"hurt myself",
        r"انتحر|انتحار|عايز اموت|اريد ان اموت|انهي حياتي|اقتل نفسي|اذي نفسي"),)),
)

_COMPILED = [(rule, [re.compile(g) for g in rule.all_of]) for rule in RULES]


def check_red_flags(user_texts: list[str]) -> RedFlagRule | None:
    """Checks the whole patient transcript, so 'chest pain' in turn 1 + 'can't breathe' in turn 3 still triggers."""
    text = normalize(" \n ".join(user_texts))
    for rule, patterns in _COMPILED:
        if all(p.search(text) for p in patterns):
            return rule
    return None


def detect_city(user_texts: list[str], cities: dict[str, dict]) -> str | None:
    """Best-effort: find a known city name in what the patient wrote (used to list nearby ERs)."""
    text = normalize(" ".join(user_texts))
    for code, row in cities.items():
        for name in (row["name_en"], row["name_ar"], code):
            if normalize(name) in text:
                return code
    return None


# ------------------------------------------------------------------ fixed emergency copy

EMERGENCY_MESSAGES = {
    "medical": {
        "en": ("What you describe can be a sign of a medical emergency. Please do not wait for an appointment: "
               "call your local emergency number now (Saudi Arabia 997 / 911, Egypt 123, UAE 998) or go to the "
               "nearest emergency department. If someone is with you, ask them to stay with you."),
        "ar": ("ما تصفه قد يكون علامة على حالة طبية طارئة. من فضلك لا تنتظر موعدًا: "
               "اتصل برقم الطوارئ فورًا (السعودية 997 / 911، مصر 123، الإمارات 998) أو توجّه إلى أقرب قسم طوارئ. "
               "إذا كان معك أحد، اطلب منه أن يبقى بجانبك."),
    },
    "mental_health": {
        "en": ("I'm really sorry you're going through this. You deserve support right now. Please call your local "
               "emergency number (Saudi Arabia 997 / 911, Egypt 123, UAE 998) or go to the nearest emergency "
               "department, and if you can, reach out to someone you trust to be with you."),
        "ar": ("أنا آسف جدًا لما تمر به، وأنت تستحق الدعم الآن. من فضلك اتصل برقم الطوارئ "
               "(السعودية 997 / 911، مصر 123، الإمارات 998) أو توجّه إلى أقرب قسم طوارئ، "
               "وإن استطعت تواصل مع شخص تثق به ليبقى معك."),
    },
}

FALLBACK_MESSAGES = {
    "en": ("Sorry, I can't complete this right now because of a temporary technical problem. "
           "If your symptoms are severe or getting worse, please go to the nearest emergency department "
           "or call your local emergency number. Otherwise, please try again in a few minutes."),
    "ar": ("عذرًا، لا أستطيع إكمال طلبك الآن بسبب مشكلة تقنية مؤقتة. "
           "إذا كانت الأعراض شديدة أو تزداد سوءًا، توجّه إلى أقرب قسم طوارئ أو اتصل برقم الطوارئ. "
           "وإلا، حاول مرة أخرى بعد بضع دقائق."),
}
