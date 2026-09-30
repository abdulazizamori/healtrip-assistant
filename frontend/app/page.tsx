"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { DoctorCardView, HospitalCardView } from "@/components/Cards";
import { api, ApiError, type ChatResponse, type Lang } from "@/lib/api";
import { t } from "@/lib/i18n";

const MAX_CHARS = 1000;

type Item =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; res: ChatResponse }
  | { id: number; role: "system-error"; code: string };

let nextId = 1;

export default function ChatPage() {
  const [lang, setLang] = useState<Lang>("en");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const s = t[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [items, busy]);

  async function ensureSession(forceNew = false): Promise<string> {
    if (sessionId && !forceNew) return sessionId;
    const { session_id } = await api.createSession();
    setSessionId(session_id);
    return session_id;
  }

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    setItems((prev) => [...prev, { id: nextId++, role: "user", text: message }]);
    setInput("");
    setBusy(true);
    try {
      let sid = await ensureSession();
      let res: ChatResponse;
      try {
        res = await api.chat(sid, message, lang);
      } catch (e) {
        // server restarted or session expired: start a fresh session once and resend
        if (e instanceof ApiError && e.status === 404) {
          sid = await ensureSession(true);
          res = await api.chat(sid, message, lang);
        } else throw e;
      }
      setItems((prev) => [...prev, { id: nextId++, role: "assistant", res }]);
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "generic";
      setItems((prev) => [...prev, { id: nextId++, role: "system-error", code }]);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(input);
  }

  function reset() {
    setItems([]);
    setSessionId(null);
    setInput("");
  }

  return (
    <main className="shell">
      <header className="top">
        <div>
          <h1>{s.title}</h1>
          <p className="muted">{s.subtitle}</p>
        </div>
        <div className="top-actions">
          <button className="ghost" onClick={reset} disabled={busy}>{s.newChat}</button>
          <div className="lang" role="group" aria-label="Language">
            <button aria-pressed={lang === "en"} onClick={() => setLang("en")}>EN</button>
            <button aria-pressed={lang === "ar"} onClick={() => setLang("ar")}>عربي</button>
          </div>
        </div>
      </header>

      <section className="chat" aria-live="polite">
        {items.length === 0 && (
          <div className="examples">
            <p className="muted small">{s.examplesTitle}</p>
            {s.examples.map((ex) => (
              <button key={ex} className="example" onClick={() => void send(ex)}>{ex}</button>
            ))}
          </div>
        )}

        {items.map((it) => {
          if (it.role === "user")
            return <div key={it.id} className="bubble user" dir="auto">{it.text}</div>;
          if (it.role === "system-error")
            return (
              <div key={it.id} className="bubble error">
                {s.errors[it.code] ?? s.errors.generic}
              </div>
            );
          return <AssistantMessage key={it.id} res={it.res} lang={lang} />;
        })}

        {busy && <div className="bubble assistant muted">{s.thinking}</div>}
        <div ref={endRef} />
      </section>

      <form className="composer" onSubmit={onSubmit}>
        <textarea
          value={input}
          maxLength={MAX_CHARS}
          placeholder={s.placeholder}
          dir="auto"
          rows={2}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send(input);
            }
          }}
        />
        <div className="composer-side">
          <span className="muted small">{s.counter(input.length, MAX_CHARS)}</span>
          <button type="submit" disabled={busy || !input.trim()}>{s.send}</button>
        </div>
      </form>
      <p className="disclaimer muted small">{s.disclaimer}</p>
    </main>
  );
}

function AssistantMessage({ res, lang }: { res: ChatResponse; lang: Lang }) {
  const s = t[lang];
  const kind = res.type;
  return (
    <div className={`bubble assistant ${kind}`}>
      {res.next_step && (
        <div className={`badge ${kind}`}>{s.nextStep[res.next_step]}</div>
      )}
      {kind === "question" && <div className="badge question">{s.question}</div>}
      {/* the message may be in a different language than the UI (patient wrote Arabic in the English UI) */}
      <p dir={res.language === "ar" ? "rtl" : "ltr"}>{res.message}</p>

      {res.hospitals.length > 0 && (
        <div className="cards">
          <p className="muted small">{s.erNearby}</p>
          {res.hospitals.map((h) => <HospitalCardView key={h.id} h={h} lang={lang} />)}
        </div>
      )}
      {kind === "recommendation" && res.next_step !== "EMERGENCY" && (
        <div className="cards">
          {res.doctors.length > 0 ? (
            <>
              <p className="muted small">{s.options}</p>
              {res.doctors.map((d) => <DoctorCardView key={d.id} d={d} lang={lang} />)}
            </>
          ) : (
            <p className="muted small">{s.noMatch}</p>
          )}
        </div>
      )}
    </div>
  );
}
