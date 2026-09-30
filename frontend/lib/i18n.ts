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
    years: (n: number) => `${n} years experience`,
    nextSlot: "Next slot",
    secondOpinion: "Accepts second opinions",
    tele: "Video visits",
    speaks: "Languages",
    call: "Call",
    languageGroup: "Language",
    errors: {
      network_error: "Can't reach the server. Check your connection and try again.",
      too_many_requests: "Too many messages. Please wait a minute.",
      session_turn_limit: "This conversation is long. Please start a new one.",
      turn_in_progress: "Still answering your last message. Please wait a moment.",
      message_too_long: "Your message is too long. Please shorten it.",
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
      "أشعر بألم في الصدر ولست متأكدًا هل أراجع طبيب قلب، أم أذهب إلى الطوارئ، أم أطلب رأيًا طبيًا ثانيًا.",
      "أخبرني الطبيب أنني أحتاج إلى عملية في الركبة في الرياض، وأرغب في رأي طبي ثانٍ.",
      "أعاني من صداع منذ ثلاثة أسابيع وأسكن في القاهرة.",
    ],
    disclaimer:
      "هذه إرشادات فقط وليست تشخيصًا. في حالة الطوارئ اتصل برقم الطوارئ (السعودية 997 / 911، مصر 123، الإمارات 998).",
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
    years: (n: number) => `${n} سنة خبرة`,
    nextSlot: "أقرب موعد",
    secondOpinion: "يقبل الرأي الطبي الثاني",
    tele: "استشارة فيديو",
    speaks: "اللغات",
    call: "اتصال",
    languageGroup: "اللغة",
    errors: {
      network_error: "تعذّر الاتصال بالخادم. تحقق من الاتصال وحاول مرة أخرى.",
      too_many_requests: "رسائل كثيرة. انتظر دقيقة من فضلك.",
      session_turn_limit: "المحادثة طويلة. ابدأ محادثة جديدة من فضلك.",
      turn_in_progress: "ما زلت أجيب عن رسالتك السابقة. انتظر لحظة من فضلك.",
      message_too_long: "رسالتك طويلة جدًا. اختصرها من فضلك.",
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

/** Dates and numbers: Western digits in both languages, matching phone numbers and DB addresses. */
export const locale: Record<Lang, string> = { en: "en-GB", ar: "ar-SA-u-ca-gregory-nu-latn" };

/** Read `name_ar` / `name_en` (etc.) from a DB row. Localized text comes from the database, not the LLM. */
export function pick(obj: object, base: string, lang: Lang): string {
  const o = obj as Record<string, unknown>;
  return String(o[`${base}_${lang}`] ?? o[`${base}_en`] ?? "");
}
