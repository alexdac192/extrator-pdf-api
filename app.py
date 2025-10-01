# --- Imports da Aplicação Web ---
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import re
from datetime import datetime
import fitz  # PyMuPDF

# --- Suas Bibliotecas Adicionais ---
from thefuzz import fuzz

# --- Inicialização da Aplicação Flask ---
app = Flask(__name__)
CORS(app)

# --- Suas Constantes de Status ---
STATUS_OPEN = "OPEN"
STATUS_CLOSED = "CLOSED"
STATUS_WAIT_APPROVAL = "WAIT APPROVAL"
STATUS_POSTPONED = "POSTPONED"
STATUS_REPLANEJADO = "REPLANEJADO"
STATUS_RETIRADA = "RETIRADA"

# --- SUA LÓGICA DE EXTRAÇÃO, AGORA INTEGRADA ---


def extrair_dados_pdf_pymupdf(pdf_stream):
    dados_cabecalho = {"report_date": None}
    try:
        doc = fitz.open(stream=pdf_stream, filetype="pdf")

        page_one = doc[0]
        text_page_one = page_one.get_text()

        report_date = None
        match1 = re.search(
            r"Today\s+([\w\s,]+\d{4})", text_page_one, re.IGNORECASE)
        if match1:
            date_str_raw = match1.group(1).strip()
            date_str_clean = date_str_raw.replace(',', '')
            for fmt in ["%B %d %Y", "%b %d %Y"]:
                try:
                    report_date = datetime.strptime(date_str_clean, fmt)
                    break
                except ValueError:
                    continue
        if not report_date:
            match2 = re.search(
                r"Today\s+(\d{2}/\d{2}/\d{4})", text_page_one, re.IGNORECASE)
            if match2:
                date_str = match2.group(1).strip()
                try:
                    report_date = datetime.strptime(date_str, "%d/%m/%Y")
                except ValueError:
                    pass

        dados_cabecalho["report_date"] = report_date or datetime.now()

    except Exception as e:
        print(f"Aviso: Não foi possível ler o cabeçalho do PDF. Erro: {e}.")
        dados_cabecalho["report_date"] = datetime.now()
        # Se não conseguir ler o cabeçalho, não podemos continuar. Retornamos vazio.
        return dados_cabecalho, pd.DataFrame()

    validated_rows = []
    VALID_GROUPS = {"Planned", "Internal Procedure", "Customer Request"}
    ALL_STATUSES = {STATUS_OPEN, STATUS_CLOSED, STATUS_WAIT_APPROVAL,
                    STATUS_POSTPONED, STATUS_REPLANEJADO, STATUS_RETIRADA}

    try:
        for page_num in range(1, len(doc)):
            page = doc[page_num]
            tables_on_page = page.find_tables()
            if not tables_on_page:
                continue

            raw_table_data = tables_on_page[0].extract()
            if not raw_table_data:
                continue

            header_signature = ['SEQ', 'GROUP', 'DESCRIPTION']

            for row in raw_table_data:
                if any(sig in str(cell) for sig, cell in zip(header_signature, row[:len(header_signature)])):
                    continue

                # Sua lógica de parsing de linha aqui...
                # (A lógica original foi mantida e simplificada para o contexto da API)
                id_val = str(row[0] or '').strip()
                seq_val = str(row[1] or '').strip()
                group_val = str(row[2] or '').strip()
                desc_val = str(row[3] or '').strip()
                status_val = str(row[4] or '').strip() if len(
                    row) > 4 else STATUS_OPEN

                validated_rows.append(
                    [None, seq_val, group_val, desc_val, status_val, id_val, None])

        doc.close()
    except Exception as e:
        print(f"Erro ao extrair tabelas com PyMuPDF: {e}")
        return dados_cabecalho, pd.DataFrame()

    if not validated_rows:
        return dados_cabecalho, pd.DataFrame()

    colunas = ['PHASE', 'SEQ', 'GROUP', 'DESCRIPTION',
               'STATUS', 'EXTERNAL TASK', 'ORIG']
    df_final = pd.DataFrame(validated_rows, columns=colunas)

    if df_final.empty:
        return dados_cabecalho, df_final

    df_final['SEQ'] = pd.to_numeric(df_final['SEQ'], errors='coerce')
    df_final.dropna(subset=['SEQ'], inplace=True)
    df_final['SEQ'] = df_final['SEQ'].astype(int)

    # Simplicamos a agregação para o contexto de um único PDF
    df_final = df_final.groupby('SEQ', as_index=False).first()
    df_final.loc[df_final['STATUS'] == '', 'STATUS'] = STATUS_WAIT_APPROVAL

    return dados_cabecalho, df_final


# --- ROTA DA API ---
@app.route("/api/upload", methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nome de arquivo vazio"}), 400

    if file and file.filename.lower().endswith('.pdf'):
        pdf_bytes = file.read()
        dados_cabecalho, df_resultado = extrair_dados_pdf_pymupdf(pdf_bytes)

        if df_resultado.empty:
            return jsonify({"message": "Nenhum dado relevante encontrado no PDF."})

        resultado_json = df_resultado.to_dict(orient='records')
        data_relatorio_str = dados_cabecalho.get(
            'report_date').isoformat() if dados_cabecalho.get('report_date') else None

        return jsonify({
            "report_date": data_relatorio_str,
            "tasks": resultado_json
        })
    else:
        return jsonify({"error": "Formato de arquivo inválido. Apenas PDFs são aceitos."}), 400


# --- Ponto de Entrada para Rodar o Servidor ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
