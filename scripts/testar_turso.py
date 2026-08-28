"""Script utilitário para testar a conexão com o Turso (LibSQL) na nuvem.

Uso:
    1. Defina as variáveis de ambiente ou passe como argumento:
       set TURSO_DATABASE_URL=libsql://sua-database-org.turso.io
       set TURSO_AUTH_TOKEN=seu_token_aqui
       python scripts/testar_turso.py

    Ou passe direto no comando:
       python scripts/testar_turso.py libsql://sua-database-org.turso.io seu_token_aqui
"""

import sys
import os

# Força UTF-8 no stdout para consoles Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Adiciona a raiz do projeto ao path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

if len(sys.argv) >= 3:
    os.environ['TURSO_DATABASE_URL'] = sys.argv[1]
    os.environ['TURSO_AUTH_TOKEN'] = sys.argv[2]

from src import banco

def main():
    url = os.environ.get('TURSO_DATABASE_URL')
    token = os.environ.get('TURSO_AUTH_TOKEN')

    print("=" * 60)
    print("TESTE DE CONEXAO COM TURSO (LibSQL)")
    print("=" * 60)

    if not url:
        print("[ERRO] TURSO_DATABASE_URL nao esta configurada!")
        print("\nComo configurar no terminal Windows (cmd):")
        print("  set TURSO_DATABASE_URL=libsql://seu-banco-org.turso.io")
        print("  set TURSO_AUTH_TOKEN=seu-token")
        print("  python scripts/testar_turso.py")
        print("\nOu no PowerShell:")
        print("  $env:TURSO_DATABASE_URL='libsql://seu-banco-org.turso.io'")
        print("  $env:TURSO_AUTH_TOKEN='seu-token'")
        print("  python scripts/testar_turso.py")
        sys.exit(1)

    print(f"URL: {url}")
    print(f"Token: {'*' * (len(token) - 8) + token[-8:] if token and len(token) > 8 else '[nao informado]'}")
    print("\n1. Conectando e inicializando schema no Turso...")

    try:
        banco.inicializar()
        print("[OK] Schema criado/verificado com sucesso!")
    except Exception as e:
        print(f"[ERRO] Falha ao inicializar banco no Turso: {e}")
        sys.exit(1)

    print("\n2. Verificando dados e parques...")
    try:
        parques = banco.listar_parques()
        print(f"[OK] Total de parques no Turso: {len(parques)}")
        for p in parques:
            print(f"   * Parque: {p['nome']} (ID: {p['id']})")
            print(f"     - Ferragens: {p['contagens']['ferragens']} tipos")
            print(f"     - Parafusos: {p['contagens']['parafusos']} tipos")
            print(f"     - Alcas/Lacos: {p['contagens']['alcas_lacos']} regras")
            print(f"     - Estais: {p['contagens']['estais']} materiais")

        ativo = banco.obter_parque_ativo()
        print(f"\n[OK] Parque ativo: {ativo['nome'] if ativo else 'Nenhum'}")
        print("\n" + "=" * 60)
        print("[SUCESSO] O banco Turso esta 100% pronto para o Render!")
        print("=" * 60)

    except Exception as e:
        print(f"[ERRO] Erro ao consultar dados: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
