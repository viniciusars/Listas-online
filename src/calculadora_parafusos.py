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

COMPRIMENTOS_COMERCIAIS = list(range(200, 1501, 50))


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

    if 'CH' in s:
        if altura_m is None or altura_m <= 0:
            raise ValueError("A cota com referência 'CH' requer a informação da altura nominal do poste.")
        hu = calcular_altura_util(altura_m)
        ch_base = max(0.0, round(hu - 6.55, 2))
        s_clean = s.replace('CH', '').replace(' ', '')
        if not s_clean:
            return ch_base
        try:
            val = float(s_clean.replace(',', '.'))
            return max(0.0, round(ch_base + val, 2))
        except ValueError:
            return ch_base

    try:
        return max(0.0, float(s.replace(',', '.')))
    except ValueError:
        return 0.2


def estrutura_depende_altura(niveis: List[Dict[str, Any]]) -> bool:
    """Retorna True se algum nível da estrutura contiver cota 'CH' ou montagem de chave."""
    for n in niveis:
        dp = str(n.get('distancia_prog', '')).upper()
        mont = str(n.get('montagem', '')).upper()
        if 'CH' in dp or 'CHAVE' in mont:
            return True
    return False


def calcular_vao_ch(altura_m: float, cota_anterior: float) -> float:
    """Calcula o vão variável CH baseado na altura do poste e cota anterior.
    
    Fórmula física da concessionária:
    CH = H - cota_anterior + 0.25 - 6.8 - Engastamento (0.1*H + 0.6)
    """
    engastamento = round((0.1 * altura_m) + 0.6, 2)
    ch = round(altura_m - cota_anterior + 0.25 - 6.8 - engastamento, 2)
    return max(0.0, ch)


def calcular_vaos_adicionais(ch: float) -> Tuple[int, List[float]]:
    """
    Se CH >= 5.0m, a cada 3m de distância deve haver cruzetas adicionais espaçadas igualmente.
    Retorna (num_niveis_extras, lista_de_vaos_em_decimos).
    """
    if ch < 5.0:
        return 0, [ch]

    n_vaos = max(2, math.ceil(ch / 3.0))
    total_decimos = round(ch * 10)
    q = total_decimos // n_vaos
    r = total_decimos % n_vaos

    spans = [round(q / 10.0, 1)] * (n_vaos - r) + [round((q + 1) / 10.0, 1)] * r
    k_extras = n_vaos - 1
    return k_extras, spans


def expandir_niveis_com_ch(
    linhas_grid: List[Dict[str, Any]], 
    altura_m: Optional[float]
) -> Tuple[List[Dict[str, Any]], int, Optional[float]]:
    """
    Expande os níveis de uma estrutura caso ela possua chave seccionadora com vão variável (CH).
    Se CH >= 5.0m, insere automaticamente níveis de suporte com 2 cruzetas metálicas a cada <= 3m.
    Retorna (linhas_expandidas, qtd_cruzetas_adicionais, valor_ch).
    """
    if not estrutura_depende_altura(linhas_grid):
        linhas_resolvidas = []
        for idx, l in enumerate(linhas_grid, 1):
            item = dict(l)
            item['nivel'] = int(item.get('nivel') or idx)
            item['cota_m'] = resolver_distancia_metros(str(item.get('distancia_prog', '0.2')), altura_m)
            linhas_resolvidas.append(item)
        return linhas_resolvidas, 0, None

    if altura_m is None or altura_m <= 0:
        raise ValueError("A estrutura possui níveis com vão variável ('CH'). "
                         "Por favor, informe a altura nominal do poste em metros.")

    # 1. Encontra o primeiro nível associado ao vão variável CH (Chave Seccionadora)
    idx_ch = None
    for i, l in enumerate(linhas_grid):
        dp = str(l.get('distancia_prog', '')).upper()
        mont = str(l.get('montagem', '')).upper()
        if 'CH' in dp or 'CHAVE' in mont:
            idx_ch = i
            break

    if idx_ch is None:
        idx_ch = len(linhas_grid) - 1

    # 2. Cota acumulada anterior à chave e nível máximo anterior
    cota_anterior = 0.0
    max_nivel_pre = 0
    if idx_ch > 0:
        cota_anterior = resolver_distancia_metros(str(linhas_grid[idx_ch - 1].get('distancia_prog', '0.2')), altura_m)
        max_nivel_pre = max(int(l.get('nivel', 1)) for l in linhas_grid[:idx_ch])
    else:
        max_nivel_pre = 0

    # 3. Calcula o vão livre variável CH
    valor_ch = calcular_vao_ch(altura_m, cota_anterior)
    k_extras, spans = calcular_vaos_adicionais(valor_ch)
    qtd_cruzetas_adic = k_extras * 2

    # 4. Constrói a lista expandida de níveis
    linhas_expandidas = []

    # Níveis anteriores à chave (preservam seus números de nível originais)
    for i in range(idx_ch):
        item = dict(linhas_grid[i])
        item['nivel'] = int(item.get('nivel', 1))
        c_m = resolver_distancia_metros(str(item.get('distancia_prog', '0.2')), altura_m)
        item['cota_m'] = c_m
        linhas_expandidas.append(item)

    # Níveis intermediários de Cruzeta Adicional (quando CH >= 5.0)
    cota_acum = cota_anterior
    for s_idx in range(k_extras):
        s_val = spans[s_idx]
        cota_acum = round(cota_acum + s_val, 2)
        spans_str = ' + '.join(str(s) for s in spans[:s_idx+1])
        disp_txt = f"{cota_anterior} + {spans_str} ({cota_acum} m)"
        nivel_extra = max_nivel_pre + 1 + s_idx
        linhas_expandidas.append({
            'nivel': nivel_extra,
            'distancia_prog': f"{cota_acum}",
            'distancia_prog_raw': disp_txt,
            'cota_m': cota_acum,
            'montagem': 'CRUZETA ADICIONAL',
            'cruzeta': 2.0,
            'p_maquina': 4.0,
            'esf_maq': 50.0,
            'porca_m': 2.0,
            'arruela_m': 2.0,
            'olhal_m': 0.0,
            'sobra_m': 1.0,
            'p_dupla': 0.0,
            'esf_dup': 70.0,
            'porca_d': 2.0,
            'arruela_d': 2.0,
            'olhal_d': 0.0,
            'sobra_d': 1.0,
            'face_oposta': False,
            'is_auto_cruzeta': True,
            'descricao': 'Nível de suporte dos cabos (Cruzeta adicional)'
        })

    last_intermediate = max_nivel_pre + k_extras
    orig_nivel_ch = int(linhas_grid[idx_ch].get('nivel', max_nivel_pre + 1))
    shift = max(0, (last_intermediate + 1) - orig_nivel_ch) if k_extras > 0 else 0

    # Nível da Chave Seccionadora
    cota_chave = round(cota_anterior + valor_ch, 2)
    disp_chave = f"{cota_anterior} + {' + '.join(str(s) for s in spans)} ({cota_chave} m)" if k_extras > 0 else f"{cota_anterior} + {valor_ch} ({cota_chave} m)"
    linha_ch = dict(linhas_grid[idx_ch])
    linha_ch['nivel'] = int(linha_ch.get('nivel', 1)) + shift
    linha_ch['distancia_prog'] = f"{cota_chave}"
    linha_ch['distancia_prog_raw'] = disp_chave
    linha_ch['cota_m'] = cota_chave
    linhas_expandidas.append(linha_ch)

    # Extrai o valor numérico base associado à chave (ex: 1.2 em 'CH+1.2' ou 0 em 'CH')
    nums_ch = re.findall(r'[\d\.,]+', str(linhas_grid[idx_ch].get('distancia_prog', '')).upper())
    chave_num = float(nums_ch[0].replace(',', '.')) if nums_ch else 0.0

    # Níveis posteriores à Chave (ex: suporte inferior dos cabos)
    for j in range(idx_ch + 1, len(linhas_grid)):
        item = dict(linhas_grid[j])
        item['nivel'] = int(item.get('nivel', 1)) + shift
        dp_raw = str(item.get('distancia_prog', '')).upper()
        if int(linhas_grid[j].get('nivel', 1)) == orig_nivel_ch and ('CH' in dp_raw or not dp_raw):
            cota_post = cota_chave
            disp_post = disp_chave
        else:
            nums = re.findall(r'[\d\.,]+', dp_raw)
            if nums:
                val = float(nums[0].replace(',', '.'))
                if val > chave_num:
                    delta = round(val - chave_num, 2)
                elif val > 0:
                    delta = val
                else:
                    delta = 1.7
            else:
                delta = 1.7
            cota_post = round(cota_chave + delta, 2)
            disp_post = f"{disp_chave} + {delta} ({cota_post} m)" if k_extras > 0 else f"{cota_anterior} + {valor_ch} + {delta} ({cota_post} m)"
        item['distancia_prog'] = f"{cota_post}"
        item['distancia_prog_raw'] = disp_post
        item['cota_m'] = cota_post
        linhas_expandidas.append(item)

    return linhas_expandidas, qtd_cruzetas_adic, valor_ch


def arredondar_comprimento_comercial(comp_calculado: float) -> int:
    """Retorna o menor comprimento comercial maior ou igual a comp_calculado (passos de 50 mm, mínimo 200 mm)."""
    if comp_calculado <= 200:
        return 200
    return int(math.ceil(round(float(comp_calculado), 3) / 50.0) * 50)


def calcular_secao_poste(
    distancia_m: float, 
    esforco_dan: float, 
    face: str,
    config_poste: Optional[Dict[str, Any]] = None
) -> float:
    """Calcula a seção física da face A (Topo) ou B (Gaveta) em mm."""
    face = face.upper()
    if face not in ('A', 'B'):
        face = 'B'
    topo_base = POSTE_DT[face]['topo']
    conicidade = POSTE_DT[face]['conicidade']

    if config_poste:
        if face in config_poste and isinstance(config_poste[face], dict):
            topo_base = float(config_poste[face].get('topo', topo_base))
            conicidade = float(config_poste[face].get('conicidade', conicidade))
        elif face == 'A':
            if 'topo_a' in config_poste and config_poste['topo_a'] is not None:
                topo_base = float(config_poste['topo_a'])
            if 'conicidade_a' in config_poste and config_poste['conicidade_a'] is not None:
                conicidade = float(config_poste['conicidade_a'])
        elif face == 'B':
            if 'topo_b' in config_poste and config_poste['topo_b'] is not None:
                topo_base = float(config_poste['topo_b'])
            if 'conicidade_b' in config_poste and config_poste['conicidade_b'] is not None:
                conicidade = float(config_poste['conicidade_b'])

    coef_esf = COEFICIENTES_ESFORCO.get(int(esforco_dan), 1.5)
    largura = topo_base + (conicidade * coef_esf) + (conicidade * distancia_m)
    return round(largura, 2)


def calcular_linha_grid(
    linha: Dict[str, Any], 
    esforco_dan: float, 
    altura_m: Optional[float] = None,
    config_poste: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Calcula o dimensionamento de uma linha da grade de níveis para AMBAS as faces (Topo e Gaveta)."""
    if 'cota_m' in linha and linha['cota_m'] is not None:
        dist_m = float(linha['cota_m'])
        dist_raw = str(linha.get('distancia_prog_raw', linha.get('distancia_prog', '0.2'))).strip()
    else:
        dist_raw = str(linha.get('distancia_prog_raw', linha.get('distancia_prog', '0.2'))).strip()
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

    esf_maq = float(linha.get('esf_maq', linha.get('esf_maquina', 50.0)))
    esf_dup = float(linha.get('esf_dup', linha.get('esf_dupla', 70.0)))

    is_oposta = bool(linha.get('face_oposta', False) or str(linha.get('face_oposta', '')).strip().lower() in ('1', 'true', 'sim'))

    # Dimensões de seções do poste
    w_topo = calcular_secao_poste(dist_m, esforco_dan, 'A', config_poste=config_poste)
    w_gaveta = calcular_secao_poste(dist_m, esforco_dan, 'B', config_poste=config_poste)

    # Se o poste estiver instalado na posição TOPO:
    # - Nível padrão fura a Face A (Topo)
    # - Nível de Face Oposta (90°) fura a Face B (Gaveta)
    sec_pos_topo = w_gaveta if is_oposta else w_topo
    face_desc_topo = 'GAVETA (Oposta)' if is_oposta else 'TOPO'

    # Se o poste estiver instalado na posição GAVETA:
    # - Nível padrão fura a Face B (Gaveta)
    # - Nível de Face Oposta (90°) fura a Face A (Topo)
    sec_pos_gaveta = w_topo if is_oposta else w_gaveta
    face_desc_gaveta = 'TOPO (Oposta)' if is_oposta else 'GAVETA'

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

    # 1. Posição de Instalação do Poste: TOPO
    if p_maq > 0:
        comp_calc = sec_pos_topo + esp_m
        comercial = arredondar_comprimento_comercial(comp_calc)
        parafusos.append({
            'posicao': 'TOPO',
            'parafuso': 'CABEÇA QUADRADA',
            'esf_parafuso': esf_maq,
            'comprimento': comercial,
            'quantidade': p_maq,
            'comp_calculado': round(comp_calc, 2),
        })
        detalhes_topo.append({
            'tipo': 'CABEÇA QUADRADA',
            'esf_parafuso': esf_maq,
            'posicao': 'TOPO',
            'face_calculada': face_desc_topo,
            'secao_poste': sec_pos_topo,
            'esp_ferragens': round(esp_m, 2),
            'comp_calc': round(comp_calc, 2),
            'comp_comercial': comercial,
            'quantidade': p_maq,
            'is_auto_cruzeta': bool(linha.get('is_auto_cruzeta', False))
        })

    if p_dup > 0:
        comp_calc = sec_pos_topo + esp_d
        comercial = arredondar_comprimento_comercial(comp_calc)
        parafusos.append({
            'posicao': 'TOPO',
            'parafuso': 'ROSCA DUPLA',
            'esf_parafuso': esf_dup,
            'comprimento': comercial,
            'quantidade': p_dup,
            'comp_calculado': round(comp_calc, 2),
        })
        detalhes_topo.append({
            'tipo': 'ROSCA DUPLA',
            'esf_parafuso': esf_dup,
            'posicao': 'TOPO',
            'face_calculada': face_desc_topo,
            'secao_poste': sec_pos_topo,
            'esp_ferragens': round(esp_d, 2),
            'comp_calc': round(comp_calc, 2),
            'comp_comercial': comercial,
            'quantidade': p_dup,
            'is_auto_cruzeta': bool(linha.get('is_auto_cruzeta', False))
        })

    # 2. Posição de Instalação do Poste: GAVETA
    if p_maq > 0:
        comp_calc = sec_pos_gaveta + esp_m
        comercial = arredondar_comprimento_comercial(comp_calc)
        parafusos.append({
            'posicao': 'GAVETA',
            'parafuso': 'CABEÇA QUADRADA',
            'esf_parafuso': esf_maq,
            'comprimento': comercial,
            'quantidade': p_maq,
            'comp_calculado': round(comp_calc, 2),
        })
        detalhes_gaveta.append({
            'tipo': 'CABEÇA QUADRADA',
            'esf_parafuso': esf_maq,
            'posicao': 'GAVETA',
            'face_calculada': face_desc_gaveta,
            'secao_poste': sec_pos_gaveta,
            'esp_ferragens': round(esp_m, 2),
            'comp_calc': round(comp_calc, 2),
            'comp_comercial': comercial,
            'quantidade': p_maq,
            'is_auto_cruzeta': bool(linha.get('is_auto_cruzeta', False))
        })

    if p_dup > 0:
        comp_calc = sec_pos_gaveta + esp_d
        comercial = arredondar_comprimento_comercial(comp_calc)
        parafusos.append({
            'posicao': 'GAVETA',
            'parafuso': 'ROSCA DUPLA',
            'esf_parafuso': esf_dup,
            'comprimento': comercial,
            'quantidade': p_dup,
            'comp_calculado': round(comp_calc, 2),
        })
        detalhes_gaveta.append({
            'tipo': 'ROSCA DUPLA',
            'esf_parafuso': esf_dup,
            'posicao': 'GAVETA',
            'face_calculada': face_desc_gaveta,
            'secao_poste': sec_pos_gaveta,
            'esp_ferragens': round(esp_d, 2),
            'comp_calc': round(comp_calc, 2),
            'comp_comercial': comercial,
            'quantidade': p_dup,
            'is_auto_cruzeta': bool(linha.get('is_auto_cruzeta', False))
        })

    return {
        'nivel': linha.get('nivel', 1),
        'distancia_prog_raw': dist_raw,
        'distancia_m': round(dist_m, 3),
        'face_oposta': is_oposta,
        'is_auto_cruzeta': bool(linha.get('is_auto_cruzeta', False)),
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
    config_poste: Optional[Dict[str, Any]] = None,
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
        raise ValueError(f"A estrutura '{tipo_estrutura}' depende da altura do poste (possui cota de vão variável 'CH'). "
                         "Por favor, informe a altura do poste em metros.")

    linhas_expandidas, qtd_cruzetas_calc, valor_ch = expandir_niveis_com_ch(linhas_grid, altura_m)

    detalhes_niveis = []
    todos_parafusos = []
    
    for idx, item in enumerate(linhas_expandidas, 1):
        calc_res = calcular_linha_grid(item, esforco_dan=esforco_dan, altura_m=altura_m, config_poste=config_poste)
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

    qtd_cruzeta_final = qtd_cruzetas_calc if qtd_cruzetas_calc > 0 else (float(cruzeta_adicional) if cruzeta_adicional not in (None, '', 0) else 0.0)

    total_niveis_unicos = len(set(l.get('nivel', 1) for l in linhas_expandidas))
    total_linhas = len(linhas_expandidas)

    cfg_retorno = {
        'topo_a': float(config_poste['topo_a']) if config_poste and 'topo_a' in config_poste else 140.0,
        'conicidade_a': float(config_poste['conicidade_a']) if config_poste and 'conicidade_a' in config_poste else 28.0,
        'topo_b': float(config_poste['topo_b']) if config_poste and 'topo_b' in config_poste else 110.0,
        'conicidade_b': float(config_poste['conicidade_b']) if config_poste and 'conicidade_b' in config_poste else 20.0,
    }

    return {
        'ok': True,
        'tipo': tipo_estrutura,
        'esforco': esforco_dan,
        'altura': altura_m if dep_alt else None,
        'depende_altura': dep_alt,
        'cruzeta_adicional': qtd_cruzeta_final,
        'qtd_cruzetas_adic': qtd_cruzetas_calc,
        'total_niveis_unicos': total_niveis_unicos,
        'total_linhas': total_linhas,
        'valor_ch': valor_ch,
        'config_poste': cfg_retorno,
        'linhas_expandidas': [
            {
                'nivel': l.get('nivel', 1),
                'distancia_prog': l.get('distancia_prog', '0.2'),
                'distancia_prog_raw': l.get('distancia_prog_raw', l.get('distancia_prog', '0.2')),
                'cota_m': l.get('cota_m', 0.2),
                'montagem': l.get('montagem', ''),
                'cruzeta': l.get('cruzeta', 0),
                'is_auto_cruzeta': l.get('is_auto_cruzeta', False)
            } for l in linhas_expandidas
        ],
        'detalhes_niveis': detalhes_niveis,
        'parafusos_consolidados': linhas_grade,
        'avisos': avisos
    }
