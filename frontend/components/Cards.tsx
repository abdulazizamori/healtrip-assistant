import type { DoctorCard, HospitalCard, Lang } from "@/lib/api";
import { languageNames, locale, pick, t } from "@/lib/i18n";

function formatSlot(iso: string, lang: Lang) {
  return new Intl.DateTimeFormat(locale[lang], {
    weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
  }).format(new Date(iso));
}

export function DoctorCardView({ d, lang }: { d: DoctorCard; lang: Lang }) {
  const s = t[lang];
  return (
    <article className="card">
      <div className="card-head">
        <strong>{pick(d, "name", lang)}</strong>
        <span className="muted">{pick(d.specialty, "name", lang)}</span>
      </div>
      <div className="muted">
        {pick(d, "hospital", lang)} · {pick(d.city, "name", lang)}
      </div>
      <div className="tags">
        <span className="tag">{s.years(d.years_experience)}</span>
        {d.accepts_second_opinion && <span className="tag">{s.secondOpinion}</span>}
        {d.offers_teleconsult && <span className="tag">{s.tele}</span>}
      </div>
      <div className="muted small">
        {s.speaks}: {d.languages.map((c) => languageNames[c]?.[lang] ?? c).join(lang === "ar" ? "، " : ", ")}
      </div>
      {d.next_available && (
        <div className="slot">{s.nextSlot}: {formatSlot(d.next_available, lang)}</div>
      )}
    </article>
  );
}

export function HospitalCardView({ h, lang }: { h: HospitalCard; lang: Lang }) {
  const s = t[lang];
  return (
    <article className={`card ${h.has_emergency ? "card-er" : ""}`}>
      <div className="card-head">
        <strong>{pick(h, "name", lang)}</strong>
        <span className="muted">{pick(h.city, "name", lang)}</span>
      </div>
      <div className="muted">{pick(h, "address", lang)}</div>
      <a className="call" href={`tel:${h.phone.replace(/[^\d+]/g, "")}`}>
        {s.call} <bdi dir="ltr">{h.phone}</bdi>
      </a>
    </article>
  );
}
