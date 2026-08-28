import os
import io
import pandas as pd

def processar_consolidacao(arquivos):
    """
    Recebe uma lista de objetos FileStorage (do Flask), processa a consolidação
    das planilhas RMT e TMA, e retorna um objeto BytesIO com o Excel gerado.
    """
    abas_alvo = ["RMT", "TMA", "Lista"]
    dados_por_aba = {"RMT": [], "TMA": [], "Lista": []}

    for arquivo in arquivos:
        nome_arquivo = arquivo.filename
        nome_sem_extensao = os.path.splitext(nome_arquivo)[0]
        # Extrai os últimos 2 caracteres como código do documento
        codigo_doc = nome_sem_extensao[-2:]
        
        try:
            # pd.ExcelFile aceita objetos FileStorage diretamente (file-like)
            xls = pd.ExcelFile(arquivo)
            abas_existentes = xls.sheet_names

            for aba in abas_alvo:
                if aba in abas_existentes:
                    df = pd.read_excel(
                        xls, 
                        sheet_name=aba, 
                        usecols="C:E", 
                        header=None,
                        names=["Descricao", "Unidade", "Quantidade"]
                    )
                    df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce")
                    df = df.dropna(subset=["Descricao", "Quantidade"])

                    if not df.empty:
                        df["Origem_Doc"] = codigo_doc
                        dados_por_aba[aba].append(df)
        except Exception as e:
            # Ignoramos falhas pontuais de leitura de um arquivo específico
            continue

    dfs_finais = {}
    for aba in abas_alvo:
        lista_materiais = dados_por_aba[aba]
        if not lista_materiais:
            continue
            
        df_aba = pd.concat(lista_materiais, ignore_index=True)

        df_aba["Descricao"] = df_aba["Descricao"].astype(str).str.strip()
        df_aba["Unidade"] = df_aba["Unidade"].astype(str).str.strip()

        df_pivot = df_aba.pivot_table(
            index=["Descricao", "Unidade"],
            columns="Origem_Doc",
            values="Quantidade",
            aggfunc="sum",
            fill_value=0
        ).reset_index()

        colunas_docs = [c for c in df_pivot.columns if c not in ["Descricao", "Unidade"]]
        df_pivot["Total"] = df_pivot[colunas_docs].sum(axis=1)
        
        cols_ordenadas = ["Descricao", "Unidade", "Total"] + colunas_docs
        df_pivot = df_pivot[cols_ordenadas]
        df_pivot = df_pivot.sort_values(by="Descricao")
        
        dfs_finais[aba] = df_pivot

    if not dfs_finais:
        raise ValueError("Nenhum material válido foi encontrado nas abas 'RMT' ou 'TMA' ou 'Lista'.")

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if "RMT" in dfs_finais:
            dfs_finais["RMT"].to_excel(writer, sheet_name="RMT", index=False)
        if "TMA" in dfs_finais:
            dfs_finais["TMA"].to_excel(writer, sheet_name="TMA", index=False)
        if "Lista" in dfs_finais:
                    dfs_finais["Lista"].to_excel(writer, sheet_name="Lista", index=False)
            
    output.seek(0)
    return output
