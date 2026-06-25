#!/usr/bin/env bash
# ==========================================================
#   CRM Virtualder - Lanzador (Linux / macOS)
#   Ejecutar: ./run.sh  luego abrir http://localhost:5000
# ==========================================================
set -e
cd "$(dirname "$0")"

echo ""
echo "  ============================================"
echo "    CRM Virtualder - Iniciando..."
echo "  ============================================"
echo ""

# Instalar dependencias si faltan
python -m pip install -q -r requirements.txt

python app.py
