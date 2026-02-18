
CREATE TABLE IF NOT EXISTS lezioni (
    id SERIAL PRIMARY KEY,
    id_corso TEXT NOT NULL,
    materia TEXT NOT NULL,
    data TEXT NOT NULL,
    ora_inizio TEXT NOT NULL,
    ora_fine TEXT NOT NULL,
    luogo TEXT NOT NULL,
    compenso_orario REAL NOT NULL,
    stato TEXT NOT NULL,
    fatturato INTEGER DEFAULT 0,
    mese_fatturato TEXT DEFAULT NULL,
    ore_fatturate REAL DEFAULT 0,
    google_calendar_event_id TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS archiviate (
    id SERIAL PRIMARY KEY,
    id_corso TEXT NOT NULL,
    materia TEXT NOT NULL,
    data TEXT NOT NULL,
    ora_inizio TEXT NOT NULL,
    ora_fine TEXT NOT NULL,
    luogo TEXT NOT NULL,
    compenso_orario REAL NOT NULL,
    stato TEXT NOT NULL,
    fatturato INTEGER DEFAULT 0,
    mese_fatturato TEXT DEFAULT NULL,
    ore_fatturate REAL DEFAULT 0,
    google_calendar_event_id TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS fatture (
    id_fattura SERIAL PRIMARY KEY,
    numero_fattura TEXT NOT NULL,
    id_corso TEXT,
    data_fattura TEXT NOT NULL,
    importo REAL NOT NULL,
    tipo_fatturazione TEXT NOT NULL CHECK(tipo_fatturazione IN ('parziale', 'totale')),
    file_pdf TEXT NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS fatture_lezioni (
    id_fattura INTEGER,
    id_lezione INTEGER,
    FOREIGN KEY (id_fattura) REFERENCES fatture (id_fattura),
    FOREIGN KEY (id_lezione) REFERENCES lezioni (id)
);

CREATE TABLE IF NOT EXISTS corsi (
    id_corso TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    cliente TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS corsi_archiviati (
    id_corso TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    cliente TEXT DEFAULT NULL,
    data_archiviazione TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);


CREATE OR REPLACE FUNCTION extract_year(data TEXT) 
RETURNS TEXT AS $$
BEGIN
    RETURN EXTRACT(YEAR FROM TO_DATE(data, 'YYYY-MM-DD'))::TEXT;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION extract_year_month(data TEXT) 
RETURNS TEXT AS $$
BEGIN
    RETURN TO_CHAR(TO_DATE(data, 'YYYY-MM-DD'), 'YYYY-MM');
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION extract_year_week(data TEXT) 
RETURNS TEXT AS $$
BEGIN
    RETURN TO_CHAR(TO_DATE(data, 'YYYY-MM-DD'), 'YYYY-IW');
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION extract_weekday(data TEXT) 
RETURNS TEXT AS $$
BEGIN
    RETURN EXTRACT(DOW FROM TO_DATE(data, 'YYYY-MM-DD'))::TEXT;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION calcola_ore(ora_inizio TEXT, ora_fine TEXT) 
RETURNS REAL AS $$
BEGIN
    RETURN EXTRACT(EPOCH FROM (
        TO_TIMESTAMP('2000-01-01 ' || ora_fine, 'YYYY-MM-DD HH24:MI') - 
        TO_TIMESTAMP('2000-01-01 ' || ora_inizio, 'YYYY-MM-DD HH24:MI')
    )) / 3600.0;
END;
$$ LANGUAGE plpgsql;

INSERT INTO users (username, password) 
VALUES ('admin', 'pbkdf2:sha256:600000$Ub4Nt9Oa$e0c7e2c1c9e5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5')
ON CONFLICT (username) DO NOTHING;
