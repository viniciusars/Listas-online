# Documento de Contexto para Migração: Sistema de Quantitativos RMT

## 1. Visão Geral do Projeto
O projeto consiste em um sistema web local desenvolvido em Python para gerar listas de quantitativos de materiais (BOM - Bill of Materials) para projetos de Redes de Média Tensão (RMT). O motor de processamento utiliza a biblioteca `pandas` para ler, limpar e cruzar dados de planilhas Excel (Tabelas de Locação). O servidor é `Flask` e a interface é uma página HTML/CSS/JS servida localmente em `http://127.0.0.1:5000`. O usuário inicia o sistema rodando `python main.py`, que sobe o servidor e abre o browser automaticamente.

---

## 2. Histórico de Desenvolvimento e Pedidos do Usuário
* **Fase 1: Motor Base (Postes):** O usuário pediu para iniciar a lógica do cálculo de quantitativos isolada da interface. As regras estipuladas foram que todos os postes são duplo T e apenas uma estrutura física por linha é válida. A lógica aplicada foi o empilhamento das abas da Locação, separação da coluna "ALTURA / CARGA" (ex: 14/1000), contagem de ocorrências (`value_counts`) e formatação da string de saída.
* **Fase 2: Condutores (Cabos):** O pedido inicial era calcular os cabos com base no "Plano de Corte". Houve uma mudança de rota, e o usuário preferiu criar uma inserção manual na interface gráfica via Combobox para adicionar cabos, evitando a complexidade de ler planilhas de terceiros com células mescladas e facilitando o reaproveitamento em outras obras.
* **Fase 3: Ferragens e Estaiamento:** O pedido foi multiplicar a quantidade de estruturas por uma "receita de bolo" de materiais. A decisão foi pausar a lógica de ferragens gerais e fibra óptica para focar no MVP. O sistema focou apenas no Estaiamento, somando a coluna `ESTAIS` global e multiplicando por uma receita estática mapeada em dicionário no código.
* **Fase 4: Arquitetura Modular:** O usuário pediu para dividir o código em múltiplos arquivos simulando um ambiente de software/executável. A ação tomada foi a criação da estrutura de pastas `src/`, `data/input/`, `data/output/` e o orquestrador `main.py`.
* **Fase 5: Interface e Exportação:** O pedido foi criar um menu inicial com a inserção de cabos e exportar os relatórios. Criou-se uma UI em Tkinter que integra a entrada de cabos, um botão de disparo geral e um console de log visual. O usuário demonstrou a preferência de isolar a lista de Postes em um arquivo `.xlsx` exclusivo, além de gerar o arquivo completo (Postes + Estais + Cabos).
* **Fase 6: Alças e Laços (Implementado):** A lógica foi refeita do zero usando um arquivo de receita externo `data/config/receita_alcas_lacos.csv`. Cada linha do CSV mapeia um TIPO de estrutura + NÍVEL + DIREÇÃO (VANTE ou RE) para uma quantidade de alças e laços. O motor lê a coluna de cabo do nível atual (Vante) e da linha anterior dentro do mesmo circuito (Ré, usando `.shift(1)` agrupado por `_letra_circuito`). O módulo `motor_alcas_lacos.py` está implementado e integrado ao fluxo do `main.py`.
* **Fase 7: Migração da Interface para Flask/Web:** A interface Tkinter foi substituída por uma aplicação web Flask. O `main.py` virou um servidor Flask com rotas `/` (página principal), `/preview` (lê o Excel e retorna JSON para pré-visualização), `/processar` (executa todos os motores e exporta), e `/download/<arquivo>` (servir os arquivos gerados). O front-end é `templates/index.html` com HTML/CSS/JS puro, sem dependências externas. O arquivo `src/interface.py` (Tkinter) ficou obsoleto mas não foi deletado.
* **Fase 8: Validação e Maturação do Motor de Alças/Laços:** O motor foi reescrito do zero após divergências detectadas na validação manual. A causa raiz era o uso de `groupby().transform(lambda s: s.astype(str).shift(1))`, que preenchia o primeiro elemento de cada circuito com Python `None` (não `numpy.NaN`). `str(None)` = `'None'` passava pelo filtro `cabo.lower() == 'nan'` e gerava contagens espúrias. A correção foi fazer o `.shift(1)` nos valores originais (antes do `astype(str)`), garantindo que o fill seja `NaN` → capturado pelo filtro `in ('nan', 'none', '<na>')`. Foram adicionadas duas funcionalidades: (1) `gerar_tabela_validacao()` em `motor_alcas_lacos.py`, que retorna uma tabela detalhada por TIPO·NÍVEL·DIREÇÃO·CABO com COUNT e totais de alças/laços, exportável opcionalmente via checkbox na UI; (2) sistema de aviso (⚠ amarelo no log) para TIPOs presentes na planilha mas ausentes na `receita_alcas_lacos.csv`, permitindo identificar estruturas novas que precisam ser cadastradas. O motor foi validado com dados reais e os resultados foram confirmados corretos pelo usuário.

---

## 3. Alternativas Consideradas e Descartadas
* **Leitura Automática de Cabos (Plano de Corte):** Descartada em favor de um input manual na UI para maior controle e flexibilidade.
* **Lista de Cabos "Hardcoded" vs. Banco de Dados:** Optou-se conceitualmente por um arquivo externo de configuração para escalar os tipos de cabos no futuro, embora atualmente exista uma lista provisória fixa no código (`CABOS_PADRAO`).
* **Processamento de Fibra Óptica e Ferragens Gerais:** Descartados do escopo do MVP para evitar tratamento de exceções (como o texto "Var.") antes de o núcleo base estar operante.

---

## 4. Erros Encontrados e Como Foram Corrigidos
* **Erro de Leitura de Cabeçalho (`KeyError: ['ALTURA / CARGA']`):** A causa era o Pandas lendo o cabeçalho da prancha (linha 5) em vez do cabeçalho da tabela (linha 6). A correção foi alterar para `skiprows=6` na importação e adicionar a limpeza de strings para remover espaços invisíveis.
* **Erro de Concatenação (`FutureWarning` no `pd.concat`):** A causa era tentar concatenar DataFrames vazios (ex: quando nenhum cabo manual era inserido). A correção foi implementar um filtro de validação usando list comprehension antes do método concat.
* **Erro de Omissão de Colunas nas Alças/Laços:** A causa foi o código buscar por colunas literais como "NÍVEL SUPERIOR RÉ", que não existiam nativamente na Tabela de Locação devido ao formato do Excel. Esse módulo foi descartado e refeito com a abordagem do CSV de receita.
* **Erro `ERR_UPLOAD_FILE_CHANGED` (browser bloqueava o envio):** A causa era a rota `/preview` salvar o arquivo enviado em `data/input/` com o mesmo nome do arquivo original. Quando o usuário clicava em "Executar", o browser tentava reler o arquivo do disco para reenviá-lo, detectava que o timestamp havia mudado (o servidor sobrescreveu) e bloqueava o upload. A correção foi eliminar o salvamento em disco nas rotas `/preview` e `/processar`, lendo o arquivo direto para memória com `io.BytesIO(arquivo.read())` e passando o objeto para `pd.ExcelFile()`, que aceita tanto caminhos quanto file-like objects.
* **Erro de `None` espúrio nas Alças/Laços (contagens incorretas):** O uso de `groupby().transform(lambda s: s.astype(str).shift(1))` gerava Python `None` (não `numpy.NaN`) como fill do primeiro elemento de cada grupo. `str(None)` resulta em `'None'`, que passava pelo filtro `cabo.lower() == 'nan'` e criava itens fantasma no quantitativo. A correção foi inverter a ordem: `df.groupby('_letra_circuito')[col].shift(1)` nos valores originais antes de qualquer conversão para string, garantindo que o fill seja `NaN` → coberto pelo filtro `in ('nan', 'none', '<na>')`.

---

## 5. Preferências do Usuário e Convenções
* **Arquitetura Limpa:** Separação rígida de responsabilidades. O `main.py` cuida da UI e orquestração; o `leitor_excel.py` cuida da extração; os módulos `motor_*.py` cuidam exclusivamente da matemática; e o `exportador.py` salva os dados.
* **Transparência Visual:** O log de atividades na interface web (div escura no fundo da página) deve sempre registrar os passos (Leitura, Cálculo, Consolidação, Exportação), com cores diferenciadas: verde (`✓`) para sucesso, vermelho (`✗`) para erro, cinza para info, amarelo (`⚠`) para avisos não-bloqueantes.
* **Relatórios Isolados:** A geração de listas deve ser flexível, gerando um Master unificado e relatórios isolados (como o de Postes).
* **Desenvolvimento Guiado:** Em regras de negócio complexas, o usuário prefere ditar a lógica passo a passo, em vez de a IA assumir formatos de planilha e criar códigos complexos sem validação.

---

## 6. Estado Atual do Projeto
O sistema roda como servidor web Flask local. A interface web está funcional e validada com dados reais. Todos os motores (Postes, Estais, Alças/Laços) estão implementados, integrados e com resultados confirmados. O motor de Alças/Laços possui planilha de validação opcional e sistema de aviso para estruturas novas não cadastradas na receita.

**Árvore de Diretórios:**
> sistema_quantitativos/
> ├── data/
> │   ├── config/               # Contém: "receita_alcas_lacos.csv"
> │   ├── input/                # (pasta mantida, mas arquivos não são mais salvos aqui pelo servidor)
> │   └── output/               # Recebe: "RMT_Output_Completo.xlsx", "Quantitativo_Postes_Isolado.xlsx", "Validacao_Alcas_Lacos.xlsx" (opcional)
> ├── src/
> │   ├── __init__.py
> │   ├── leitor_excel.py       # (OK) Empilha abas, limpa cabeçalhos, aceita caminho OU BytesIO.
> │   ├── motor_postes.py       # (OK) Separa Altura/Carga e formata string.
> │   ├── motor_estais.py       # (OK) Soma global e multiplica por receita fixa.
> │   ├── exportador.py         # (OK) Salva em .xlsx (requer openpyxl).
> │   ├── motor_alcas_lacos.py  # (OK) Retorna tupla (df_resultado, avisos). Funções: calcular_alcas_lacos() e gerar_tabela_validacao().
> │   └── interface.py          # (OBSOLETO) Tkinter — não é mais usado, pode ser deletado.
> ├── templates/
> │   └── index.html            # (OK) Interface web completa. Seção "Opções adicionais" com checkbox para planilha de validação.
> └── main.py                   # (OK) Servidor Flask: rotas /, /preview, /processar, /download.

---

## 7. Próxima Tarefa Imediata
Nenhuma pendência crítica identificada. O motor de Alças/Laços foi validado com dados reais e está correto. Possíveis evoluções futuras:
* Avaliar a necessidade de incluir novos TIPOs de estrutura na `receita_alcas_lacos.csv` à medida que aparecerem avisos `⚠` em novos projetos.
* Avaliar escopo de ferragens gerais e fibra óptica (descartados do MVP) para futuras fases.