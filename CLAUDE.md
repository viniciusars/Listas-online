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
* **Fase 9: Reestruturação Multi-página, Banco SQLite e Motor de Ferragens:** A página única (`index.html`) virou um menu inicial (`home.html`) com 3 cards de navegação: "Gerar Quantitativos" (`/gerar`, motores de cálculo), "Materiais por Poste" (`/materiais`, CRUD da receita de ferragens) e "Cadastrar Parafusos" (`/parafusos`, ainda placeholder). Foi criado `src/banco.py`, uma camada SQLite (`data/sistema.db`, gitignored) que passou a ser a **fonte única de verdade** das receitas — os motores não leem mais Excel diretamente. Na primeira execução, se as tabelas estiverem vazias, o banco é semeado a partir dos arquivos em `config/`. A receita de ferragens gerais (antes descartada do MVP) foi implementada em `src/motor_ferragens.py`, semeada de `config/QUANTIDADE-MATERIAIS.xlsx` (uma aba por TIPO de estrutura), com o mesmo padrão de avisos ⚠ para tipos sem receita cadastrada e uma `gerar_tabela_validacao_ferragens()` pivotada por material×tipo. A tela `/materiais` permite listar, editar e substituir globalmente valores de um campo (ex: trocar um código de material em todos os registros de uma vez).
* **Fase 10: Motor de Parafusos:** O usuário forneceu `PARAFUSOS POR ESTRUTURA.xlsx` (exportado da `CALCULADORA PARAFUSO 2.0.xlsx`, uma calculadora geométrica de 34 abas já validada — **não reimplementada em Python**, só consultada). A planilha tem 3 abas (TIPICAS, ESPECIAIS, TE) com uma linha por especificação de parafuso (TIPO+ESFORÇO+POSIÇÃO+PARAFUSO+ESF_PARAFUSO, e ALTURA para estruturas TR-CH/TE dependentes de altura) e colunas de comprimento comercial (200–900mm) onde a célula é a quantidade. Decisões de modelagem, fechadas por rodadas de perguntas ao usuário: (1) a coluna `COMECO` (valores `C`/`I`) só existe na família N3-3/2N3-3/N4-N3-3 e indica o sentido de chegada dos cabos (`C` = chega pelo 1º nível, `I` = chega pelo nível inferior) — informação só visível na planta perfil (DWG), nunca derivável da Tabela de Locação. Por isso ela é resolvida **manualmente pelo usuário na interface web**, nunca automaticamente, mesmo quando só existe uma variante cadastrada na receita (a receita é alimentada aos poucos conforme obras reais aparecem, então "só ter C hoje" não decide o caso — pode surgir "I" amanhã). (2) `ESF_PARAFUSO` (50 ou 70, classe em kN) são parafusos fisicamente diferentes e nunca somam juntos. (3) A coluna `CRUZETA ADICIONAL` (1 ou 2, repetida em todas as linhas do mesmo bloco de estrutura) não é material novo — é uma quantidade extra do item **código 36** ("Viga tipo U") que já existe na receita de ferragens (`materiais_poste`), e deve ser somada **uma vez por estrutura**, não uma vez por linha de parafuso repetida. Implementação: tabela `parafusos_receita` no banco (seed de `config/PARAFUSOS POR ESTRUTURA.xlsx`, concatenando `TIPO+"."+COMECO` na gravação, ex. `N3-3`+`C` → `N3-3.C`); `src/motor_parafusos.py` com `identificar_estruturas_ambiguas()` e `calcular_parafusos(df, resolucoes)`; a rota `/processar` retorna `{'ambiguidade': [...]}` quando encontra TIPOs ambíguos sem sufixo, e a tela `gerar.html` mostra um painel amarelo pedindo pro usuário escolher C/I por estrutura antes de recalcular. O motor decide por tipo se a receita depende de altura (checando se existe algum `altura` não nulo pra aquele TIPO) em vez de assumir isso globalmente — necessário porque TE tem altura real na Locação mas a receita de TE não depende dela.

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
O sistema roda como servidor web Flask local, multi-página. Todos os motores (Postes, Estais, Alças/Laços, Ferragens, Parafusos) estão implementados e integrados na tela `/gerar`. O banco SQLite (`data/sistema.db`) é a fonte de verdade das receitas de Ferragens e Parafusos, semeado automaticamente dos arquivos de `config/` na primeira execução. O motor de Parafusos foi validado com dados reais (arquivo de exemplo `LOCACAO - EDIV 14 - 0B.xlsx`) via teste HTTP ponta a ponta: detecção de ambiguidade C/I, resolução manual, cálculo de comprimentos/classes e incremento do item 36 — todos corretos. A tela `/parafusos` (CRUD de edição da receita) ainda é um placeholder "em construção", mas não bloqueia o cálculo.

**Árvore de Diretórios:**
> sistema_quantitativos/
> ├── config/                        # Seeds do banco (lidos só na 1ª execução, se as tabelas estiverem vazias)
> │   ├── QUANTIDADE-MATERIAIS.xlsx      # Seed de materiais_poste (ferragens gerais + item 36 "Viga tipo U")
> │   ├── PARAFUSOS POR ESTRUTURA.xlsx   # Seed de parafusos_receita (abas TIPICAS/ESPECIAIS/TE)
> │   ├── CALCULADORA PARAFUSO 2.0.xlsx  # Calculadora geométrica original (34 abas) — só referência, não é lida pelo código
> │   └── receita_alcas_lacos.csv        # Receita de alças/laços por TIPO·NÍVEL·DIREÇÃO
> ├── data/
> │   ├── input/                # Não é mais usada pelo servidor (uploads vão direto pra memória)
> │   ├── output/                # RMT_Output_Completo.xlsx, Quantitativo_Postes_Isolado.xlsx, Validacao_Alcas_Lacos.xlsx (opcional)
> │   └── sistema.db             # Banco SQLite (gitignored) — materiais_poste + parafusos_receita
> ├── src/
> │   ├── __init__.py
> │   ├── banco.py              # (OK) Schema + seed + CRUD de materiais_poste e parafusos_receita. Fonte única de verdade das receitas.
> │   ├── leitor_excel.py       # (OK) Empilha abas, limpa cabeçalhos, aceita caminho OU BytesIO. Tem detectar_coluna_numero().
> │   ├── motor_postes.py       # (OK) Separa Altura/Carga e formata string.
> │   ├── motor_estais.py       # (OK) Soma global e multiplica por receita fixa.
> │   ├── motor_alcas_lacos.py  # (OK) Retorna (df_resultado, avisos). Funções: calcular_alcas_lacos() e gerar_tabela_validacao().
> │   ├── motor_ferragens.py    # (OK) Retorna (df_resultado, avisos), lê receita do banco. gerar_tabela_validacao_ferragens() pivotada.
> │   ├── motor_parafusos.py    # (OK) identificar_estruturas_ambiguas() e calcular_parafusos(df, resolucoes) -> (df, incremento_item36, avisos).
> │   ├── exportador.py         # (OK) Salva em .xlsx (requer openpyxl). Suporta múltiplas abas e abas lado-a-lado.
> │   └── interface.py          # (OBSOLETO) Tkinter — não é mais usado, pode ser deletado.
> ├── templates/
> │   ├── base.html             # (OK) Layout comum (header, estilos base, spinner).
> │   ├── home.html             # (OK) Menu inicial com 3 cards.
> │   ├── gerar.html            # (OK) Upload, preview, seleção de motores, cabos manuais, painel de ambiguidade C/I, log, downloads.
> │   ├── materiais.html        # (OK) CRUD da receita de ferragens por TIPO.
> │   └── parafusos.html        # (PLACEHOLDER) "Em construção" — tela de edição da receita de parafusos ainda não feita.
> └── main.py                   # (OK) Servidor Flask: rotas /, /gerar, /materiais, /parafusos, /preview, /processar, /download, /materiais/api/*.

---

## 7. Próxima Tarefa Imediata
Nenhuma pendência crítica identificada. Possíveis evoluções futuras:
* Construir a tela `/parafusos` como CRUD de edição da receita `parafusos_receita` (hoje só editável via re-seed do Excel), espelhando o padrão já usado em `/materiais`.
* Avaliar a necessidade de incluir novos TIPOs de estrutura nas receitas (`receita_alcas_lacos.csv`, `materiais_poste`, `parafusos_receita`) à medida que aparecerem avisos `⚠` em novos projetos.
* Avaliar escopo de fibra óptica (descartado do MVP) para futuras fases.