import os
import io
import json
import webbrowser
import traceback
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.exceptions import HTTPException
import pandas as pd

# Garante que caminhos relativos dos motores resolvem corretamente
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

from src import banco
from src.banco import (listar_tipos_ferragens, obter_materiais,
                        obter_todos_materiais, substituir_materiais,
                        substituir_campo_global, listar_estruturas_parafusos,
                        obter_grade_parafusos, salvar_grade_parafusos,
                        excluir_estrutura_parafusos)
from src.leitor_excel import consolidar_tabela_locacao
from src.motor_postes import calcular_quantitativo_postes
from src.motor_estais import calcular_quantitativo_estais
from src.motor_alcas_lacos import calcular_alcas_lacos, gerar_tabela_validacao
from src.motor_ferragens import calcular_ferragens, gerar_tabela_validacao_ferragens
from src.motor_parafusos import calcular_parafusos, identificar_estruturas_ambiguas
from src.exportador import exportar_para_excel, exportar_multiplas_abas

app = Flask(__name__)

# Cria o schema e popula o banco a partir do xlsx na primeira execução
banco.inicializar()


@app.errorhandler(Exception)
def handle_exception(e):
    # Erros HTTP legítimos (404, 400, ...) passam adiante com o status correto
    if isinstance(e, HTTPException):
        return e
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
    {"id": "parafusos",   "label": "Parafusos",     "descricao": "Cabeça quadrada e rosca dupla por comprimento"},
]


@app.route('/')
def index():
    return render_template('home.html')


@app.route('/gerar')
def gerar():
    return render_template('gerar.html',
                           motores=MOTORES_DISPONIVEIS,
                           cabos_padrao=CABOS_PADRAO)


@app.route('/materiais')
def materiais():
    tipos = banco.listar_tipos_ferragens()
    total_materiais = sum(len(banco.obter_materiais(t)) for t in tipos)
    return render_template('materiais.html',
                           total_tipos=len(tipos),
                           total_materiais=total_materiais)


@app.route('/parafusos')
def parafusos():
    return render_template('parafusos.html')


# ── API: Materiais por Poste ───────────────────────────────────────────────

@app.route('/materiais/api/tipos')
def api_mat_tipos():
    return jsonify(listar_tipos_ferragens())


@app.route('/materiais/api/materiais')
def api_mat_por_tipo():
    tipo = request.args.get('tipo', '').strip()
    if not tipo:
        return jsonify({'erro': 'Parâmetro "tipo" é obrigatório.'}), 400
    return jsonify(obter_materiais(tipo))


@app.route('/materiais/api/todos')
def api_mat_todos():
    return jsonify(obter_todos_materiais())


@app.route('/materiais/api/salvar', methods=['POST'])
def api_mat_salvar():
    data = request.get_json(force=True)
    tipo = (data.get('tipo') or '').strip()
    materiais = data.get('materiais', [])
    if not tipo:
        return jsonify({'erro': 'Campo "tipo" é obrigatório.'}), 400
    substituir_materiais(tipo, materiais)
    return jsonify({'ok': True, 'count': len(materiais)})


@app.route('/materiais/api/substituir', methods=['POST'])
def api_mat_substituir():
    data = request.get_json(force=True)
    campo = (data.get('campo') or '').strip()
    de    = (data.get('de')    or '')
    para  = (data.get('para')  or '')
    if not campo or de == '':
        return jsonify({'erro': 'Campos "campo" e "de" são obrigatórios.'}), 400
    try:
        count = substituir_campo_global(campo, de, para)
    except ValueError as e:
        return jsonify({'erro': str(e)}), 400
    return jsonify({'ok': True, 'count': count})


# ── API: Cadastrar Parafusos ───────────────────────────────────────────────

def _parse_altura(valor):
    """Converte string do query/body em float ou None ('', '-', ausente -> None)."""
    if valor in (None, '', '-'):
        return None
    return float(valor)


@app.route('/parafusos/api/estruturas')
def api_paraf_estruturas():
    return jsonify(listar_estruturas_parafusos())


@app.route('/parafusos/api/grade')
def api_paraf_grade():
    tipo = request.args.get('tipo', '').strip()
    if not tipo:
        return jsonify({'erro': 'Parâmetro "tipo" é obrigatório.'}), 400
    try:
        esforco = float(request.args.get('esforco', ''))
        altura = _parse_altura(request.args.get('altura'))
    except (TypeError, ValueError):
        return jsonify({'erro': 'Parâmetros "esforco"/"altura" inválidos.'}), 400
    return jsonify(obter_grade_parafusos(tipo, esforco, altura))


@app.route('/parafusos/api/salvar', methods=['POST'])
def api_paraf_salvar():
    data = request.get_json(force=True)
    tipo = (data.get('tipo') or '').strip().upper()
    if not tipo:
        return jsonify({'erro': 'Campo "tipo" é obrigatório.'}), 400
    try:
        esforco = float(data.get('esforco'))
        altura = _parse_altura(data.get('altura'))
    except (TypeError, ValueError):
        return jsonify({'erro': 'Campos "esforco"/"altura" inválidos.'}), 400

    cruzeta = data.get('cruzeta_adicional')
    cruzeta = float(cruzeta) if cruzeta not in (None, '') else None

    linhas_in = data.get('linhas', [])
    linhas = []
    for l in linhas_in:
        posicao = str(l.get('posicao', '')).strip().upper()
        parafuso = str(l.get('parafuso', '')).strip().upper()
        if not posicao or not parafuso:
            continue
        try:
            esf_parafuso = float(l['esf_parafuso'])
            comprimento = int(float(l['comprimento']))
            quantidade = float(l['quantidade'])
        except (TypeError, ValueError, KeyError):
            continue
        if quantidade <= 0:
            continue
        linhas.append({
            'posicao': posicao, 'parafuso': parafuso, 'esf_parafuso': esf_parafuso,
            'comprimento': comprimento, 'quantidade': quantidade,
        })

    count = salvar_grade_parafusos(tipo, esforco, altura, cruzeta, linhas)
    return jsonify({'ok': True, 'count': count})


@app.route('/parafusos/api/excluir', methods=['POST'])
def api_paraf_excluir():
    data = request.get_json(force=True)
    tipo = (data.get('tipo') or '').strip()
    if not tipo:
        return jsonify({'erro': 'Campo "tipo" é obrigatório.'}), 400
    try:
        esforco = float(data.get('esforco'))
        altura = _parse_altura(data.get('altura'))
    except (TypeError, ValueError):
        return jsonify({'erro': 'Campos "esforco"/"altura" inválidos.'}), 400
    count = excluir_estrutura_parafusos(tipo, esforco, altura)
    return jsonify({'ok': True, 'count': count})


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
        resolucoes = json.loads(request.form.get('resolucoes', '{}'))
        log.append(f"Lendo arquivo: {arquivo.filename}...")
        conteudo = io.BytesIO(arquivo.read())
        df_base = consolidar_tabela_locacao(conteudo)
        log.append(f"✓ {len(df_base)} estruturas lidas.")

        if 'parafusos' in motores:
            ambiguos = identificar_estruturas_ambiguas(df_base)
            pendentes = [a for a in ambiguos if resolucoes.get(a['numero']) not in ('C', 'I')]
            if pendentes:
                vistos, unicos = set(), []
                for a in pendentes:
                    chave = (a['numero'], a['tipo'])
                    if chave not in vistos:
                        vistos.add(chave)
                        unicos.append(a)
                return jsonify({'ambiguidade': unicos})

        abas = {}  # {nome_aba: df} ou {nome_aba: (df_esq, df_dir)} — ordem de inserção = ordem das abas

        if 'postes' in motores:
            log.append("Calculando Postes...")
            df, avisos = calcular_quantitativo_postes(df_base)
            if not df.empty:
                abas['Postes'] = df
                resultados['postes'] = df
            for aviso in avisos:
                log.append(f"⚠ {aviso}")
            log.append(f"✓ {len(df)} tipos de poste encontrados.")

        if 'estais' in motores:
            log.append("Calculando Estais...")
            df, avisos = calcular_quantitativo_estais(df_base)
            if not df.empty:
                abas['Estais'] = df
            for aviso in avisos:
                log.append(f"⚠ {aviso}")
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

        if 'parafusos' in motores:
            log.append("Calculando Parafusos...")
            df, incremento_item36, avisos, detalhe_cruzeta = calcular_parafusos(df_base, resolucoes)
            if not df.empty:
                abas['Parafusos'] = df
            for aviso in avisos:
                log.append(f"⚠ {aviso}")
            log.append(f"✓ {len(df)} itens de parafusos calculados.")

            if incremento_item36 > 0:
                info36 = next((m for m in obter_todos_materiais() if str(m['codigo']).strip() == '36'), None)
                descricao36 = info36['descricao'] if info36 else 'Viga tipo U (Cruzeta metálica)'
                unidade36   = info36['unidade'] if info36 else 'un.'

                if 'Ferragens' in abas:
                    df_ferr, df_val_ferr, freeze = abas['Ferragens']
                    mask = df_ferr['Código'].astype(str).str.strip() == '36'
                    if mask.any():
                        df_ferr.loc[mask, 'Quantidade'] += incremento_item36
                    else:
                        df_ferr.loc[len(df_ferr)] = {
                            'Código': '36', 'Material': descricao36,
                            'Unidade': unidade36, 'Quantidade': incremento_item36,
                        }
                    abas['Ferragens'] = (df_ferr, df_val_ferr, freeze)
                else:
                    abas['Ferragens'] = pd.DataFrame([{
                        'Código': '36', 'Material': descricao36,
                        'Unidade': unidade36, 'Quantidade': incremento_item36,
                    }])
                log.append(f"✓ +{incremento_item36:g} un. de '{descricao36}' (cruzeta adicional) somadas ao item 36.")
                for det in detalhe_cruzeta:
                    log.append(f"⚠ Cruzeta adicional: poste {det['numero']} "
                               f"(estrutura '{det['tipo']}') → +{det['quantidade']:g} un. do item 36.")

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
        if isinstance(e, PermissionError):
            log.append("⚠ A planilha de saída provavelmente está aberta no Excel — feche-a e execute novamente.")
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
    # send_from_directory valida o nome e impede path traversal (../ e ..\)
    return send_from_directory(os.path.join(BASE_DIR, 'data', 'output'),
                               nome_arquivo, as_attachment=True)


if __name__ == '__main__':
    webbrowser.open('http://127.0.0.1:5000')
    app.run(debug=False, port=5000, threaded=True)
