"""Recherche uniquement : détection d'un franchissement, aucun ordre MT5."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Signal:
    side: str
    level: float
    trigger: float
    stop: float
    target: float


def signal(previous, current, support, resistance, trend, penetration, stop_distance):
    """Bid en unités de prix. Les niveaux doivent être connus avant le tick courant.

    Le stop est défini depuis le prix indicatif; les frais et le spread sont exclus.
    Aucun signal si la cible est absente ou mal placée.
    """
    values = (previous, current, support, resistance, penetration, stop_distance)
    if not all(isfinite(v) for v in values):
        raise ValueError('Données non finies')
    if min(previous, current, support, resistance, penetration, stop_distance) <= 0 or support >= resistance:
        raise ValueError('Niveaux ou distances invalides')
    if trend not in ('up', 'down', 'none'):
        raise ValueError('Tendance invalide')
    if trend == 'up' and previous > support - penetration >= current:
        return Signal('BUY', support, current, current-stop_distance, resistance)
    if trend == 'down' and previous < resistance + penetration <= current:
        return Signal('SELL', resistance, current, current+stop_distance, support)
    return None
