// Mirrors backend/app/schemas.py — the single contract between UI and API.

export type Lang = "ar" | "en";
export type ResponseType = "question" | "recommendation" | "emergency" | "error";
export type NextStep = "EMERGENCY" | "SPECIALIST" | "SECOND_OPINION" | "GENERAL_PRACTITIONER";

export interface LocalizedName {
  code: string;
  name_en: string;
  name_ar: string;
}

export interface DoctorCard {
  id: number;
  name_en: string;
  name_ar: string;
  specialty: LocalizedName;
  hospital_id: number;
  hospital_en: string;
  hospital_ar: string;
  city: LocalizedName;
  languages: string[];
  years_experience: number;
  accepts_second_opinion: boolean;
  offers_teleconsult: boolean;
  next_available: string | null;
}

export interface HospitalCard {
  id: number;
  name_en: string;
  name_ar: string;
  address_en: string;
  address_ar: string;
  phone: string;
  has_emergency: boolean;
  city: LocalizedName;
}

export interface ChatResponse {
  session_id: string;
  type: ResponseType;
  message: string;
  language: Lang;
  next_step: NextStep | null;
  urgency: "routine" | "soon" | "urgent" | "emergency" | null;
  specialty: LocalizedName | null;
  doctors: DoctorCard[];
  hospitals: HospitalCard[];
  disclaimer: boolean;
}

// "" = same origin (single-service deploy, API serves the page); unset = local API on :8000
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, public code: string) {
    super(code);
  }
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60_000);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      // "message_too_long (max 1000 characters)" -> "message_too_long"; the UI maps codes to localized text
      const detail = typeof data.detail === "string" ? data.detail : String(data.error ?? "request_failed");
      throw new ApiError(res.status, detail.split(" ")[0]);
    }
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(0, "network_error");
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  createSession: () => post<{ session_id: string }>("/api/sessions"),
  chat: (session_id: string, message: string, ui_language: Lang) =>
    post<ChatResponse>("/api/chat", { session_id, message, ui_language }),
};
