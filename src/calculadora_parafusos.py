"""Motor de dimensionamento automático de parafusos.

Baseado no modelo modular de Montagens (PADRÃO) e Composição por Níveis (ESTRUTURAS).
Calcula a seção física do poste duplo T nas faces A (Topo) e B (Gaveta), soma as
espessuras de ferragens (cruzeta, porca, arruela, olhal, sobra) e determina os
comprimentos comerciais correspondentes para cabeças quadradas e roscas duplas.
"""

import math
import re
from typing import Dict, List, Optional, Tuple, Any

# ── Constantes Físicas Padrão ──────────────────────────────────────────────

DIMENSOES_FERRAGENS = {
    'cruzeta': 105.0,     # mm (cruzeta concreto ou metálica)
    'porca': 11.0,        # mm
    'arruela': 4.0,       # mm
    'porca_olhal': 16.0,  # mm
    'sobra': 30.0,        # mm
}

POSTE_DT = {
    'A': {'topo': 140.0, 'conicidade': 28.0},  # mm e mm/m (Face A - Topo)
    'B': {'topo': 110.0, 'conicidade': 20.0},  # mm e mm/m (Face B - Gaveta)
}

COEFICIENTES_ESFORCO = {
    600: 0.0,
    1000: 1.5,
    1500: 3.0,
    2000: 4.5,
    2500: 6.0,
    3000: 7.5,
}

COMPRIMENTOS_COMERCIAIS = [
    150, 200, 250, 300, 350, 400, 450, 500,
    550, 600, 650, 700, 750, 800, 850, 900, 950, 1000
]

# ── Catálogo de Montagens Padrão (PADRAO) ──────────────────────────────────

PADROES_MONTAGEM: Dict[str, Dict[str, Any]] = {
    'N1': {
        'nome': 'N1',
        'descricao': 'N1 simples (1 cruzeta, 3 paraf. simples)',
        'cruzeta': 1.0,
        'parafuso_simples': 3.0,
        'parafuso_dupla': 0.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 0.0,
        'sobra': 1.0,
        'face_padrao': 'B',  # Gaveta por padrão
    },
    'N4.C': {
        'nome': 'N4.C',
        'descricao': 'N4 Topo (2 cruzetas, 3 roscas duplas c/ olhais)',
        'cruzeta': 2.0,
        'parafuso_simples': 0.0,
        'parafuso_dupla': 3.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 2.0,
        'sobra': 1.0,
        'face_padrao': 'A',  # Face A (Topo)
    },
    'N4.B': {
        'nome': 'N4.B',
        'descricao': 'N4 Gaveta (2 cruzetas, 2 paraf. simples)',
        'cruzeta': 2.0,
        'parafuso_simples': 2.0,
        'parafuso_dupla': 0.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 0.0,
        'sobra': 1.0,
        'face_padrao': 'B',  # Face B (Gaveta)
    },
    'N3.C': {
        'nome': 'N3.C',
        'descricao': 'N3 Topo (2 cruzetas, 3 paraf. simples, 1 olhal)',
        'cruzeta': 2.0,
        'parafuso_simples': 3.0,
        'parafuso_dupla': 0.0,
        'arruela': 2.0,
        'porca': 1.0,
        'porca_olhal': 1.0,
        'sobra': 1.0,
        'face_padrao': 'A',  # Face A (Topo)
    },
    'N3.B': {
        'nome': 'N3.B',
        'descricao': 'N3 Gaveta (2 cruzetas, 2 paraf. simples)',
        'cruzeta': 2.0,
        'parafuso_simples': 2.0,
        'parafuso_dupla': 0.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 0.0,
        'sobra': 1.0,
        'face_padrao': 'B',  # Face B (Gaveta)
    },
    'N3.C_1C': {
        'nome': 'N3.C_1C',
        'descricao': 'N3 Topo 1 Cruzeta (1 cruzeta, 3 paraf. simples)',
        'cruzeta': 1.0,
        'parafuso_simples': 3.0,
        'parafuso_dupla': 0.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 0.0,
        'sobra': 1.0,
        'face_padrao': 'A',
    },
    'CHAVE': {
        'nome': 'CHAVE',
        'descricao': 'Montagem Chave (2 cruzetas, 4 paraf. simples)',
        'cruzeta': 2.0,
        'parafuso_simples': 4.0,
        'parafuso_dupla': 0.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 0.0,
        'sobra': 1.0,
        'face_padrao': 'B',
    },
    'SUSP': {
        'nome': 'SUSP',
        'descricao': 'Suspensão com cruzeta (1 cruzeta, 3 paraf. simples)',
        'cruzeta': 1.0,
        'parafuso_simples': 3.0,
        'parafuso_dupla': 0.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 0.0,
        'sobra': 1.0,
        'face_padrao': 'B',
    },
    'SUSP_NU': {
        'nome': 'SUSP_NU',
        'descricao': 'Suspensão direta no poste (0 cruzeta, 2 paraf. simples)',
        'cruzeta': 0.0,
        'parafuso_simples': 2.0,
        'parafuso_dupla': 0.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 0.0,
        'sobra': 1.0,
        'face_padrao': 'B',
    },
}

# ── Catálogo de Estruturas (ESTRUTURAS) ────────────────────────────────────

ESTRUTURAS_PADRAO: Dict[str, List[Dict[str, Any]]] = {
    'N1': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N1', 'inverte': 0},
    ],
    '2N1': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N1', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.4', 'montagem': 'N1', 'inverte': 0},
    ],
    'N4': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.C', 'inverte': 0},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.B', 'inverte': 0},
    ],
    '2N4': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.C', 'inverte': 0},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.B', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.4', 'montagem': 'N4.C', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.4', 'montagem': 'N4.B', 'inverte': 0},
    ],
    '(N3-N3)': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.C', 'inverte': 1},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.B', 'inverte': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'N3.B', 'inverte': 0},
    ],
    '2(N3-N3)': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.C', 'inverte': 1},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.B', 'inverte': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'N3.C', 'inverte': 1},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'N3.B', 'inverte': 1},
        {'nivel': 4, 'distancia_prog': '3.4', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 4, 'distancia_prog': '3.4', 'montagem': 'N3.B', 'inverte': 0},
    ],
    'N4(N3-N3)': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.C', 'inverte': 0},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.B', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.4', 'montagem': 'N3.C', 'inverte': 1},
        {'nivel': 2, 'distancia_prog': '1.4', 'montagem': 'N3.B', 'inverte': 1},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'N3.B', 'inverte': 0},
    ],
    'N4-N3': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.C', 'inverte': 0},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.B', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.4', 'montagem': 'N3.C', 'inverte': 1},
        {'nivel': 2, 'distancia_prog': '1.4', 'montagem': 'N3.B', 'inverte': 1},
    ],
    '(N3-N3)-N4-N3': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.C', 'inverte': 1},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.B', 'inverte': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'N4.C', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'N4.B', 'inverte': 0},
        {'nivel': 4, 'distancia_prog': '3.4', 'montagem': 'N3.C', 'inverte': 1},
        {'nivel': 4, 'distancia_prog': '3.4', 'montagem': 'N3.B', 'inverte': 1},
    ],
    'N3-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'SUSP', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': 'CH+1.2', 'montagem': 'CHAVE', 'inverte': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.9', 'montagem': 'SUSP_NU', 'inverte': 0},
    ],
    'N3.TR': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': 'CH+1.2', 'montagem': 'SUSP_NU', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': 'CH+2.9', 'montagem': 'SUSP_NU', 'inverte': 0},
    ],
    '2N3-2CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'SUSP', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.4', 'montagem': 'CHAVE', 'inverte': 0},
        {'nivel': 5, 'distancia_prog': 'CH+4.1', 'montagem': 'SUSP_NU', 'inverte': 0},
    ],
    '2N3-2TR': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'SUSP', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.4', 'montagem': 'SUSP_NU', 'inverte': 0},
        {'nivel': 5, 'distancia_prog': 'CH+4.1', 'montagem': 'SUSP_NU', 'inverte': 0},
    ],
    'N3-CHP-02': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'SUSP', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': 'CH+1.2', 'montagem': 'CHAVE', 'inverte': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.9', 'montagem': 'SUSP_NU', 'inverte': 0},
    ],
    '2N3-2CHP-02': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'SUSP', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': '2.2', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': '2.2', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.2', 'montagem': 'CHAVE', 'inverte': 0},
        {'nivel': 5, 'distancia_prog': 'CH+3.9', 'montagem': 'SUSP_NU', 'inverte': 0},
    ],
    'N4-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.C', 'inverte': 0},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.B', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'SUSP', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': 'CH+1.2', 'montagem': 'CHAVE', 'inverte': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.9', 'montagem': 'SUSP_NU', 'inverte': 0},
    ],
    '2N4-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.C', 'inverte': 0},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.B', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.4', 'montagem': 'N4.C', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.4', 'montagem': 'N4.B', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'SUSP', 'inverte': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.4', 'montagem': 'CHAVE', 'inverte': 0},
        {'nivel': 5, 'distancia_prog': 'CH+4.1', 'montagem': 'SUSP_NU', 'inverte': 0},
    ],
    '2(N3-N3)-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.C', 'inverte': 1},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N3.B', 'inverte': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'N3.C', 'inverte': 1},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'N3.B', 'inverte': 1},
        {'nivel': 4, 'distancia_prog': '3.4', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 4, 'distancia_prog': '3.4', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 5, 'distancia_prog': '4.4', 'montagem': 'SUSP', 'inverte': 0},
        {'nivel': 6, 'distancia_prog': 'CH+4.4', 'montagem': 'CHAVE', 'inverte': 0},
        {'nivel': 7, 'distancia_prog': 'CH+6.1', 'montagem': 'SUSP_NU', 'inverte': 0},
    ],
    'N4-N3-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.C', 'inverte': 0},
        {'nivel': 1, 'distancia_prog': '0.2', 'montagem': 'N4.B', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.4', 'montagem': 'N3.C', 'inverte': 0},
        {'nivel': 2, 'distancia_prog': '1.4', 'montagem': 'N3.B', 'inverte': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'montagem': 'SUSP', 'inverte': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.4', 'montagem': 'CHAVE', 'inverte': 0},
        {'nivel': 5, 'distancia_prog': 'CH+4.1', 'montagem': 'SUSP_NU', 'inverte': 0},
    ],
}


def gerar_linhas_iniciais_estruturas() -> Dict[str, List[Dict[str, Any]]]:
    """Converte o catálogo de ESTRUTURAS_PADRAO e PADROES_MONTAGEM para a grade completa
    de elementos por nível (Cruzeta, Máquina e Rosca Dupla com todos os seus componentes)."""
    res = {}
    for est_nome, niveis in ESTRUTURAS_PADRAO.items():
        linhas = []
        for idx, n in enumerate(niveis, 1):
            mont_nome = n.get('montagem', 'N1')
            mont = PADROES_MONTAGEM.get(mont_nome, PADROES_MONTAGEM['N1'])
            inv = int(n.get('inverte', 0))
            face_base = mont.get('face_padrao', 'B').upper()
            if face_base == 'B' and inv:
                face = 'A'
            elif face_base == 'A' and inv:
                face = 'B'
            else:
                face = face_base
                
            p_simples = float(mont.get('parafuso_simples', 0))
            p_dupla = float(mont.get('parafuso_dupla', 0))
            
            linhas.append({
                'ordem': idx,
                'nivel': int(n.get('nivel', idx)),
                'distancia_prog': str(n.get('distancia_prog', '0.2')),
                'face': face,
                'cruzeta': float(mont.get('cruzeta', 0)),
                'p_maquina': p_simples,
                'porca_m': float(mont.get('porca', 0)) if p_simples > 0 else 0.0,
                'arruela_m': float(mont.get('arruela', 0)) if p_simples > 0 else 0.0,
                'olhal_m': float(mont.get('porca_olhal', 0)) if p_simples > 0 else 0.0,
                'sobra_m': float(mont.get('sobra', 1)) if p_simples > 0 else 0.0,
                'p_dupla': p_dupla,
                'porca_d': float(mont.get('porca', 0)) if p_dupla > 0 else 0.0,
                'arruela_d': float(mont.get('arruela', 0)) if p_dupla > 0 else 0.0,
                'olhal_d': float(mont.get('porca_olhal', 0)) if p_dupla > 0 else 0.0,
                'sobra_d': float(mont.get('sobra', 1)) if p_dupla > 0 else 0.0,
                'montagem': mont_nome
            })
        res[est_nome] = linhas
    return res


# ── Funções de Cálculo Geométrico ──────────────────────────────────────────

def calcular_engaste(altura_m: float) -> float:
    """Calcula o engaste padrão do poste: H/10 + 0.60 m."""
    return round((altura_m / 10.0) + 0.60, 2)


def calcular_ch(altura_m: float) -> float:
    """Calcula a cota base da chave (CH): H - 0.20 - 6.80 - Engaste."""
    engaste = calcular_engaste(altura_m)
    ch = altura_m - 0.20 - 6.80 - engaste
    return round(max(ch, 0.0), 3)


def estrutura_depende_altura(niveis: List[Dict[str, Any]]) -> bool:
    """Verifica se algum nível possui distância expressa com 'CH'."""
    for n in niveis:
        d = str(n.get('distancia_prog', '')).upper()
        if 'CH' in d:
            return True
    return False


def resolver_distancia_metros(dist_prog: Any, altura_m: Optional[float] = None) -> float:
    """Resolve expressões como '0.2', '1.4', 'CH+1.2', 'CH+2.4' em metros."""
    if isinstance(dist_prog, (int, float)):
        return float(dist_prog)
    
    txt = str(dist_prog).strip().upper().replace(' ', '')
    if 'CH' in txt:
        if altura_m is None or altura_m <= 0:
            raise ValueError(f"A cota '{dist_prog}' depende da altura do poste, mas a altura não foi informada.")
        ch_val = calcular_ch(altura_m)
        if txt == 'CH':
            return ch_val
        match = re.search(r'CH([\+\-])([0-9\.]+)', txt)
        if match:
            sinal = match.group(1)
            valor = float(match.group(2))
            return round(ch_val + valor if sinal == '+' else ch_val - valor, 3)
        return ch_val
    try:
        return float(txt)
    except ValueError:
        raise ValueError(f"Distância inválida: '{dist_prog}'.")


def obter_coeficiente_esforco(esforco_dan: float) -> float:
    """Retorna o coeficiente de esforço do poste duplo T (interpolação linear se fora da tabela)."""
    esf_int = int(esforco_dan)
    if esf_int in COEFICIENTES_ESFORCO:
        return COEFICIENTES_ESFORCO[esf_int]
    if esforco_dan <= 600:
        return 0.0
    return ((esforco_dan - 600.0) / 500.0) * 1.5


def arredondar_comprimento_comercial(comp_mm: float) -> int:
    """Arredonda para cima para o próximo comprimento comercial padrão."""
    for c in COMPRIMENTOS_COMERCIAIS:
        if c >= comp_mm:
            return c
    return COMPRIMENTOS_COMERCIAIS[-1]


def calcular_secao_poste(distancia_m: float, esforco_dan: float, face: str) -> float:
    """Calcula a largura da seção do poste duplo T na cota (mm).
    
    Face A (Topo):   Largura = 140 + 28 * Coef_Esforco + 28 * distancia_m
    Face B (Gaveta): Largura = 110 + 20 * Coef_Esforco + 20 * distancia_m
    """
    face_key = 'A' if str(face).upper() in ('A', 'TOPO') else 'B'
    params = POSTE_DT[face_key]
    coef_esf = obter_coeficiente_esforco(esforco_dan)
    largura = params['topo'] + (params['conicidade'] * coef_esf) + (params['conicidade'] * distancia_m)
    return round(largura, 2)


def calcular_linha_grid(linha: Dict[str, Any], esforco_dan: float, altura_m: Optional[float] = None) -> Dict[str, Any]:
    """Calcula o dimensionamento de uma linha da grade de níveis e elementos."""
    dist_raw = str(linha.get('distancia_prog', '0.2')).strip()
    dist_m = resolver_distancia_metros(dist_raw, altura_m)
    
    face = str(linha.get('face', 'B')).strip().upper()
    if face not in ('A', 'B'):
        face = 'A' if face in ('TOPO', 'A') else 'B'
        
    posicao_nome = 'TOPO' if face == 'A' else 'GAVETA'
    w_poste = calcular_secao_poste(dist_m, esforco_dan, face)
    
    cruzeta = float(linha.get('cruzeta', 0))
    
    # Máquina
    p_maq = float(linha.get('p_maquina', 0))
    porca_m = float(linha.get('porca_m', 0))
    arr_m = float(linha.get('arruela_m', 0))
    olh_m = float(linha.get('olhal_m', 0))
    sob_m = float(linha.get('sobra_m', 1 if p_maq > 0 else 0))

    # Rosca Dupla
    p_dup = float(linha.get('p_dupla', 0))
    porca_d = float(linha.get('porca_d', 0))
    arr_d = float(linha.get('arruela_d', 0))
    olh_d = float(linha.get('olhal_d', 0))
    sob_d = float(linha.get('sobra_d', 1 if p_dup > 0 else 0))

    parafusos = []
    detalhes_m = None
    detalhes_d = None

    if p_maq > 0:
        esp_m = (
            (cruzeta * DIMENSOES_FERRAGENS['cruzeta']) +
            (porca_m * DIMENSOES_FERRAGENS['porca']) +
            (arr_m * DIMENSOES_FERRAGENS['arruela']) +
            (olh_m * DIMENSOES_FERRAGENS['porca_olhal']) +
            (sob_m * DIMENSOES_FERRAGENS['sobra'])
        )
        comp_m = w_poste + esp_m
        comercial_m = arredondar_comprimento_comercial(comp_m)
        detalhes_m = {
            'esp_ferragens': round(esp_m, 2),
            'comp_calc': round(comp_m, 2),
            'comp_comercial': comercial_m,
            'quantidade': p_maq,
        }
        parafusos.append({
            'posicao': posicao_nome,
            'parafuso': 'CABEÇA QUADRADA',
            'esf_parafuso': 50.0,
            'comprimento': comercial_m,
            'quantidade': p_maq,
            'comp_calculado': round(comp_m, 2),
        })

    if p_dup > 0:
        esp_d = (
            (cruzeta * DIMENSOES_FERRAGENS['cruzeta']) +
            (porca_d * DIMENSOES_FERRAGENS['porca']) +
            (arr_d * DIMENSOES_FERRAGENS['arruela']) +
            (olh_d * DIMENSOES_FERRAGENS['porca_olhal']) +
            (sob_d * DIMENSOES_FERRAGENS['sobra'])
        )
        comp_d = w_poste + esp_d
        comercial_d = arredondar_comprimento_comercial(comp_d)
        detalhes_d = {
            'esp_ferragens': round(esp_d, 2),
            'comp_calc': round(comp_d, 2),
            'comp_comercial': comercial_d,
            'quantidade': p_dup,
        }
        parafusos.append({
            'posicao': posicao_nome,
            'parafuso': 'ROSCA DUPLA',
            'esf_parafuso': 70.0,
            'comprimento': comercial_d,
            'quantidade': p_dup,
            'comp_calculado': round(comp_d, 2),
        })

    return {
        'nivel': linha.get('nivel', 1),
        'distancia_prog_raw': dist_raw,
        'distancia_m': round(dist_m, 3),
        'face': face,
        'posicao': posicao_nome,
        'secao_poste_mm': round(w_poste, 2),
        'cruzeta': cruzeta,
        'p_maquina': p_maq,
        'porca_m': porca_m,
        'arruela_m': arr_m,
        'olhal_m': olh_m,
        'sobra_m': sob_m,
        'p_dupla': p_dup,
        'porca_d': porca_d,
        'arruela_d': arr_d,
        'olhal_d': olh_d,
        'sobra_d': sob_d,
        'montagem': linha.get('montagem', ''),
        'detalhes_maquina': detalhes_m,
        'detalhes_dupla': detalhes_d,
        'parafusos': parafusos,
    }


def calcular_estrutura_completa(
    tipo_estrutura: str,
    esforco_dan: float,
    altura_m: Optional[float] = None,
    niveis_grid: Optional[List[Dict[str, Any]]] = None,
    cruzeta_adicional: Optional[float] = None,
) -> Dict[str, Any]:
    """Calcula todos os níveis de uma estrutura a partir da grade de elementos."""
    avisos = []
    
    if niveis_grid is not None and len(niveis_grid) > 0:
        linhas_grid = niveis_grid
    else:
        grid_all = gerar_linhas_iniciais_estruturas()
        linhas_grid = grid_all.get(tipo_estrutura, [])
        if not linhas_grid:
            raise ValueError(f"Estrutura '{tipo_estrutura}' não encontrada no catálogo. "
                             "Forneça a definição de níveis para calcular.")

    dep_alt = estrutura_depende_altura(linhas_grid)
    if dep_alt and (altura_m is None or altura_m <= 0):
        raise ValueError(f"A estrutura '{tipo_estrutura}' depende da altura do poste (possui cotas 'CH'). "
                         "Por favor, informe a altura do poste em metros.")

    detalhes_niveis = []
    todos_parafusos = []
    
    for idx, item in enumerate(linhas_grid, 1):
        calc_res = calcular_linha_grid(item, esforco_dan=esforco_dan, altura_m=altura_m)
        detalhes_niveis.append(calc_res)
        todos_parafusos.extend(calc_res['parafusos'])

    # Consolida os parafusos por (posicao, parafuso, esf_parafuso, comprimento)
    consolidado: Dict[Tuple[str, str, float, int], float] = {}
    for p in todos_parafusos:
        chave = (p['posicao'], p['parafuso'], float(p['esf_parafuso']), int(p['comprimento']))
        consolidado[chave] = consolidado.get(chave, 0.0) + p['quantidade']

    linhas_grade = []
    for (pos, paraf, esf_p, comp), qtd in sorted(consolidado.items(), key=lambda x: (x[0][0], x[0][1], x[0][3])):
        linhas_grade.append({
            'posicao': pos,
            'parafuso': paraf,
            'esf_parafuso': esf_p,
            'comprimento': comp,
            'quantidade': qtd
        })

    return {
        'ok': True,
        'tipo': tipo_estrutura,
        'esforco': esforco_dan,
        'altura': altura_m if dep_alt else None,
        'depende_altura': dep_alt,
        'cruzeta_adicional': float(cruzeta_adicional) if cruzeta_adicional not in (None, '', 0) else None,
        'detalhes_niveis': detalhes_niveis,
        'parafusos_consolidados': linhas_grade,
        'avisos': avisos
    }
