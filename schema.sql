CREATE TABLE lezioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
CREATE TABLE archiviate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
CREATE TABLE fatture (
    id_fattura INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_fattura TEXT NOT NULL UNIQUE,
    id_corso TEXT,
    data_fattura TEXT NOT NULL,
    importo REAL NOT NULL,
    tipo_fatturazione TEXT CHECK(tipo_fatturazione IN ('parziale', 'totale')) NOT NULL,
    file_pdf TEXT NOT NULL,
    note TEXT
);
CREATE TABLE fatture_lezioni (
    id_fattura INTEGER,
    id_lezione INTEGER,
    FOREIGN KEY (id_fattura) REFERENCES fatture (id_fattura),
    FOREIGN KEY (id_lezione) REFERENCES lezioni (id)
);

CREATE TABLE corsi_archiviati (
    id_corso TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    cliente TEXT DEFAULT NULL,
    data_archiviazione TEXT NOT NULL
);

CREATE TABLE corsi (
    id_corso TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    cliente TEXT DEFAULT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);
