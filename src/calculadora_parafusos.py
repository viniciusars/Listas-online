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
    'face_a': {'topo': 140.0, 'conicidade': 28.0},  # mm e mm/m (Face A - Topo)
    'face_b': {'topo': 110.0, 'conicidade': 20.0},  # mm e mm/m (Face B - Gaveta)
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
        'cruzeta': 1,
        'parafuso_simples': 3,
        'parafuso_dupla': 0,
        'arruela': 2,
        'porca': 2,
        'porca_olhal': 0,
        'sobra': 1,
        'face_padrao': 'B',  # Gaveta por padrão
    },
    'N4.C': {
        'nome': 'N4.C',
        'descricao': 'N4 Topo (2 cruzetas, 3 roscas duplas c/ olhais)',
        'cruzeta': 2,
        'parafuso_simples': 0,
        'parafuso_dupla': 3,
        'arruela': 2,
        'porca': 2,
        'porca_olhal': 2,
        'sobra': 1,
        'face_padrao': 'A',  # Face A (Topo)
    },
    'N4.B': {
        'nome': 'N4.B',
        'descricao': 'N4 Gaveta (2 cruzetas, 2 paraf. simples)',
        'cruzeta': 2,
        'parafuso_simples': 2,
        'parafuso_dupla': 0,
        'arruela': 2,
        'porca': 2,
        'porca_olhal': 0,
        'sobra': 1,
        'face_padrao': 'B',  # Face B (Gaveta)
    },
    'N3.C': {
        'nome': 'N3.C',
        'descricao': 'N3 Topo (2 cruzetas, 3 paraf. simples, 1 olhal)',
        'cruzeta': 2,
        'parafuso_simples': 3,
        'parafuso_dupla': 0,
        'arruela': 2,
        'porca': 1,
        'porca_olhal': 1,
        'sobra': 1,
        'face_padrao': 'A',  # Face A (Topo)
    },
    'N3.B': {
        'nome': 'N3.B',
        'descricao': 'N3 Gaveta (2 cruzetas, 2 paraf. simples)',
        'cruzeta': 2,
        'parafuso_simples': 2,
        'parafuso_dupla': 0,
        'arruela': 2,
        'porca': 2,
        'porca_olhal': 0,
        'sobra': 1,
        'face_padrao': 'B',  # Face B (Gaveta)
    },
    'N3.C_1C': {
        'nome': 'N3.C_1C',
        'descricao': 'N3 Topo 1 Cruzeta (1 cruzeta, 3 paraf. simples)',
        'cruzeta': 1,
        'parafuso_simples': 3,
        'parafuso_dupla': 0,
        'arruela': 2,
        'porca': 2,
        'porca_olhal': 0,
        'sobra': 1,
        'face_padrao': 'A',
    },
    'CHAVE': {
        'nome': 'CHAVE',
        'descricao': 'Montagem Chave (2 cruzetas, 4 paraf. simples)',
        'cruzeta': 2,
        'parafuso_simples': 4,
        'parafuso_dupla': 0,
        'arruela': 2,
        'porca': 2,
        'porca_olhal': 0,
        'sobra': 1,
        'face_padrao': 'B',
    },
    'SUSP': {
        'nome': 'SUSP',
        'descricao': 'Suspensão com cruzeta (1 cruzeta, 3 paraf. simples)',
        'cruzeta': 1,
        'parafuso_simples': 3,
        'parafuso_dupla': 0,
        'arruela': 2,
        'porca': 2,
        'porca_olhal': 0,
        'sobra': 1,
        'face_padrao': 'B',
    },
    'SUSP_NU': {
        'nome': 'SUSP_NU',
        'descricao': 'Suspensão direta no poste (0 cruzeta, 2 paraf. simples)',
        'cruzeta': 0,
        'parafuso_simples': 2,
        'parafuso_dupla': 0,
        'arruela': 2,
        'porca': 2,
        'porca_olhal': 0,
        'sobra': 1,
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
        # Processa CH+X ou CH-X
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
    face_key = 'face_a' if face.upper() in ('A', 'TOPO') else 'face_b'
    params = POSTE_DT[face_key]
    coef_esf = obter_coeficiente_esforco(esforco_dan)
    largura = params['topo'] + (params['conicidade'] * coef_esf) + (params['conicidade'] * distancia_m)
    return round(largura, 2)


def calcular_espessura_ferragens(montagem_info: Dict[str, Any], custom_dim: Optional[Dict[str, float]] = None) -> float:
    """Calcula o somatório das espessuras de ferragens e acessórios para a montagem."""
    dim = DIMENSOES_FERRAGENS.copy()
    if custom_dim:
        dim.update(custom_dim)
        
    cruz = float(montagem_info.get('cruzeta', 0))
    porca = float(montagem_info.get('porca', 0))
    arr = float(montagem_info.get('arruela', 0))
    olhal = float(montagem_info.get('porca_olhal', 0))
    sobra = float(montagem_info.get('sobra', 1))

    total = (
        (cruz * dim['cruzeta']) +
        (porca * dim['porca']) +
        (arr * dim['arruela']) +
        (olhal * dim['porca_olhal']) +
        (sobra * dim['sobra'])
    )
    return round(total, 2)


def processar_calculo_nivel(
    nivel_idx: int,
    dist_prog_raw: str,
    montagem_nome: str,
    inverte_flag: int,
    esforco_dan: float,
    altura_m: Optional[float] = None,
    custom_padroes: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Calcula um nível individual e gera os dados detalhados."""
    padroes = custom_padroes or PADROES_MONTAGEM
    mont = padroes.get(montagem_nome)
    if not mont:
        raise ValueError(f"Montagem '{montagem_nome}' não encontrada no cadastro de padrões.")

    dist_m = resolver_distancia_metros(dist_prog_raw, altura_m)
    
    # Determina Face (A ou B)
    face_base = mont.get('face_padrao', 'B').upper()
    if inverte_flag:
        face = 'B' if face_base == 'A' else 'A'
    else:
        face = face_base
        
    posicao_nome = 'TOPO' if face == 'A' else 'GAVETA'
    
    w_poste = calcular_secao_poste(dist_m, esforco_dan, face)
    esp_ferragens = calcular_espessura_ferragens(mont)
    comp_calc = round(w_poste + esp_ferragens, 2)
    comp_comercial = arredondar_comprimento_comercial(comp_calc)
    
    qtd_simples = int(mont.get('parafuso_simples', 0))
    qtd_dupla = int(mont.get('parafuso_dupla', 0))
    
    parafusos_gerados = []
    if qtd_simples > 0:
        parafusos_gerados.append({
            'posicao': posicao_nome,
            'parafuso': 'CABEÇA QUADRADA',
            'esf_parafuso': 50.0,
            'comprimento': comp_comercial,
            'quantidade': float(qtd_simples),
            'comp_calculado': comp_calc,
        })
    if qtd_dupla > 0:
        parafusos_gerados.append({
            'posicao': posicao_nome,
            'parafuso': 'ROSCA DUPLA',
            'esf_parafuso': 70.0,
            'comprimento': comp_comercial,
            'quantidade': float(qtd_dupla),
            'comp_calculado': comp_calc,
        })

    return {
        'nivel': nivel_idx,
        'distancia_prog_raw': str(dist_prog_raw),
        'distancia_m': dist_m,
        'montagem': montagem_nome,
        'inverte': int(inverte_flag),
        'face': face,
        'posicao': posicao_nome,
        'secao_poste_mm': w_poste,
        'ferragens_mm': esp_ferragens,
        'comp_calculado_mm': comp_calc,
        'comp_comercial_mm': comp_comercial,
        'montagem_detalhe': mont,
        'parafusos': parafusos_gerados,
    }


def calcular_estrutura_completa(
    tipo_estrutura: str,
    esforco_dan: float,
    altura_m: Optional[float] = None,
    niveis_custom: Optional[List[Dict[str, Any]]] = None,
    cruzeta_adicional: Optional[float] = None,
    custom_padroes: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Calcula todos os níveis de uma estrutura e consolida os parafusos gerados."""
    avisos = []
    
    # Se não foram fornecidos níveis customizados, busca no catálogo padrão
    if niveis_custom is not None:
        niveis_def = niveis_custom
    else:
        niveis_def = ESTRUTURAS_PADRAO.get(tipo_estrutura)
        if not niveis_def:
            raise ValueError(f"Estrutura '{tipo_estrutura}' não encontrada no catálogo. "
                             "Forneça a definição de níveis para calcular.")

    # Valida necessidade de altura
    dep_alt = estrutura_depende_altura(niveis_def)
    if dep_alt and (altura_m is None or altura_m <= 0):
        raise ValueError(f"A estrutura '{tipo_estrutura}' depende da altura do poste (possui cotas 'CH'). "
                         "Por favor, informe a altura do poste em metros.")

    detalhes_niveis = []
    todos_parafusos = []
    
    for idx, item in enumerate(niveis_def, 1):
        nivel_num = item.get('nivel', idx)
        dist_raw = item.get('distancia_prog', '0.2')
        mont_nome = item.get('montagem', 'N1')
        inv = item.get('inverte', 0)
        
        calc_res = processar_calculo_nivel(
            nivel_idx=nivel_num,
            dist_prog_raw=dist_raw,
            montagem_nome=mont_nome,
            inverte_flag=inv,
            esforco_dan=esforco_dan,
            altura_m=altura_m,
            custom_padroes=custom_padroes
        )
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


def listar_estruturas_disponiveis() -> List[Dict[str, Any]]:
    """Retorna a lista de estruturas do catálogo com resumo de níveis."""
    lista = []
    for nome, niveis in ESTRUTURAS_PADRAO.items():
        dep_alt = estrutura_depende_altura(niveis)
        lista.append({
            'nome': nome,
            'total_niveis': len(niveis),
            'depende_altura': dep_alt,
            'niveis': niveis
        })
    return lista


def listar_padroes_montagem() -> Dict[str, Dict[str, Any]]:
    """Retorna os blocos de montagem padrão disponíveis."""
    return PADROES_MONTAGEM
