-- Least privilege: the API connects as a role that can only SELECT.
-- Even if a bug or a prompt injection reached the database layer, it could not write or delete.
-- (The password here is for local development only; in production it comes from a secret manager.)

CREATE ROLE healtrip_agent_ro LOGIN PASSWORD 'readonly_dev_password';
GRANT CONNECT ON DATABASE healtrip TO healtrip_agent_ro;
GRANT USAGE ON SCHEMA public TO healtrip_agent_ro;
GRANT SELECT ON cities, specialties, hospitals, doctors, languages, doctor_languages, availability_slots
      TO healtrip_agent_ro;
