"""Camada de persistência do sistema (SQLite).

Fonte única de verdade das receitas. O banco fica em data/sistema.db (não
versionado). Na primeira execução, se a tabela estiver vazia, é populado
automaticamente a partir de config/QUANTIDADE-MATERIAIS.xlsx (seed).

Os motores NÃO leem mais o Excel diretamente — consomem este módulo.
O Excel continua servindo como seed inicial e destino de exportação (backup).
"""

import os
import sqlite3
import pandas as pd

CAMINHO_DB = os.path.join('data', 'sistema.db')
CAMINHO_SEED_FERRAGENS = os.path.join('config', 'QUANTIDADE-MATERIAIS.xlsx')
CAMINHO_SEED_PARAFUSOS = os.path.join('config', 'PARAFUSOS POR ESTRUTURA.xlsx')

# Sufixos usados para desambiguar estruturas cuja receita de parafusos muda
# conforme o sentido de chegada dos cabos (só visível na planta perfil/DWG).
SUFIXOS_PARAFUSOS_AMBIGUOS = ('.C', '.I')


# ---------------------------------------------------------------------------
# Conexão e schema
# ---------------------------------------------------------------------------
def conectar():
    """Abre conexão com row_factory para acesso por nome de coluna."""
    os.makedirs(os.path.dirname(CAMINHO_DB), exist_ok=True)
    conn = sqlite3.connect(CAMINHO_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _criar_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS materiais_poste (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo       TEXT    NOT NULL,
            ordem      INTEGER NOT NULL,
            codigo     TEXT,
            descricao  TEXT    NOT NULL,
            unidade    TEXT,
            quantidade REAL    NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_materiais_tipo ON materiais_poste(tipo)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parafusos_receita (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo              TEXT    NOT NULL,
            esforco           REAL    NOT NULL,
            altura            REAL,
            posicao           TEXT    NOT NULL,
            parafuso          TEXT    NOT NULL,
            esf_parafuso      REAL    NOT NULL,
            comprimento       INTEGER NOT NULL,
            quantidade        REAL    NOT NULL,
            cruzeta_adicional REAL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_parafusos_tipo ON parafusos_receita(tipo)"
    )
    conn.commit()


def inicializar():
    """Cria o schema e, se a receita de ferragens estiver vazia, faz o seed do xlsx."""
    conn = conectar()
    try:
        _criar_schema(conn)
        vazio = conn.execute("SELECT COUNT(*) FROM materiais_poste").fetchone()[0] == 0
        if vazio:
            if os.path.exists(CAMINHO_SEED_FERRAGENS):
                receita = _parse_xlsx_ferragens(CAMINHO_SEED_FERRAGENS)
                _gravar_receita_ferragens(conn, receita)
                total = sum(len(v) for v in receita.values())
                print(f"[BANCO] Seed inicial: {total} materiais em {len(receita)} tipos "
                      f"importados de {CAMINHO_SEED_FERRAGENS}")
            else:
                print(f"[BANCO] AVISO: {CAMINHO_SEED_FERRAGENS} não encontrado — "
                      "banco de ferragens iniciará vazio.")

        vazio_parafusos = conn.execute("SELECT COUNT(*) FROM parafusos_receita").fetchone()[0] == 0
        if vazio_parafusos:
            if os.path.exists(CAMINHO_SEED_PARAFUSOS):
                linhas = _parse_xlsx_parafusos(CAMINHO_SEED_PARAFUSOS)
                _gravar_receita_parafusos(conn, linhas)
                print(f"[BANCO] Seed inicial: {len(linhas)} linhas de receita de parafusos "
                      f"importadas de {CAMINHO_SEED_PARAFUSOS}")
            else:
                print(f"[BANCO] AVISO: {CAMINHO_SEED_PARAFUSOS} não encontrado — "
                      "banco de parafusos iniciará vazio.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Parsing do Excel (seed) — migrado do motor_ferragens
# ---------------------------------------------------------------------------
def _normalizar_tipo(nome_aba):
    """Converte separadores do Excel (' I ' e ' | ') para '/' usado na Tabela de Locação."""
    return nome_aba.replace(' I ', '/').replace(' | ', '/').strip()


def _is_valid_qty(val):
    """Retorna True apenas se val for um número finito maior que zero."""
    try:
        n = float(val)
        return n > 0 and pd.notna(n)
    except (TypeError, ValueError):
        return False


def _parse_xlsx_ferragens(caminho):
    """Lê o Excel e retorna dict {tipo_normalizado: [{codigo, descricao, unidade, qtd}, ...]}."""
    xl = pd.ExcelFile(caminho)
    receita = {}

    for aba in xl.sheet_names:
        if aba.strip().upper() == 'CONTAGEM':
            continue

        tipo = _normalizar_tipo(aba)
        df = xl.parse(aba, header=0)

        materiais = []
        for _, row in df.iterrows():
            item    = row.iloc[0]
            descr   = row.iloc[1]
            unidade = row.iloc[2]
            qty     = row.iloc[3]

            # Linha vazia/separador
            if pd.isna(item) or pd.isna(descr):
                continue

            # Cabeçalho da seção de Fibra Óptica → para o loop desta aba
            if str(item).strip().upper() == 'ITEM':
                if 'FIBRA' in str(descr).upper():
                    break
                continue

            # Quantidade ausente ou variável ("Var.", "var.", NaN)
            if not _is_valid_qty(qty):
                continue

            materiais.append({
                'codigo':    str(item).strip(),
                'descricao': str(descr).strip(),
                'unidade':   str(unidade).strip(),
                'qtd':       float(qty),
            })

        receita[tipo] = materiais

    return receita


_PARAFUSOS_COLS_META = {
    'TIPO', 'ESFORCO', 'ALTURA', 'POSIÇÃO', 'PARAFUSO',
    'ESF_PARAFUSO', 'COMECO', 'CRUZETA ADICIONAL',
}


def _parse_xlsx_parafusos(caminho):
    """Lê as abas TIPICAS/ESPECIAIS/TE e retorna uma lista de linhas planas.

    Cada linha da planilha original tem uma coluna por comprimento comercial
    (200, 250, ... 900mm); aqui cada célula preenchida vira uma linha própria.
    
    Quando a coluna COMECO estiver preenchida ('C' ou 'I'), ela é incorporada
    ao TIPO (ex: 'N3-3' + 'C' -> 'N3-3.C'), pois essa variação só é visível na
    planta perfil (DWG) e precisa ser escolhida manualmente na Locação.
    """
    xl = pd.ExcelFile(caminho)
    linhas = []

    for aba in xl.sheet_names:
        df = xl.parse(aba, header=0)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(how='all')

        cols_comprimento = [c for c in df.columns if c not in _PARAFUSOS_COLS_META]

        for _, row in df.iterrows():
            tipo_base = row.get('TIPO')
            if pd.isna(tipo_base):
                continue
            tipo_base = str(tipo_base).strip()

            comeco = row.get('COMECO')
            if pd.notna(comeco) and str(comeco).strip():
                tipo = f"{tipo_base}.{str(comeco).strip().upper()}"
            else:
                tipo = tipo_base

            try:
                esforco = float(row['ESFORCO'])
            except (TypeError, ValueError):
                continue

            altura = None
            altura_val = row.get('ALTURA')
            if pd.notna(altura_val) and str(altura_val).strip() not in ('', '-'):
                try:
                    altura = float(altura_val)
                except (TypeError, ValueError):
                    altura = None

            posicao = str(row.get('POSIÇÃO', '')).strip().upper()
            parafuso = str(row.get('PARAFUSO', '')).strip().upper()

            try:
                esf_parafuso = float(row['ESF_PARAFUSO'])
            except (TypeError, ValueError):
                continue

            cruzeta_val = row.get('CRUZETA ADICIONAL')
            cruzeta = float(cruzeta_val) if pd.notna(cruzeta_val) else None

            for col in cols_comprimento:
                qtd = row[col]
                if pd.isna(qtd):
                    continue
                try:
                    qtd = float(qtd)
                except (TypeError, ValueError):
                    continue
                if qtd <= 0:
                    continue
                try:
                    comprimento = int(float(col))
                except (TypeError, ValueError):
                    continue

                linhas.append({
                    'tipo': tipo, 'esforco': esforco, 'altura': altura,
                    'posicao': posicao, 'parafuso': parafuso,
                    'esf_parafuso': esf_parafuso, 'comprimento': comprimento,
                    'quantidade': qtd, 'cruzeta_adicional': cruzeta,
                })

    return linhas


def _gravar_receita_parafusos(conn, linhas):
    """Substitui toda a tabela parafusos_receita pelo conteúdo de `linhas`."""
    conn.execute("DELETE FROM parafusos_receita")
    for l in linhas:
        conn.execute(
            "INSERT INTO parafusos_receita "
            "(tipo, esforco, altura, posicao, parafuso, esf_parafuso, comprimento, quantidade, cruzeta_adicional) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (l['tipo'], l['esforco'], l['altura'], l['posicao'], l['parafuso'],
             l['esf_parafuso'], l['comprimento'], l['quantidade'], l['cruzeta_adicional'])
        )
    conn.commit()


def _gravar_receita_ferragens(conn, receita):
    """Substitui toda a tabela materiais_poste pelo conteúdo de `receita`."""
    conn.execute("DELETE FROM materiais_poste")
    for tipo, materiais in receita.items():
        for ordem, mat in enumerate(materiais):
            conn.execute(
                "INSERT INTO materiais_poste (tipo, ordem, codigo, descricao, unidade, quantidade) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (tipo, ordem, mat['codigo'], mat['descricao'], mat['unidade'], mat['qtd'])
            )
    conn.commit()


# ---------------------------------------------------------------------------
# Leitura (consumida pelos motores)
# ---------------------------------------------------------------------------
def ler_receita_ferragens():
    """Retorna dict {tipo: [{codigo, descricao, unidade, qtd}, ...]} a partir do banco.

    Mesma estrutura que o antigo _ler_receita() do motor, para os motores
    consumirem sem alteração de lógica.
    """
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT tipo, codigo, descricao, unidade, quantidade "
            "FROM materiais_poste ORDER BY tipo, ordem"
        ).fetchall()
    finally:
        conn.close()

    receita = {}
    for r in rows:
        receita.setdefault(r['tipo'], []).append({
            'codigo':    r['codigo'],
            'descricao': r['descricao'],
            'unidade':   r['unidade'],
            'qtd':       r['quantidade'],
        })
    return receita


def ler_receita_parafusos_df():
    """Retorna a receita de parafusos completa como DataFrame (para o motor operar em pandas)."""
    conn = conectar()
    try:
        df = pd.read_sql_query(
            "SELECT tipo, esforco, altura, posicao, parafuso, esf_parafuso, "
            "comprimento, quantidade, cruzeta_adicional FROM parafusos_receita",
            conn
        )
    finally:
        conn.close()
    return df


def listar_tipos_ambiguos_parafusos():
    """Bases de TIPO cuja receita de parafusos varia conforme o sentido de chegada dos
    cabos (sufixo .C ou .I) — precisam de confirmação manual quando aparecem sem sufixo."""
    conn = conectar()
    try:
        rows = conn.execute("SELECT DISTINCT tipo FROM parafusos_receita").fetchall()
    finally:
        conn.close()
    bases = set()
    for r in rows:
        tipo = r['tipo']
        if tipo.endswith(SUFIXOS_PARAFUSOS_AMBIGUOS):
            bases.add(tipo[:-2])
    return bases


# ---------------------------------------------------------------------------
# CRUD para a tela "Cadastrar Parafusos"
# ---------------------------------------------------------------------------
def listar_estruturas_parafusos():
    """Lista os combos distintos (tipo, esforco, altura) cadastrados, ordenados.

    Cada combo representa uma "grade" editável na tela de parafusos.
    """
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT DISTINCT tipo, esforco, altura FROM parafusos_receita "
            "ORDER BY tipo, esforco, altura"
        ).fetchall()
    finally:
        conn.close()
    return [{'tipo': r['tipo'], 'esforco': r['esforco'], 'altura': r['altura']} for r in rows]


def obter_grade_parafusos(tipo, esforco, altura=None):
    """Retorna as linhas de receita de um combo tipo+esforço+altura.

    Cada linha: {posicao, parafuso, esf_parafuso, comprimento, quantidade, cruzeta_adicional}.
    """
    conn = conectar()
    try:
        if altura is None:
            rows = conn.execute(
                "SELECT posicao, parafuso, esf_parafuso, comprimento, quantidade, cruzeta_adicional "
                "FROM parafusos_receita WHERE tipo = ? AND esforco = ? AND altura IS NULL",
                (tipo, esforco)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT posicao, parafuso, esf_parafuso, comprimento, quantidade, cruzeta_adicional "
                "FROM parafusos_receita WHERE tipo = ? AND esforco = ? AND altura = ?",
                (tipo, esforco, altura)
            ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def salvar_grade_parafusos(tipo, esforco, altura, cruzeta_adicional, linhas):
    """Substitui todas as linhas de um combo tipo+esforço+altura pelas fornecidas.

    linhas: lista de dicts {posicao, parafuso, esf_parafuso, comprimento, quantidade}.
    cruzeta_adicional é gravado repetido em cada linha (mesmo padrão do seed original).
    Retorna o número de linhas gravadas.
    """
    conn = conectar()
    try:
        if altura is None:
            conn.execute(
                "DELETE FROM parafusos_receita WHERE tipo = ? AND esforco = ? AND altura IS NULL",
                (tipo, esforco)
            )
        else:
            conn.execute(
                "DELETE FROM parafusos_receita WHERE tipo = ? AND esforco = ? AND altura = ?",
                (tipo, esforco, altura)
            )
        for l in linhas:
            conn.execute(
                "INSERT INTO parafusos_receita "
                "(tipo, esforco, altura, posicao, parafuso, esf_parafuso, comprimento, quantidade, cruzeta_adicional) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (tipo, esforco, altura, l['posicao'], l['parafuso'], l['esf_parafuso'],
                 l['comprimento'], l['quantidade'], cruzeta_adicional)
            )
        conn.commit()
    finally:
        conn.close()
    return len(linhas)


def excluir_estrutura_parafusos(tipo, esforco, altura=None):
    """Remove todas as linhas de um combo tipo+esforço+altura. Retorna linhas afetadas."""
    conn = conectar()
    try:
        if altura is None:
            conn.execute(
                "DELETE FROM parafusos_receita WHERE tipo = ? AND esforco = ? AND altura IS NULL",
                (tipo, esforco)
            )
        else:
            conn.execute(
                "DELETE FROM parafusos_receita WHERE tipo = ? AND esforco = ? AND altura = ?",
                (tipo, esforco, altura)
            )
        affected = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    return affected


# ---------------------------------------------------------------------------
# CRUD para a tela "Materiais por Poste" (Fase 3)
# ---------------------------------------------------------------------------
def listar_tipos_ferragens():
    """Lista os TIPOs de estrutura cadastrados, em ordem alfabética."""
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT DISTINCT tipo FROM materiais_poste ORDER BY tipo"
        ).fetchall()
    finally:
        conn.close()
    return [r['tipo'] for r in rows]


def obter_materiais(tipo):
    """Retorna a lista de materiais de um TIPO, em ordem."""
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT codigo, descricao, unidade, quantidade FROM materiais_poste "
            "WHERE tipo = ? ORDER BY ordem", (tipo,)
        ).fetchall()
    finally:
        conn.close()
    return [
        {'codigo': r['codigo'], 'descricao': r['descricao'],
         'unidade': r['unidade'], 'qtd': r['quantidade']}
        for r in rows
    ]


def substituir_materiais(tipo, materiais):
    """Substitui todos os materiais de um TIPO pela lista fornecida.

    materiais: lista de dicts com chaves codigo, descricao, unidade, qtd.
    """
    conn = conectar()
    try:
        conn.execute("DELETE FROM materiais_poste WHERE tipo = ?", (tipo,))
        for ordem, mat in enumerate(materiais):
            conn.execute(
                "INSERT INTO materiais_poste (tipo, ordem, codigo, descricao, unidade, quantidade) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (tipo, ordem, mat.get('codigo', ''), mat['descricao'],
                 mat.get('unidade', ''), float(mat['qtd']))
            )
        conn.commit()
    finally:
        conn.close()


def obter_todos_materiais():
    """Retorna todos os materiais (todos os tipos), ordenados por tipo e ordem."""
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT tipo, codigo, descricao, unidade, quantidade "
            "FROM materiais_poste ORDER BY tipo, ordem"
        ).fetchall()
    finally:
        conn.close()
    return [
        {'tipo': r['tipo'], 'codigo': r['codigo'], 'descricao': r['descricao'],
         'unidade': r['unidade'], 'qtd': r['quantidade']}
        for r in rows
    ]


def substituir_campo_global(campo, de, para):
    """Substitui um valor de texto em TODOS os registros de um campo.

    campo: 'descricao', 'codigo' ou 'unidade'.
    Retorna o número de linhas afetadas.
    """
    if campo not in ('descricao', 'codigo', 'unidade'):
        raise ValueError(f"Campo não permitido para substituição global: {campo}")
    conn = conectar()
    try:
        conn.execute(
            f"UPDATE materiais_poste SET {campo} = ? WHERE {campo} = ?",
            (para, de)
        )
        affected = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    return affected


# ---------------------------------------------------------------------------
# Exportação (backup em Excel)
# ---------------------------------------------------------------------------
def _tipo_para_aba(tipo):
    """Reverte '/' para ' I ' (caractere inválido em nome de aba no Excel)."""
    return tipo.replace('/', ' I ')[:31]  # limite de 31 chars do Excel


def exportar_ferragens_xlsx(caminho):
    """Exporta a receita de ferragens do banco para um .xlsx (uma aba por tipo)."""
    receita = ler_receita_ferragens()
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with pd.ExcelWriter(caminho, engine='openpyxl') as writer:
        for tipo, materiais in receita.items():
            df = pd.DataFrame([
                {'ITEM': m['codigo'], 'DESCRIÇÃO': m['descricao'],
                 'UND': m['unidade'], 'QUANT.': m['qtd']}
                for m in materiais
            ])
            df.to_excel(writer, sheet_name=_tipo_para_aba(tipo), index=False)
    print(f"[BANCO] Receita de ferragens exportada para {caminho}")


if __name__ == '__main__':
    # Permite rodar a migração manualmente: python -m src.banco
    inicializar()
    print("[BANCO] Inicialização concluída.")
