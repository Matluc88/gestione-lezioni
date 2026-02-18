-- Script per rimuovere il vincolo UNIQUE da numero_fattura in PostgreSQL
-- Questo permette di avere lo stesso numero fattura per anni diversi

-- Trova e rimuove il vincolo UNIQUE su numero_fattura
ALTER TABLE fatture DROP CONSTRAINT IF EXISTS fatture_numero_fattura_key;

-- Verifica che il vincolo sia stato rimosso
SELECT conname, contype 
FROM pg_constraint 
WHERE conrelid = 'fatture'::regclass 
  AND contype = 'u';

-- Se non c'è output, il vincolo è stato rimosso con successo
