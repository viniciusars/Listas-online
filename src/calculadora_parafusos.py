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

# ── Catálogo de Estruturas (ESTRUTURAS) ────────────────────────────────────

ESTRUTURAS_PADRAO: Dict[str, List[Dict[str, Any]]] = {
    'N1': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 1, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    '2N1': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 1, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.4', 'cruzeta': 1, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    'N4': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 3, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 2, 'sobra_d': 1},
    ],
    '2N4': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 3, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 2, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.4', 'cruzeta': 2, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 3, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 2, 'sobra_d': 1},
    ],
    '(N3-N3)': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    '2(N3-N3)': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 4, 'distancia_prog': '3.4', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    'N4(N3-N3)': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 3, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 2, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.4', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    'N4-N3': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 3, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 2, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.4', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    '(N3-N3)-N4-N3': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 2, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 3, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 2, 'sobra_d': 1},
        {'nivel': 4, 'distancia_prog': '3.4', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    'N3-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 1, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 3, 'distancia_prog': 'CH+1.2', 'cruzeta': 2, 'p_maquina': 4, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 4, 'distancia_prog': 'CH+2.9', 'cruzeta': 0, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    'N3.TR': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': 'CH+1.2', 'cruzeta': 0, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 3, 'distancia_prog': 'CH+2.9', 'cruzeta': 0, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    '2N3-2CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 1, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 4, 'distancia_prog': 'CH+2.4', 'cruzeta': 2, 'p_maquina': 4, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 5, 'distancia_prog': 'CH+4.1', 'cruzeta': 0, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    '2N3-2TR': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 1, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 4, 'distancia_prog': 'CH+2.4', 'cruzeta': 0, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 5, 'distancia_prog': 'CH+4.1', 'cruzeta': 0, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    'N3-CHP-02': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 1, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 3, 'distancia_prog': 'CH+1.2', 'cruzeta': 2, 'p_maquina': 4, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 4, 'distancia_prog': 'CH+2.9', 'cruzeta': 0, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    '2N3-2CHP-02': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 1, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 3, 'distancia_prog': '2.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 4, 'distancia_prog': 'CH+2.2', 'cruzeta': 2, 'p_maquina': 4, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 5, 'distancia_prog': 'CH+3.9', 'cruzeta': 0, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    'N4-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 3, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 2, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 1, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 3, 'distancia_prog': 'CH+1.2', 'cruzeta': 2, 'p_maquina': 4, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 4, 'distancia_prog': 'CH+2.9', 'cruzeta': 0, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    '2N4-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 3, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 2, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.4', 'cruzeta': 2, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 3, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 2, 'sobra_d': 1},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 1, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 4, 'distancia_prog': 'CH+2.4', 'cruzeta': 2, 'p_maquina': 4, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 5, 'distancia_prog': 'CH+4.1', 'cruzeta': 0, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    '2(N3-N3)-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.2', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 4, 'distancia_prog': '3.4', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 5, 'distancia_prog': '4.4', 'cruzeta': 1, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 6, 'distancia_prog': 'CH+4.4', 'cruzeta': 2, 'p_maquina': 4, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 7, 'distancia_prog': 'CH+6.1', 'cruzeta': 0, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
    ],
    'N4-N3-CHP': [
        {'nivel': 1, 'distancia_prog': '0.2', 'cruzeta': 2, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 3, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 2, 'sobra_d': 1},
        {'nivel': 2, 'distancia_prog': '1.4', 'cruzeta': 2, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 3, 'distancia_prog': '2.4', 'cruzeta': 1, 'p_maquina': 3, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 4, 'distancia_prog': 'CH+2.4', 'cruzeta': 2, 'p_maquina': 4, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
        {'nivel': 5, 'distancia_prog': 'CH+4.1', 'cruzeta': 0, 'p_maquina': 2, 'porca_m': 2, 'arruela_m': 2, 'olhal_m': 0, 'sobra_m': 1, 'p_dupla': 0, 'porca_d': 2, 'arruela_d': 2, 'olhal_d': 0, 'sobra_d': 1},
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
                'porca_m': float(n.get('porca_m', 2)),
                'arruela_m': float(n.get('arruela_m', 2)),
                'olhal_m': float(n.get('olhal_m', 0)),
                'sobra_m': float(n.get('sobra_m', 1)),
                'p_dupla': float(n.get('p_dupla', 0)),
                'porca_d': float(n.get('porca_d', 2)),
                'arruela_d': float(n.get('arruela_d', 2)),
                'olhal_d': float(n.get('olhal_d', 0)),
                'sobra_d': float(n.get('sobra_d', 1)),
            })
        res[est_nome] = linhas
    return res


# ── Funções de Cálculo Geométrico ──────────────────────────────────────────

def calcular_engaste(altura_m: float) -> float:
    """Calcula o engaste padrão do poste: H/10 + 0.60 m."""
    return round((altura_m / 10.0) + 0.60, 2)


def calcular_altura_util(altura_m: float) -> float:
    """Calcula a altura útil (comprimento nominal menos engaste)."""
    return round(altura_m - calcular_engaste(altura_m), 2)


def resolver_distancia_metros(distancia_prog: str, altura_m: Optional[float] = None) -> float:
    """Converte expressão de cota de progressão geométrica em metros a partir do topo."""
    s = str(distancia_prog).strip().upper()
    if not s:
        return 0.2

    if s.startswith('CH'):
        if altura_m is None or altura_m <= 0:
            raise ValueError("A cota com referência 'CH' requer a informação da altura nominal do poste.")
        hu = calcular_altura_util(altura_m)
        ch_base = hu - 6.0
        s_rest = s[2:].strip()
        if not s_rest:
            return max(0.0, ch_base)
        if s_rest.startswith('+'):
            val = float(s_rest[1:].replace(',', '.'))
            return max(0.0, ch_base + val)
        elif s_rest.startswith('-'):
            val = float(s_rest[1:].replace(',', '.'))
            return max(0.0, ch_base - val)
        else:
            val = float(s_rest.replace(',', '.'))
            return max(0.0, ch_base + val)

    try:
        return max(0.0, float(s.replace(',', '.')))
    except ValueError:
        return 0.2


def estrutura_depende_altura(niveis: List[Dict[str, Any]]) -> bool:
    """Retorna True se algum nível da estrutura contiver cota 'CH'."""
    for n in niveis:
        dp = str(n.get('distancia_prog', '')).upper()
        if 'CH' in dp:
            return True
    return False


def arredondar_comprimento_comercial(comp_calculado: float) -> int:
    """Retorna o menor comprimento comercial maior ou igual a comp_calculado."""
    for c in COMPRIMENTOS_COMERCIAIS:
        if c >= comp_calculado:
            return c
    return COMPRIMENTOS_COMERCIAIS[-1]


def calcular_secao_poste(distancia_m: float, esforco_dan: float, face: str) -> float:
    """Calcula a seção física da face A (Topo) ou B (Gaveta) em mm."""
    face = face.upper()
    if face not in POSTE_DT:
        face = 'B'
    topo_base = POSTE_DT[face]['topo']
    conicidade = POSTE_DT[face]['conicidade']

    coef_esf = COEFICIENTES_ESFORCO.get(int(esforco_dan), 1.5)
    largura = topo_base + (conicidade * coef_esf) + (conicidade * distancia_m)
    return round(largura, 2)


def calcular_linha_grid(linha: Dict[str, Any], esforco_dan: float, altura_m: Optional[float] = None) -> Dict[str, Any]:
    """Calcula o dimensionamento de uma linha da grade de níveis para AMBAS as faces (Topo e Gaveta)."""
    dist_raw = str(linha.get('distancia_prog', '0.2')).strip()
    dist_m = resolver_distancia_metros(dist_raw, altura_m)
    
    cruzeta = float(linha.get('cruzeta', 0))
    p_maq = float(linha.get('p_maquina', 0))
    porca_m = float(linha.get('porca_m', 2))
    arr_m = float(linha.get('arruela_m', 2))
    olhal_m = float(linha.get('olhal_m', 0))
    sobra_m = float(linha.get('sobra_m', 1))

    p_dup = float(linha.get('p_dupla', 0))
    porca_d = float(linha.get('porca_d', 2))
    arr_d = float(linha.get('arruela_d', 2))
    olhal_d = float(linha.get('olhal_d', 0))
    sobra_d = float(linha.get('sobra_d', 1))

    # Dimensões de seções do poste
    w_topo = calcular_secao_poste(dist_m, esforco_dan, 'A')
    w_gaveta = calcular_secao_poste(dist_m, esforco_dan, 'B')

    # Espessuras somadas de ferragens para Cabeça Quadrada e Rosca Dupla
    esp_m = (cruzeta * DIMENSOES_FERRAGENS['cruzeta']) + \
            (porca_m * DIMENSOES_FERRAGENS['porca']) + \
            (arr_m * DIMENSOES_FERRAGENS['arruela']) + \
            (olhal_m * DIMENSOES_FERRAGENS['porca_olhal']) + \
            (sobra_m * DIMENSOES_FERRAGENS['sobra'])

    esp_d = (cruzeta * DIMENSOES_FERRAGENS['cruzeta']) + \
            (porca_d * DIMENSOES_FERRAGENS['porca']) + \
            (arr_d * DIMENSOES_FERRAGENS['arruela']) + \
            (olhal_d * DIMENSOES_FERRAGENS['porca_olhal']) + \
            (sobra_d * DIMENSOES_FERRAGENS['sobra'])

    parafusos = []
    detalhes_topo = []
    detalhes_gaveta = []

    # 1. FACE A (TOPO)
    if p_maq > 0:
        comp_calc = w_topo + esp_m
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
            'esp_ferragens': round(esp_m, 2),
            'comp_calc': round(comp_calc, 2),
            'comp_comercial': comercial,
            'quantidade': p_maq
        })

    if p_dup > 0:
        comp_calc = w_topo + esp_d
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
            'esp_ferragens': round(esp_d, 2),
            'comp_calc': round(comp_calc, 2),
            'comp_comercial': comercial,
            'quantidade': p_dup
        })

    # 2. FACE B (GAVETA)
    if p_maq > 0:
        comp_calc = w_gaveta + esp_m
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
            'esp_ferragens': round(esp_m, 2),
            'comp_calc': round(comp_calc, 2),
            'comp_comercial': comercial,
            'quantidade': p_maq
        })

    if p_dup > 0:
        comp_calc = w_gaveta + esp_d
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
            'esp_ferragens': round(esp_d, 2),
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
        'porca_m': porca_m,
        'arruela_m': arr_m,
        'olhal_m': olhal_m,
        'sobra_m': sobra_m,
        'p_dupla': p_dup,
        'porca_d': porca_d,
        'arruela_d': arr_d,
        'olhal_d': olhal_d,
        'sobra_d': sobra_d,
        'secao_topo_mm': w_topo,
        'secao_gaveta_mm': w_gaveta,
        'esp_ferragens_m_mm': round(esp_m, 2),
        'esp_ferragens_d_mm': round(esp_d, 2),
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
