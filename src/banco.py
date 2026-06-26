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
