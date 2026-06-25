import pandas as pd
import os


CAMINHO_RECEITA = os.path.join('data', 'config', 'QUANTIDADE-MATERIAIS.xlsx')


def _normalizar_tipo(nome_aba):
    """Converte separadores do Excel (' I ' e ' | ') para '/' usado na Tabela de Locação."""
    return nome_aba.replace(' I ', '/').replace(' | ', '/').strip()


def _is_valid_qty(val):
    """Retorna True apenas se val for um número finito maior que zero."""
    try:
        n = float(val)
        return n > 0 and pd.notna(n)
    except (TypeError, ValueError):
        return False


def _ler_receita():
    """Lê o Excel e retorna dict {tipo_normalizado: [(descricao, unidade, qtd), ...]}"""
    if not os.path.exists(CAMINHO_RECEITA):
        raise FileNotFoundError(
            f"Arquivo de receita não encontrado: {CAMINHO_RECEITA}\n"
            "Copie 'QUANTIDADE-MATERIAIS.xlsx' para a pasta data/config/"
        )

    xl = pd.ExcelFile(CAMINHO_RECEITA)
    receita = {}

    for aba in xl.sheet_names:
        if aba.strip().upper() == 'CONTAGEM':
            continue

        tipo = _normalizar_tipo(aba)
        # header=0: linha 0 vira nome das colunas; dados começam na linha 1
        df = xl.parse(aba, header=0)

        materiais = []
        for _, row in df.iterrows():
            item    = row.iloc[0]
            descr   = row.iloc[1]
            unidade = row.iloc[2]
            qty     = row.iloc[3]

            # Linha vazia/separador
            if pd.isna(item) or pd.isna(descr):
                continue

            # Cabeçalho da seção de Fibra Óptica → para o loop desta aba
            if str(item).strip().upper() == 'ITEM':
                if 'FIBRA' in str(descr).upper():
                    break
                continue

            # Quantidade ausente ou variável ("Var.", "var.", NaN)
            if not _is_valid_qty(qty):
                continue

            materiais.append({
                'codigo':    str(item).strip(),
                'descricao': str(descr).strip(),
                'unidade':   str(unidade).strip(),
                'qtd':       float(qty),
            })

        receita[tipo] = materiais

    return receita


def gerar_tabela_validacao_ferragens(df_locacao):
    """Retorna tabela pivotada: linhas = materiais, colunas = TIPOs (com contagem no cabeçalho).
    Ex: coluna 'N4 (×64)' contém a quantidade por estrutura daquele material para o tipo N4."""
    receita = _ler_receita()

    contagem_tipos = (
        df_locacao['TIPO']
        .astype(str).str.strip()
        .value_counts()
        .to_dict()
    )

    linhas = []
    for tipo, count in contagem_tipos.items():
        tipo = tipo.strip()
        if tipo.lower() in ('', 'nan', 'none', '<na>'):
            continue
        if tipo not in receita:
            continue
        for mat in receita[tipo]:
            linhas.append({
                'CÓDIGO':   mat['codigo'],
                'MATERIAL': mat['descricao'],
                'UNIDADE':  mat['unidade'],
                'TIPO':     tipo,
                'CONTAGEM': count,
                'QTD':      mat['qtd'],
            })

    if not linhas:
        return pd.DataFrame()

    # Registra a ordem de primeira aparição de cada material (segue a ordem do Excel)
    ordem_material = {}
    for l in linhas:
        mat = l['MATERIAL']
        if mat not in ordem_material:
            ordem_material[mat] = len(ordem_material)

    df = pd.DataFrame(linhas)

    # Pivota: linhas = CÓDIGO+MATERIAL+UNIDADE, colunas = TIPO, valores = QTD por estrutura
    df_pivot = df.pivot_table(
        index=['CÓDIGO', 'MATERIAL', 'UNIDADE'],
        columns='TIPO',
        values='QTD',
        aggfunc='first',
    ).reset_index()
    df_pivot.columns.name = None

    contagem_map = df.drop_duplicates('TIPO').set_index('TIPO')['CONTAGEM'].to_dict()

    # Ordena colunas de TIPO por contagem decrescente (estrutura mais frequente primeiro)
    cols_tipo = sorted(
        [c for c in df_pivot.columns if c not in ('CÓDIGO', 'MATERIAL', 'UNIDADE')],
        key=lambda t: -contagem_map.get(t, 0)
    )
    df_pivot = df_pivot[['CÓDIGO', 'MATERIAL', 'UNIDADE'] + cols_tipo]

    # Linha de contagem: célula isolada abaixo do código de cada estrutura
    linha_contagem = {'CÓDIGO': '', 'MATERIAL': 'Qtd. de estruturas', 'UNIDADE': ''}
    linha_contagem.update({t: contagem_map[t] for t in cols_tipo})

    df_pivot['_sort'] = pd.to_numeric(df_pivot['CÓDIGO'], errors='coerce').fillna(0)
    df_pivot = df_pivot.sort_values('_sort').drop(columns='_sort').reset_index(drop=True)

    return pd.concat(
        [pd.DataFrame([linha_contagem]), df_pivot],
        ignore_index=True
    )


def calcular_ferragens(df_locacao):
    print("Processando quantitativo de ferragens...")

    receita = _ler_receita()

    contagem_tipos = (
        df_locacao['TIPO']
        .astype(str).str.strip()
        .value_counts()
        .to_dict()
    )

    lista_materiais = []
    avisos = []

    tipos_receita = set(receita.keys())
    tipos_dados = {
        t for t in contagem_tipos
        if t.lower() not in ('', 'nan', 'none', '<na>')
    }

    for t in sorted(tipos_dados - tipos_receita):
        avisos.append(f"Estrutura '{t}' não encontrada na receita de ferragens — ignorada")

    for tipo, count in contagem_tipos.items():
        tipo = tipo.strip()
        if tipo.lower() in ('', 'nan', 'none', '<na>'):
            continue
        if tipo not in receita:
            continue

        for mat in receita[tipo]:
            lista_materiais.append({
                'Código':      mat['codigo'],
                'Material':    mat['descricao'],
                'Unidade':     mat['unidade'],
                'Quantidade':  mat['qtd'] * count,
            })

    if not lista_materiais:
        return pd.DataFrame(columns=['Código', 'Material', 'Unidade', 'Quantidade']), avisos

    df_resultado = pd.DataFrame(lista_materiais)
    df_agrupado  = (
        df_resultado
        .groupby(['Código', 'Material', 'Unidade'], sort=False)['Quantidade']
        .sum()
        .reset_index()
    )
    df_agrupado['_sort'] = pd.to_numeric(df_agrupado['Código'], errors='coerce').fillna(0)
    df_agrupado = df_agrupado.sort_values('_sort').drop(columns='_sort').reset_index(drop=True)
    return df_agrupado, avisos
