-- HealTrip AI Patient Decision Assistant — database schema
--
-- Designed backwards from the questions the agent needs to answer:
--   "Which cardiologists are in Jeddah?"                  -> doctors.specialty_id, hospitals.city_id
--   "...who speak Arabic?"                                 -> doctor_languages (many-to-many)
--   "...who accept second-opinion requests?"               -> doctors.accepts_second_opinion
--   "Where is the nearest emergency department?"           -> hospitals.has_emergency
--   "Do they have an open slot soon?"                      -> availability_slots
-- Every entity has name_en + name_ar so the UI can render either language
-- straight from the database (the LLM never writes names).

CREATE TABLE cities (
    id          SERIAL PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,          -- stable key the agent uses, e.g. 'jeddah'
    name_en     TEXT NOT NULL,
    name_ar     TEXT NOT NULL,
    country_code CHAR(2) NOT NULL
);

CREATE TABLE specialties (
    id          SERIAL PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,          -- e.g. 'cardiology' — closed list the agent must pick from
    name_en     TEXT NOT NULL,
    name_ar     TEXT NOT NULL
);

CREATE TABLE hospitals (
    id            SERIAL PRIMARY KEY,
    name_en       TEXT NOT NULL,
    name_ar       TEXT NOT NULL,
    city_id       INT NOT NULL REFERENCES cities(id),
    address_en    TEXT NOT NULL,
    address_ar    TEXT NOT NULL,
    phone         TEXT NOT NULL,               -- public switchboard number only
    has_emergency BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE doctors (
    id                      SERIAL PRIMARY KEY,
    name_en                 TEXT NOT NULL,
    name_ar                 TEXT NOT NULL,
    specialty_id            INT NOT NULL REFERENCES specialties(id),
    hospital_id             INT NOT NULL REFERENCES hospitals(id),   -- one hospital -> many doctors
    years_experience        INT NOT NULL CHECK (years_experience >= 0),
    accepts_second_opinion  BOOLEAN NOT NULL DEFAULT FALSE,
    offers_teleconsult      BOOLEAN NOT NULL DEFAULT FALSE,
    is_active               BOOLEAN NOT NULL DEFAULT TRUE             -- soft-delete: never recommend inactive doctors
);

CREATE TABLE languages (
    code    TEXT PRIMARY KEY,                  -- ISO 639-1: 'ar', 'en', 'fr', 'ur'
    name_en TEXT NOT NULL,
    name_ar TEXT NOT NULL
);

-- Many-to-many: a doctor speaks many languages, a language is spoken by many doctors.
-- Composite PK prevents duplicate (doctor, language) rows.
CREATE TABLE doctor_languages (
    doctor_id     INT  NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    language_code TEXT NOT NULL REFERENCES languages(code),
    PRIMARY KEY (doctor_id, language_code)
);

CREATE TABLE availability_slots (
    id         SERIAL PRIMARY KEY,
    doctor_id  INT NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    starts_at  TIMESTAMPTZ NOT NULL,
    is_booked  BOOLEAN NOT NULL DEFAULT FALSE
);

-- Indexes for the exact filters the search tool runs
CREATE INDEX idx_doctors_specialty_hospital ON doctors (specialty_id, hospital_id) WHERE is_active;
CREATE INDEX idx_hospitals_city ON hospitals (city_id);
CREATE INDEX idx_hospitals_er ON hospitals (city_id) WHERE has_emergency;
CREATE INDEX idx_slots_open ON availability_slots (doctor_id, starts_at) WHERE NOT is_booked;
