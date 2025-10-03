# --- Imports da Aplicação Web ---
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import re
from datetime import datetime
import fitz  # PyMuPDF
import os  # Importar a biblioteca os

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
    # (O seu código de extração, que está perfeito, continua aqui inalterado)
    # ... [código de extração omitido para brevidade] ...
    """
    Sua função original, adaptada para receber um stream de bytes de um PDF.
    """
    dados_cabecalho = {"report_date": None}
    try:
        # ADAPTAÇÃO PRINCIPAL: Abrir o PDF a partir do stream de bytes
        doc = fitz.open(stream=pdf_stream, filetype="pdf")

        page_one = doc[0]
        text_page_one = page_one.get_text()

        # Extração de data (sua lógica mantida)
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
        print(
            f"Aviso: Não foi possível ler o cabeçalho do PDF. Erro: {e}. Usando data atual.")
        dados_cabecalho["report_date"] = datetime.now()

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
            header_signature = ['SEQ', 'GROUP', 'DESCRIPTION']

            for row in raw_table_data:
                if any(sig in str(cell) for sig, cell in zip(header_signature, row)):
                    continue

                id_val = str(row[0] or '').strip() if len(row) > 0 else ''
                seq_val_c = str(row[1] or '').strip() if len(row) > 1 else ''
                is_critical_issue = id_val.isdigit() and seq_val_c.isdigit()

                seq_val_n = str(row[1] or '').strip() if len(row) > 1 else ''
                is_task_normal = seq_val_n.isdigit()

                seq_val_s = str(row[0] or '').strip() if len(row) > 0 else ''
                is_task_shifted = seq_val_s.isdigit()

                if is_critical_issue:
                    description = str(row[2] or '').strip() if len(
                        row) > 2 else ''
                    status = str(row[3] or '').strip() if len(
                        row) > 3 else STATUS_OPEN
                    if status not in ALL_STATUSES and len(status) > 20:
                        description = (description + ' ' + status).strip()
                        status = STATUS_OPEN
                    elif status not in ALL_STATUSES:
                        status = STATUS_OPEN
                    normalized_row = [None, seq_val_c, 'Finding',
                                      description, status, id_val, None]
                    validated_rows.append(normalized_row)

                elif is_task_normal:
                    group_val = str(row[2] or '').strip() if len(
                        row) > 2 else ''
                    if group_val in VALID_GROUPS:
                        validated_rows.append(list(row))
                    else:
                        seq = seq_val_n
                        phase = row[0]
                        content_cells = row[2:]
                        full_text = ' '.join(str(c or '').strip()
                                             for c in content_cells if c).strip()
                        group, description, status, external_task = "Finding", full_text, STATUS_OPEN, None
                        validated_rows.append(
                            [phase, seq, group, description, status, external_task, None])

                elif is_task_shifted and not is_critical_issue:
                    group_val = str(row[1] or '').strip() if len(
                        row) > 1 else ''
                    if group_val in VALID_GROUPS:
                        validated_rows.append([None] + list(row))
                    else:
                        seq = seq_val_s
                        content_cells = row[1:]
                        full_text = ' '.join(str(c or '').strip()
                                             for c in content_cells if c).strip()
                        group, description, status, external_task = "Finding", full_text, STATUS_OPEN, None
                        validated_rows.append(
                            [None, seq, group, description, status, external_task, None])

                elif validated_rows:
                    continuation_text = ' '.join(str(c or '').replace(
                        '\n', ' ').strip() for c in row if c is not None and str(c).strip())
                    if continuation_text:
                        validated_rows[-1][3] = (str(validated_rows[-1]
                                                 [3] or '') + ' ' + continuation_text).strip()
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

    def prioritize_group(series):
        if 'Customer Report' in series.values:
            return 'Customer Report'
        if 'SB/ADs' in series.values:
            return 'SB/ADs'
        if 'Planned' in series.values:
            return 'Planned'
        return series.iloc[0]

    def prioritize_description(series):
        descriptions = pd.Series(series).str.strip().dropna().unique()
        descriptions = [d for d in descriptions if d]
        if not descriptions:
            return ""
        clean_descriptions = [
            d for d in descriptions if 'PHASE SEQ GROUP' not in d]
        if clean_descriptions:
            return min(clean_descriptions, key=len)
        return max(descriptions, key=len)

    agg_dict = {'PHASE': 'first', 'GROUP': prioritize_group, 'DESCRIPTION': prioritize_description,
                'STATUS': 'first', 'EXTERNAL TASK': 'first', 'ORIG': 'first'}

    df_final = df_final.groupby('SEQ', as_index=False).agg(agg_dict)
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
    # CORREÇÃO: Obter a porta da variável de ambiente PORT, com 5000 como padrão
    port = int(os.environ.get('PORT', 5000))
    # Usar host='0.0.0.0' para ser acessível externamente
    app.run(host='0.0.0.0', port=port, debug=True)
