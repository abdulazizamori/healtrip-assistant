"""Database access. Every query is parameterized and lives here — the LLM never writes SQL."""

from dataclasses import dataclass

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class Database:
    def __init__(self, url: str):
        self.pool = ConnectionPool(url, min_size=1, max_size=10, kwargs={"row_factory": dict_row}, open=False)

    def open(self) -> None:
        self.pool.open(wait=True, timeout=10)

    def close(self) -> None:
        self.pool.close()

    def fetch_all(self, sql: str, params: dict | tuple = ()) -> list[dict]:
        with self.pool.connection() as conn:
            return conn.execute(sql, params).fetchall()

    def ping(self) -> bool:
        try:
            self.fetch_all("SELECT 1 AS ok")
            return True
        except Exception:
            return False


@dataclass(frozen=True)
class ReferenceData:
    """Closed lists loaded once at startup. They become enums in the tool schemas,
    so the model can only pick values that actually exist in the database."""

    cities: dict[str, dict]        # code -> row
    specialties: dict[str, dict]   # code -> row
    languages: dict[str, dict]     # code -> row


def load_reference_data(db: Database) -> ReferenceData:
    return ReferenceData(
        cities={r["code"]: r for r in db.fetch_all("SELECT code, name_en, name_ar FROM cities ORDER BY code")},
        specialties={r["code"]: r for r in db.fetch_all("SELECT code, name_en, name_ar FROM specialties ORDER BY code")},
        languages={r["code"]: r for r in db.fetch_all("SELECT code, name_en, name_ar FROM languages ORDER BY code")},
    )


# ---------------------------------------------------------------- queries

SEARCH_DOCTORS_SQL = """
SELECT d.id,
       s.code  AS specialty_code,
       h.id    AS hospital_id,
       c.code  AS city_code,
       d.years_experience,
       d.accepts_second_opinion,
       d.offers_teleconsult,
       ARRAY(SELECT dl.language_code FROM doctor_languages dl WHERE dl.doctor_id = d.id ORDER BY 1) AS languages,
       (SELECT min(a.starts_at) FROM availability_slots a
         WHERE a.doctor_id = d.id AND NOT a.is_booked AND a.starts_at > now()) AS next_available
FROM doctors d
JOIN specialties s ON s.id = d.specialty_id
JOIN hospitals   h ON h.id = d.hospital_id
JOIN cities      c ON c.id = h.city_id
WHERE d.is_active
  AND s.code = %(specialty)s
  AND c.code = %(city)s
  AND (%(language)s::text IS NULL OR EXISTS (
        SELECT 1 FROM doctor_languages dl WHERE dl.doctor_id = d.id AND dl.language_code = %(language)s))
  AND (NOT %(second_opinion)s OR d.accepts_second_opinion)
  AND (NOT %(teleconsult)s OR d.offers_teleconsult)
ORDER BY next_available NULLS LAST, d.years_experience DESC
LIMIT %(limit)s
"""

EMERGENCY_HOSPITALS_SQL = """
SELECT h.id, c.code AS city_code
FROM hospitals h JOIN cities c ON c.id = h.city_id
WHERE h.has_emergency AND c.code = %(city)s
ORDER BY h.id
LIMIT 3
"""

DOCTOR_SLOTS_SQL = """
SELECT a.starts_at
FROM availability_slots a JOIN doctors d ON d.id = a.doctor_id
WHERE a.doctor_id = %(doctor_id)s AND d.is_active AND NOT a.is_booked AND a.starts_at > now()
ORDER BY a.starts_at
LIMIT 3
"""

# Hydration: full display data for IDs that already passed validation.
DOCTOR_CARDS_SQL = """
SELECT d.id, d.name_en, d.name_ar, d.years_experience, d.accepts_second_opinion, d.offers_teleconsult,
       s.code AS specialty_code, s.name_en AS specialty_en, s.name_ar AS specialty_ar,
       h.id AS hospital_id, h.name_en AS hospital_en, h.name_ar AS hospital_ar, h.has_emergency,
       c.code AS city_code, c.name_en AS city_en, c.name_ar AS city_ar,
       ARRAY(SELECT dl.language_code FROM doctor_languages dl WHERE dl.doctor_id = d.id ORDER BY 1) AS languages,
       (SELECT min(a.starts_at) FROM availability_slots a
         WHERE a.doctor_id = d.id AND NOT a.is_booked AND a.starts_at > now()) AS next_available
FROM doctors d
JOIN specialties s ON s.id = d.specialty_id
JOIN hospitals   h ON h.id = d.hospital_id
JOIN cities      c ON c.id = h.city_id
WHERE d.id = ANY(%(ids)s) AND d.is_active
"""

HOSPITAL_CARDS_SQL = """
SELECT h.id, h.name_en, h.name_ar, h.address_en, h.address_ar, h.phone, h.has_emergency,
       c.code AS city_code, c.name_en AS city_en, c.name_ar AS city_ar
FROM hospitals h JOIN cities c ON c.id = h.city_id
WHERE h.id = ANY(%(ids)s)
"""

# Used by the deterministic emergency path (no LLM involved).
EMERGENCY_HOSPITAL_CARDS_SQL = """
SELECT h.id, h.name_en, h.name_ar, h.address_en, h.address_ar, h.phone, h.has_emergency,
       c.code AS city_code, c.name_en AS city_en, c.name_ar AS city_ar
FROM hospitals h JOIN cities c ON c.id = h.city_id
WHERE h.has_emergency AND c.code = %(city)s
ORDER BY h.id
LIMIT 3
"""
