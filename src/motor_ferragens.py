import pandas as pd

from src import banco


def _ler_receita():
    """Receita de ferragens vinda do banco: {tipo: [{codigo, descricao, unidade, qtd}, ...]}."""
    return banco.ler_receita_ferragens()


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
