import pandas as pd

def calcular_quantitativo_postes(df_locacao):
    print("Processando quantitativo de postes...")
    
    df_postes = df_locacao.dropna(subset=['ALTURA / CARGA']).copy()
    contagem_bruta = df_postes['ALTURA / CARGA'].value_counts().reset_index()
    contagem_bruta.columns = ['ALTURA_CARGA', 'QUANTIDADE']
    
    lista_final_postes = []
    
    for index, row in contagem_bruta.iterrows():
        texto_original = str(row['ALTURA_CARGA'])
        
        if '/' in texto_original:
            altura, carga = texto_original.split('/')
            descricao = f"Poste de concreto duplo T (tipo B): H = {altura}m - {carga}daN"
            
            lista_final_postes.append({
                'Material': descricao,
                'Unidade': 'Pç',
                'Quantidade': row['QUANTIDADE']
            })
            
    return pd.DataFrame(lista_final_postes)