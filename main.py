import os
import io
import json
import webbrowser
import traceback
from flask import Flask, request, jsonify, render_template, send_file
import pandas as pd

# Garante que caminhos relativos dos motores resolvem corretamente
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

from src.leitor_excel import consolidar_tabela_locacao
from src.motor_postes import calcular_quantitativo_postes
from src.motor_estais import calcular_quantitativo_estais
from src.motor_alcas_lacos import calcular_alcas_lacos, gerar_tabela_validacao
from src.motor_ferragens import calcular_ferragens, gerar_tabela_validacao_ferragens
from src.exportador import exportar_para_excel, exportar_multiplas_abas

app = Flask(__name__)


@app.errorhandler(Exception)
def handle_exception(e):
    print(traceback.format_exc())
    return jsonify({'log': [f'✗ ERRO inesperado: {str(e)}'], 'erro': str(e)}), 500

CABOS_PADRAO = [
    "CA MAGNOLIA 954 MCM",
    "CA OXLIP 4/0 AWG",
    "XLPE 90°C AL 20/35 kV 95 mm²",
    "CA ORCHID 636 MCM"
]

# Adicione novos motores aqui conforme forem sendo criados
MOTORES_DISPONIVEIS = [
    {"id": "postes",      "label": "Postes",        "descricao": "Postes de concreto duplo T"},
    {"id": "estais",      "label": "Estais",        "descricao": "Estaiamento e ferragens de ancoragem"},
    {"id": "alcas_lacos", "label": "Alças e Laços", "descricao": "Alças e laços preformados por nível"},
    {"id": "ferragens",   "label": "Ferragens",     "descricao": "Ferragens gerais por tipo de estrutura"},
]


@app.route('/')
def index():
    return render_template('index.html',
                           motores=MOTORES_DISPONIVEIS,
                           cabos_padrao=CABOS_PADRAO)


@app.route('/processar', methods=['POST'])
def processar():
    log = []
    arquivos_gerados = []
    resultados = {}

    if 'arquivo' not in request.files or not request.files['arquivo'].filename:
        return jsonify({'erro': 'Nenhum arquivo selecionado.'}), 400

    arquivo = request.files['arquivo']

    try:
        motores = set(request.form.getlist('motores'))
        cabos = json.loads(request.form.get('cabos', '[]'))
        gerar_validacao = request.form.get('gerar_validacao', 'false') == 'true'
        log.append(f"Lendo arquivo: {arquivo.filename}...")
        conteudo = io.BytesIO(arquivo.read())
        df_base = consolidar_tabela_locacao(conteudo)
        log.append(f"✓ {len(df_base)} estruturas lidas.")

        abas = {}  # {nome_aba: df} ou {nome_aba: (df_esq, df_dir)} — ordem de inserção = ordem das abas

        if 'postes' in motores:
            log.append("Calculando Postes...")
            df = calcular_quantitativo_postes(df_base)
            if not df.empty:
                abas['Postes'] = df
                resultados['postes'] = df
            log.append(f"✓ {len(df)} tipos de poste encontrados.")

        if 'estais' in motores:
            log.append("Calculando Estais...")
            df = calcular_quantitativo_estais(df_base)
            if not df.empty:
                abas['Estais'] = df
            log.append("✓ Estais calculados.")

        if 'alcas_lacos' in motores:
            log.append("Calculando Alças e Laços...")
            df, avisos = calcular_alcas_lacos(df_base)
            if not df.empty:
                abas['Alças e Laços'] = df
            for aviso in avisos:
                log.append(f"⚠ {aviso}")
            log.append(f"✓ {len(df)} itens de alças/laços calculados.")
            if gerar_validacao:
                df_val = gerar_tabela_validacao(df_base)
                exportar_para_excel(df_val, "Validacao_Alcas_Lacos.xlsx")
                arquivos_gerados.append("Validacao_Alcas_Lacos.xlsx")
                log.append("✓ Tabela de validação de alças/laços gerada.")

        if 'ferragens' in motores:
            log.append("Calculando Ferragens...")
            df, avisos = calcular_ferragens(df_base)
            df_val = gerar_tabela_validacao_ferragens(df_base)
            if not df.empty:
                abas['Ferragens'] = (df, df_val, 1)
            for aviso in avisos:
                log.append(f"⚠ {aviso}")
            log.append(f"✓ {len(df)} itens de ferragens calculados.")

        if cabos:
            log.append(f"Adicionando {len(cabos)} cabo(s) manual(is)...")
            df_cabos = pd.DataFrame(cabos)
            if not df_cabos.empty:
                abas['Cabos'] = df_cabos

        log.append("Exportando arquivos...")
        if abas:
            exportar_multiplas_abas(abas, "RMT_Output_Completo.xlsx")
            arquivos_gerados.append("RMT_Output_Completo.xlsx")

        if 'postes' in resultados and not resultados['postes'].empty:
            exportar_para_excel(resultados['postes'], "Quantitativo_Postes_Isolado.xlsx")
            arquivos_gerados.append("Quantitativo_Postes_Isolado.xlsx")

        log.append("✓ Concluído com sucesso!")
        return jsonify({'log': log, 'arquivos': arquivos_gerados})

    except Exception as e:
        log.append(f"✗ ERRO: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'log': log, 'erro': str(e)}), 500


@app.route('/preview', methods=['POST'])
def preview():
    if 'arquivo' not in request.files or not request.files['arquivo'].filename:
        return jsonify({'erro': 'Nenhum arquivo.'}), 400

    arquivo = request.files['arquivo']

    try:
        conteudo = io.BytesIO(arquivo.read())
        df = consolidar_tabela_locacao(conteudo)
        df.columns = df.columns.astype(str).str.strip()

        # Detecta colunas de nível
        colunas_nivel = {}
        for col in df.columns:
            col_up = col.strip().upper()
            if col_up in ('NÍVEL 1', 'NIVEL 1'):
                colunas_nivel[1] = col
            elif col_up in ('NÍVEL 2', 'NIVEL 2'):
                colunas_nivel[2] = col
            elif col_up in ('NÍVEL 3', 'NIVEL 3'):
                colunas_nivel[3] = col

        preview_cols = {}

        # Coluna NÚMERO
        for c in df.columns:
            if c.strip().upper() in ('NÚMERO', 'NUMERO', 'N°', 'Nº', 'NUM'):
                preview_cols['NÚMERO'] = df[c].astype(str).str.strip()
                break

        # TIPO
        if 'TIPO' in df.columns:
            preview_cols['TIPO'] = df['TIPO'].astype(str).str.strip()

        # Níveis: Vante (linha atual) e Ré (linha anterior dentro do mesmo circuito)
        usar_grupos = '_letra_circuito' in df.columns
        for nivel, col in sorted(colunas_nivel.items()):
            serie = df[col].astype(str).str.strip().replace('nan', '')
            preview_cols[f'N{nivel} Vante'] = serie
            if usar_grupos:
                cabo_re = df.groupby('_letra_circuito')[col].transform(
                    lambda s: s.astype(str).str.strip().shift(1)
                ).fillna('')
            else:
                cabo_re = serie.shift(1).fillna('')
            preview_cols[f'N{nivel} Ré'] = cabo_re

        df_prev = pd.DataFrame(preview_cols).replace('nan', '')

        return jsonify({
            'colunas': list(df_prev.columns),
            'dados':   df_prev.to_dict(orient='records')
        })

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'erro': str(e)}), 500


@app.route('/download/<nome_arquivo>')
def download(nome_arquivo):
    caminho = os.path.join(BASE_DIR, 'data', 'output', nome_arquivo)
    return send_file(caminho, as_attachment=True)


if __name__ == '__main__':
    webbrowser.open('http://127.0.0.1:5000')
    app.run(debug=False, port=5000, threaded=True)
