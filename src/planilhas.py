"""Exportação e importação das receitas em .xlsx.

O formato de cada arquivo é o mesmo dos seeds de config/, para que o ciclo
baixar → editar no Excel → subir funcione sem tradução mental.

Semântica da importação, definida com o usuário: o que está no arquivo apaga e
regrava a unidade correspondente; o que não está no arquivo fica intacto. A
unidade varia por receita:

    Ferragens     → o TIPO (uma aba por TIPO)
    Alças/Laços   → o TIPO
    Parafusos     → o combo TIPO + ESFORÇO + ALTURA
    Estais        → a lista inteira (não tem TIPO)

Consequência assumida: não se exclui uma estrutura subindo arquivo. Uma unidade
que chegue sem nenhuma linha aproveitável é ignorada com aviso, nunca apagada —
senão uma aba em branco esvaziaria a receita sem o usuário perceber.

O arquivo é validado por inteiro antes de qualquer gravação: ou entra tudo, ou
não entra nada.
"""

import io

import pandas as pd

from src import banco

# Comprimentos comerciais de parafuso (mm), 200 a 900 de 50 em 50
COMPRIMENTOS_PARAFUSOS = list(range(200, 901, 50))

COLS_FERRAGENS = ['ITEM', 'DESCRIÇÃO', 'UND', 'QUANT.']
COLS_ALCAS = ['TIPO', 'NIVEL', 'DIRECAO', 'QTD_ALCAS', 'QTD_LACOS']
COLS_ESTAIS = ['MATERIAL', 'UNIDADE', 'QTD_POR_ESTAI']
COLS_PARAFUSOS_META = ['TIPO', 'ESFORCO', 'ALTURA', 'POSIÇÃO', 'PARAFUSO',
                       'ESF_PARAFUSO', 'COMECO', 'CRUZETA ADICIONAL']

DIRECOES_VALIDAS = ('VANTE', 'RE')


class ErroPlanilha(ValueError):
    """Arquivo inválido a ponto de nada poder ser importado."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _texto(valor):
    """Converte célula em texto limpo ('' para vazio/NaN)."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ''
    if pd.isna(valor):
        return ''
    return str(valor).strip()


def _numero(valor):
    """Converte célula em float, ou None se não for número."""
    if valor is None or _texto(valor) == '':
        return None
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(n) else n


def _abrir(arquivo):
    """Aceita caminho, bytes ou file-like (upload do Flask)."""
    try:
        if hasattr(arquivo, 'read'):
            return pd.ExcelFile(io.BytesIO(arquivo.read()))
        return pd.ExcelFile(arquivo)
    except Exception as e:
        raise ErroPlanilha(f"Não foi possível ler o arquivo como Excel: {e}")


def _exigir_colunas(df, obrigatorias, contexto):
    faltando = [c for c in obrigatorias if c not in df.columns]
    if faltando:
        raise ErroPlanilha(
            f"{contexto}: faltam as colunas {', '.join(faltando)}. "
            f"Encontradas: {', '.join(str(c) for c in df.columns) or '(nenhuma)'}"
        )


def _para_bytes(escrever):
    """Roda `escrever(writer)` e devolve o .xlsx em memória."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        escrever(writer)
    buffer.seek(0)
    return buffer


def _nome_aba(tipo, usados):
    """Nome de aba válido no Excel: '/' vira ' I ' e o limite é 31 caracteres."""
    base = tipo.replace('/', ' I ')[:31]
    nome, n = base, 2
    while nome in usados:            # defensivo: os TIPOs reais são bem curtos
        sufixo = f"~{n}"
        nome = base[:31 - len(sufixo)] + sufixo
        n += 1
    usados.add(nome)
    return nome


def _tipo_da_aba(nome_aba):
    """Inverso de _nome_aba: recompõe o TIPO a partir do nome da aba."""
    return nome_aba.replace(' I ', '/').replace(' | ', '/').strip()


# ---------------------------------------------------------------------------
# Exportação
# ---------------------------------------------------------------------------
def exportar_ferragens(parque_id=None):
    receita = banco.ler_receita_ferragens(parque_id)
    if not receita:
        raise ErroPlanilha("A receita de ferragens deste parque está vazia — "
                           "não há o que baixar.")

    def escrever(writer):
        usados = set()
        for tipo, materiais in receita.items():
            df = pd.DataFrame(
                [{'ITEM': m['codigo'], 'DESCRIÇÃO': m['descricao'],
                  'UND': m['unidade'], 'QUANT.': m['qtd']} for m in materiais],
                columns=COLS_FERRAGENS)
            df.to_excel(writer, sheet_name=_nome_aba(tipo, usados), index=False)

    return _para_bytes(escrever)


def exportar_parafusos(parque_id=None):
    df = banco.ler_receita_parafusos_df(parque_id)
    if df.empty:
        raise ErroPlanilha("A receita de parafusos deste parque está vazia — "
                           "não há o que baixar.")

    linhas = {}
    for _, r in df.iterrows():
        tipo = str(r['tipo'])
        # Desfaz o sufixo .C/.I, devolvendo a coluna COMECO do formato original
        if tipo.endswith(banco.SUFIXOS_PARAFUSOS_AMBIGUOS):
            tipo_base, comeco = tipo[:-2], tipo[-1]
        else:
            tipo_base, comeco = tipo, ''

        # NaN nunca é igual a si mesmo: sem normalizar para None, cada linha de
        # receita sem altura viraria uma chave nova e a tabela sairia duplicada
        altura = None if pd.isna(r['altura']) else float(r['altura'])
        cruzeta = (None if pd.isna(r['cruzeta_adicional'])
                   else float(r['cruzeta_adicional']))

        chave = (tipo_base, r['esforco'], altura, r['posicao'],
                 r['parafuso'], r['esf_parafuso'], comeco)
        if chave not in linhas:
            linhas[chave] = {
                'TIPO': tipo_base,
                'ESFORCO': r['esforco'],
                'ALTURA': altura,
                'POSIÇÃO': r['posicao'],
                'PARAFUSO': r['parafuso'],
                'ESF_PARAFUSO': r['esf_parafuso'],
                'COMECO': comeco,
                'CRUZETA ADICIONAL': cruzeta,
            }
        linhas[chave][int(r['comprimento'])] = r['quantidade']

    comprimentos_presentes = set()
    for c in df['comprimento'].dropna():
        try:
            comprimentos_presentes.add(int(float(c)))
        except (ValueError, TypeError):
            pass
    max_c = max(max(comprimentos_presentes, default=900), 900)
    comprs_colunas = list(range(200, max_c + 1, 50))
    for c in sorted(comprimentos_presentes):
        if c not in comprs_colunas:
            comprs_colunas.append(c)
    comprs_colunas.sort()

    tabela = pd.DataFrame(list(linhas.values()),
                          columns=COLS_PARAFUSOS_META + comprs_colunas)
    tabela = tabela.sort_values(['TIPO', 'ESFORCO', 'ALTURA', 'POSIÇÃO'],
                                na_position='first').reset_index(drop=True)

    return _para_bytes(
        lambda w: tabela.to_excel(w, sheet_name='PARAFUSOS', index=False))


def exportar_alcas(parque_id=None):
    dados = banco.obter_todas_alcas_lacos(parque_id)
    if not dados:
        raise ErroPlanilha("A receita de alças/laços deste parque está vazia — "
                           "não há o que baixar.")

    df = pd.DataFrame([{'TIPO': d['tipo'], 'NIVEL': d['nivel'],
                        'DIRECAO': d['direcao'], 'QTD_ALCAS': d['qtd_alcas'],
                        'QTD_LACOS': d['qtd_lacos']} for d in dados],
                      columns=COLS_ALCAS)
    return _para_bytes(
        lambda w: df.to_excel(w, sheet_name='ALCAS E LACOS', index=False))


def exportar_estais(parque_id=None):
    dados = banco.ler_receita_estais(parque_id)
    if not dados:
        raise ErroPlanilha("A receita de estais deste parque está vazia — "
                           "não há o que baixar.")

    df = pd.DataFrame([{'MATERIAL': d['material'], 'UNIDADE': d['unidade'],
                        'QTD_POR_ESTAI': d['qtd_por_estai']} for d in dados],
                      columns=COLS_ESTAIS)
    return _para_bytes(
        lambda w: df.to_excel(w, sheet_name='ESTAIS', index=False))


# ---------------------------------------------------------------------------
# Importação
# ---------------------------------------------------------------------------
def importar_ferragens(arquivo, parque_id=None):
    """Uma aba por TIPO, colunas ITEM / DESCRIÇÃO / UND / QUANT."""
    xl = _abrir(arquivo)
    avisos = []
    por_tipo = {}

    for aba in xl.sheet_names:
        if aba.strip().upper() == 'CONTAGEM':
            continue
        tipo = _tipo_da_aba(aba)
        if not tipo:
            continue

        df = xl.parse(aba, header=0)
        df.columns = [_texto(c) for c in df.columns]
        _exigir_colunas(df, COLS_FERRAGENS, f"Aba '{aba}'")

        materiais, descartadas = [], 0
        for _, r in df.iterrows():
            codigo = _texto(r['ITEM'])
            descricao = _texto(r['DESCRIÇÃO'])
            qtd = _numero(r['QUANT.'])

            if not codigo and not descricao:
                continue                       # linha em branco / separador
            if codigo.upper() == 'ITEM':
                continue                       # cabeçalho repetido no meio da aba
            if not descricao or qtd is None or qtd <= 0:
                descartadas += 1               # quantidade ausente ou "Var."
                continue

            materiais.append({'codigo': codigo, 'descricao': descricao,
                              'unidade': _texto(r['UND']), 'qtd': qtd})

        if descartadas:
            avisos.append(f"'{tipo}': {descartadas} linha(s) sem quantidade válida "
                          f"foram ignoradas.")
        if not materiais:
            avisos.append(f"'{tipo}': nenhuma linha aproveitável — o tipo foi mantido "
                          f"como está, nada foi apagado.")
            continue
        por_tipo[tipo] = materiais

    if not por_tipo:
        raise ErroPlanilha("Nenhuma aba do arquivo tinha materiais válidos. "
                           "Nada foi importado.")

    banco.importar_ferragens(por_tipo, parque_id)
    return {
        'unidades': sorted(por_tipo),
        'linhas': sum(len(v) for v in por_tipo.values()),
        'avisos': avisos,
        'rotulo_unidade': 'tipo',
    }


def importar_parafusos(arquivo, parque_id=None):
    """Tabela plana: metadados + uma coluna por comprimento comercial."""
    xl = _abrir(arquivo)
    avisos = []
    por_combo = {}
    obrigatorias = ['TIPO', 'ESFORCO', 'POSIÇÃO', 'PARAFUSO', 'ESF_PARAFUSO']

    for aba in xl.sheet_names:
        df = xl.parse(aba, header=0)
        df.columns = [_texto(c) for c in df.columns]
        df = df.dropna(how='all')
        if df.empty:
            continue
        _exigir_colunas(df, obrigatorias, f"Aba '{aba}'")

        cols_comprimento = []
        for c in df.columns:
            if c in COLS_PARAFUSOS_META:
                continue
            n = _numero(c)
            if n is not None:
                cols_comprimento.append((c, int(n)))
        if not cols_comprimento:
            raise ErroPlanilha(
                f"Aba '{aba}': nenhuma coluna de comprimento encontrada. "
                f"Esperado colunas numéricas de {COMPRIMENTOS_PARAFUSOS[0]} a "
                f"{COMPRIMENTOS_PARAFUSOS[-1]}.")

        for idx, r in df.iterrows():
            linha_num = idx + 2                # +1 do cabeçalho, +1 base 1 do Excel
            tipo_base = _texto(r['TIPO'])
            if not tipo_base:
                continue

            esforco = _numero(r['ESFORCO'])
            esf_parafuso = _numero(r['ESF_PARAFUSO'])
            if esforco is None or esf_parafuso is None:
                avisos.append(f"Aba '{aba}', linha {linha_num}: ESFORCO ou ESF_PARAFUSO "
                              f"não é número — linha ignorada.")
                continue

            comeco = _texto(r['COMECO']).upper() if 'COMECO' in df.columns else ''
            if comeco and comeco not in ('C', 'I'):
                raise ErroPlanilha(f"Aba '{aba}', linha {linha_num}: COMECO deve ser "
                                   f"'C' ou 'I', veio '{comeco}'.")
            tipo = f"{tipo_base}.{comeco}" if comeco else tipo_base

            altura = _numero(r['ALTURA']) if 'ALTURA' in df.columns else None
            cruzeta = (_numero(r['CRUZETA ADICIONAL'])
                       if 'CRUZETA ADICIONAL' in df.columns else None)
            posicao = _texto(r['POSIÇÃO']).upper()
            parafuso = _texto(r['PARAFUSO']).upper()
            if not posicao or not parafuso:
                avisos.append(f"Aba '{aba}', linha {linha_num}: POSIÇÃO ou PARAFUSO "
                              f"em branco — linha ignorada.")
                continue

            combo = (tipo, esforco, altura)
            achou = False
            for col, comprimento in cols_comprimento:
                qtd = _numero(r[col])
                if qtd is None or qtd <= 0:
                    continue
                por_combo.setdefault(combo, []).append({
                    'posicao': posicao, 'parafuso': parafuso,
                    'esf_parafuso': esf_parafuso, 'comprimento': comprimento,
                    'quantidade': qtd, 'cruzeta_adicional': cruzeta,
                })
                achou = True
            if not achou:
                avisos.append(f"Aba '{aba}', linha {linha_num} ({tipo}): nenhuma "
                              f"quantidade preenchida — linha ignorada.")

    if not por_combo:
        raise ErroPlanilha("Nenhuma linha do arquivo tinha quantidade de parafuso. "
                           "Nada foi importado.")

    banco.importar_parafusos(por_combo, parque_id)

    def rotulo(combo):
        tipo, esforco, altura = combo
        alt = '' if altura is None else f" · {altura:g}m"
        return f"{tipo} · {esforco:g}{alt}"

    return {
        'unidades': sorted(rotulo(k) for k in por_combo),
        'linhas': sum(len(v) for v in por_combo.values()),
        'avisos': avisos,
        'rotulo_unidade': 'estrutura (tipo + esforço + altura)',
    }


def importar_alcas(arquivo, parque_id=None):
    """Tabela plana: TIPO / NIVEL / DIRECAO / QTD_ALCAS / QTD_LACOS.

    Zero é quantidade válida aqui: significa que a estrutura existe na receita e
    não precisa de alça ou laço naquele nível/direção.
    """
    xl = _abrir(arquivo)
    avisos = []
    por_tipo = {}

    for aba in xl.sheet_names:
        df = xl.parse(aba, header=0)
        df.columns = [_texto(c) for c in df.columns]
        df = df.dropna(how='all')
        if df.empty:
            continue
        _exigir_colunas(df, COLS_ALCAS, f"Aba '{aba}'")

        for idx, r in df.iterrows():
            linha_num = idx + 2
            tipo = _texto(r['TIPO'])
            if not tipo:
                continue

            nivel = _numero(r['NIVEL'])
            direcao = _texto(r['DIRECAO']).upper()
            qtd_alcas = _numero(r['QTD_ALCAS'])
            qtd_lacos = _numero(r['QTD_LACOS'])

            if nivel is None or nivel <= 0:
                avisos.append(f"Linha {linha_num} ({tipo}): NIVEL inválido — ignorada.")
                continue
            if direcao not in DIRECOES_VALIDAS:
                avisos.append(f"Linha {linha_num} ({tipo}): DIRECAO deve ser VANTE ou RE, "
                              f"veio '{direcao}' — ignorada.")
                continue
            if qtd_alcas is None or qtd_lacos is None or qtd_alcas < 0 or qtd_lacos < 0:
                avisos.append(f"Linha {linha_num} ({tipo}): quantidade inválida — ignorada.")
                continue

            por_tipo.setdefault(tipo, []).append({
                'nivel': int(nivel), 'direcao': direcao,
                'qtd_alcas': qtd_alcas, 'qtd_lacos': qtd_lacos,
            })

    if not por_tipo:
        raise ErroPlanilha("Nenhuma linha válida encontrada. Nada foi importado.")

    banco.importar_alcas(por_tipo, parque_id)
    return {
        'unidades': sorted(por_tipo),
        'linhas': sum(len(v) for v in por_tipo.values()),
        'avisos': avisos,
        'rotulo_unidade': 'tipo',
    }


def importar_estais(arquivo, parque_id=None):
    """Tabela plana: MATERIAL / UNIDADE / QTD_POR_ESTAI. Substitui a lista inteira."""
    xl = _abrir(arquivo)
    avisos = []
    linhas = []

    for aba in xl.sheet_names:
        df = xl.parse(aba, header=0)
        df.columns = [_texto(c) for c in df.columns]
        df = df.dropna(how='all')
        if df.empty:
            continue
        _exigir_colunas(df, COLS_ESTAIS, f"Aba '{aba}'")

        for idx, r in df.iterrows():
            linha_num = idx + 2
            material = _texto(r['MATERIAL'])
            if not material:
                continue
            qtd = _numero(r['QTD_POR_ESTAI'])
            if qtd is None or qtd < 0:
                avisos.append(f"Linha {linha_num} ('{material[:40]}'): "
                              f"QTD_POR_ESTAI inválida — ignorada.")
                continue
            linhas.append({'material': material, 'unidade': _texto(r['UNIDADE']),
                           'qtd_por_estai': qtd})

    if not linhas:
        raise ErroPlanilha("Nenhum material válido encontrado. A receita de estais "
                           "atual foi mantida.")

    banco.substituir_estais(linhas, parque_id)
    return {
        'unidades': [f"{len(linhas)} materiais"],
        'linhas': len(linhas),
        'avisos': avisos,
        'rotulo_unidade': 'lista completa',
    }


# ---------------------------------------------------------------------------
# Registro — usado pelas rotas genéricas de download/upload
# ---------------------------------------------------------------------------
RECEITAS = {
    'ferragens': {
        'rotulo': 'Ferragens',
        'exportar': exportar_ferragens,
        'importar': importar_ferragens,
    },
    'parafusos': {
        'rotulo': 'Parafusos',
        'exportar': exportar_parafusos,
        'importar': importar_parafusos,
    },
    'alcas': {
        'rotulo': 'Alças e Laços',
        'exportar': exportar_alcas,
        'importar': importar_alcas,
    },
    'estais': {
        'rotulo': 'Estais',
        'exportar': exportar_estais,
        'importar': importar_estais,
    },
}
