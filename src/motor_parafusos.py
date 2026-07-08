import pandas as pd

from src import banco
from src.leitor_excel import detectar_coluna_numero

CODIGO_VIGA_U = '36'


def _split_altura_carga(valor):
    """Separa 'ALTURA / CARGA' (ex: '13/1000') em (altura, esforco)."""
    texto = str(valor).strip()
    if '/' not in texto:
        return None, None
    altura_txt, esforco_txt = texto.split('/', 1)
    try:
        return float(altura_txt), float(esforco_txt)
    except (TypeError, ValueError):
        return None, None


def identificar_estruturas_ambiguas(df_locacao):
    """Retorna as estruturas cujo TIPO está numa família ambígua (ex: N3-3) e ainda
    não foi digitado com o sufixo .C/.I na Locação — precisam de confirmação manual,
    pois essa informação só é visível na planta perfil (DWG)."""
    bases = banco.listar_tipos_ambiguos_parafusos()
    if not bases or 'TIPO' not in df_locacao.columns:
        return []

    col_num = detectar_coluna_numero(df_locacao)
    ambiguos = []
    for _, row in df_locacao.iterrows():
        tipo = str(row.get('TIPO', '')).strip()
        if tipo in bases:
            numero = str(row.get(col_num, '')).strip() if col_num else ''
            ambiguos.append({'numero': numero, 'tipo': tipo})
    return ambiguos


def calcular_parafusos(df_locacao, resolucoes=None):
    """Calcula o quantitativo de parafusos (cabeça quadrada e rosca dupla) por
    comprimento comercial e classe (kN), a partir da receita cadastrada no banco.

    resolucoes: dict {numero_estrutura: 'C'|'I'} para estruturas de TIPO ambíguo.
    Retorna (df_resultado, incremento_item_36, avisos).
    """
    resolucoes = resolucoes or {}
    avisos = []
    colunas_saida = ['Parafuso', 'Classe (kN)', 'Comprimento (mm)', 'Quantidade']

    receita = banco.ler_receita_parafusos_df()
    if receita.empty:
        avisos.append("Receita de parafusos não cadastrada — nada foi calculado.")
        return pd.DataFrame(columns=colunas_saida), 0.0, avisos

    if 'TIPO' not in df_locacao.columns or 'ALTURA / CARGA' not in df_locacao.columns:
        avisos.append("Colunas TIPO / ALTURA-CARGA não encontradas na Locação.")
        return pd.DataFrame(columns=colunas_saida), 0.0, avisos

    bases_ambiguas = banco.listar_tipos_ambiguos_parafusos()
    col_num = detectar_coluna_numero(df_locacao)
    col_posicao = next((c for c in df_locacao.columns if c.strip().upper() == 'POSIÇÃO'), None)

    df = df_locacao.copy()
    df['_tipo_parafuso'] = df['TIPO'].astype(str).str.strip()

    if bases_ambiguas and col_num:
        for idx, row in df.iterrows():
            tipo = row['_tipo_parafuso']
            if tipo in bases_ambiguas:
                numero = str(row.get(col_num, '')).strip()
                escolha = resolucoes.get(numero)
                if escolha in ('C', 'I'):
                    df.at[idx, '_tipo_parafuso'] = f"{tipo}.{escolha}"

    alturas_esforcos = df['ALTURA / CARGA'].apply(_split_altura_carga)
    df['_altura']  = [a for a, _ in alturas_esforcos]
    df['_esforco'] = [e for _, e in alturas_esforcos]
    df['_posicao'] = df[col_posicao].astype(str).str.strip().str.upper() if col_posicao else ''

    contagem = (
        df.groupby(['_tipo_parafuso', '_esforco', '_altura', '_posicao'], dropna=False)
        .size()
        .reset_index(name='CONTAGEM')
    )

    tipos_receita = set(receita['tipo'])
    itens = []
    incremento_item36 = 0.0

    for _, row in contagem.iterrows():
        tipo, esforco, altura, posicao, count = (
            row['_tipo_parafuso'], row['_esforco'], row['_altura'], row['_posicao'], row['CONTAGEM']
        )
        if tipo.lower() in ('', 'nan', 'none'):
            continue
        if tipo not in tipos_receita:
            if tipo in bases_ambiguas:
                avisos.append(f"Estrutura '{tipo}' com sentido de chegada dos cabos não "
                               "confirmado — parafusos não calculados.")
            else:
                avisos.append(f"Estrutura '{tipo}' não encontrada na receita de parafusos — ignorada")
            continue

        sub_tipo_esforco = receita[(receita['tipo'] == tipo) & (receita['esforco'] == esforco)]
        if sub_tipo_esforco.empty:
            avisos.append(f"Receita de parafusos não cadastrada para '{tipo}' com esforço {esforco:g} — ignorada")
            continue

        depende_altura = sub_tipo_esforco['altura'].notna().any()
        if depende_altura:
            sub = sub_tipo_esforco[sub_tipo_esforco['altura'] == altura]
        else:
            sub = sub_tipo_esforco

        sub = sub[sub['posicao'] == posicao]
        if sub.empty:
            avisos.append(f"Receita de parafusos incompleta para '{tipo}' "
                           f"(esforço {esforco:g}, posição {posicao}) — ignorada")
            continue

        for _, mat in sub.iterrows():
            itens.append({
                'Parafuso':          mat['parafuso'].title(),
                'Classe (kN)':       mat['esf_parafuso'],
                'Comprimento (mm)':  mat['comprimento'],
                'Quantidade':        mat['quantidade'] * count,
            })

        cruzeta_vals = sub['cruzeta_adicional'].dropna().unique()
        if len(cruzeta_vals):
            incremento_item36 += float(cruzeta_vals[0]) * count

    if not itens:
        return pd.DataFrame(columns=colunas_saida), incremento_item36, avisos

    df_resultado = pd.DataFrame(itens)
    df_agrupado = (
        df_resultado
        .groupby(['Parafuso', 'Classe (kN)', 'Comprimento (mm)'], sort=False)['Quantidade']
        .sum()
        .reset_index()
        .sort_values(['Parafuso', 'Classe (kN)', 'Comprimento (mm)'])
        .reset_index(drop=True)
    )
    return df_agrupado, incremento_item36, avisos
