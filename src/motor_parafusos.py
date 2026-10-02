import re
import pandas as pd

from src import banco
from src.leitor_excel import detectar_coluna_numero, formatar_numeros_postes

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


def eh_tipo_ambiguo(tipo, bases_cadastradas=None):
    """Verifica se um TIPO de estrutura requer confirmação do sentido de chegada dos cabos (.C ou .I).

    Critérios:
    1. Não se aplica se já possuir sufixo explícito (.C ou .I).
    2. Contém 'N3-3' em qualquer parte da nomenclatura (ex: 'N3-3', '2N3-3', 'N4-N3-3', 'N4/N3-3', etc.); OU
    3. Coincide com alguma base ambígua cadastrada no banco de dados.
    """
    t = str(tipo).strip()
    t_up = t.upper()
    if not t or t_up in ('', 'NAN', 'NONE', '<NA>'):
        return False
    if t_up.endswith(('.C', '.I')):
        return False
    if re.search(r'N3\s*-\s*3', t_up):
        return True
    if bases_cadastradas and t in bases_cadastradas:
        return True
    return False


def identificar_estruturas_ambiguas(df_locacao, parque_id=None):
    """Retorna as estruturas cujo TIPO está numa família ambígua (ex: contém N3-3) e ainda
    não foi digitado com o sufixo .C/.I na Locação — precisam de confirmação manual,
    pois essa informação só é visível na planta perfil (DWG)."""
    if 'TIPO' not in df_locacao.columns:
        return []

    bases = banco.listar_tipos_ambiguos_parafusos(parque_id)
    col_num = detectar_coluna_numero(df_locacao)
    ambiguos = []
    for _, row in df_locacao.iterrows():
        tipo = str(row.get('TIPO', '')).strip()
        if eh_tipo_ambiguo(tipo, bases):
            numero = str(row.get(col_num, '')).strip() if col_num else ''
            ambiguos.append({'numero': numero, 'tipo': tipo})
    return ambiguos


def calcular_parafusos(df_locacao, resolucoes=None, parque_id=None):
    """Calcula o quantitativo de parafusos (cabeça quadrada e rosca dupla) por
    comprimento comercial e classe (kN), a partir da receita cadastrada no banco.

    resolucoes: dict {numero_estrutura: 'C'|'I'} para estruturas de TIPO ambíguo.
    Retorna (df_resultado, incremento_item_36, avisos, detalhe_cruzeta).

    detalhe_cruzeta: lista de {'numero': str, 'tipo': str, 'quantidade': float}
    indicando de quais postes (número + TIPO) veio a cruzeta adicional somada ao
    item 36. A soma das quantidades é igual a incremento_item_36.
    """
    resolucoes = resolucoes or {}
    avisos = []
    detalhe_cruzeta = {}
    colunas_saida = ['Parafuso', 'Classe (kN)', 'Comprimento (mm)', 'Quantidade']

    receita = banco.ler_receita_parafusos_df(parque_id)
    if receita.empty:
        avisos.append("Receita de parafusos não cadastrada neste parque — nada foi calculado.")
        return pd.DataFrame(columns=colunas_saida), 0.0, avisos, []

    if 'TIPO' not in df_locacao.columns or 'ALTURA / CARGA' not in df_locacao.columns:
        avisos.append("Colunas TIPO / ALTURA-CARGA não encontradas na Locação.")
        return pd.DataFrame(columns=colunas_saida), 0.0, avisos, []

    bases_ambiguas = banco.listar_tipos_ambiguos_parafusos(parque_id)
    col_num = detectar_coluna_numero(df_locacao)
    col_posicao = next((c for c in df_locacao.columns if c.strip().upper() == 'POSIÇÃO'), None)

    df = df_locacao.copy()
    df['_tipo_parafuso'] = df['TIPO'].astype(str).str.strip()

    if col_num:
        for idx, row in df.iterrows():
            tipo = row['_tipo_parafuso']
            if eh_tipo_ambiguo(tipo, bases_ambiguas):
                numero = str(row.get(col_num, '')).strip()
                escolha = resolucoes.get(numero)
                if escolha in ('C', 'I'):
                    df.at[idx, '_tipo_parafuso'] = f"{tipo}.{escolha}"

    alturas_esforcos = df['ALTURA / CARGA'].apply(_split_altura_carga)
    df['_altura']  = [a for a, _ in alturas_esforcos]
    df['_esforco'] = [e for _, e in alturas_esforcos]
    df['_posicao'] = df[col_posicao].astype(str).str.strip().str.upper() if col_posicao else ''
    df['_numero']  = df[col_num].astype(str).str.strip() if col_num else ''

    contagem = (
        df.groupby(['_tipo_parafuso', '_esforco', '_altura', '_posicao'], dropna=False)
        .agg(CONTAGEM=('_numero', 'size'), NUMEROS=('_numero', list))
        .reset_index()
    )

    tipos_receita = set(receita['tipo'])
    itens = []
    incremento_item36 = 0.0
    # TIPO sem nenhuma receita: acumula os números pra emitir um aviso único por TIPO,
    # em vez de repetir a mesma mensagem em cada combinação de esforço/altura/posição.
    tipos_sem_receita = {}

    for _, row in contagem.iterrows():
        tipo, esforco, altura, posicao, count, numeros = (
            row['_tipo_parafuso'], row['_esforco'], row['_altura'],
            row['_posicao'], row['CONTAGEM'], row['NUMEROS']
        )
        if tipo.lower() in ('', 'nan', 'none'):
            continue
        if tipo not in tipos_receita:
            tipos_sem_receita.setdefault(tipo, []).extend(numeros)
            continue

        onde = formatar_numeros_postes(numeros)
        sufixo_onde = f" [{onde}]" if onde else ''

        sub_tipo_esforco = receita[(receita['tipo'] == tipo) & (receita['esforco'] == esforco)]
        if sub_tipo_esforco.empty:
            avisos.append(f"Receita de parafusos não cadastrada para '{tipo}' com esforço "
                          f"{esforco:g} — ignorada{sufixo_onde}")
            continue

        depende_altura = sub_tipo_esforco['altura'].notna().any()
        if depende_altura:
            sub = sub_tipo_esforco[sub_tipo_esforco['altura'] == altura]
        else:
            sub = sub_tipo_esforco

        sub = sub[sub['posicao'] == posicao]
        if sub.empty:
            avisos.append(f"Receita de parafusos incompleta para '{tipo}' "
                          f"(esforço {esforco:g}, posição {posicao}) — ignorada{sufixo_onde}")
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
            valor_unit = float(cruzeta_vals[0])
            incremento_item36 += valor_unit * count
            for numero in numeros:
                num = str(numero).strip()
                if num.lower() in ('', 'nan', 'none'):
                    num = '(sem número)'
                chave = (num, tipo)
                acc = detalhe_cruzeta.get(chave, 0.0) + valor_unit
                detalhe_cruzeta[chave] = acc

    for tipo, numeros in tipos_sem_receita.items():
        onde = formatar_numeros_postes(numeros)
        sufixo_onde = f" [{onde}]" if onde else ''
        if eh_tipo_ambiguo(tipo, bases_ambiguas):
            avisos.append(f"Estrutura '{tipo}' com sentido de chegada dos cabos não "
                          f"confirmado — parafusos não calculados{sufixo_onde}")
        else:
            avisos.append(f"Estrutura '{tipo}' não encontrada na receita de parafusos "
                          f"— ignorada{sufixo_onde}")

    detalhe_lista = [
        {'numero': num, 'tipo': tipo, 'quantidade': q}
        for (num, tipo), q in detalhe_cruzeta.items() if q > 0
    ]

    if not itens:
        return pd.DataFrame(columns=colunas_saida), incremento_item36, avisos, detalhe_lista

    df_resultado = pd.DataFrame(itens)
    df_agrupado = (
        df_resultado
        .groupby(['Parafuso', 'Classe (kN)', 'Comprimento (mm)'], sort=False)['Quantidade']
        .sum()
        .reset_index()
        .sort_values(['Parafuso', 'Classe (kN)', 'Comprimento (mm)'])
        .reset_index(drop=True)
    )
    return df_agrupado, incremento_item36, avisos, detalhe_lista
