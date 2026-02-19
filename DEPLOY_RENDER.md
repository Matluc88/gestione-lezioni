# 🚀 Deploy su Render - Modulo Contratti

## 📍 Problema Attuale

Dopo il force push su GitHub, Render NON ha fatto il deploy automatico. Devi:
1. Fare un deploy manuale
2. Aggiornare le variabili d'ambiente con la nuova API key

---

## 🔧 STEP 1: Aggiorna Variabili d'Ambiente su Render

### 1. Vai su Render Dashboard
https://dashboard.render.com

### 2. Seleziona il tuo Web Service "gestione-lezioni"

### 3. Vai su **"Environment"** nel menu laterale

### 4. Aggiungi/Aggiorna questa variabile:

**Nome variabile:** `ANTHROPIC_API_KEY`  
**Valore:** La tua nuova chiave API Claude (quella che ti ho dato in privato, inizia con sk-ant-api03-)

⚠️ **NOTA**: Usa la chiave API che hai rigenerato, NON quella vecchia!

### 5. Clicca **"Save Changes"**

⚠️ **IMPORTANTE**: Quando salvi le variabili d'ambiente, Render potrebbe fare il deploy automaticamente. Se NON lo fa, procedi allo Step 2.

---

## 🚀 STEP 2: Deploy Manuale

### Opzione A: Trigger Manual Deploy (Preferito)

1. Vai sulla pagina del tuo servizio su Render
2. In alto a destra, clicca su **"Manual Deploy"**
3. Seleziona **"Deploy latest commit"**
4. Clicca **"Deploy"**

### Opzione B: Forza Deploy con Commit Vuoto

Se l'opzione A non funziona, forza il deploy con un commit vuoto:

```bash
cd /Users/matteo/Desktop/gestione-lezioni-main
git commit --allow-empty -m "Trigger Render deploy"
git push origin main
```

Questo forzerà Render a fare il deploy.

---

## ⏱️ STEP 3: Monitora il Deploy

1. Nella dashboard Render, vedrai **"Deploy in progress"**
2. Clicca sul deploy per vedere i logs in tempo reale
3. Cerca questi messaggi di successo:
   ```
   ==> Installing dependencies from requirements.txt
   ==> Successfully installed anthropic-x.x.x pypdf2-x.x.x
   ==> Starting service with 'gunicorn app:app'
   ==> Your service is live 🎉
   ```

Il deploy dovrebbe richiedere **2-5 minuti**.

---

## ✅ STEP 4: Verifica Funzionalità

Una volta completato il deploy:

1. Vai sul tuo sito: **https://[tuo-sito].onrender.com**
2. Fai **login**
3. Clicca su **⋯ Altro** (tab in basso a destra)
4. Dovresti vedere **📄 Contratti** nel menu!

---

## 🔍 Troubleshooting

### Errore: "ModuleNotFoundError: No module named 'anthropic'"

**Causa**: Le dipendenze non sono state installate.  
**Soluzione**: Verifica che `requirements.txt` contenga:
```
anthropic>=0.18.0
pypdf2>=3.0.0
```

Se manca, aggiungilo localmente e fai push:
```bash
echo "anthropic>=0.18.0" >> requirements.txt
echo "pypdf2>=3.0.0" >> requirements.txt
git add requirements.txt
git commit -m "Add anthropic and pypdf2 dependencies"
git push origin main
```

### Errore: "ANTHROPIC_API_KEY not configured"

**Causa**: Variabile d'ambiente non impostata su Render.  
**Soluzione**: Torna allo STEP 1 e verifica di aver salvato correttamente.

### Il deploy non parte

**Soluzione**: Usa l'Opzione B (commit vuoto) per forzare il deploy.

---

## 📊 Verifica Logs

Per vedere cosa sta succedendo:

1. Dashboard Render → Tuo servizio
2. Tab **"Logs"**
3. Filtra per "Error" se ci sono problemi

---

## ✨ Tutto Fatto!

Una volta completati questi step, il modulo Contratti sarà LIVE su Render! 🎉

Se hai errori durante il deploy, copia i logs e inviameli così ti aiuto a risolvere.

---

**Tempo stimato**: 5-10 minuti  
**Difficoltà**: Facile (seguendo gli step)
