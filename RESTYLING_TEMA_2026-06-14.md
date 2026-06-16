# Restyling — Tema unico (2026-06-14)

Documento di lavoro per la modifica grafica "tema unico". Serve a sapere
**esattamente cosa è cambiato** e a **tornare indietro** se qualcosa non va.

## Perché

L'app era incoerente: alcune pagine (Fatture, Corsi, Contratti...) usano un
design "iOS" pulito; altre — inclusa la **Dashboard** — erano pagine
standalone con uno sfondo a **gradiente beige** e usavano variabili CSS
(`--surface-color`, `--primary-color`, ...) che però **non avevano un valore
in modalità chiara** (erano definite solo dentro un `@media dark`). Risultato:
schede semi-trasparenti, colori a caso, aspetto "non a posto".

## Cosa è stato fatto (Step 1 — solo colori/tema, nessun ridisegno)

1. **Nuovo file `static/css/theme.css`** — caricato per ultimo in ogni pagina:
   - definisce la palette unica (uguale a `ios-core.css`: blu `#007AFF`,
     verde `#34C759`, sfondo `#F2F2F7`, schede bianche, testo `#1C1C1E`);
   - dà finalmente un valore alle variabili usate dalle pagine standalone;
   - **sostituisce il gradiente beige** con lo sfondo neutro delle pagine iOS;
   - allinea i **pulsanti primari Bootstrap** e i link al blu iOS.
2. **Link a `theme.css`** aggiunto nei template standalone + `base_ios.html`
   (quindi copre anche le 9 pagine in stile iOS), 1 riga per pagina.

**Principio**: nessuna pagina è stata riscritta. Solo aggiunte. Il foglio è
caricato dopo gli stili esistenti, quindi vince senza bisogno di `!important`.

### Nota modalità scura
Le pagine standalone avevano una modalità scura abbozzata e incoerente. Il
tema unico forza un aspetto **chiaro e coerente** anche su telefoni in dark
mode (scelta voluta per uniformità). Una vera variante dark è eventualmente
un lavoro successivo.

## File toccati
- `static/css/theme.css` (NUOVO)
- `RESTYLING_TEMA_2026-06-14.md` (questo file, NUOVO)
- `templates/*.html` standalone + `base_ios.html`: +1 riga `<link ... theme.css>`

## Deploy
- Base di partenza (commit live PRIMA della modifica): **`6374dc3`**
  (= "mobile: correzioni layout per smartphone").
- Branch: `feat/tema-unico` → push fast-forward su `main` → Render pubblica.
- Commit della modifica: _vedi `git log` di `main` dopo il push (riga "tema unico")._

## ROLLBACK (tornare com'era prima)

Se il tema non convince, da `/Users/matteo`:

```bash
# Riporta il sito live ESATTAMENTE allo stato precedente (commit 6374dc3)
git push origin 6374dc3:main --force
```

Render ripubblica automaticamente la versione precedente in 1-3 minuti.
Le correzioni mobile del passaggio precedente restano (erano in 6374dc3).

In alternativa, rollback "morbido" senza toccare la storia (crea un commit
che annulla solo il tema), da un worktree pulito su `origin/main`:

```bash
git worktree add /tmp/glez-rb origin/main -b revert-tema
cd /tmp/glez-rb
git revert --no-edit <commit-del-tema>
git push origin revert-tema:main
```

## Come verificare che vada bene (sul telefono)
Aprire e controllare che siano leggibili e coerenti (stesso azzurro, sfondo
chiaro uniforme, niente beige): **Dashboard**, Calendario, Compenso,
Stato Crediti, Resoconto, una pagina di inserimento (Aggiungi lezione/fattura).

---

## CHANGELOG

### 2026-06-15 — Fix leggibilità calendario
**Problema**: dentro gli eventi del calendario il **nome del corso non si
leggeva**. Causa: il backend non imposta il colore del testo degli eventi e la
regola `a:not(.btn){color:#007AFF}` del tema (gli eventi sono `<a>`) rendeva il
nome **blu su sfondo blu/verde**.

**Fix** (solo `static/css/theme.css`):
- esclusi gli eventi dalla regola dei link;
- testo eventi (vista griglia) **bianco, grassetto**, con **a-capo** invece del
  troncamento; la vista lista/agenda resta scura su bianco.

**Rollback solo di questo fix**: `git push origin fe7217b:main --force`
(`fe7217b` = stato con tema ma senza questo fix). Per tornare a prima del tema,
vedi sopra (`6374dc3`).

### 2026-06-15 — Grafici ricolorati (palette unica)
**Problema**: i grafici usavano la palette "arcobaleno" di default di Chart.js
(blu/teal/rosa/giallo/indaco a caso) + beige/marrone → aspetto incoerente.

**Fix** (templates `resoconto_annuale.html`, `compenso.html`): rimappati i
colori dei dataset sulla palette iOS, mantenendo le trasparenze:
- 54,162,235 → 0,122,255 (blu) · 75,192,192 → 90,200,250 (azzurro) ·
  255,99,132 → 255,59,48 (rosso) · 255,206,86 → 255,149,0 (arancio) ·
  102,126,234 → 88,86,214 (indaco) · 40,167,69 → 52,199,89 (verde) ·
  #28a745 → #34C759.
- 46 sostituzioni totali. Nessuna logica toccata, solo colori.

**Da fare eventualmente** (non incluso): gli sfondi/bordi beige-marrone
(`#a67c52`, `#d4c5b9`) rimasti nel CSS di queste due pagine (chrome, non
grafici); e — su richiesta dell'utente "non li guardo quasi mai" — si possono
nascondere/comprimere i grafici dando priorità ai numeri/totali.

**Rollback solo di questo fix**: `git push origin f8e60ee:main --force`

### 2026-06-15 — Pulizia resti tema beige/marrone
**Analisi (da pagine live, login admin)**: dopo il tema unico restavano resti
del vecchio tema in 8+ pagine: bottoni/intestazioni/bordi **marrone `#a67c52`**
e **beige `#d4c5b9`/`#e8dfd6`** (chrome non toccato dal tema, che agiva solo su
body+grafici).

**Fix**: sostituzione globale nei template:
- `#a67c52` → `#007AFF` (blu iOS) · `#d4c5b9`/`#e8dfd6` → `#F2F2F7` (grigio chiaro).
- 67 sostituzioni su 14 file, 0 residui. Verificato sicuro: il marrone era
  quasi solo sfondo/bordo (1 sola occorrenza come testo), il beige solo sfondo.

**Restano (decisioni a parte)**:
- **Navigazione doppia**: Fatture/Corsi usano la barra iOS in basso, le altre il
  menu hamburger → unificare è un lavoro più grosso.
- **Angoli squadrati** (`border-radius:0`) su varie pagine vs arrotondati iOS.
- Emoji come icone nei titoli.

**Rollback solo di questo fix**: `git push origin e157c1f:main --force`
