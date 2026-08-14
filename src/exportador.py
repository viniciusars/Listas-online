import pandas as pd
import os


def exportar_multiplas_abas(abas_dict, nome_arquivo="RMT_Output_Completo.xlsx"):
    """Exporta múltiplas abas para um único .xlsx.

    abas_dict: {nome_aba: df} ou {nome_aba: (df_esquerda, df_direita)}
    Quando o valor é uma tupla, os dois DataFrames são escritos lado a lado
    na mesma aba (1 coluna de espaço entre eles).
    """
    caminho_pasta = os.path.join('data', 'output')
    os.makedirs(caminho_pasta, exist_ok=True)
    caminho = os.path.join(caminho_pasta, nome_arquivo)

    try:
        with pd.ExcelWriter(caminho, engine='openpyxl') as writer:
            for nome_aba, conteudo in abas_dict.items():
                if isinstance(conteudo, tuple):
                    # 2-tupla: (df_esq, df_dir)
                    # 3-tupla: (df_esq, df_dir, offset) — offset desloca df_esq N linhas
                    # abaixo para alinhar seus dados com os dados de df_dir
                    if len(conteudo) == 3:
                        df_esq, df_dir, offset = conteudo
                    else:
                        df_esq, df_dir, offset = conteudo[0], conteudo[1], 0
                    df_esq.to_excel(writer, sheet_name=nome_aba, index=False,
                                    startrow=offset, startcol=0)
                    if df_dir is not None and not df_dir.empty:
                        startcol = len(df_esq.columns) + 1
                        df_dir.to_excel(writer, sheet_name=nome_aba, index=False,
                                        startrow=0, startcol=startcol)
                else:
                    conteudo.to_excel(writer, sheet_name=nome_aba, index=False)
        print(f"[SUCESSO] Planilha multi-abas salva em: {caminho}")
    except Exception as e:
        print(f"[ERRO] Falha ao salvar planilha multi-abas: {e}")
        raise


def exportar_para_excel(df_final, nome_arquivo="RMT_Gerada.xlsx"):
    print("\nIniciando exportação para Excel...")
    
    # Garante que a pasta output existe, se não existir, cria
    caminho_pasta = os.path.join('data', 'output')
    os.makedirs(caminho_pasta, exist_ok=True)
    
    caminho_completo = os.path.join(caminho_pasta, nome_arquivo)
    
    try:
        # Exporta o arquivo sem a coluna de índice do Pandas
        df_final.to_excel(caminho_completo, index=False)
        print(f"[SUCESSO] Planilha salva em: {caminho_completo}")
    except Exception as e:
        print(f"[ERRO] Falha ao salvar a planilha: {e}")
        print("Dica: Se a planilha já estiver aberta no Excel, feche-a e rode novamente.")
        raise