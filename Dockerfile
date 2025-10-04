# 1. Usar a imagem Python completa para garantir que todas as bibliotecas do sistema estão presentes
FROM python:3.11

# 2. MUDANÇA FINAL E DEFINITIVA: Instalar as dependências de sistema, incluindo as de fontes/gráficos que o PyMuPDF pode precisar
RUN apt-get update && apt-get install -y libgl1 tcl tk

# 3. Definir a pasta de trabalho dentro do nosso "mini-computador"
WORKDIR /app

# 4. Copiar o ficheiro de dependências para a pasta de trabalho
COPY requirements.txt .

# 5. Instalar todas as bibliotecas do requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

# 6. Copiar todo o resto do nosso código (app.py, etc.) para a pasta de trabalho
COPY . .

# 7. O comando que será executado, otimizado para o Render.
CMD ["gunicorn", "--workers", "1", "--timeout", "120", "--bind", "0.0.0.0:$PORT", "app:app"]


### **O Passo Final (A Promessa Final)**