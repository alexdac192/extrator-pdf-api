#!/usr/bin/env bash

# Sair imediatamente se um comando falhar
set -o errexit

# 1. Instalar as dependências
python -m pip install -r requirements.txt

# 2. Iniciar o servidor de produção Gunicorn
#    O Render usa a variável de ambiente PORT para saber em que porta deve correr.
python -m gunicorn --bind 0.0.0.0:$PORT app:app
