"""Camada de persistência do sistema (SQLite).

Fonte única de verdade das receitas. O banco fica em data/sistema.db (não
versionado). Na primeira execução ele é criado e semeado a partir da pasta
config/, dentro de um parque inicial ("Dom Inocêncio").

Todas as receitas são separadas por PARQUE (obra/cliente): ferragens,
parafusos, alças/laços e estais. As funções de leitura e CRUD aceitam um
`parque_id` opcional — quando omitido, usam o parque ativo (persistido na
tabela app_estado, então a escolha sobrevive a reinícios do servidor).

Os motores NÃO leem mais Excel/CSV diretamente — consomem este módulo.
config/ serve apenas como seed inicial de um banco vazio.
"""

import os
import sqlite3
from datetime import datetime

import pandas as pd

CAMINHO_DB = os.path.join('data', 'sistema.db')
CAMINHO_SEED_FERRAGENS = os.path.join('config', 'QUANTIDADE-MATERIAIS.xlsx')
CAMINHO_SEED_PARAFUSOS = os.path.join('config', 'PARAFUSOS POR ESTRUTURA.xlsx')
CAMINHO_SEED_ALCAS = os.path.join('config', 'receita_alcas_lacos.csv')
CAMINHO_SEED_ESTAIS = os.path.join('config', 'receita_estais.csv')

# Nome do parque que recebe os dados pré-existentes na migração multi-parque
PARQUE_PADRAO = 'Dom Inocêncio'

# Versão do schema — incrementada a cada migração estrutural (PRAGMA user_version)
VERSAO_SCHEMA = 1

# Sufixos usados para desambiguar estruturas cuja receita de parafusos muda
# conforme o sentido de chegada dos cabos (só visível na planta perfil/DWG).
SUFIXOS_PARAFUSOS_AMBIGUOS = ('.C', '.I')

# Tabelas de receita que pertencem a um parque (usadas na cópia e na exclusão)
TABELAS_RECEITA = (
    'materiais_poste',
    'parafusos_receita',
    'alcas_lacos_receita',
    'estais_receita',
    'calculadora_montagens',
    'calculadora_estruturas',
    'calculadora_conicidade',
)


try:
    import libsql
except ImportError:
    libsql = None


class LibSqlRow:
    """Emula o comportamento do sqlite3.Row para objetos vindos do driver libsql."""
    def __init__(self, values, cols):
        self._values = tuple(values)
        self._mapping = {c: values[i] for i, c in enumerate(cols)}

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        return self._mapping[key]

    def get(self, key, default=None):
        return self._mapping.get(key, default)

    def keys(self):
        return self._mapping.keys()

    def values(self):
        return self._mapping.values()

    def items(self):
        return self._mapping.items()

    def __iter__(self):
        return iter(self._mapping.keys())

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"<Row {self._mapping}>"


class LibSqlCursor:
    """Cursor que encapsula os resultados do libsql em LibSqlRow."""
    def __init__(self, cursor):
        self._cur = cursor

    def __getattr__(self, name):
        return getattr(self._cur, name)

    def __iter__(self):
        return (self._wrap_row(r) for r in self._cur)

    def _wrap_row(self, row):
        if row is None or not self._cur.description:
            return row
        cols = [d[0] for d in self._cur.description]
        return LibSqlRow(row, cols)

    def fetchone(self):
        row = self._cur.fetchone()
        return self._wrap_row(row)

    def fetchall(self):
        rows = self._cur.fetchall()
        if not self._cur.description:
            return rows
        cols = [d[0] for d in self._cur.description]
        return [LibSqlRow(r, cols) for r in rows]


class LibSqlConnection:
    """Wrapper para a conexão do libsql para prover interface idêntica ao sqlite3."""
    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def execute(self, sql, params=()):
        cur = self._conn.execute(sql, params)
        return LibSqlCursor(cur)

    def executemany(self, sql, params_list):
        cur = self._conn.executemany(sql, params_list)
        return LibSqlCursor(cur)

    def cursor(self):
        return LibSqlCursor(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()


def conectar():
    """Abre conexão com o banco de dados.

    Se as variáveis de ambiente TURSO_DATABASE_URL e TURSO_AUTH_TOKEN estiverem
    configuradas, conecta ao Turso Cloud (LibSQL). Caso contrário, conecta ao
    arquivo SQLite local data/sistema.db.
    """
    turso_url = (os.environ.get('TURSO_DATABASE_URL') or os.environ.get('TURSO_URL') or '').strip().strip('"\'')
    turso_token = (os.environ.get('TURSO_AUTH_TOKEN') or os.environ.get('TURSO_TOKEN') or '').strip().strip('"\'')

    if turso_url and libsql is not None:
        raw_conn = libsql.connect(database=turso_url, auth_token=turso_token)
        return LibSqlConnection(raw_conn)

    os.makedirs(os.path.dirname(CAMINHO_DB), exist_ok=True)
    conn = sqlite3.connect(CAMINHO_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _agora():
    return datetime.now().strftime('%Y-%m-%d %H:%M')


# DDL de cada tabela isolado, para que a migração possa recriar uma tabela
# individualmente com exatamente o mesmo formato de um banco novo.
_DDL = {
    'parques': """
        CREATE TABLE IF NOT EXISTS parques (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            nome         TEXT NOT NULL UNIQUE,
            cliente      TEXT,
            observacoes  TEXT,
            criado_em    TEXT,
            atualizado_em TEXT
        )
    """,
    'app_estado': """
        CREATE TABLE IF NOT EXISTS app_estado (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """,
    'materiais_poste': """
        CREATE TABLE IF NOT EXISTS materiais_poste (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            parque_id  INTEGER NOT NULL REFERENCES parques(id) ON DELETE CASCADE,
            tipo       TEXT    NOT NULL,
            ordem      INTEGER NOT NULL,
            codigo     TEXT,
            descricao  TEXT    NOT NULL,
            unidade    TEXT,
            quantidade REAL    NOT NULL
        )
    """,
    'parafusos_receita': """
        CREATE TABLE IF NOT EXISTS parafusos_receita (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            parque_id         INTEGER NOT NULL REFERENCES parques(id) ON DELETE CASCADE,
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
    """,
    'alcas_lacos_receita': """
        CREATE TABLE IF NOT EXISTS alcas_lacos_receita (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            parque_id INTEGER NOT NULL REFERENCES parques(id) ON DELETE CASCADE,
            tipo      TEXT    NOT NULL,
            nivel     INTEGER NOT NULL,
            direcao   TEXT    NOT NULL,
            qtd_alcas REAL    NOT NULL,
            qtd_lacos REAL    NOT NULL,
            UNIQUE (parque_id, tipo, nivel, direcao)
        )
    """,
    'estais_receita': """
        CREATE TABLE IF NOT EXISTS estais_receita (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            parque_id     INTEGER NOT NULL REFERENCES parques(id) ON DELETE CASCADE,
            ordem         INTEGER NOT NULL,
            material      TEXT    NOT NULL,
            unidade       TEXT,
            qtd_por_estai REAL    NOT NULL
        )
    """,
    'calculadora_montagens': """
        CREATE TABLE IF NOT EXISTS calculadora_montagens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            parque_id  INTEGER NOT NULL REFERENCES parques(id) ON DELETE CASCADE,
            nome       TEXT    NOT NULL,
            cruzeta    REAL    NOT NULL DEFAULT 0,
            p_maquina  REAL    NOT NULL DEFAULT 0,
            porca_m    REAL    NOT NULL DEFAULT 0,
            arruela_m  REAL    NOT NULL DEFAULT 0,
            olhal_m    REAL    NOT NULL DEFAULT 0,
            sobra_m    REAL    NOT NULL DEFAULT 1,
            esf_maq    REAL    NOT NULL DEFAULT 50.0,
            p_dupla    REAL    NOT NULL DEFAULT 0,
            porca_d    REAL    NOT NULL DEFAULT 0,
            arruela_d  REAL    NOT NULL DEFAULT 0,
            olhal_d    REAL    NOT NULL DEFAULT 0,
            sobra_d    REAL    NOT NULL DEFAULT 1,
            esf_dup    REAL    NOT NULL DEFAULT 70.0,
            UNIQUE (parque_id, nome)
        )
    """,
    'calculadora_estruturas': """
        CREATE TABLE IF NOT EXISTS calculadora_estruturas (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            parque_id      INTEGER NOT NULL REFERENCES parques(id) ON DELETE CASCADE,
            estrutura      TEXT    NOT NULL,
            ordem          INTEGER NOT NULL DEFAULT 0,
            nivel          INTEGER NOT NULL DEFAULT 1,
            distancia_prog TEXT    NOT NULL DEFAULT '0.2',
            montagem       TEXT,
            face           TEXT    NOT NULL DEFAULT 'B',
            face_oposta    INTEGER NOT NULL DEFAULT 0,
            cruzeta        REAL    NOT NULL DEFAULT 0,
            p_maquina      REAL    NOT NULL DEFAULT 0,
            porca_m        REAL    NOT NULL DEFAULT 0,
            arruela_m      REAL    NOT NULL DEFAULT 0,
            olhal_m        REAL    NOT NULL DEFAULT 0,
            sobra_m        REAL    NOT NULL DEFAULT 1,
            esf_maq        REAL    NOT NULL DEFAULT 50.0,
            p_dupla        REAL    NOT NULL DEFAULT 0,
            porca_d        REAL    NOT NULL DEFAULT 0,
            arruela_d      REAL    NOT NULL DEFAULT 0,
            olhal_d        REAL    NOT NULL DEFAULT 0,
            sobra_d        REAL    NOT NULL DEFAULT 1,
            esf_dup        REAL    NOT NULL DEFAULT 70.0
        )
    """,
    'calculadora_conicidade': """
        CREATE TABLE IF NOT EXISTS calculadora_conicidade (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            parque_id     INTEGER NOT NULL REFERENCES parques(id) ON DELETE CASCADE,
            topo_a        REAL NOT NULL DEFAULT 140.0,
            conicidade_a  REAL NOT NULL DEFAULT 28.0,
            topo_b        REAL NOT NULL DEFAULT 110.0,
            conicidade_b  REAL NOT NULL DEFAULT 20.0,
            UNIQUE (parque_id)
        )
    """,
}

_DDL_INDICES = (
    "CREATE INDEX IF NOT EXISTS idx_materiais_parque_tipo    ON materiais_poste(parque_id, tipo)",
    "CREATE INDEX IF NOT EXISTS idx_parafusos_parque_tipo    ON parafusos_receita(parque_id, tipo)",
    "CREATE INDEX IF NOT EXISTS idx_alcas_parque_tipo        ON alcas_lacos_receita(parque_id, tipo)",
    "CREATE INDEX IF NOT EXISTS idx_estais_parque            ON estais_receita(parque_id)",
    "CREATE INDEX IF NOT EXISTS idx_calc_montagens_parque    ON calculadora_montagens(parque_id, nome)",
    "CREATE INDEX IF NOT EXISTS idx_calc_estruturas_parque   ON calculadora_estruturas(parque_id, estrutura)",
    "CREATE INDEX IF NOT EXISTS idx_calc_conicidade_parque   ON calculadora_conicidade(parque_id)",
)


def _criar_schema(conn):
    """Cria as tabelas que ainda não existem.

    Os índices ficam de fora de propósito: num banco legado (pré multi-parque)
    a tabela existente ainda não tem a coluna parque_id, e o CREATE INDEX
    falharia. Eles são criados por _criar_indices(), depois da migração.
    """
    for ddl in _DDL.values():
        conn.execute(ddl)
    conn.commit()


def _criar_indices(conn):
    for ddl in _DDL_INDICES:
        conn.execute(ddl)
    conn.commit()


def _tem_coluna(conn, tabela, coluna):
    try:
        conn.execute(f"SELECT {coluna} FROM {tabela} LIMIT 0")
        return True
    except Exception:
        return False


def _tabela_existe(conn, tabela):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabela,)
    ).fetchone()
    return row is not None


def _ler_estado(conn, chave):
    row = conn.execute("SELECT valor FROM app_estado WHERE chave = ?", (chave,)).fetchone()
    return row['valor'] if row else None


def _gravar_estado(conn, chave, valor):
    conn.execute(
        "INSERT INTO app_estado (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, str(valor))
    )
    conn.commit()


def _obter_versao_schema(conn):
    try:
        val = _ler_estado(conn, 'schema_version')
        return int(val) if val is not None else 0
    except Exception:
        return 0


def _definir_versao_schema(conn, versao):
    _gravar_estado(conn, 'schema_version', str(versao))


# ---------------------------------------------------------------------------
# Migração de schema
# ---------------------------------------------------------------------------
def _migrar_para_multi_parque(conn):
    """Migração v0 → v1: receitas globais passam a pertencer a um parque.

    Recria materiais_poste e parafusos_receita com a coluna parque_id (SQLite
    não permite adicionar NOT NULL + FK via ALTER), atribuindo tudo que já
    existia ao parque PARQUE_PADRAO. Alças/laços e estais, que antes viviam
    fora do banco (CSV e dicionário no motor), são semeados no mesmo parque.
    """
    legado = {
        t: (_tabela_existe(conn, t) and not _tem_coluna(conn, t, 'parque_id'))
        for t in ('materiais_poste', 'parafusos_receita')
    }
    if not any(legado.values()):
        return False

    parque_id = _obter_ou_criar_parque(
        conn, PARQUE_PADRAO,
        observacoes='Parque criado automaticamente na migração multi-parque; '
                    'recebeu todas as receitas que existiam antes da separação por obra.'
    )

    colunas = {
        'materiais_poste': 'tipo, ordem, codigo, descricao, unidade, quantidade',
        'parafusos_receita': ('tipo, esforco, altura, posicao, parafuso, esf_parafuso, '
                              'comprimento, quantidade, cruzeta_adicional'),
    }
    indices_antigos = ('idx_materiais_tipo', 'idx_parafusos_tipo')

    for idx in indices_antigos:
        conn.execute(f"DROP INDEX IF EXISTS {idx}")

    for tabela, precisa in legado.items():
        if not precisa:
            continue
        cols = colunas[tabela]
        conn.execute(f"ALTER TABLE {tabela} RENAME TO _legado_{tabela}")
        conn.execute(_DDL[tabela])
        conn.execute(
            f"INSERT INTO {tabela} (parque_id, {cols}) "
            f"SELECT ?, {cols} FROM _legado_{tabela}",
            (parque_id,)
        )
        movidas = conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        conn.execute(f"DROP TABLE _legado_{tabela}")
        print(f"[BANCO] Migração: {movidas} linhas de {tabela} atribuídas ao parque "
              f"'{PARQUE_PADRAO}'.")

    # Alças/laços e estais nunca estiveram no banco — semeia do config/ neste parque
    _seed_alcas(conn, parque_id)
    _seed_estais(conn, parque_id)

    conn.commit()
    return True


def inicializar():
    """Cria o schema, aplica migrações pendentes e semeia um banco vazio."""
    turso_url = (os.environ.get('TURSO_DATABASE_URL') or '').strip().strip('"\'')
    modo = f"Turso Cloud ({turso_url[:30]}...)" if turso_url else f"SQLite Local ({CAMINHO_DB})"
    print(f"[BANCO] Conectando ao banco de dados [{modo}]...", flush=True)

    conn = conectar()
    try:
        print("[BANCO] Criando schema de tabelas...", flush=True)
        _criar_schema(conn)

        print("[BANCO] Verificando versão de migração...", flush=True)
        versao = _obter_versao_schema(conn)
        if versao < 1:
            print("[BANCO] Aplicando migração v1...", flush=True)
            _migrar_para_multi_parque(conn)
            _definir_versao_schema(conn, VERSAO_SCHEMA)

        print("[BANCO] Criando índices...", flush=True)
        _criar_indices(conn)

        # Migração incremental: garante que colunas de classe de esforço (esf_maq, esf_dup) existam
        for tabela in ('calculadora_montagens', 'calculadora_estruturas'):
            if _tabela_existe(conn, tabela):
                if not _tem_coluna(conn, tabela, 'esf_maq'):
                    conn.execute(f"ALTER TABLE {tabela} ADD COLUMN esf_maq REAL NOT NULL DEFAULT 50.0")
                if not _tem_coluna(conn, tabela, 'esf_dup'):
                    conn.execute(f"ALTER TABLE {tabela} ADD COLUMN esf_dup REAL NOT NULL DEFAULT 70.0")
        if _tabela_existe(conn, 'calculadora_estruturas') and not _tem_coluna(conn, 'calculadora_estruturas', 'face_oposta'):
            conn.execute("ALTER TABLE calculadora_estruturas ADD COLUMN face_oposta INTEGER NOT NULL DEFAULT 0")
        conn.commit()

        total_parques = conn.execute("SELECT COUNT(*) FROM parques").fetchone()[0]
        print(f"[BANCO] Parques existentes: {total_parques}", flush=True)
        if total_parques == 0:
            print("[BANCO] Semeando dados iniciais no banco...", flush=True)
            _seed_banco_novo(conn)

        # Garante que as montagens padrão da calculadora estejam semeadas em todos os parques
        for r_p in conn.execute("SELECT id FROM parques").fetchall():
            _seed_montagens(conn, r_p['id'])

        # Garante que a calculadora esteja semeada em parques existentes apenas na 1ª vez
        if not _ler_estado(conn, 'calculadora_semeada'):
            for r_p in conn.execute("SELECT id FROM parques").fetchall():
                pid = r_p['id']
                cnt = conn.execute("SELECT COUNT(*) FROM calculadora_estruturas WHERE parque_id = ?", (pid,)).fetchone()[0]
                if cnt == 0:
                    _seed_calculadora(conn, pid)
            _gravar_estado(conn, 'calculadora_semeada', '1')

        _garantir_parque_ativo(conn)
        print("[BANCO] Banco de dados pronto e operacional!", flush=True)
    except Exception as e:
        print(f"[BANCO] ERRO durante inicialização: {e}", flush=True)
        raise
    finally:
        conn.close()


def _seed_banco_novo(conn):
    """Banco recém-criado: cria o parque inicial e importa tudo que houver em config/."""
    parque_id = _obter_ou_criar_parque(conn, PARQUE_PADRAO)
    print(f"[BANCO] Banco novo — parque inicial '{PARQUE_PADRAO}' criado.")

    if os.path.exists(CAMINHO_SEED_FERRAGENS):
        receita = _parse_xlsx_ferragens(CAMINHO_SEED_FERRAGENS)
        _gravar_receita_ferragens(conn, parque_id, receita)
        total = sum(len(v) for v in receita.values())
        print(f"[BANCO] Seed: {total} materiais em {len(receita)} tipos de "
              f"{CAMINHO_SEED_FERRAGENS}")
    else:
        print(f"[BANCO] AVISO: {CAMINHO_SEED_FERRAGENS} não encontrado — "
              "receita de ferragens iniciará vazia.")

    if os.path.exists(CAMINHO_SEED_PARAFUSOS):
        linhas = _parse_xlsx_parafusos(CAMINHO_SEED_PARAFUSOS)
        _gravar_receita_parafusos(conn, parque_id, linhas)
        print(f"[BANCO] Seed: {len(linhas)} linhas de parafusos de "
              f"{CAMINHO_SEED_PARAFUSOS}")
    else:
        print(f"[BANCO] AVISO: {CAMINHO_SEED_PARAFUSOS} não encontrado — "
              "receita de parafusos iniciará vazia.")

    _seed_alcas(conn, parque_id)
    _seed_estais(conn, parque_id)
    _seed_montagens(conn, parque_id)
    _seed_calculadora(conn, parque_id)
    conn.commit()


def _seed_alcas(conn, parque_id):
    if not os.path.exists(CAMINHO_SEED_ALCAS):
        print(f"[BANCO] AVISO: {CAMINHO_SEED_ALCAS} não encontrado — "
              "receita de alças/laços iniciará vazia.")
        return
    df = pd.read_csv(CAMINHO_SEED_ALCAS)
    linhas = []
    for _, r in df.iterrows():
        linhas.append({
            'tipo': str(r['TIPO']).strip(),
            'nivel': int(r['NIVEL']),
            'direcao': str(r['DIRECAO']).strip().upper(),
            'qtd_alcas': float(r['QTD_ALCAS']),
            'qtd_lacos': float(r['QTD_LACOS']),
        })
    _gravar_receita_alcas(conn, parque_id, linhas)
    print(f"[BANCO] Seed: {len(linhas)} linhas de alças/laços de {CAMINHO_SEED_ALCAS}")


def _seed_estais(conn, parque_id):
    if not os.path.exists(CAMINHO_SEED_ESTAIS):
        print(f"[BANCO] AVISO: {CAMINHO_SEED_ESTAIS} não encontrado — "
              "receita de estais iniciará vazia.")
        return
    df = pd.read_csv(CAMINHO_SEED_ESTAIS)
    linhas = []
    for _, r in df.iterrows():
        linhas.append({
            'material': str(r['MATERIAL']).strip(),
            'unidade': str(r['UNIDADE']).strip(),
            'qtd_por_estai': float(r['QTD_POR_ESTAI']),
        })
    _gravar_receita_estais(conn, parque_id, linhas)
    print(f"[BANCO] Seed: {len(linhas)} materiais de estais de {CAMINHO_SEED_ESTAIS}")


MONTAGENS_PADRAO_SEED = [
    {
        'nome': 'N1',
        'cruzeta': 1,
        'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1,
        'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1,
    },
    {
        'nome': 'N3',
        'cruzeta': 2,
        'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1,
        'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1,
    },
    {
        'nome': 'N4',
        'cruzeta': 2,
        'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1,
        'p_dupla': 3, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 2, 'sobra_d': 1,
    },
    {
        'nome': 'CRUZETA AUXILIAR',
        'cruzeta': 1,
        'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1,
        'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1,
    },
    {
        'nome': 'CHAVE FUSÍVEL',
        'cruzeta': 2,
        'p_maquina': 4, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1,
        'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1,
    },
    {
        'nome': 'TRANSFORMADOR',
        'cruzeta': 0,
        'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1,
        'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1,
    },
    {
        'nome': 'CRUZETA ADICIONAL',
        'cruzeta': 2,
        'p_maquina': 4, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'esf_maq': 50.0,
        'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1, 'esf_dup': 70.0,
    },
]


def _seed_montagens(conn, parque_id):
    for m in MONTAGENS_PADRAO_SEED:
        conn.execute(
            "INSERT OR IGNORE INTO calculadora_montagens "
            "(parque_id, nome, cruzeta, p_maquina, porca_m, arruela_m, olhal_m, sobra_m, esf_maq, "
            "p_dupla, porca_d, arruela_d, olhal_d, sobra_d, esf_dup) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (parque_id, m['nome'], float(m.get('cruzeta', 0)),
             float(m.get('p_maquina', 0)), float(m.get('porca_m', 2)), float(m.get('arruela_m', 2)),
             float(m.get('olhal_m', 0)), float(m.get('sobra_m', 1)), float(m.get('esf_maq', 50.0)),
             float(m.get('p_dupla', 0)), float(m.get('porca_d', 2)), float(m.get('arruela_d', 2)),
             float(m.get('olhal_d', 0)), float(m.get('sobra_d', 1)), float(m.get('esf_dup', 70.0)))
        )
    conn.commit()
    print(f"[BANCO] Seed: {len(MONTAGENS_PADRAO_SEED)} montagens da calculadora no parque {parque_id}")


def _seed_calculadora(conn, parque_id):
    from src import calculadora_parafusos
    grid_all = calculadora_parafusos.gerar_linhas_iniciais_estruturas()
    for est_nome, linhas in grid_all.items():
        for l in linhas:
            conn.execute(
                "INSERT INTO calculadora_estruturas "
                "(parque_id, estrutura, ordem, nivel, distancia_prog, montagem, face, face_oposta, "
                "cruzeta, p_maquina, porca_m, arruela_m, olhal_m, sobra_m, esf_maq, "
                "p_dupla, porca_d, arruela_d, olhal_d, sobra_d, esf_dup) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (parque_id, est_nome, int(l['ordem']), int(l['nivel']), str(l['distancia_prog']),
                 '', 'B', int(bool(l.get('face_oposta', 0))), float(l['cruzeta']),
                 float(l['p_maquina']), float(l.get('porca_m', 2)), float(l.get('arruela_m', 2)),
                 float(l.get('olhal_m', 0)), float(l.get('sobra_m', 1)), float(l.get('esf_maq', 50.0)),
                 float(l['p_dupla']), float(l.get('porca_d', 2)), float(l.get('arruela_d', 2)),
                 float(l.get('olhal_d', 0)), float(l.get('sobra_d', 1)), float(l.get('esf_dup', 70.0)))
            )
    conn.commit()
    print(f"[BANCO] Seed: {len(grid_all)} estruturas da calculadora no parque {parque_id}")


# ---------------------------------------------------------------------------
# Parques
# ---------------------------------------------------------------------------
def _obter_ou_criar_parque(conn, nome, cliente=None, observacoes=None):
    """Retorna o id do parque `nome`, criando-o se ainda não existir."""
    row = conn.execute("SELECT id FROM parques WHERE nome = ?", (nome,)).fetchone()
    if row:
        return row['id']
    agora = _agora()
    cur = conn.execute(
        "INSERT INTO parques (nome, cliente, observacoes, criado_em, atualizado_em) "
        "VALUES (?, ?, ?, ?, ?)",
        (nome, cliente, observacoes, agora, agora)
    )
    return cur.lastrowid


def listar_parques():
    """Lista os parques com a contagem de linhas de cada receita."""
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT id, nome, cliente, observacoes, criado_em, atualizado_em "
            "FROM parques ORDER BY nome COLLATE NOCASE"
        ).fetchall()
        parques = []
        for r in rows:
            p = dict(r)
            p['contagens'] = {
                'ferragens': conn.execute(
                    "SELECT COUNT(DISTINCT tipo) FROM materiais_poste WHERE parque_id = ?",
                    (r['id'],)).fetchone()[0],
                'parafusos': conn.execute(
                    "SELECT COUNT(DISTINCT tipo) FROM parafusos_receita WHERE parque_id = ?",
                    (r['id'],)).fetchone()[0],
                'alcas_lacos': conn.execute(
                    "SELECT COUNT(*) FROM alcas_lacos_receita WHERE parque_id = ?",
                    (r['id'],)).fetchone()[0],
                'estais': conn.execute(
                    "SELECT COUNT(*) FROM estais_receita WHERE parque_id = ?",
                    (r['id'],)).fetchone()[0],
            }
            parques.append(p)
        return parques
    finally:
        conn.close()


def listar_parques_resumo():
    """Lista apenas id e nome dos parques — versão leve para o seletor do header.

    Roda em toda página renderizada, por isso evita as contagens de listar_parques().
    """
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT id, nome FROM parques ORDER BY nome COLLATE NOCASE"
        ).fetchall()
    finally:
        conn.close()
    return [{'id': r['id'], 'nome': r['nome']} for r in rows]


def obter_parque(parque_id):
    """Retorna os dados de um parque, ou None se não existir."""
    conn = conectar()
    try:
        row = conn.execute(
            "SELECT id, nome, cliente, observacoes, criado_em, atualizado_em "
            "FROM parques WHERE id = ?", (parque_id,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def criar_parque(nome, cliente=None, observacoes=None, copiar_de=None):
    """Cria um parque. Se `copiar_de` for o id de outro parque, duplica as receitas dele.

    Retorna o id do novo parque. Levanta ValueError se o nome for vazio ou repetido.
    """
    nome = (nome or '').strip()
    if not nome:
        raise ValueError("O nome do parque é obrigatório.")

    conn = conectar()
    try:
        existe = conn.execute(
            "SELECT 1 FROM parques WHERE nome = ? COLLATE NOCASE", (nome,)
        ).fetchone()
        if existe:
            raise ValueError(f"Já existe um parque chamado '{nome}'.")

        if copiar_de is not None:
            origem = conn.execute(
                "SELECT 1 FROM parques WHERE id = ?", (copiar_de,)
            ).fetchone()
            if not origem:
                raise ValueError("Parque de origem para a cópia não encontrado.")

        agora = _agora()
        cur = conn.execute(
            "INSERT INTO parques (nome, cliente, observacoes, criado_em, atualizado_em) "
            "VALUES (?, ?, ?, ?, ?)",
            (nome, (cliente or '').strip() or None,
             (observacoes or '').strip() or None, agora, agora)
        )
        novo_id = cur.lastrowid

        if copiar_de is not None:
            _copiar_receitas(conn, copiar_de, novo_id)

        conn.commit()
        return novo_id
    finally:
        conn.close()


def _copiar_receitas(conn, origem_id, destino_id):
    """Duplica todas as receitas de um parque para outro."""
    copias = {
        'materiais_poste': 'tipo, ordem, codigo, descricao, unidade, quantidade',
        'parafusos_receita': ('tipo, esforco, altura, posicao, parafuso, esf_parafuso, '
                              'comprimento, quantidade, cruzeta_adicional'),
        'alcas_lacos_receita': 'tipo, nivel, direcao, qtd_alcas, qtd_lacos',
        'estais_receita': 'ordem, material, unidade, qtd_por_estai',
        'calculadora_montagens': ('nome, cruzeta, p_maquina, porca_m, arruela_m, olhal_m, sobra_m, esf_maq, '
                                  'p_dupla, porca_d, arruela_d, olhal_d, sobra_d, esf_dup'),
        'calculadora_estruturas': ('estrutura, ordem, nivel, distancia_prog, montagem, face, '
                                   'cruzeta, p_maquina, porca_m, arruela_m, olhal_m, sobra_m, esf_maq, '
                                   'p_dupla, porca_d, arruela_d, olhal_d, sobra_d, esf_dup'),
    }
    for tabela, cols in copias.items():
        conn.execute(
            f"INSERT INTO {tabela} (parque_id, {cols}) "
            f"SELECT ?, {cols} FROM {tabela} WHERE parque_id = ?",
            (destino_id, origem_id)
        )


def atualizar_parque(parque_id, nome, cliente=None, observacoes=None):
    """Atualiza nome/cliente/observações de um parque e carimba a data de alteração."""
    nome = (nome or '').strip()
    if not nome:
        raise ValueError("O nome do parque é obrigatório.")

    conn = conectar()
    try:
        existe = conn.execute(
            "SELECT 1 FROM parques WHERE nome = ? COLLATE NOCASE AND id <> ?",
            (nome, parque_id)
        ).fetchone()
        if existe:
            raise ValueError(f"Já existe outro parque chamado '{nome}'.")
        conn.execute(
            "UPDATE parques SET nome = ?, cliente = ?, observacoes = ?, atualizado_em = ? "
            "WHERE id = ?",
            (nome, (cliente or '').strip() or None,
             (observacoes or '').strip() or None, _agora(), parque_id)
        )
        conn.commit()
    finally:
        conn.close()


def excluir_parque(parque_id):
    """Exclui um parque e, em cascata, todas as suas receitas.

    Recusa excluir o último parque (o sistema precisa de pelo menos um).
    Se o parque excluído era o ativo, outro assume automaticamente.
    """
    conn = conectar()
    try:
        total = conn.execute("SELECT COUNT(*) FROM parques").fetchone()[0]
        if total <= 1:
            raise ValueError("Não é possível excluir o único parque cadastrado.")
        if not conn.execute("SELECT 1 FROM parques WHERE id = ?", (parque_id,)).fetchone():
            raise ValueError("Parque não encontrado.")

        conn.execute("DELETE FROM parques WHERE id = ?", (parque_id,))
        conn.commit()
        _garantir_parque_ativo(conn)
    finally:
        conn.close()




def _garantir_parque_ativo(conn):
    """Garante que o parque ativo aponte para um parque existente. Retorna o id."""
    atual = _ler_estado(conn, 'parque_ativo')
    if atual is not None:
        row = conn.execute("SELECT id FROM parques WHERE id = ?", (int(atual),)).fetchone()
        if row:
            return row['id']

    row = conn.execute(
        "SELECT id FROM parques ORDER BY nome COLLATE NOCASE LIMIT 1"
    ).fetchone()
    if not row:
        return None
    _gravar_estado(conn, 'parque_ativo', row['id'])
    return row['id']


def obter_parque_ativo():
    """Retorna o dict do parque ativo (ou None se não houver nenhum parque)."""
    conn = conectar()
    try:
        pid = _garantir_parque_ativo(conn)
        if pid is None:
            return None
        row = conn.execute(
            "SELECT id, nome, cliente, observacoes, criado_em, atualizado_em "
            "FROM parques WHERE id = ?", (pid,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def definir_parque_ativo(parque_id):
    """Troca o parque ativo. Levanta ValueError se o parque não existir."""
    conn = conectar()
    try:
        if not conn.execute("SELECT 1 FROM parques WHERE id = ?", (parque_id,)).fetchone():
            raise ValueError("Parque não encontrado.")
        _gravar_estado(conn, 'parque_ativo', parque_id)
    finally:
        conn.close()


def _pid(parque_id):
    """Resolve o parque alvo: o informado, ou o ativo quando None."""
    if parque_id is not None:
        return parque_id
    conn = conectar()
    try:
        pid = _garantir_parque_ativo(conn)
    finally:
        conn.close()
    if pid is None:
        raise ValueError("Nenhum parque cadastrado.")
    return pid


# ---------------------------------------------------------------------------
# Parsing dos seeds (config/)
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


# ---------------------------------------------------------------------------
# Gravação em massa (seed / importação)
# ---------------------------------------------------------------------------
def _gravar_receita_parafusos(conn, parque_id, linhas):
    """Substitui toda a receita de parafusos DO PARQUE pelo conteúdo de `linhas`."""
    conn.execute("DELETE FROM parafusos_receita WHERE parque_id = ?", (parque_id,))
    if linhas:
        params = [
            (parque_id, l['tipo'], l['esforco'], l['altura'], l['posicao'], l['parafuso'],
             l['esf_parafuso'], l['comprimento'], l['quantidade'], l['cruzeta_adicional'])
            for l in linhas
        ]
        conn.executemany(
            "INSERT INTO parafusos_receita "
            "(parque_id, tipo, esforco, altura, posicao, parafuso, esf_parafuso, "
            "comprimento, quantidade, cruzeta_adicional) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            params
        )
    conn.commit()


def _gravar_receita_ferragens(conn, parque_id, receita):
    """Substitui toda a receita de ferragens DO PARQUE pelo conteúdo de `receita`."""
    conn.execute("DELETE FROM materiais_poste WHERE parque_id = ?", (parque_id,))
    params = []
    for tipo, materiais in receita.items():
        for ordem, mat in enumerate(materiais):
            params.append((
                parque_id, tipo, ordem, mat['codigo'], mat['descricao'],
                mat['unidade'], mat['qtd']
            ))
    if params:
        conn.executemany(
            "INSERT INTO materiais_poste "
            "(parque_id, tipo, ordem, codigo, descricao, unidade, quantidade) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            params
        )
    conn.commit()


def _gravar_receita_alcas(conn, parque_id, linhas):
    """Substitui toda a receita de alças/laços DO PARQUE pelo conteúdo de `linhas`."""
    conn.execute("DELETE FROM alcas_lacos_receita WHERE parque_id = ?", (parque_id,))
    if linhas:
        params = [
            (parque_id, l['tipo'], l['nivel'], l['direcao'], l['qtd_alcas'], l['qtd_lacos'])
            for l in linhas
        ]
        conn.executemany(
            "INSERT INTO alcas_lacos_receita "
            "(parque_id, tipo, nivel, direcao, qtd_alcas, qtd_lacos) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            params
        )
    conn.commit()


def _gravar_receita_estais(conn, parque_id, linhas):
    """Substitui toda a receita de estais DO PARQUE pelo conteúdo de `linhas`."""
    conn.execute("DELETE FROM estais_receita WHERE parque_id = ?", (parque_id,))
    if linhas:
        params = [
            (parque_id, ordem, l['material'], l['unidade'], l['qtd_por_estai'])
            for ordem, l in enumerate(linhas)
        ]
        conn.executemany(
            "INSERT INTO estais_receita (parque_id, ordem, material, unidade, qtd_por_estai) "
            "VALUES (?, ?, ?, ?, ?)",
            params
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Leitura (consumida pelos motores)
# ---------------------------------------------------------------------------
def ler_receita_ferragens(parque_id=None):
    """Retorna dict {tipo: [{codigo, descricao, unidade, qtd}, ...]} do parque."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT tipo, codigo, descricao, unidade, quantidade "
            "FROM materiais_poste WHERE parque_id = ? ORDER BY tipo, ordem",
            (parque_id,)
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


def ler_receita_parafusos_df(parque_id=None):
    """Retorna a receita de parafusos do parque como DataFrame (o motor opera em pandas)."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT tipo, esforco, altura, posicao, parafuso, esf_parafuso, "
            "comprimento, quantidade, cruzeta_adicional FROM parafusos_receita "
            "WHERE parque_id = ?",
            (parque_id,)
        ).fetchall()
        cols = ['tipo', 'esforco', 'altura', 'posicao', 'parafuso', 'esf_parafuso',
                'comprimento', 'quantidade', 'cruzeta_adicional']
        df = pd.DataFrame([dict(r) for r in rows], columns=cols)
    finally:
        conn.close()
    return df


def ler_receita_alcas_df(parque_id=None):
    """Retorna a receita de alças/laços do parque no formato do CSV original.

    Colunas TIPO, NIVEL, DIRECAO, QTD_ALCAS, QTD_LACOS — o motor de alças/laços
    consome exatamente esse formato.
    """
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT tipo AS TIPO, nivel AS NIVEL, direcao AS DIRECAO, "
            "qtd_alcas AS QTD_ALCAS, qtd_lacos AS QTD_LACOS "
            "FROM alcas_lacos_receita WHERE parque_id = ? ORDER BY tipo, nivel, direcao",
            (parque_id,)
        ).fetchall()
        cols = ['TIPO', 'NIVEL', 'DIRECAO', 'QTD_ALCAS', 'QTD_LACOS']
        df = pd.DataFrame([dict(r) for r in rows], columns=cols)
    finally:
        conn.close()
    return df


def ler_receita_estais(parque_id=None):
    """Retorna [{material, unidade, qtd_por_estai}, ...] do parque, em ordem."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT material, unidade, qtd_por_estai FROM estais_receita "
            "WHERE parque_id = ? ORDER BY ordem", (parque_id,)
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def listar_tipos_ambiguos_parafusos(parque_id=None):
    """Bases de TIPO cuja receita de parafusos varia conforme o sentido de chegada dos
    cabos (sufixo .C ou .I) — precisam de confirmação manual quando aparecem sem sufixo."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT DISTINCT tipo FROM parafusos_receita WHERE parque_id = ?",
            (parque_id,)
        ).fetchall()
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
def listar_estruturas_parafusos(parque_id=None):
    """Lista os combos distintos (tipo, esforco, altura) cadastrados no parque."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT DISTINCT tipo, esforco, altura FROM parafusos_receita "
            "WHERE parque_id = ? ORDER BY tipo, esforco, altura",
            (parque_id,)
        ).fetchall()
    finally:
        conn.close()
    return [{'tipo': r['tipo'], 'esforco': r['esforco'], 'altura': r['altura']} for r in rows]


def obter_grade_parafusos(tipo, esforco, altura=None, parque_id=None):
    """Retorna as linhas de receita de um combo tipo+esforço+altura do parque.

    Cada linha: {posicao, parafuso, esf_parafuso, comprimento, quantidade, cruzeta_adicional}.
    """
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        base = ("SELECT posicao, parafuso, esf_parafuso, comprimento, quantidade, "
                "cruzeta_adicional FROM parafusos_receita "
                "WHERE parque_id = ? AND tipo = ? AND esforco = ? AND altura ")
        if altura is None:
            rows = conn.execute(base + "IS NULL", (parque_id, tipo, esforco)).fetchall()
        else:
            rows = conn.execute(base + "= ?", (parque_id, tipo, esforco, altura)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def salvar_grade_parafusos(tipo, esforco, altura, cruzeta_adicional, linhas, parque_id=None):
    """Substitui as linhas de um combo tipo+esforço+altura do parque pelas fornecidas.

    linhas: lista de dicts {posicao, parafuso, esf_parafuso, comprimento, quantidade}.
    cruzeta_adicional é gravado repetido em cada linha (mesmo padrão do seed original).
    Retorna o número de linhas gravadas.
    """
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        _excluir_combo_parafusos(conn, parque_id, tipo, esforco, altura)
        if linhas:
            params = [
                (parque_id, tipo, esforco, altura, l['posicao'], l['parafuso'],
                 l['esf_parafuso'], l['comprimento'], l['quantidade'], cruzeta_adicional)
                for l in linhas
            ]
            conn.executemany(
                "INSERT INTO parafusos_receita "
                "(parque_id, tipo, esforco, altura, posicao, parafuso, esf_parafuso, "
                "comprimento, quantidade, cruzeta_adicional) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                params
            )
        conn.commit()
    finally:
        conn.close()
    return len(linhas)


def _excluir_combo_parafusos(conn, parque_id, tipo, esforco, altura):
    base = ("DELETE FROM parafusos_receita "
            "WHERE parque_id = ? AND tipo = ? AND esforco = ? AND altura ")
    if altura is None:
        conn.execute(base + "IS NULL", (parque_id, tipo, esforco))
    else:
        conn.execute(base + "= ?", (parque_id, tipo, esforco, altura))


def excluir_estrutura_parafusos(tipo, esforco, altura=None, parque_id=None):
    """Remove as linhas de um combo tipo+esforço+altura do parque. Retorna linhas afetadas."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        _excluir_combo_parafusos(conn, parque_id, tipo, esforco, altura)
        affected = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    return affected


# ---------------------------------------------------------------------------
# CRUD para a tela "Materiais por Poste"
# ---------------------------------------------------------------------------
def listar_tipos_ferragens(parque_id=None):
    """Lista os TIPOs de estrutura cadastrados no parque, em ordem alfabética."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT DISTINCT tipo FROM materiais_poste WHERE parque_id = ? ORDER BY tipo",
            (parque_id,)
        ).fetchall()
    finally:
        conn.close()
    return [r['tipo'] for r in rows]


def obter_materiais(tipo, parque_id=None):
    """Retorna a lista de materiais de um TIPO no parque, em ordem."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT codigo, descricao, unidade, quantidade FROM materiais_poste "
            "WHERE parque_id = ? AND tipo = ? ORDER BY ordem", (parque_id, tipo)
        ).fetchall()
    finally:
        conn.close()
    return [
        {'codigo': r['codigo'], 'descricao': r['descricao'],
         'unidade': r['unidade'], 'qtd': r['quantidade']}
        for r in rows
    ]


def substituir_materiais(tipo, materiais, parque_id=None):
    """Substitui todos os materiais de um TIPO no parque pela lista fornecida.

    materiais: lista de dicts com chaves codigo, descricao, unidade, qtd.
    """
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        conn.execute(
            "DELETE FROM materiais_poste WHERE parque_id = ? AND tipo = ?",
            (parque_id, tipo)
        )
        if materiais:
            params = [
                (parque_id, tipo, ordem, mat.get('codigo', ''), mat['descricao'],
                 mat.get('unidade', ''), float(mat['qtd']))
                for ordem, mat in enumerate(materiais)
            ]
            conn.executemany(
                "INSERT INTO materiais_poste "
                "(parque_id, tipo, ordem, codigo, descricao, unidade, quantidade) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                params
            )
        conn.commit()
    finally:
        conn.close()


def obter_todos_materiais(parque_id=None):
    """Retorna todos os materiais do parque (todos os tipos), ordenados por tipo e ordem."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT tipo, codigo, descricao, unidade, quantidade "
            "FROM materiais_poste WHERE parque_id = ? ORDER BY tipo, ordem",
            (parque_id,)
        ).fetchall()
    finally:
        conn.close()
    return [
        {'tipo': r['tipo'], 'codigo': r['codigo'], 'descricao': r['descricao'],
         'unidade': r['unidade'], 'qtd': r['quantidade']}
        for r in rows
    ]


def substituir_campo_global(campo, de, para, parque_id=None):
    """Substitui um valor de texto em TODOS os registros de um campo, dentro do parque.

    campo: 'descricao', 'codigo' ou 'unidade'.
    Retorna o número de linhas afetadas.
    """
    if campo not in ('descricao', 'codigo', 'unidade'):
        raise ValueError(f"Campo não permitido para substituição global: {campo}")
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        conn.execute(
            f"UPDATE materiais_poste SET {campo} = ? WHERE parque_id = ? AND {campo} = ?",
            (para, parque_id, de)
        )
        affected = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    return affected


# ---------------------------------------------------------------------------
# CRUD para a tela "Alças e Laços"
# ---------------------------------------------------------------------------
def listar_tipos_alcas(parque_id=None):
    """Lista os TIPOs com receita de alças/laços no parque, em ordem alfabética."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT DISTINCT tipo FROM alcas_lacos_receita WHERE parque_id = ? ORDER BY tipo",
            (parque_id,)
        ).fetchall()
    finally:
        conn.close()
    return [r['tipo'] for r in rows]


def obter_alcas_lacos(tipo, parque_id=None):
    """Retorna [{nivel, direcao, qtd_alcas, qtd_lacos}, ...] de um TIPO no parque."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT nivel, direcao, qtd_alcas, qtd_lacos FROM alcas_lacos_receita "
            "WHERE parque_id = ? AND tipo = ? ORDER BY nivel, direcao",
            (parque_id, tipo)
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def obter_todas_alcas_lacos(parque_id=None):
    """Retorna a receita de alças/laços inteira do parque, como lista de dicts."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT tipo, nivel, direcao, qtd_alcas, qtd_lacos FROM alcas_lacos_receita "
            "WHERE parque_id = ? ORDER BY tipo, nivel, direcao", (parque_id,)
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def substituir_alcas_lacos(tipo, linhas, parque_id=None):
    """Substitui a receita de alças/laços de um TIPO no parque.

    linhas: lista de dicts {nivel, direcao, qtd_alcas, qtd_lacos}.
    """
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        conn.execute(
            "DELETE FROM alcas_lacos_receita WHERE parque_id = ? AND tipo = ?",
            (parque_id, tipo)
        )
        if linhas:
            params = [
                (parque_id, tipo, int(l['nivel']), str(l['direcao']).strip().upper(),
                 float(l['qtd_alcas']), float(l['qtd_lacos']))
                for l in linhas
            ]
            conn.executemany(
                "INSERT INTO alcas_lacos_receita "
                "(parque_id, tipo, nivel, direcao, qtd_alcas, qtd_lacos) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                params
            )
        conn.commit()
    finally:
        conn.close()
    return len(linhas)


def excluir_tipo_alcas_lacos(tipo, parque_id=None):
    """Remove toda a receita de alças/laços de um TIPO no parque. Retorna linhas afetadas."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        conn.execute(
            "DELETE FROM alcas_lacos_receita WHERE parque_id = ? AND tipo = ?",
            (parque_id, tipo)
        )
        affected = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    return affected


# ---------------------------------------------------------------------------
# CRUD para a tela "Estais"
# ---------------------------------------------------------------------------
def substituir_estais(linhas, parque_id=None):
    """Substitui a receita de estais inteira do parque (lista única, sem TIPO).

    linhas: lista de dicts {material, unidade, qtd_por_estai}, na ordem desejada.
    """
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        normalizadas = [
            {'material': str(l['material']).strip(),
             'unidade': str(l.get('unidade', '') or '').strip(),
             'qtd_por_estai': float(l['qtd_por_estai'])}
            for l in linhas
        ]
        _gravar_receita_estais(conn, parque_id, normalizadas)
    finally:
        conn.close()
    return len(linhas)


# ---------------------------------------------------------------------------
# Importação em lote (consumida por src/planilhas.py)
#
# Semântica combinada com o usuário: o que está no arquivo apaga e regrava a
# unidade correspondente; o que não está no arquivo permanece intacto. Por isso
# nenhuma destas funções faz DELETE global — só das unidades recebidas.
# Cada uma grava tudo numa transação só: ou entra inteiro, ou não entra nada.
# ---------------------------------------------------------------------------
def importar_ferragens(por_tipo, parque_id=None):
    """Substitui a receita de ferragens dos TIPOs recebidos. por_tipo: {tipo: [materiais]}."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        for tipo, materiais in por_tipo.items():
            conn.execute("DELETE FROM materiais_poste WHERE parque_id = ? AND tipo = ?",
                         (parque_id, tipo))
            if materiais:
                params = [
                    (parque_id, tipo, ordem, mat['codigo'], mat['descricao'],
                     mat['unidade'], mat['qtd'])
                    for ordem, mat in enumerate(materiais)
                ]
                conn.executemany(
                    "INSERT INTO materiais_poste "
                    "(parque_id, tipo, ordem, codigo, descricao, unidade, quantidade) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    params
                )
        conn.commit()
    finally:
        conn.close()


def importar_parafusos(por_combo, parque_id=None):
    """Substitui a receita de parafusos dos combos recebidos.

    por_combo: {(tipo, esforco, altura): [linhas]}, onde cada linha tem
    posicao, parafuso, esf_parafuso, comprimento, quantidade e cruzeta_adicional.
    """
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        for (tipo, esforco, altura), linhas in por_combo.items():
            _excluir_combo_parafusos(conn, parque_id, tipo, esforco, altura)
            if linhas:
                params = [
                    (parque_id, tipo, esforco, altura, l['posicao'], l['parafuso'],
                     l['esf_parafuso'], l['comprimento'], l['quantidade'],
                     l['cruzeta_adicional'])
                    for l in linhas
                ]
                conn.executemany(
                    "INSERT INTO parafusos_receita "
                    "(parque_id, tipo, esforco, altura, posicao, parafuso, esf_parafuso, "
                    "comprimento, quantidade, cruzeta_adicional) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    params
                )
        conn.commit()
    finally:
        conn.close()


def importar_alcas(por_tipo, parque_id=None):
    """Substitui a receita de alças/laços dos TIPOs recebidos. por_tipo: {tipo: [linhas]}."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        for tipo, linhas in por_tipo.items():
            conn.execute("DELETE FROM alcas_lacos_receita WHERE parque_id = ? AND tipo = ?",
                         (parque_id, tipo))
            if linhas:
                params = [
                    (parque_id, tipo, l['nivel'], l['direcao'],
                     l['qtd_alcas'], l['qtd_lacos'])
                    for l in linhas
                ]
                conn.executemany(
                    "INSERT INTO alcas_lacos_receita "
                    "(parque_id, tipo, nivel, direcao, qtd_alcas, qtd_lacos) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    params
                )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Exportação (backup em Excel)
# ---------------------------------------------------------------------------
def _tipo_para_aba(tipo):
    """Reverte '/' para ' I ' (caractere inválido em nome de aba no Excel)."""
    return tipo.replace('/', ' I ')[:31]  # limite de 31 chars do Excel


def exportar_ferragens_xlsx(caminho, parque_id=None):
    """Exporta a receita de ferragens de um parque para um .xlsx (uma aba por tipo)."""
    receita = ler_receita_ferragens(parque_id)
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


# ---------------------------------------------------------------------------
# CRUD para a Calculadora de Parafusos (Por Parque)
# ---------------------------------------------------------------------------

def listar_estruturas_calculadora(parque_id=None):
    """Lista os nomes de estruturas configuradas na calculadora para o parque."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT DISTINCT estrutura FROM calculadora_estruturas "
            "WHERE parque_id = ? ORDER BY estrutura",
            (parque_id,)
        ).fetchall()
        return [r['estrutura'] for r in rows]
    finally:
        conn.close()


def obter_estrutura_calculadora(estrutura_nome, parque_id=None):
    """Retorna as linhas da grade de níveis e elementos da estrutura para o parque."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT ordem, nivel, distancia_prog, montagem, face, face_oposta, cruzeta, "
            "p_maquina, porca_m, arruela_m, olhal_m, sobra_m, esf_maq, "
            "p_dupla, porca_d, arruela_d, olhal_d, sobra_d, esf_dup "
            "FROM calculadora_estruturas "
            "WHERE parque_id = ? AND estrutura = ? ORDER BY ordem, nivel",
            (parque_id, estrutura_nome)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def salvar_estrutura_calculadora(estrutura_nome, linhas, parque_id=None):
    """Salva/substitui os níveis e elementos de uma estrutura na calculadora do parque."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        conn.execute(
            "DELETE FROM calculadora_estruturas WHERE parque_id = ? AND estrutura = ?",
            (parque_id, estrutura_nome)
        )
        if linhas:
            params = [
                (parque_id, estrutura_nome, idx, int(l.get('nivel', idx)),
                 str(l.get('distancia_prog', '0.2')), str(l.get('montagem', '')),
                 'B', int(bool(l.get('face_oposta', 0))), float(l.get('cruzeta', 0)),
                 float(l.get('p_maquina', 0)), float(l.get('porca_m', 0)),
                 float(l.get('arruela_m', 0)), float(l.get('olhal_m', 0)),
                 float(l.get('sobra_m', 0)), float(l.get('esf_maq', 50.0)),
                 float(l.get('p_dupla', 0)),
                 float(l.get('porca_d', 0)), float(l.get('arruela_d', 0)),
                 float(l.get('olhal_d', 0)), float(l.get('sobra_d', 0)),
                 float(l.get('esf_dup', 70.0)))
                for idx, l in enumerate(linhas, 1)
            ]
            conn.executemany(
                "INSERT INTO calculadora_estruturas "
                "(parque_id, estrutura, ordem, nivel, distancia_prog, montagem, face, face_oposta, "
                "cruzeta, p_maquina, porca_m, arruela_m, olhal_m, sobra_m, esf_maq, "
                "p_dupla, porca_d, arruela_d, olhal_d, sobra_d, esf_dup) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                params
            )
        conn.commit()
        return len(linhas)
    finally:
        conn.close()


def excluir_estrutura_calculadora(estrutura_nome, parque_id=None):
    """Exclui uma estrutura da calculadora do parque."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        conn.execute(
            "DELETE FROM calculadora_estruturas WHERE parque_id = ? AND estrutura = ?",
            (parque_id, estrutura_nome)
        )
        affected = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
        return affected
    finally:
        conn.close()


def renomear_estrutura_calculadora(tipo_antigo, tipo_novo, parque_id=None):
    """Renomeia uma estrutura da calculadora no parque."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        conn.execute(
            "UPDATE calculadora_estruturas SET estrutura = ? WHERE parque_id = ? AND estrutura = ?",
            (tipo_novo, parque_id, tipo_antigo)
        )
        affected = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
        return affected
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Montagens Padrão da Calculadora (Por Parque)
# ---------------------------------------------------------------------------

def listar_montagens_calculadora(parque_id=None):
    """Lista as montagens padrão cadastradas para o parque."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        rows = conn.execute(
            "SELECT id, nome, cruzeta, p_maquina, porca_m, arruela_m, olhal_m, sobra_m, esf_maq, "
            "p_dupla, porca_d, arruela_d, olhal_d, sobra_d, esf_dup "
            "FROM calculadora_montagens WHERE parque_id = ? "
            "ORDER BY nome COLLATE NOCASE",
            (parque_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def obter_montagem_calculadora(nome, parque_id=None):
    """Retorna os dados de uma montagem padrão pelo nome."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        row = conn.execute(
            "SELECT id, nome, cruzeta, p_maquina, porca_m, arruela_m, olhal_m, sobra_m, esf_maq, "
            "p_dupla, porca_d, arruela_d, olhal_d, sobra_d, esf_dup "
            "FROM calculadora_montagens WHERE parque_id = ? AND nome = ?",
            (parque_id, nome)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def salvar_montagem_calculadora(nome, dados, parque_id=None, nome_antigo=None, propagar=True):
    """Cria ou atualiza uma montagem padrão no parque.
    
    Se propagar=True, atualiza todas as linhas de estruturas que usam essa montagem
    no parque ativo para refletir os novos valores de ferragens/parafusos.
    """
    parque_id = _pid(parque_id)
    nome = (nome or '').strip().upper()
    if not nome:
        raise ValueError("O nome da montagem padrão é obrigatório.")

    cruzeta   = float(dados.get('cruzeta', 0))
    p_maquina = float(dados.get('p_maquina', 0))
    porca_m   = float(dados.get('porca_m', 0))
    arruela_m = float(dados.get('arruela_m', 0))
    olhal_m   = float(dados.get('olhal_m', 0))
    sobra_m   = float(dados.get('sobra_m', 0))
    esf_maq   = float(dados.get('esf_maq', 50.0))
    p_dupla   = float(dados.get('p_dupla', 0))
    porca_d   = float(dados.get('porca_d', 0))
    arruela_d = float(dados.get('arruela_d', 0))
    olhal_d   = float(dados.get('olhal_d', 0))
    sobra_d   = float(dados.get('sobra_d', 0))
    esf_dup   = float(dados.get('esf_dup', 70.0))

    conn = conectar()
    try:
        nome_busca = (nome_antigo or nome).strip().upper()
        row = conn.execute(
            "SELECT id FROM calculadora_montagens WHERE parque_id = ? AND nome = ?",
            (parque_id, nome_busca)
        ).fetchone()

        if row:
            conn.execute(
                "UPDATE calculadora_montagens SET "
                "nome = ?, cruzeta = ?, p_maquina = ?, porca_m = ?, arruela_m = ?, "
                "olhal_m = ?, sobra_m = ?, esf_maq = ?, p_dupla = ?, porca_d = ?, arruela_d = ?, "
                "olhal_d = ?, sobra_d = ?, esf_dup = ? WHERE id = ?",
                (nome, cruzeta, p_maquina, porca_m, arruela_m, olhal_m, sobra_m, esf_maq,
                 p_dupla, porca_d, arruela_d, olhal_d, sobra_d, esf_dup, row['id'])
            )
            if nome_busca != nome:
                conn.execute(
                    "UPDATE calculadora_estruturas SET montagem = ? "
                    "WHERE parque_id = ? AND montagem = ?",
                    (nome, parque_id, nome_busca)
                )
        else:
            conn.execute(
                "INSERT INTO calculadora_montagens "
                "(parque_id, nome, cruzeta, p_maquina, porca_m, arruela_m, olhal_m, sobra_m, esf_maq, "
                "p_dupla, porca_d, arruela_d, olhal_d, sobra_d, esf_dup) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (parque_id, nome, cruzeta, p_maquina, porca_m, arruela_m, olhal_m, sobra_m, esf_maq,
                 p_dupla, porca_d, arruela_d, olhal_d, sobra_d, esf_dup)
            )

        afetados_estruturas = 0
        if propagar:
            conn.execute(
                "UPDATE calculadora_estruturas SET "
                "cruzeta = ?, p_maquina = ?, porca_m = ?, arruela_m = ?, olhal_m = ?, sobra_m = ?, esf_maq = ?, "
                "p_dupla = ?, porca_d = ?, arruela_d = ?, olhal_d = ?, sobra_d = ?, esf_dup = ? "
                "WHERE parque_id = ? AND montagem = ?",
                (cruzeta, p_maquina, porca_m, arruela_m, olhal_m, sobra_m, esf_maq,
                 p_dupla, porca_d, arruela_d, olhal_d, sobra_d, esf_dup, parque_id, nome)
            )
            afetados_estruturas = conn.execute("SELECT changes()").fetchone()[0]

        conn.commit()
        return {'ok': True, 'nome': nome, 'propagados': afetados_estruturas}
    finally:
        conn.close()


def excluir_montagem_calculadora(nome, parque_id=None):
    """Exclui uma montagem padrão e desvincula os níveis de estruturas que a usavam."""
    parque_id = _pid(parque_id)
    nome = (nome or '').strip().upper()
    conn = conectar()
    try:
        conn.execute(
            "DELETE FROM calculadora_montagens WHERE parque_id = ? AND nome = ?",
            (parque_id, nome)
        )
        del_count = conn.execute("SELECT changes()").fetchone()[0]
        # Limpa o vínculo nas estruturas (elas mantêm os valores como personalizados)
        conn.execute(
            "UPDATE calculadora_estruturas SET montagem = '' WHERE parque_id = ? AND montagem = ?",
            (parque_id, nome)
        )
        conn.commit()
        return del_count
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Conicidade e Parâmetros Físicos do Poste (Por Parque)
# ---------------------------------------------------------------------------

def obter_conicidade_calculadora(parque_id=None):
    """Retorna os fatores de conicidade e dimensões do topo do parque ou valores padrão."""
    parque_id = _pid(parque_id)
    padrao = {
        'topo_a': 140.0,
        'conicidade_a': 28.0,
        'topo_b': 110.0,
        'conicidade_b': 20.0
    }
    if not parque_id:
        return padrao
    conn = conectar()
    try:
        row = conn.execute(
            "SELECT topo_a, conicidade_a, topo_b, conicidade_b FROM calculadora_conicidade WHERE parque_id = ?",
            (parque_id,)
        ).fetchone()
        if row:
            return {
                'topo_a': float(row['topo_a']),
                'conicidade_a': float(row['conicidade_a']),
                'topo_b': float(row['topo_b']),
                'conicidade_b': float(row['conicidade_b'])
            }
        return padrao
    finally:
        conn.close()


def salvar_conicidade_calculadora(dados, parque_id=None):
    """Salva os fatores de conicidade e dimensões do poste para o parque."""
    parque_id = _pid(parque_id)
    topo_a = float(dados.get('topo_a', 140.0))
    conicidade_a = float(dados.get('conicidade_a', 28.0))
    topo_b = float(dados.get('topo_b', 110.0))
    conicidade_b = float(dados.get('conicidade_b', 20.0))

    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO calculadora_conicidade (parque_id, topo_a, conicidade_a, topo_b, conicidade_b) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(parque_id) DO UPDATE SET "
            "topo_a = excluded.topo_a, conicidade_a = excluded.conicidade_a, "
            "topo_b = excluded.topo_b, conicidade_b = excluded.conicidade_b",
            (parque_id, topo_a, conicidade_a, topo_b, conicidade_b)
        )
        conn.commit()
        return {
            'topo_a': topo_a,
            'conicidade_a': conicidade_a,
            'topo_b': topo_b,
            'conicidade_b': conicidade_b
        }
    finally:
        conn.close()


def restaurar_conicidade_calculadora(parque_id=None):
    """Restaura os valores padrão de conicidade removendo a personalização do parque."""
    parque_id = _pid(parque_id)
    conn = conectar()
    try:
        conn.execute("DELETE FROM calculadora_conicidade WHERE parque_id = ?", (parque_id,))
        conn.commit()
        return {
            'topo_a': 140.0,
            'conicidade_a': 28.0,
            'topo_b': 110.0,
            'conicidade_b': 20.0
        }
    finally:
        conn.close()


if __name__ == '__main__':
    # Permite rodar a migração manualmente: python -m src.banco
    inicializar()
    ativo = obter_parque_ativo()
    print(f"[BANCO] Inicialização concluída. Parque ativo: {ativo['nome'] if ativo else '—'}")
