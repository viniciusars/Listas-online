import pandas as pd

COLUNAS_SAIDA = ["Material", "Unidade", "Quantidade"]


def calcular_quantitativo_estais(df_locacao):
    """Soma a coluna ESTAIS e multiplica pela receita fixa. Retorna (df_resultado, avisos)."""
    print("Processando quantitativo de estais e multiplicando pela receita...")
    avisos = []

    if "ESTAIS" not in df_locacao.columns:
        avisos.append(
            "Coluna 'ESTAIS' não encontrada na Locação — estais não calculados."
        )
        return pd.DataFrame(columns=COLUNAS_SAIDA), avisos

    # Opera numa cópia da série para não alterar o DataFrame compartilhado entre os motores
    total_estais = pd.to_numeric(df_locacao["ESTAIS"], errors="coerce").sum()

    # Receita Padrão de Estaiamento (Edite os nomes e quantidades conforme sua imagem)
    receita_estai = [
        {
            "Material": "parafuso cabeça quadrada m16 x tamanho adequado",
            "Unidade": "Pç",
            "Qtd_por_Estai": 1,
        },
        {
            "Material": "porca quadrada, em aço galvanizado, m16",
            "Unidade": "Pç",
            "Qtd_por_Estai": 2,
        },
        {
            "Material": "arruela quadrada 100x100x5mm para parafuso m16 galvanizada a fogo",
            "Unidade": "Pç",
            "Qtd_por_Estai": 2,
        },
        {
            "Material": "sapatilha galvanizado a fogo",
            "Unidade": "Pç",
            "Qtd_por_Estai": 2,
        },
        {
            "Material": "alça preformadapara cordoalha 3/8' (cabo de estai)",
            "Unidade": "Pç",
            "Qtd_por_Estai": 2,
        },
        {
            "Material": "chapa para fixação do estai no poste",
            "Unidade": "Pç",
            "Qtd_por_Estai": 1,
        },
        {
            "Material": "cordoalha de aço cas 3/8' (m)",
            "Unidade": "Pç",
            "Qtd_por_Estai": 24,
        },
        {
            "Material": "haste-âncora 16-2400mm com 2xporca + arruela quadrada (100x100x6mm e furo 18mm)",
            "Unidade": "Pç",
            "Qtd_por_Estai": 1,
        },
        {
            "Material": "bloco de concreto para estai 500x500x150mm",
            "Unidade": "Pç",
            "Qtd_por_Estai": 1,
        },
        {
            "Material": "sinalização de estai  - sinalizador de estai helicoidal com abraçadeira plástica ou de aço inox",
            "Unidade": "Pç",
            "Qtd_por_Estai": 1,
        },
    ]

    lista_final_estais = []

    for item in receita_estai:
        lista_final_estais.append(
            {
                "Material": item["Material"],
                "Unidade": item["Unidade"],
                "Quantidade": total_estais * item["Qtd_por_Estai"],
            }
        )

    return pd.DataFrame(lista_final_estais, columns=COLUNAS_SAIDA), avisos
