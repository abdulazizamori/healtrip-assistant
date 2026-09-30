import type { Lang, NextStep } from "./api";

export const t = {
  en: {
    title: "HealTrip Care Guide",
    subtitle: "Tell me what you're feeling. I'll help you decide the right next step.",
    placeholder: "Describe your symptoms…",
    send: "Send",
    newChat: "New conversation",
    thinking: "Thinking…",
    examplesTitle: "Try an example",
    examples: [
      "I have chest pain and I'm not sure whether I should see a cardiologist, go to the ER, or seek a second opinion.",
      "I was told I need knee surgery in Riyadh. I'd like a second opinion.",
      "I've had headaches for three weeks and I live in Cairo.",
    ],
    disclaimer:
      "Guidance only — not a diagnosis. In an emergency call your local emergency number (KSA 997 / 911, Egypt 123, UAE 998).",
    nextStep: {
      EMERGENCY: "Go to emergency now",
      SPECIALIST: "See a specialist",
      SECOND_OPINION: "Get a second opinion",
      GENERAL_PRACTITIONER: "Start with a general doctor",
    } as Record<NextStep, string>,
    question: "Question",
    options: "Options from the HealTrip network",
    erNearby: "Emergency departments",
    noMatch: "No matching doctors were found in our network for this search.",
    years: "years",
    nextSlot: "Next slot",
    secondOpinion: "Second opinions",
    tele: "Video visits",
    speaks: "Speaks",
    call: "Call",
    errors: {
      network_error: "Can't reach the server. Check your connection and try again.",
      too_many_requests: "Too many messages. Please wait a minute.",
      session_turn_limit: "This conversation is long. Please start a new one.",
      generic: "Something went wrong. Please try again.",
    } as Record<string, string>,
    counter: (n: number, max: number) => `${n}/${max}`,
  },
  ar: {
    title: "دليل هيل تريب للرعاية",
    subtitle: "أخبرني بما تشعر به، وسأساعدك في اختيار الخطوة التالية المناسبة.",
    placeholder: "صف الأعراض التي تشعر بها…",
    send: "إرسال",
    newChat: "محادثة جديدة",
    thinking: "جارٍ التفكير…",
    examplesTitle: "جرّب مثالًا",
    examples: [
      "عندي ألم في الصدر ومش عارف أروح لدكتور قلب ولا الطوارئ ولا آخد رأي تاني.",
      "قالولي محتاج عملية في الركبة وأنا في الرياض، وعايز رأي طبي تاني.",
      "عندي صداع بقاله ٣ أسابيع وأنا ساكن في القاهرة.",
    ],
    disclaimer:
      "هذه إرشادات فقط وليست تشخيصًا. في حالة الطوارئ اتصل برقم الطوارئ (السعودية ٩٩٧ / ٩١١، مصر ١٢٣، الإمارات ٩٩٨).",
    nextStep: {
      EMERGENCY: "توجّه إلى الطوارئ الآن",
      SPECIALIST: "راجع طبيبًا مختصًا",
      SECOND_OPINION: "احصل على رأي طبي ثانٍ",
      GENERAL_PRACTITIONER: "ابدأ بطبيب عام",
    } as Record<NextStep, string>,
    question: "سؤال",
    options: "خيارات من شبكة هيل تريب",
    erNearby: "أقسام الطوارئ",
    noMatch: "لم نجد أطباء مطابقين في شبكتنا لهذا البحث.",
    years: "سنة خبرة",
    nextSlot: "أقرب موعد",
    secondOpinion: "يقبل الرأي الثاني",
    tele: "استشارة فيديو",
    speaks: "اللغات",
    call: "اتصال",
    errors: {
      network_error: "تعذّر الاتصال بالخادم. تحقق من الاتصال وحاول مرة أخرى.",
      too_many_requests: "رسائل كثيرة. انتظر دقيقة من فضلك.",
      session_turn_limit: "المحادثة طويلة. ابدأ محادثة جديدة من فضلك.",
      generic: "حدث خطأ. حاول مرة أخرى.",
    } as Record<string, string>,
    counter: (n: number, max: number) => `${n}/${max}`,
  },
} satisfies Record<Lang, unknown>;

export const languageNames: Record<string, { en: string; ar: string }> = {
  ar: { en: "Arabic", ar: "العربية" },
  en: { en: "English", ar: "الإنجليزية" },
  fr: { en: "French", ar: "الفرنسية" },
  ur: { en: "Urdu", ar: "الأردية" },
};

/** Read `name_ar` / `name_en` (etc.) from a DB row. Localized text comes from the database, not the LLM. */
export function pick(obj: object, base: string, lang: Lang): string {
  const o = obj as Record<string, unknown>;
  return String(o[`${base}_${lang}`] ?? o[`${base}_en`] ?? "");
}
