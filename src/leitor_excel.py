import pandas as pd
import re


def _extrair_letra_circuito(valor):
    """Extrai a(s) letra(s) de circuito do final do NÚMERO (ex: '10/3A' → 'A')."""
    m = re.search(r'[A-Za-z]+$', str(valor).strip())
    return m.group(0).upper() if m else ''


def _numero_valido(valor): #Função para validar que aquela linha possui informação válida para os cálculos
    """Retorna True se o valor parece um número de estrutura válido (tem dígito e termina com letra)."""
    s = str(valor).strip()
    if s in ('', 'nan', 'NaN', 'None'):
        return False
    tem_digito = bool(re.search(r'\d', s))
    tem_letra_final = bool(re.search(r'[A-Za-z]+$', s))
    return tem_digito and tem_letra_final


def detectar_coluna_numero(df):
    """Encontra a coluna NÚMERO da estrutura, cujo nome pode variar entre planilhas."""
    for c in df.columns:
        if c.strip().upper() in ('NÚMERO', 'NUMERO', 'N°', 'Nº', 'NUM'):
            return c
    return None


def formatar_numeros_postes(numeros):
    """Formata uma lista de números de estrutura para exibição em avisos.
    Ex: ['10/3A', '10/3A', '11/3A'] → 'poste 10/3A, 11/3A'. Retorna '' se não houver nenhum."""
    limpos = []
    for numero in numeros:
        num = str(numero).strip()
        if num.lower() in ('', 'nan', 'none', '<na>'):
            num = '(sem número)'
        if num not in limpos:
            limpos.append(num)
    if not limpos:
        return ''
    rotulo = 'poste' if len(limpos) == 1 else 'postes'
    return f"{rotulo} {', '.join(limpos)}"


def numeros_por_tipo(df, tipo):
    """Lista os números das estruturas de um TIPO dentro da Locação (na ordem em que aparecem)."""
    col_num = detectar_coluna_numero(df)
    if col_num is None or 'TIPO' not in df.columns:
        return []
    mascara = df['TIPO'].astype(str).str.strip() == str(tipo).strip()
    return df.loc[mascara, col_num].tolist()


def consolidar_tabela_locacao(caminho_arquivo):
    print(f"Lendo e unificando abas do arquivo: {caminho_arquivo}...")
    xls = pd.ExcelFile(caminho_arquivo)
    abas_locacao = [aba for aba in xls.sheet_names if 'TABELA DE LOCAÇÃO' in aba.upper()]

    lista_dfs = []
    for ordem, aba in enumerate(abas_locacao): #Pegar os valores de cada aba e localizar cada valor
        df = pd.read_excel(xls, sheet_name=aba, skiprows=6)
        df.columns = df.columns.astype(str).str.strip()
        df['_ordem_aba']   = ordem                      
        df['_ordem_linha'] = range(len(df))
        lista_dfs.append(df)

    if not lista_dfs:
        return pd.DataFrame()

    df_mestre = pd.concat(lista_dfs, ignore_index=True)

    # Detecta coluna NÚMERO (nome pode variar)
    col_num = None
    for c in df_mestre.columns: # Procura a coluna que possui os valores do NÚMERO de cada poste
        if c.strip().upper() in ('NÚMERO', 'NUMERO', 'N°', 'Nº', 'NUM'):
            col_num = c
            break

    if col_num:
        # Remove rodapé e linhas inválidas: só mantém estruturas com dígito + letra no final
        mascara = df_mestre[col_num].apply(_numero_valido)
        df_mestre = df_mestre[mascara].copy() # Faz o filtro 'mascara' por TRUE ou FALSE, isso acontece nativamente no PANDAS

        # Extrai letra de circuito e usa para agrupar abas com continuidade
        df_mestre['_letra_circuito'] = df_mestre[col_num].apply(_extrair_letra_circuito)

        # Ordena: todas as estruturas do mesmo circuito juntas, na ordem das abas e linhas
        df_mestre = df_mestre.sort_values(
            ['_letra_circuito', '_ordem_aba', '_ordem_linha'],
            kind='stable'
        ).reset_index(drop=True)

    # Remove colunas auxiliares de ordenação (mantém _letra_circuito para os motores usarem)
    df_mestre = df_mestre.drop(columns=['_ordem_aba', '_ordem_linha'], errors='ignore')

    return df_mestre
