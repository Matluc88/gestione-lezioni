#!/bin/bash
# Script per installare le dipendenze del modulo Contratti
# Esegui questo script dal terminale con: bash INSTALLA_DIPENDENZE.sh

echo "🔧 Installazione dipendenze modulo Contratti..."
echo ""

# Prova metodo 1: con --break-system-packages
echo "Metodo 1: Installazione con --break-system-packages"
python3 -m pip install --break-system-packages anthropic pypdf2

if [ $? -eq 0 ]; then
    echo "✅ Dipendenze installate con successo!"
    echo ""
    echo "Puoi ora avviare l'applicazione con:"
    echo "  python3 app.py"
else
    echo "❌ Installazione fallita."
    echo ""
    echo "Prova manualmente uno di questi comandi:"
    echo ""
    echo "1) pip3 install anthropic pypdf2"
    echo "2) python3 -m pip install anthropic pypdf2"
    echo "3) Crea un virtual environment:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
fi
