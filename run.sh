#!/usr/bin/env bash
set -e

if [ ! -d ".venv" ]; then
  echo "Creando entorno virtual..."
  python3 -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "Se creó .env desde .env.example"
fi

if [ -f ".env" ] && grep -q "pega_aqui_el_token_de_botfather" .env; then
  echo "Falta configurar el token de Telegram en .env"
  echo "1. Abre .env"
  echo "2. Cambia TELEGRAM_BOT_TOKEN=pega_aqui_el_token_de_botfather"
  echo "3. Pon el token real de BotFather"
  echo "4. Ejecuta: python bot.py"
  exit 1
fi

python bot.py
