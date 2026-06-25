import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd

# Lista padrão provisória (futuramente faremos o código ler o arquivo Base_Cabos.xlsx)
CABOS_PADRAO = [
    "CA MAGNOLIA 954 MCM",
    "CA OXLIP 4/0 AWG",
    "XLPE 90°C AL 20/35 kV 95 mm²",
    "CA ORCHID 636 MCM"
]

class InterfaceQuantitativo:
    def __init__(self, root):
        self.root = root
        self.root.title("Gerador de Quantitativos - RMT")
        self.root.geometry("550x450")
        self.root.configure(padx=20, pady=20)

        # Memória interna da interface para guardar os cabos
        self.cabos_adicionados = []

        # --- TÍTULO ---
        ttk.Label(root, text="Inserção Manual de Cabos", font=("Arial", 14, "bold")).pack(pady=(0, 15))

        # --- SELEÇÃO DO CABO ---
        ttk.Label(root, text="Selecione o Condutor:").pack(anchor="w")
        self.combo_cabos = ttk.Combobox(root, values=CABOS_PADRAO, width=50, state="readonly")
        self.combo_cabos.pack(pady=(0, 15), fill="x")
        self.combo_cabos.set(CABOS_PADRAO[0]) # Deixa o primeiro selecionado por padrão

        # --- QUANTIDADE ---
        ttk.Label(root, text="Quantidade Utilizada (m):").pack(anchor="w")
        self.entrada_qtd = ttk.Entry(root, width=20)
        self.entrada_qtd.pack(pady=(0, 15), anchor="w")

        # --- BOTÃO ADICIONAR ---
        ttk.Button(root, text="➕ Adicionar Cabo", command=self.adicionar_cabo).pack(pady=(0, 15), fill="x")

        # --- LISTA VISUAL ---
        ttk.Label(root, text="Cabos na Fila de Processamento:").pack(anchor="w")
        self.lista_visual = tk.Listbox(root, height=8)
        self.lista_visual.pack(fill="both", expand=True, pady=(0, 15))

        # --- BOTÃO EXECUTAR (Ponte com o Backend) ---
        ttk.Button(root, text="🚀 Processar Quantitativos (Postes, Estais e Cabos)", command=self.processar_tudo).pack(fill="x", pady=10)

    def adicionar_cabo(self):
        tipo = self.combo_cabos.get()
        qtd_texto = self.entrada_qtd.get()

        # Validação simples para evitar que você digite letras sem querer
        try:
            qtd_num = float(qtd_texto.replace(',', '.'))
        except ValueError:
            messagebox.showerror("Erro de Digitação", "Por favor, insira apenas números na quantidade.")
            return

        # Salva na memória do Python
        self.cabos_adicionados.append({
            'Material': tipo,
            'Unidade': 'm',
            'Quantidade': qtd_num
        })
        
        # Mostra na tela
        self.lista_visual.insert(tk.END, f"{tipo}  --->  {qtd_num} m")
        
        # Limpa a caixa de texto para o próximo cabo
        self.entrada_qtd.delete(0, tk.END)

    def processar_tudo(self):
        """
        No futuro, este botão vai pegar a self.cabos_adicionados
        e mandar lá para o nosso exportador junto com as planilhas.
        """
        if not self.cabos_adicionados:
            resposta = messagebox.askyesno("Aviso", "Nenhum cabo foi adicionado. Deseja gerar o arquivo mesmo assim?")
            if not resposta:
                return
                
        df_cabos = pd.DataFrame(self.cabos_adicionados)
        print("\n--- DADOS COLETADOS PELA INTERFACE ---")
        print(df_cabos if not df_cabos.empty else "Nenhum cabo inserido.")
        messagebox.showinfo("Sucesso", "Dados capturados! Dê uma olhada no terminal.")

if __name__ == "__main__":
    janela_principal = tk.Tk()
    app = InterfaceQuantitativo(janela_principal)
    janela_principal.mainloop()