import pandas as pd
import os

from src.leitor_excel import formatar_numeros_postes, numeros_por_tipo


def _is_valid_cabo(val):
    s = str(val).strip().lower()
    return bool(s) and s not in ('nan', 'none', '<na>')


def _preparar_df(df_locacao):
    """Prepara df com colunas de ré (via shift) e efetivas (preenchimento cruzado vante↔ré).

    Regra: se uma estrutura tiver cabo em apenas um dos lados, o lado vazio recebe
    o valor do lado preenchido (ex: ponto final de circuito só tem cabo no vante).
    """
    caminho_receita = os.path.join('config', 'receita_alcas_lacos.csv')
    receita = pd.read_csv(caminho_receita)

    df = df_locacao.copy()
    df.columns = df.columns.astype(str).str.strip()

    col_vante = {}
    for col in df.columns:
        c = col.strip().upper()
        if c in ('NÍVEL 1', 'NIVEL 1'):
            col_vante[1] = col
        elif c in ('NÍVEL 2', 'NIVEL 2'):
            col_vante[2] = col

    usar_grupos = '_letra_circuito' in df.columns

    col_map = {}
    for nivel, v_col in col_vante.items():
        # Ré: shift(1) nos valores originais para que o fill seja NaN (não None)
        nome_re = f'_re_{nivel}'
        if usar_grupos:
            df[nome_re] = df.groupby('_letra_circuito')[v_col].shift(1)
        else:
            df[nome_re] = df[v_col].shift(1)

        r_col = nome_re
        v_valid = df[v_col].apply(_is_valid_cabo)
        r_valid = df[r_col].apply(_is_valid_cabo)

        eff_v = f'_eff_vante_{nivel}'
        eff_r = f'_eff_re_{nivel}'
        # Se só um lado tem cabo, usa o lado disponível para preencher o outro
        df[eff_v] = df[v_col].where(v_valid, df[r_col])
        df[eff_r] = df[r_col].where(r_valid, df[v_col])

        col_map[(nivel, 'VANTE')] = eff_v
        col_map[(nivel, 'RE')]    = eff_r

    return df, receita, col_map


def calcular_alcas_lacos(df_locacao):
    print("Processando quantitativo de Alças e Laços...")

    df, receita, col_map = _preparar_df(df_locacao)

    lista_materiais = []

    for _, linha in receita.iterrows():
        tipo      = str(linha['TIPO']).strip()
        nivel     = linha['NIVEL']
        direcao   = str(linha['DIRECAO']).strip()
        qtd_alcas = linha['QTD_ALCAS']
        qtd_lacos = linha['QTD_LACOS']

        if qtd_alcas == 0 and qtd_lacos == 0:
            continue

        col_cabo = col_map.get((nivel, direcao))
        if col_cabo is None:
            continue

        mascara = df['TIPO'].astype(str).str.strip() == tipo
        subset  = df.loc[mascara, col_cabo]

        for idx, valor in subset.items():
            if not _is_valid_cabo(valor):
                continue

            cabo = str(valor).strip()

            if qtd_alcas > 0:
                lista_materiais.append({
                    'Material': f"Alça preformada de distribuição para cabo {cabo}",
                    'Unidade': 'Pç',
                    'Quantidade': qtd_alcas
                })

            if qtd_lacos > 0:
                lista_materiais.append({
                    'Material': f"Laço preformado de distribuição para cabo {cabo}",
                    'Unidade': 'Pç',
                    'Quantidade': qtd_lacos
                })

    # Detecta TIPOs presentes nos dados mas ausentes na receita
    tipos_receita  = set(receita['TIPO'].astype(str).str.strip())
    tipos_dados    = set(df['TIPO'].astype(str).str.strip()) - {'', 'nan', 'none', 'NaN', 'None'}
    tipos_ausentes = sorted(tipos_dados - tipos_receita)
    avisos = []
    for t in tipos_ausentes:
        onde = formatar_numeros_postes(numeros_por_tipo(df, t))
        sufixo_onde = f" [{onde}]" if onde else ''
        avisos.append(f"Estrutura '{t}' não encontrada na receita "
                      f"— ignorada no cálculo{sufixo_onde}")

    if not lista_materiais:
        return pd.DataFrame(columns=['Material', 'Unidade', 'Quantidade']), avisos

    df_resultado = pd.DataFrame(lista_materiais)
    df_agrupado  = df_resultado.groupby(['Material', 'Unidade'])['Quantidade'].sum().reset_index()
    return df_agrupado, avisos


def gerar_tabela_validacao(df_locacao):
    """Retorna tabela detalhada: TIPO | NIVEL | DIRECAO | CABO | COUNT | QTD_ALCAS | QTD_LACOS | TOTAL_ALCAS | TOTAL_LACOS"""
    df, receita, col_map = _preparar_df(df_locacao)

    linhas = []
    for (nivel, direcao), col in col_map.items():
        for _, row in df.iterrows():
            if not _is_valid_cabo(row[col]):
                continue
            linhas.append({
                'TIPO':    str(row['TIPO']).strip(),
                'NIVEL':   nivel,
                'DIRECAO': direcao,
                'CABO':    str(row[col]).strip()
            })

    colunas_vazias = ['TIPO', 'NIVEL', 'DIRECAO', 'CABO', 'COUNT',
                      'QTD_ALCAS', 'QTD_LACOS', 'TOTAL_ALCAS', 'TOTAL_LACOS']
    if not linhas:
        return pd.DataFrame(columns=colunas_vazias)

    contagem = pd.DataFrame(linhas).groupby(['TIPO', 'NIVEL', 'DIRECAO', 'CABO']).size().reset_index(name='COUNT')
    contagem = contagem.merge(receita, on=['TIPO', 'NIVEL', 'DIRECAO'], how='left')
    contagem['QTD_ALCAS']   = contagem['QTD_ALCAS'].fillna(0).astype(int)
    contagem['QTD_LACOS']   = contagem['QTD_LACOS'].fillna(0).astype(int)
    contagem['TOTAL_ALCAS'] = contagem['COUNT'] * contagem['QTD_ALCAS']
    contagem['TOTAL_LACOS'] = contagem['COUNT'] * contagem['QTD_LACOS']

    return contagem.sort_values(['TIPO', 'NIVEL', 'DIRECAO', 'CABO']).reset_index(drop=True)
