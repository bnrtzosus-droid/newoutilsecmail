#!/bin/bash
echo "============================================"
echo "  INSTALLATION - Detecteur de Comptes"
echo "============================================"
echo ""

echo "[1/3] Vérification de Python..."
if ! command -v python3 &> /dev/null; then
    echo "ERREUR: Python3 non installé."
    echo "Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "Mac: brew install python3"
    exit 1
fi
echo "OK - Python détecté."

echo ""
echo "[2/3] Installation des dépendances..."
pip3 install playwright
if [ $? -ne 0 ]; then
    echo "ERREUR lors de l'installation."
    exit 1
fi

echo ""
echo "[3/3] Installation du navigateur Chromium..."
playwright install chromium
if [ $? -ne 0 ]; then
    echo "ERREUR lors de l'installation de Chromium."
    exit 1
fi

echo ""
echo "============================================"
echo "  INSTALLATION TERMINÉE !"
echo "============================================"
echo ""
echo "Pour lancer le logiciel :"
echo "  python3 checker.py"
echo ""
