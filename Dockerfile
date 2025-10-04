# 1. Usar a imagem Python completa para garantir que todas as bibliotecas do sistema estão presentes
FROM python:3.11

# 2. Instalar a dependência de sistema com o nome correto para esta versão do Debian
RUN apt-get update && apt-get install -y libgl1

# 3. Definir a pasta de trabalho dentro do nosso "mini-computador"
WORKDIR /app

# 4. Copiar o ficheiro de dependências para a pasta de trabalho
COPY requirements.txt .

# 5. Instalar todas as bibliotecas do requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

# 6. Copiar todo o resto do nosso código (app.py, etc.) para a pasta de trabalho
COPY . .

# 7. CORREÇÃO FINAL: O comando que será executado, otimizado para o Render.
#    --workers 1: Usa apenas um trabalhador (melhor para pouca memória).
#    --timeout 120: Aumenta o tempo de espera para 120 segundos.
CMD ["gunicorn", "--workers", "1", "--timeout", "120", "--bind", "0.0.0.0:$PORT", "app:app"]


### **O Passo Final (Agora com um Build Bem-Sucedido)**