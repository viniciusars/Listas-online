import pandas as pd

from src import banco

COLUNAS_SAIDA = ["Material", "Unidade", "Quantidade"]


def calcular_quantitativo_estais(df_locacao, parque_id=None):
    """Soma a coluna ESTAIS e multiplica pela receita do parque. Retorna (df_resultado, avisos)."""
    print("Processando quantitativo de estais e multiplicando pela receita...")
    avisos = []

    if "ESTAIS" not in df_locacao.columns:
        avisos.append(
            "Coluna 'ESTAIS' não encontrada na Locação — estais não calculados."
        )
        return pd.DataFrame(columns=COLUNAS_SAIDA), avisos

    receita_estai = banco.ler_receita_estais(parque_id)
    if not receita_estai:
        avisos.append(
            "Receita de estais não cadastrada neste parque — estais não calculados."
        )
        return pd.DataFrame(columns=COLUNAS_SAIDA), avisos

    # Opera numa cópia da série para não alterar o DataFrame compartilhado entre os motores
    total_estais = pd.to_numeric(df_locacao["ESTAIS"], errors="coerce").sum()

    lista_final_estais = [
        {
            "Material": item["material"],
            "Unidade": item["unidade"],
            "Quantidade": total_estais * item["qtd_por_estai"],
        }
        for item in receita_estai
    ]

    return pd.DataFrame(lista_final_estais, columns=COLUNAS_SAIDA), avisos
