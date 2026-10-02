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
* **Fase 10: Motor de Parafusos:** O usuário forneceu `PARAFUSOS POR ESTRUTURA.xlsx` (exportado da `CALCULADORA PARAFUSO 2.0.xlsx`, uma calculadora geométrica de 34 abas já validada — **não reimplementada em Python**, só consultada). A planilha tem 3 abas (TIPICAS, ESPECIAIS, TE) com uma linha por especificação de parafuso (TIPO+ESFORÇO+POSIÇÃO+PARAFUSO+ESF_PARAFUSO, e ALTURA para estruturas TR-CH/TE dependentes de altura) e colunas de comprimento comercial (200–900mm, de 50 em 50) onde a célula é a quantidade. Decisões de modelagem, fechadas por rodadas de perguntas ao usuário: (1) a coluna `COMECO` (valores `C`/`I`) só existe na família N3-3/2N3-3/N4-N3-3 e indica o sentido de chegada dos cabos (`C` = chega pelo 1º nível, `I` = chega pelo nível inferior) — informação só visível na planta perfil (DWG), nunca derivável da Tabela de Locação. Por isso ela é resolvida **manualmente pelo usuário na interface web**, nunca automaticamente, mesmo quando só existe uma variante cadastrada na receita (a receita é alimentada aos poucos conforme obras reais aparecem, então "só ter C hoje" não decide o caso — pode surgir "I" amanhã). (2) `ESF_PARAFUSO` (50 ou 70, classe em kN) são parafusos fisicamente diferentes e nunca somam juntos. (3) A coluna `CRUZETA ADICIONAL` (1 ou 2, repetida em todas as linhas do mesmo bloco de estrutura) não é material novo — é uma quantidade extra do item **código 36** ("Viga tipo U") que já existe na receita de ferragens (`materiais_poste`), e deve ser somada **uma vez por estrutura**, não uma vez por linha de parafuso repetida. Implementação: tabela `parafusos_receita` no banco (seed de `config/PARAFUSOS POR ESTRUTURA.xlsx`, concatenando `TIPO+"."+COMECO` na gravação, ex. `N3-3`+`C` → `N3-3.C`); `src/motor_parafusos.py` com `identificar_estruturas_ambiguas()` e `calcular_parafusos(df, resolucoes)`; a rota `/processar` retorna `{'ambiguidade': [...]}` quando encontra TIPOs ambíguos sem sufixo, e a tela `gerar.html` mostra um painel amarelo pedindo pro usuário escolher C/I por estrutura antes de recalcular. O motor decide por tipo se a receita depende de altura (checando se existe algum `altura` não nulo pra aquele TIPO) em vez de assumir isso globalmente — necessário porque TE tem altura real na Locação mas a receita de TE não depende dela.
* **Fase 11: Tela `/parafusos` (CRUD da receita):** O placeholder "em construção" foi substituído por um editor completo. Antes de implementar, o usuário escolheu — entre 3 opções de layout apresentadas com mockups (grade estilo planilha, lista de linhas simples, formulário guiado) — o formato de **grade estilo planilha**: linhas = especificação (POSIÇÃO + PARAFUSO + CLASSE kN), colunas = os 15 comprimentos comerciais fixos (200 a 900mm, de 50 em 50, confirmados lendo `PARAFUSOS POR ESTRUTURA.xlsx` via Excel COM), célula = quantidade. Fluxo: dropdowns em cascata TIPO → ESFORÇO → ALTURA (só aparece se o combo tiver variantes de altura) carregam a grade daquela combinação; "+ Nova estrutura" abre um mini-formulário (TIPO, ESFORÇO, checkbox "depende de altura?") que inicia uma grade vazia. `CRUZETA ADICIONAL` é editada como um único campo por combinação (não por linha), mas gravada denormalizada em cada linha no banco — mesmo padrão do seed original. Novos TIPOs com sufixo `.C`/`.I` (ex: `N3-3.C`) são automaticamente reconhecidos como ambíguos pelo motor sem nenhuma mudança de código, porque `listar_tipos_ambiguos_parafusos()` deriva isso do sufixo do próprio TIPO gravado. Implementação: `src/banco.py` ganhou `listar_estruturas_parafusos()`, `obter_grade_parafusos()`, `salvar_grade_parafusos()` e `excluir_estrutura_parafusos()`; `main.py` ganhou as rotas `/parafusos/api/estruturas`, `/parafusos/api/grade`, `/parafusos/api/salvar` e `/parafusos/api/excluir`. Testado ponta a ponta via HTTP (listar, carregar grade de estruturas reais, criar/salvar/excluir uma estrutura de teste) sem afetar as 48 combinações já semeadas. Sobre o comportamento quando um TIPO da Locação não tem receita cadastrada: **já era tratado** desde a Fase 10 — o motor não bloqueia o processamento, só ignora aquele TIPO e emite um aviso ⚠ (mesmo padrão de Ferragens/Fase 9); esse gap virou justamente o motivador da Fase 11, já que agora existe uma tela para cadastrar o que falta em vez de precisar tocar no banco na mão.
* **Fase 12: Hardening (robustez, segurança e correções):** Após uma análise completa do código, foram aplicadas as correções priorizadas: (1) rota `/download` trocada de `send_file` com `os.path.join` para `send_from_directory`, fechando path traversal (o caso `..%5C` com backslash servia `data/sistema.db`); (2) `motor_postes` e `motor_estais` passaram a retornar `(df, avisos)` como os demais motores e não quebram mais com `KeyError` se a coluna (`ALTURA / CARGA` / `ESTAIS`) não existir na Locação — emitem aviso ⚠ e seguem; (3) `motor_estais` não modifica mais o DataFrame compartilhado in-place (a conversão `to_numeric` opera numa cópia da série); (4) `gerar.html` ganhou `esc()` e escapa tudo que vem do Excel/servidor antes de injetar via innerHTML (preview, painel de ambiguidade, cabos, mensagens de erro); (5) o painel de ambiguidade C/I **não vem mais com "C" pré-marcado** — a escolha precisa ser feita conscientemente (regra da Fase 10) e o botão valida que todas as estruturas foram respondidas; (6) `exportar_para_excel` agora propaga a exceção (antes engolia e o processamento "concluía" sem gerar arquivo) e o `/processar` mostra no log web a dica de fechar a planilha quando dá `PermissionError`; (7) o `@app.errorhandler(Exception)` global deixou de converter erros HTTP legítimos (404 etc.) em 500 — `HTTPException` passa direto; (8) criado `requirements.txt` (flask, pandas, openpyxl). Validado ponta a ponta com uma Locação sintética (estrutura ambígua 2N3-3 + TIPO inexistente): detecção de ambiguidade, resolução, avisos ⚠ nos 3 motores de receita e exportação — tudo OK. Nota operacional descoberta no teste: o Werkzeug usa `SO_REUSEADDR`, então no Windows **duas instâncias do servidor podem escutar a porta 5000 ao mesmo tempo** sem erro — se um teste responder com comportamento "antigo", verificar processos python órfãos (`netstat -ano | findstr :5000`).

* **Fase 13: Avisos ⚠ com o número do poste:** Os avisos de receita ausente/incompleta passaram a informar **quais postes** foram ignorados, no formato `... — ignorada [postes 10/1A, 11/1A]`. Foram criados dois helpers compartilhados em `src/leitor_excel.py`: `formatar_numeros_postes(numeros)` (dedup + rótulo singular/plural + fallback `(sem número)`) e `numeros_por_tipo(df, tipo)` (lista os números de um TIPO na Locação). Aplicados nos 3 motores de receita: Parafusos (as 4 mensagens — tipo ausente, ambiguidade não confirmada, esforço não cadastrado, posição/altura incompleta), Ferragens e Alças/Laços. No motor de parafusos, o `groupby` já agregava `NUMEROS`, então os números saem direto do agrupamento; o aviso de "TIPO sem nenhuma receita" passou a ser **acumulado e emitido uma vez por TIPO** (antes repetia a mesma frase em cada combinação de esforço/altura/posição, o que ficaria muito verboso com a lista de postes anexada).

* **Fase 14: Multi-parque e Import/Export das Receitas:** O usuário levantou duas necessidades: (1) tudo que estava no banco era do parque **Dom Inocêncio**, e materiais/premissas variam conforme cliente e projeto, então as receitas precisavam ser separadas por obra; (2) poder baixar as receitas cadastradas em arquivo e cadastrar a partir de um arquivo. Decisões fechadas em três rodadas de perguntas: as **4 receitas** ficam por parque (Ferragens, Parafusos, Alças/Laços e Estais); seleção por **dropdown global no header**, persistida entre reinícios; parque novo pode **começar vazio ou copiar as receitas de outro**; cadastro guarda nome + cliente + observações + datas; formato **.xlsx, um arquivo por receita**. Semântica da importação, nas palavras do usuário: *"subo uma estrutura existente, ele apaga tudo dessa estrutura e cadastra conforme o arquivo passado, porém não deve fazer nenhuma alteração das estruturas já existentes"* — ou seja, substituição por unidade, com o resto intacto. A unidade é o TIPO (Ferragens e Alças/Laços), o combo TIPO+ESFORÇO+ALTURA (Parafusos) ou a lista inteira (Estais). Consequência aceita: **não se exclui estrutura subindo arquivo** — uma unidade que chegue sem linhas aproveitáveis é ignorada com aviso, nunca apagada. Implementado em 5 etapas, uma commit cada: (1) banco — tabela `parques`, `app_estado` (parque ativo), `parque_id` com FK `ON DELETE CASCADE` em tudo, tabelas novas `alcas_lacos_receita` e `estais_receita`, e migração versionada por `PRAGMA user_version` que recria as duas tabelas legadas (SQLite não permite `ADD COLUMN NOT NULL` com FK) atribuindo tudo ao Dom Inocêncio; (2) motores lendo a receita do parque — `motor_estais` deixou o dicionário fixo e `motor_alcas_lacos` deixou de ler o CSV, ambos agora vêm do banco, e o `main.py` resolve o parque **uma vez por requisição** para que uma troca no meio do processamento não misture obras; (3) seletor no header + tela `/parques`; (4) telas `/alcas` e `/estais`; (5) `src/planilhas.py` com as 4 exportações/importações + `templates/_backup.html` incluído pelas 4 telas de receita. `parque_id` é **opcional** em todas as funções de `banco.py` e resolve para o parque ativo quando omitido — foi assim que as etapas puderam ser entregues uma a uma sem nunca deixar o sistema quebrado.

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
* **Erro de linhas duplicadas na exportação de Parafusos (`NaN` como chave de agrupamento):** A exportação agrupa as linhas da receita por especificação (TIPO, ESFORÇO, ALTURA, POSIÇÃO, PARAFUSO, ESF_PARAFUSO, COMECO) para montar uma linha com uma coluna por comprimento. Como `altura` nula vem do banco via `read_sql` como `NaN`, e `NaN` nunca é igual a si mesmo, cada linha de receita sem altura gerava uma chave nova no dicionário — a tabela saía com uma linha por comprimento em vez de uma por especificação. A correção foi normalizar `altura` e `cruzeta_adicional` para `None` (via `pd.isna`) antes de montar a chave. Mesma família do erro de `None` nas alças/laços: valor nulo que não se comporta como esperado numa comparação.

* **Erro de `None` espúrio nas Alças/Laços (contagens incorretas):** O uso de `groupby().transform(lambda s: s.astype(str).shift(1))` gerava Python `None` (não `numpy.NaN`) como fill do primeiro elemento de cada grupo. `str(None)` resulta em `'None'`, que passava pelo filtro `cabo.lower() == 'nan'` e criava itens fantasma no quantitativo. A correção foi inverter a ordem: `df.groupby('_letra_circuito')[col].shift(1)` nos valores originais antes de qualquer conversão para string, garantindo que o fill seja `NaN` → coberto pelo filtro `in ('nan', 'none', '<na>')`.

---

## 5. Preferências do Usuário e Convenções
* **Arquitetura Limpa:** Separação rígida de responsabilidades. O `main.py` cuida da UI e orquestração; o `leitor_excel.py` cuida da extração; os módulos `motor_*.py` cuidam exclusivamente da matemática; e o `exportador.py` salva os dados.
* **Transparência Visual:** O log de atividades na interface web (div escura no fundo da página) deve sempre registrar os passos (Leitura, Cálculo, Consolidação, Exportação), com cores diferenciadas: verde (`✓`) para sucesso, vermelho (`✗`) para erro, cinza para info, amarelo (`⚠`) para avisos não-bloqueantes.
* **Relatórios Isolados:** A geração de listas deve ser flexível, gerando um Master unificado e relatórios isolados (como o de Postes).
* **Desenvolvimento Guiado:** Em regras de negócio complexas, o usuário prefere ditar a lógica passo a passo, em vez de a IA assumir formatos de planilha e criar códigos complexos sem validação.

---

## 6. Estado Atual do Projeto
O sistema roda como servidor web Flask local, multi-página. Todos os motores (Postes, Estais, Alças/Laços, Ferragens, Parafusos) estão implementados e integrados na tela `/gerar`. O banco SQLite (`data/sistema.db`) é a fonte única de verdade das **4 receitas** (Ferragens, Parafusos, Alças/Laços e Estais), semeado dos arquivos de `config/` só quando o banco está vazio.

As receitas são separadas por **parque** (obra/cliente), escolhido num seletor no header presente em todas as telas e persistido no banco. Cada receita tem sua tela de cadastro (`/materiais`, `/parafusos`, `/alcas`, `/estais`) e botões de baixar/importar `.xlsx`; a tela `/parques` gerencia as obras, criando-as vazias ou copiando as receitas de outra. Postes é o único motor que não depende de receita, então sai igual em qualquer parque.

**Atenção:** os arquivos de `config/` são apenas seed de banco vazio. Editá-los não altera nada num banco já criado — o cadastro é pelas telas ou pela importação de `.xlsx`.

**Árvore de Diretórios:**
> sistema_quantitativos/
> ├── config/                        # Seeds do banco (lidos SÓ quando o banco está vazio; editar não afeta banco existente)
> │   ├── QUANTIDADE-MATERIAIS.xlsx      # Seed de materiais_poste (ferragens gerais + item 36 "Viga tipo U")
> │   ├── PARAFUSOS POR ESTRUTURA.xlsx   # Seed de parafusos_receita (abas TIPICAS/ESPECIAIS/TE)
> │   ├── CALCULADORA PARAFUSO 2.0.xlsx  # Calculadora geométrica original (34 abas) — só referência, não é lida pelo código
> │   ├── receita_alcas_lacos.csv        # Seed de alcas_lacos_receita (TIPO·NÍVEL·DIREÇÃO)
> │   └── receita_estais.csv             # Seed de estais_receita (saiu do dicionário fixo do motor_estais)
> ├── data/
> │   ├── output/                # RMT_Output_Completo.xlsx, Quantitativo_Postes_Isolado.xlsx, Validacao_Alcas_Lacos.xlsx (opcional)
> │   └── sistema.db             # Banco SQLite (gitignored) — parques, app_estado e as 4 receitas com parque_id
> │                              # (a antiga data/input/ foi removida — uploads vão direto pra memória)
> ├── src/
> │   ├── __init__.py
> │   ├── banco.py              # (OK) Schema, migração (user_version), seed, CRUD das 4 receitas e dos parques. parque_id opcional = parque ativo.
> │   ├── planilhas.py          # (OK) Exporta/importa as 4 receitas em .xlsx. Registro RECEITAS usado pelas rotas genéricas.
> │   ├── leitor_excel.py       # (OK) Empilha abas, limpa cabeçalhos, aceita caminho OU BytesIO. Tem detectar_coluna_numero().
> │   ├── motor_postes.py       # (OK) Separa Altura/Carga e formata string. Único motor sem receita — não depende de parque.
> │   ├── motor_estais.py       # (OK) Soma a coluna ESTAIS e multiplica pela receita do parque (estais_receita).
> │   ├── motor_alcas_lacos.py  # (OK) Retorna (df_resultado, avisos). Lê alcas_lacos_receita do banco (não mais o CSV).
> │   ├── motor_ferragens.py    # (OK) Retorna (df_resultado, avisos), lê receita do parque. gerar_tabela_validacao_ferragens() pivotada.
> │   ├── motor_parafusos.py    # (OK) identificar_estruturas_ambiguas() e calcular_parafusos(df, resolucoes, parque_id).
> │   ├── exportador.py         # (OK) Salva os RESULTADOS em .xlsx (requer openpyxl). Múltiplas abas e abas lado-a-lado.
> │   └── interface.py          # (OBSOLETO) Tkinter — não é mais usado, pode ser deletado.
> ├── templates/
> │   ├── base.html             # (OK) Layout comum + seletor de parque no header (presente em todas as telas).
> │   ├── _backup.html          # (OK) Bloco de baixar/importar .xlsx, incluído pelas 4 telas de receita via {% set receita = '...' %}.
> │   ├── home.html             # (OK) Menu inicial com 6 cards.
> │   ├── gerar.html            # (OK) Upload, preview, seleção de motores, cabos manuais, painel de ambiguidade C/I, log, downloads.
> │   ├── parques.html          # (OK) CRUD de obras: criar (vazio ou copiando), editar, usar e excluir (cascade).
> │   ├── materiais.html        # (OK) CRUD da receita de ferragens por TIPO.
> │   ├── parafusos.html        # (OK) CRUD em grade (posição/parafuso/classe × comprimento) da receita de parafusos.
> │   ├── alcas.html            # (OK) CRUD em grade por nível (alças/laços × vante/ré). Achata as 2 direções numa linha só.
> │   └── estais.html           # (OK) CRUD da lista de materiais de um estai.
> ├── requirements.txt           # flask, pandas, openpyxl
> └── main.py                   # (OK) Servidor Flask. Resolve o parque ativo 1x por requisição (_parque_ativo_id) e injeta no header
>                               # via context processor. Rotas: /, /gerar, /materiais, /parafusos, /alcas, /estais, /parques,
>                               # /preview, /processar, /download, e as APIs /materiais/api/*, /parafusos/api/*, /alcas/api/*,
>                               # /estais/api/*, /parques/api/*, /receitas/api/{exportar,importar}/<receita>.

* **Fase 15: Preparação para Nuvem (Render + Turso):** O usuário solicitou que o sistema rodasse 100% na web. A arquitetura escolhida foi a hospedagem contínua no **Render** com banco de dados **Turso** (LibSQL gerenciado na nuvem). Adaptações implementadas: (1) `src/banco.py` ganhou detecção automática de `TURSO_DATABASE_URL` e `TURSO_AUTH_TOKEN` conectando via `libsql` com wrappers `LibSqlConnection`, `LibSqlCursor` e `LibSqlRow` que mantêm compatibilidade com a interface `sqlite3.Row` e evitam avisos do Pandas; se as variáveis não forem informadas, recai no SQLite local `data/sistema.db`; (2) `requirements.txt` atualizado com `gunicorn>=21.0` e `libsql>=0.1.0`; (3) criado `render.yaml` (manifesto de infraestrutura como código para deploy automático); (4) criado `scripts/testar_turso.py` para validação rápida da conexão com a nuvem antes do deploy.

* **Fase 16: Calculadora e Dimensionamento Automático de Parafusos:** Implementação de uma nova aba interativa no menu (`/dimensionar-parafusos`) baseada na modelagem modular do Google Sheets do usuário (abas `PADRAO` e `ESTRUTURAS`). A engine geométrica (`src/calculadora_parafusos.py`) calcula a seção do poste duplo T (Faces A e B) a partir do esforço (600 a 3000 daN) e da cota de cada nível (distância ou `CH+...`), soma as espessuras de ferragens (cruzetas, porcas, arruelas, olhais e sobra) e arredonda para o comprimento comercial padrão. O usuário pode selecionar estruturas do catálogo (19 estruturas embutidas) ou criar novas, editar cotas e montagens em tempo real, visualizar o cálculo nível a nível e, ao validar, clicar em "Validar e Adicionar à Receita" para gravar a estrutura dimensionada diretamente em `parafusos_receita` do parque ativo sem alterar as demais estruturas.

* **Fase 17: Detecção Ampla de Ambiguidades N3-3:** A detecção de estruturas ambíguas que exigem a escolha do sentido de chegada dos cabos (.C ou .I) no motor de parafusos foi ampliada. Em vez de depender exclusivamente da correspondência exata com as receitas cadastradas no banco, o motor passou a utilizar a função `eh_tipo_ambiguo()`, que reconhece qualquer estrutura que contenha "N3-3" em qualquer parte da sua nomenclatura (e que ainda não possua sufixo .C ou .I), além de manter o suporte às bases cadastradas no banco.

* **Fase 18: Conicidade Paramétrica, Comprimentos Comerciais Dinâmicos (>900 mm) e Cruzetas Adicionais:**
  1. **Comprimentos Comerciais Flexíveis:** O dimensionamento e a matriz comercial de parafusos deixaram de ter um teto rígido em 900 mm, passando a suportar comprimentos variáveis em passos contínuos de 50 mm (200, 250, ..., 900, 950, 1000, 1050 mm...). A expansão é automática tanto na grade web quanto na exportação Excel (`planilhas.py`), além de botões para inserção manual de colunas adicionais.
  2. **Parametrização de Conicidade e Dimensões do Poste:** Adicionado modal de configuração rápida para inspeção e ajuste das dimensões de topo e conicidades das Faces A (Topo) e B (Gaveta), com persistência por parque e explicação detalhada da metodologia física no memorial de cálculo.
  3. **Cruzetas Adicionais e Agrupamento de Níveis:** Lógica aprimorada para expansão de cruzetas adicionais por cota variável (CH), cálculo cumulativo arredondado em passos de 0,1 m, alinhamento visual no resumo e consolidação de múltiplas linhas de montagem pertencentes a um mesmo nível físico.

---

## 3. Alternativas Consideradas e Descartadas
* **Vercel vs. Render:** A Vercel foi considerada para rodar o backend Python como Serverless Function (AWS Lambda). Foi descartada em favor do Render devido ao overhead de cold-starts frequentes com Pandas/NumPy, limites de timeout curto (10-15s) e sistema de arquivos stateless/efêmero que exigiria reestruturar a exportação para streaming exclusivo em memória. O Render provê execução nativa WSGI contínua sem cold-starts.

---

## 6. Estado Atual do Projeto
O sistema está preparado tanto para execução local quanto para deploy 100% na nuvem no Render com banco Turso. Todos os motores (Postes, Estais, Alças/Laços, Ferragens, Parafusos) e a nova Calculadora de Dimensionamento Automático estão operantes e testados.

**Árvore de Diretórios:**
> sistema_quantitativos/
> ├── config/                        # Seeds do banco (lidos SÓ quando o banco está vazio)
> ├── data/
> │   ├── output/                # RMT_Output_Completo.xlsx, Quantitativo_Postes_Isolado.xlsx, etc.
> │   └── sistema.db             # Banco SQLite local (fallback caso TURSO_* não esteja configurado)
> ├── scripts/
> │   └── testar_turso.py        # Validação da conexão Turso na nuvem
> ├── src/
> │   ├── banco.py              # (OK) Suporte híbrido SQLite local + Turso Cloud (LibSQL)
> │   ├── calculadora_parafusos.py # (OK) Motor geométrico de dimensionamento por montagens e níveis
> │   ├── planilhas.py          # (OK) Exporta/importa as 4 receitas em .xlsx
> │   ├── leitor_excel.py       # (OK) Empilha abas, limpa cabeçalhos
> │   ├── motor_postes.py       # (OK) Separa Altura/Carga e formata string
> │   ├── motor_estais.py       # (OK) Quantitativo de estais
> │   ├── motor_alcas_lacos.py  # (OK) Alças e laços
> │   ├── motor_ferragens.py    # (OK) Ferragens por tipo
> │   ├── motor_parafusos.py    # (OK) Parafusos por comprimento
> │   ├── exportador.py         # (OK) Salva relatórios em .xlsx
> │   └── consolidador.py       # (OK) Consolidação de materiais
> ├── templates/               # (OK) Templates Jinja2 (dimensionar_parafusos.html, etc.)
> ├── requirements.txt         # flask, pandas, openpyxl, gunicorn, libsql
> ├── render.yaml              # Manifesto de deploy no Render
> └── main.py                  # Servidor Flask / WSGI app para Gunicorn

---

## 7. Próxima Tarefa Imediata
* Criar conta e banco no Turso e configurar `TURSO_DATABASE_URL` e `TURSO_AUTH_TOKEN` no Render.
* Conectar repositório GitHub ao Render e executar o primeiro deploy.

**Nota operacional:** nesta máquina `git` e `python` não estão no PATH — usar
`C:\Users\vinicius.araujo\AppData\Local\Programs\Git\cmd\git.exe` e
`C:\Users\vinicius.araujo\AppData\Local\Programs\Python\Python312\python.exe`.