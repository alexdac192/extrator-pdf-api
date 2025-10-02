# 1. Começar com uma imagem oficial e leve do Python
FROM python:3.11-slim

# 2. Definir a pasta de trabalho dentro do nosso "mini-computador"
WORKDIR /app

# 3. Copiar o ficheiro de dependências para a pasta de trabalho
COPY requirements.txt .

# 4. Instalar todas as bibliotecas do requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

# 5. Copiar todo o resto do nosso código (app.py, etc.) para a pasta de trabalho
COPY . .

# 6. O comando que será executado quando a "caixa" for ligada
#    Isto inicia o nosso servidor Gunicorn
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
