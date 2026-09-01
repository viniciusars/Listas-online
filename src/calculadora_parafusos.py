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

# ── Catálogo de Montagens Padrão (PADRAO) ──────────────────────────────────

PADROES_MONTAGEM: Dict[str, Dict[str, Any]] = {
    'N1': {
        'nome': 'N1',
        'descricao': 'N1 simples (1 cruzeta, 3 paraf. máquina)',
        'cruzeta': 1.0,
        'parafuso_simples': 3.0,
        'parafuso_dupla': 0.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 0.0,
        'sobra': 1.0,
    },
    'N4': {
        'nome': 'N4',
        'descricao': 'N4 ancoragem (2 cruzetas, 2 paraf. máquina, 3 roscas duplas)',
        'cruzeta': 2.0,
        'parafuso_simples': 2.0,
        'parafuso_dupla': 3.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 0.0,
        'sobra': 1.0,
    },
    'N3': {
        'nome': 'N3',
        'descricao': 'N3 topo/gaveta (2 cruzetas, 3 paraf. máquina)',
        'cruzeta': 2.0,
        'parafuso_simples': 3.0,
        'parafuso_dupla': 0.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 0.0,
        'sobra': 1.0,
    },
    'CHAVE': {
        'nome': 'CHAVE',
        'descricao': 'Montagem Chave (2 cruzetas, 4 paraf. máquina)',
        'cruzeta': 2.0,
        'parafuso_simples': 4.0,
        'parafuso_dupla': 0.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 0.0,
        'sobra': 1.0,
    },
    'SUSP': {
        'nome': 'SUSP',
        'descricao': 'Suspensão com cruzeta (1 cruzeta, 3 paraf. máquina)',
        'cruzeta': 1.0,
        'parafuso_simples': 3.0,
        'parafuso_dupla': 0.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 0.0,
        'sobra': 1.0,
    },
    'SUSP_NU': {
        'nome': 'SUSP_NU',
        'descricao': 'Suspensão direta no poste (0 cruzeta, 2 paraf. máquina)',
        'cruzeta': 0.0,
        'parafuso_simples': 2.0,
        'parafuso_dupla': 0.0,
        'arruela': 2.0,
        'porca': 2.0,
        'porca_olhal': 0.0,
        'sobra': 1.0,
    },
}

# ── Catálogo de Estruturas (ESTRUTURAS) ────────────────────────────────────

ESTRUTURAS_PADRAO: Dict[str, List[Dict[str, Any]]] = {
    'N1': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 1, 'p_maquina': 3, 'p_dupla': 0},
    ],
    '2N1': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 1, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 2, 'distancia_prog': '1.4', 'cruzeta': 1, 'p_maquina': 3, 'p_dupla': 0},
    ],
    'N4': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'p_dupla': 3},
    ],
    '2N4': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'p_dupla': 3},
        {'nivel': 2, 'distancia_prog': '1.4', 'cruzeta': 2, 'p_maquina': 2, 'p_dupla': 3},
    ],
    '(N3-N3)': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
    ],
    '2(N3-N3)': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 4, 'distancia_prog': '3.4', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
    ],
    'N4(N3-N3)': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'p_dupla': 3},
        {'nivel': 2, 'distancia_prog': '1.4', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
    ],
    'N4-N3': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'p_dupla': 3},
        {'nivel': 2, 'distancia_prog': '1.4', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
    ],
    '(N3-N3)-N4-N3': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 2, 'p_maquina': 2, 'p_dupla': 3},
        {'nivel': 4, 'distancia_prog': '3.4', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
    ],
    'N3-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 1, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 3, 'distancia_prog': 'CH+1.2', 'cruzeta': 2, 'p_maquina': 4, 'p_dupla': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.9', 'cruzeta': 0, 'p_maquina': 2, 'p_dupla': 0},
    ],
    'N3.TR': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 2, 'distancia_prog': 'CH+1.2', 'cruzeta': 0, 'p_maquina': 2, 'p_dupla': 0},
        {'nivel': 3, 'distancia_prog': 'CH+2.9', 'cruzeta': 0, 'p_maquina': 2, 'p_dupla': 0},
    ],
    '2N3-2CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 1, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.4', 'cruzeta': 2, 'p_maquina': 4, 'p_dupla': 0},
        {'nivel': 5, 'distancia_prog': 'CH+4.1', 'cruzeta': 0, 'p_maquina': 2, 'p_dupla': 0},
    ],
    '2N3-2TR': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 1, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.4', 'cruzeta': 0, 'p_maquina': 2, 'p_dupla': 0},
        {'nivel': 5, 'distancia_prog': 'CH+4.1', 'cruzeta': 0, 'p_maquina': 2, 'p_dupla': 0},
    ],
    'N3-CHP-02': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 1, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 3, 'distancia_prog': 'CH+1.2', 'cruzeta': 2, 'p_maquina': 4, 'p_dupla': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.9', 'cruzeta': 0, 'p_maquina': 2, 'p_dupla': 0},
    ],
    '2N3-2CHP-02': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 1, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 3, 'distancia_prog': '2.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.2', 'cruzeta': 2, 'p_maquina': 4, 'p_dupla': 0},
        {'nivel': 5, 'distancia_prog': 'CH+3.9', 'cruzeta': 0, 'p_maquina': 2, 'p_dupla': 0},
    ],
    'N4-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'p_dupla': 3},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 1, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 3, 'distancia_prog': 'CH+1.2', 'cruzeta': 2, 'p_maquina': 4, 'p_dupla': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.9', 'cruzeta': 0, 'p_maquina': 2, 'p_dupla': 0},
    ],
    '2N4-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'p_dupla': 3},
        {'nivel': 2, 'distancia_prog': '1.4', 'cruzeta': 2, 'p_maquina': 2, 'p_dupla': 3},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 1, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.4', 'cruzeta': 2, 'p_maquina': 4, 'p_dupla': 0},
        {'nivel': 5, 'distancia_prog': 'CH+4.1', 'cruzeta': 0, 'p_maquina': 2, 'p_dupla': 0},
    ],
    '2(N3-N3)-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 4, 'distancia_prog': '3.4', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 5, 'distancia_prog': '4.4', 'cruzeta': 1, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 6, 'distancia_prog': 'CH+4.4', 'cruzeta': 2, 'p_maquina': 4, 'p_dupla': 0},
        {'nivel': 7, 'distancia_prog': 'CH+6.1', 'cruzeta': 0, 'p_maquina': 2, 'p_dupla': 0},
    ],
    'N4-N3-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'p_dupla': 3},
        {'nivel': 2, 'distancia_prog': '1.4', 'cruzeta': 2, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 1, 'p_maquina': 3, 'p_dupla': 0},
        {'nivel': 4, 'distancia_prog': 'CH+2.4', 'cruzeta': 2, 'p_maquina': 4, 'p_dupla': 0},
        {'nivel': 5, 'distancia_prog': 'CH+4.1', 'cruzeta': 0, 'p_maquina': 2, 'p_dupla': 0},
    ],
}


def gerar_linhas_iniciais_estruturas() -> Dict[str, List[Dict[str, Any]]]:
    """Retorna o catálogo de ESTRUTURAS_PADRAO na grade unificada de níveis."""
    res = {}
    for est_nome, niveis in ESTRUTURAS_PADRAO.items():
        linhas = []
        for idx, n in enumerate(niveis, 1):
            linhas.append({
                'ordem': idx,
                'nivel': int(n.get('nivel', idx)),
                'distancia_prog': str(n.get('distancia_prog', '0.2')),
                'cruzeta': float(n.get('cruzeta', 0)),
                'p_maquina': float(n.get('p_maquina', 0)),
                'p_dupla': float(n.get('p_dupla', 0)),
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
    """Calcula o dimensionamento de uma linha da grade de níveis para AMBAS as faces (Topo e Gaveta)."""
    dist_raw = str(linha.get('distancia_prog', '0.2')).strip()
    dist_m = resolver_distancia_metros(dist_raw, altura_m)
    
    cruzeta = float(linha.get('cruzeta', 0))
    p_maq = float(linha.get('p_maquina', 0))
    p_dup = float(linha.get('p_dupla', 0))

    # Dimensões de seções do poste
    w_topo = calcular_secao_poste(dist_m, esforco_dan, 'A')
    w_gaveta = calcular_secao_poste(dist_m, esforco_dan, 'B')

    # Espessuras somadas de ferragens (cruzeta + 2 porcas + 2 arruelas + 1 sobra = cruzeta*105 + 22 + 8 + 30 = cruzeta*105 + 60)
    esp_ferragens = (cruzeta * DIMENSOES_FERRAGENS['cruzeta']) + (2.0 * DIMENSOES_FERRAGENS['porca']) + (2.0 * DIMENSOES_FERRAGENS['arruela']) + (1.0 * DIMENSOES_FERRAGENS['sobra'])

    parafusos = []
    detalhes_topo = []
    detalhes_gaveta = []

    # 1. FACE A (TOPO)
    if p_maq > 0:
        comp_calc = w_topo + esp_ferragens
        comercial = arredondar_comprimento_comercial(comp_calc)
        parafusos.append({
            'posicao': 'TOPO',
            'parafuso': 'CABEÇA QUADRADA',
            'esf_parafuso': 50.0,
            'comprimento': comercial,
            'quantidade': p_maq,
            'comp_calculado': round(comp_calc, 2),
        })
        detalhes_topo.append({
            'tipo': 'CABEÇA QUADRADA',
            'posicao': 'TOPO',
            'secao_poste': w_topo,
            'esp_ferragens': round(esp_ferragens, 2),
            'comp_calc': round(comp_calc, 2),
            'comp_comercial': comercial,
            'quantidade': p_maq
        })

    if p_dup > 0:
        comp_calc = w_topo + esp_ferragens
        comercial = arredondar_comprimento_comercial(comp_calc)
        parafusos.append({
            'posicao': 'TOPO',
            'parafuso': 'ROSCA DUPLA',
            'esf_parafuso': 70.0,
            'comprimento': comercial,
            'quantidade': p_dup,
            'comp_calculado': round(comp_calc, 2),
        })
        detalhes_topo.append({
            'tipo': 'ROSCA DUPLA',
            'posicao': 'TOPO',
            'secao_poste': w_topo,
            'esp_ferragens': round(esp_ferragens, 2),
            'comp_calc': round(comp_calc, 2),
            'comp_comercial': comercial,
            'quantidade': p_dup
        })

    # 2. FACE B (GAVETA)
    if p_maq > 0:
        comp_calc = w_gaveta + esp_ferragens
        comercial = arredondar_comprimento_comercial(comp_calc)
        parafusos.append({
            'posicao': 'GAVETA',
            'parafuso': 'CABEÇA QUADRADA',
            'esf_parafuso': 50.0,
            'comprimento': comercial,
            'quantidade': p_maq,
            'comp_calculado': round(comp_calc, 2),
        })
        detalhes_gaveta.append({
            'tipo': 'CABEÇA QUADRADA',
            'posicao': 'GAVETA',
            'secao_poste': w_gaveta,
            'esp_ferragens': round(esp_ferragens, 2),
            'comp_calc': round(comp_calc, 2),
            'comp_comercial': comercial,
            'quantidade': p_maq
        })

    if p_dup > 0:
        comp_calc = w_gaveta + esp_ferragens
        comercial = arredondar_comprimento_comercial(comp_calc)
        parafusos.append({
            'posicao': 'GAVETA',
            'parafuso': 'ROSCA DUPLA',
            'esf_parafuso': 70.0,
            'comprimento': comercial,
            'quantidade': p_dup,
            'comp_calculado': round(comp_calc, 2),
        })
        detalhes_gaveta.append({
            'tipo': 'ROSCA DUPLA',
            'posicao': 'GAVETA',
            'secao_poste': w_gaveta,
            'esp_ferragens': round(esp_ferragens, 2),
            'comp_calc': round(comp_calc, 2),
            'comp_comercial': comercial,
            'quantidade': p_dup
        })

    return {
        'nivel': linha.get('nivel', 1),
        'distancia_prog_raw': dist_raw,
        'distancia_m': round(dist_m, 3),
        'cruzeta': cruzeta,
        'p_maquina': p_maq,
        'p_dupla': p_dup,
        'secao_topo_mm': w_topo,
        'secao_gaveta_mm': w_gaveta,
        'esp_ferragens_mm': round(esp_ferragens, 2),
        'detalhes_topo': detalhes_topo,
        'detalhes_gaveta': detalhes_gaveta,
        'parafusos': parafusos,
    }


def calcular_estrutura_completa(
    tipo_estrutura: str,
    esforco_dan: float,
    altura_m: Optional[float] = None,
    niveis_grid: Optional[List[Dict[str, Any]]] = None,
    cruzeta_adicional: Optional[float] = None,
) -> Dict[str, Any]:
    """Calcula todos os níveis de uma estrutura para ambas as faces (Topo e Gaveta)."""
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
    for (pos, paraf, esf_p, comp), qtd in sorted(consolidado.items(), key=lambda x: (0 if x[0][0] == 'GAVETA' else 1, x[0][1], x[0][3])):
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
