import pandas as pd

COLUNAS_SAIDA = ['Material', 'Unidade', 'Quantidade']


def calcular_quantitativo_postes(df_locacao):
    """Conta postes por ALTURA/CARGA. Retorna (df_resultado, avisos)."""
    print("Processando quantitativo de postes...")
    avisos = []

    if 'ALTURA / CARGA' not in df_locacao.columns: # Verificação de presença da informação 'ALTURA/CARGA'
        avisos.append("Coluna 'ALTURA / CARGA' não encontrada na Locação — postes não calculados.")
        return pd.DataFrame(columns=COLUNAS_SAIDA), avisos

    df_postes = df_locacao.dropna(subset=['ALTURA / CARGA']).copy() # Limpa linhas sem informação
    contagem_bruta = df_postes['ALTURA / CARGA'].value_counts().reset_index() # Conta a quantidade de cada tipo de poste
    contagem_bruta.columns = ['ALTURA_CARGA', 'QUANTIDADE'] # Renomeia as colunas

    lista_final_postes = []

    for index, row in contagem_bruta.iterrows(): # Esse for coloca na formatação utilizada na lista
        texto_original = str(row['ALTURA_CARGA'])

        if '/' in texto_original:
            altura, carga = texto_original.split('/')
            descricao = f"Poste de concreto duplo T (tipo B): H = {altura}m - {carga}daN"

            lista_final_postes.append({
                'Material': descricao,
                'Unidade': 'Pç',
                'Quantidade': row['QUANTIDADE']
            })

    return pd.DataFrame(lista_final_postes, columns=COLUNAS_SAIDA), avisos # Retorna um df com a lista_final_postes e com a nomenclatura correta das colunas
