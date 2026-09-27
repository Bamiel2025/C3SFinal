"""
Villes et domaines géographiques utilisés dans les activités.

Coordonnées en degrés décimaux WGS84 (le système de la grille ERA5), altitude
en mètres. Les domaines utilisent l'ordre CDS `[Nord, Ouest, Sud, Est]`.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class Place:
    """Une ville ou un point d'intérêt climatique."""

    name: str
    lat: float
    lon: float
    altitude: float = 0.0
    region: str = ""
    coastal: bool = False
    country: str = "France"
    tag: str = ""

    @property
    def area(self) -> tuple[float, float, float, float]:
        """Encadré CDS d'un demi-degré autour du point."""
        return (self.lat + 0.3, self.lon - 0.4, self.lat - 0.3, self.lon + 0.4)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


FRENCH_CITIES: tuple[Place, ...] = (
    Place("Paris", 48.86, 2.35, 35, "Île-de-France", True, tag="océanique atténué, influence urbaine"),
    Place("Brest", 48.39, -4.49, 60, "Bretagne", True, tag="océanique : amplitude faible"),
    Place("Nantes", 47.22, -1.55, 30, "Pays de la Loire", True, tag="transition océanique / continental"),
    Place("Bordeaux", 44.84, -0.58, 49, "Nouvelle-Aquitaine", True, tag="océanique aquitain, été sec"),
    Place("Marseille", 43.30, 5.37, 12, "Provence-Alpes-Côte d'Azur", True, tag="méditerranéen, été sec et caniculaire"),
    Place("Toulouse", 43.60, 1.44, 140, "Occitanie", False, tag="océanique dégradé, été chaud"),
    Place("Lyon", 45.76, 4.84, 165, "Auvergne-Rhône-Alpes", False, tag="continental atténué par l'altitude"),
    Place("Clermont-Ferrand", 45.78, 3.09, 390, "Auvergne-Rhône-Alpes", False, tag="continental, effet du relief"),
    Place("Strasbourg", 48.57, 7.75, 140, "Grand Est", False, tag="continental, hiver froid"),
    Place("Nancy", 48.69, 6.18, 220, "Grand Est", False, tag="forte continentalité"),
    Place("Lille", 50.63, 3.06, 25, "Hauts-de-France", False, tag="transition océanique / continental"),
    Place("Caen", 49.18, -0.37, 20, "Normandie", True, tag="océanique normand"),
    Place("Grenoble", 45.19, 5.72, 212, "Auvergne-Rhône-Alpes", False, tag="continental, plaine alpine"),
    Place("Annecy", 45.90, 6.13, 448, "Auvergne-Rhône-Alpes", False, tag="montagnard lacustre"),
    Place("Le Puy-en-Velay", 45.04, 3.88, 625, "Auvergne-Rhône-Alpes", False, tag="altitude et gradient thermique"),
    Place("Perpignan", 42.69, 2.90, 30, "Occitanie", True, tag="méditerranéen, été très sec"),
    Place("Ajaccio", 41.93, 8.74, 5, "Corse", True, tag="méditerranéen insulaire"),
    Place("Aubagne", 43.29, 5.40, 120, "Provence-Alpes-Côte d'Azur", False, tag="cuvette méditerranéenne ; référence du réchauffement"),
)

WORLD_CITIES: tuple[Place, ...] = (
    Place("Dakar", 14.69, -17.44, 22, "Afrique de l'Ouest", True, "Sénégal", tag="tropical sec et chaud"),
    Place("Bangalore", 12.97, 77.59, 920, "Inde", False, "Inde", tag="mousson, saison très contrastée"),
    Place("Reykjavik", 64.15, -21.94, 61, "Islande", True, "Islande", tag="subarctique océanique"),
    Place("New York", 40.71, -74.01, 10, "Amérique du Nord", True, "États-Unis", tag="continental humide"),
    Place("Le Caire", 30.04, 31.24, 23, "Afrique du Nord", False, "Égypte", tag="désertique chaud"),
    Place("Tokyo", 35.68, 139.65, 40, "Asie de l'Est", True, "Japon", tag="mousson humide"),
    Place("Montréal", 45.50, -73.57, 36, "Québec", False, "Canada", tag="continental très contrasté ; même latitude que Bordeaux"),
    Place("Moscou", 55.75, 37.62, 156, "Europe de l'Est", False, "Russie", tag="continental très contrasté"),
    Place("Longyearbyen", 78.22, 15.65, 30, "Svalbard", True, "Norvège", tag="polaire, été frais"),
    Place("Singapore", 1.35, 103.82, 15, "Asie du Sud-Est", True, "Singapour", tag="tropical humide équatorial"),
    Place("Sydney", -33.87, 151.21, 58, "Australie", True, "Australie", tag="hémisphère sud : saisons inversées"),
    Place("Ushuaia", -54.80, -68.30, 23, "Amérique du Sud", True, "Argentine", tag="polaire maritime"),
    Place("Mexico", 19.43, -99.13, 2240, "Amérique du Nord", False, "Mexique", tag="altitude et saison des pluies"),
)

#: Toutes les villes, indexées par nom (les doublons sont ignorés).
PLACES: dict[str, Place] = {}
for _p in (*FRENCH_CITIES, *WORLD_CITIES):
    PLACES.setdefault(_p.name, _p)


def get(name: str) -> Place | None:
    """Ville par nom, insensible à la casse et aux espaces."""
    if name in PLACES:
        return PLACES[name]
    needle = name.strip().lower()
    for key, place in PLACES.items():
        if key.lower() == needle:
            return place
    return None


def all_places() -> list[Place]:
    return list(PLACES.values())


WORLD = (90.0, -180.0, -90.0, 180.0)


@dataclass(frozen=True)
class Domain:
    """Un domaine géographique nommé."""

    name: str
    area: tuple[float, float, float, float]
    description: str
    size_hint_mb: float = 10.0


DOMAINS: tuple[Domain, ...] = (
    Domain("France métropolitaine", (51.5, -5.5, 41.0, 10.0), "Hexagone et Corse.", 12.0),
    Domain("Europe de l'Ouest", (62.0, -12.0, 36.0, 12.0), "France, Benelux, Royaume-Uni, nord de l'Espagne.", 18.0),
    Domain("Europe", (72.0, -25.0, 33.0, 45.0), "Europe occidentale et centrale.", 30.0),
    Domain("Méditerranée occidentale", (45.0, -2.0, 30.0, 25.0), "Bassin méditerranéen.", 20.0),
    Domain("Afrique de l'Ouest", (20.0, -20.0, 0.0, 20.0), "Golfe de Guinée et Sahel.", 20.0),
    Domain("Monde", WORLD, "Planète entière.", 120.0),
)


def area_label(area: tuple[float, float, float, float]) -> str:
    """Description lisible d'un encadré, pour les titres de cartes."""
    north, west, south, east = area
    if (north, west, south, east) == WORLD or (north >= 89.9 and south <= -89.9):
        return "Monde entier"

    def fmt_lat(x: float) -> str:
        return f"{abs(x):.0f}°{'N' if x >= 0 else 'S'}"

    def fmt_lon(x: float) -> str:
        return f"{abs(x):.0f}°{'E' if x >= 0 else 'O'}"

    return f"{fmt_lat(south)}–{fmt_lat(north)} / {fmt_lon(west)}–{fmt_lon(east)}"
