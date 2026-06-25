import pandas as pd

def calcular_quantitativo_estais(df_locacao):
    print("Processando quantitativo de estais e multiplicando pela receita...")
    df_locacao['ESTAIS'] = pd.to_numeric(df_locacao['ESTAIS'], errors='coerce')
    total_estais = df_locacao['ESTAIS'].sum()
    
    # Receita Padrão de Estaiamento (Edite os nomes e quantidades conforme sua imagem)
    receita_estai = [
        {"Material": "Haste de âncora cilíndrica dupla 16x2400mm", "Unidade": "Pç", "Qtd_por_Estai": 1},
        {"Material": "Cabo de aço galvanizado SM 3/8\"", "Unidade": "m", "Qtd_por_Estai": 15},
        {"Material": "Manilha sapatilha (50kN)", "Unidade": "Pç", "Qtd_por_Estai": 1},
        {"Material": "Alça preformada para cabo de aço 3/8\"", "Unidade": "Pç", "Qtd_por_Estai": 2},
        {"Material": "Isolador roldana de porcelana", "Unidade": "Pç", "Qtd_por_Estai": 1}
    ]
    
    lista_final_estais = []
    
    for item in receita_estai:
        lista_final_estais.append({
            'Material': item['Material'],
            'Unidade': item['Unidade'],
            'Quantidade': total_estais * item['Qtd_por_Estai']
        })
        
    return pd.DataFrame(lista_final_estais)