"""
Banque d'activités pédagogiques — réécrite pour C3S².

Deux règles de rédaction, appliquées à **toutes** les étapes :

1. **Une seule question par étape.** Une consigne ne contient jamais deux
   interrogations ni un « et pourquoi ? » en plus : l'élève doit savoir
   exactement ce qui est demandé pour pouvoir répondre.
2. **On décrit le climat, pas la courbe.** La consigne porte sur des
   températures, des précipitations, des amplitudes, des évolutions réelles
   (« de combien la température augmente-t-elle… ») et non sur la forme
   graphique (« décrivez la courbe »), qui ne demande aucune compréhension.

Chaque étape expose également `expected` (corrigé), `hint` (piste) et `chart`
(l'affichage à projeter), afin que la fiche et la donnée restent indissociables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Step:
    """Une étape : une consigne, une seule question, son corrigé."""

    title: str
    instruction: str
    expected: str = ""
    hint: str = ""
    #: Affichage à projeter avec cette étape (`climato`, `annual`, `map`…).
    chart: str = "climato"
    #: Durée indicative de l'étape, en minutes.
    minutes: int = 5


@dataclass
class Activity:
    """Fiche d'activité pédagogique."""

    key: str
    title: str
    levels: str
    duration: str
    subject: str
    objective: str
    skills: tuple[str, ...]
    steps: tuple[Step, ...]
    #: Contexte court, affiché en tête de fiche.
    introduction: str = ""
    default_cities: tuple[str, ...] = ()
    variables: tuple[str, ...] = ("2m_temperature",)
    chart: str = "climato"
    teacher_tip: str = ""
    difficulty: int = 1
    #: Source de données requise : `auto` laisse l'application choisir.
    source: str = "auto"
    keywords: tuple[str, ...] = ()

    def as_dict(self, *, with_answers: bool = False) -> dict[str, Any]:
        """Forme JSON ; les corrigés ne sortent que si `with_answers` est vrai."""
        steps = []
        for i, step in enumerate(self.steps, 1):
            item = {
                "n": i,
                "title": step.title,
                "instruction": step.instruction,
                "chart": step.chart,
                "minutes": step.minutes,
                "hint": step.hint,
            }
            if with_answers:
                item["expected"] = step.expected
            steps.append(item)
        return {
            "key": self.key,
            "title": self.title,
            "levels": self.levels,
            "duration": self.duration,
            "subject": self.subject,
            "objective": self.objective,
            "skills": list(self.skills),
            "introduction": self.introduction,
            "cities": list(self.default_cities),
            "variables": list(self.variables),
            "chart": self.chart,
            "teacher_tip": self.teacher_tip,
            "difficulty": self.difficulty,
            "source": self.source,
            "keywords": list(self.keywords),
            "steps": steps,
            "n_steps": len(self.steps),
        }


# --------------------------------------------------------------------------- #
# 1. Océan / continent
# --------------------------------------------------------------------------- #

OCEAN_CONTINENT = Activity(
    key="ocean_continent",
    title="Océan ou continent : d'où vient l'amplitude thermique ?",
    levels="5e · 4e",
    duration="55 min",
    subject="SVT · Physique-chimie · Géographie",
    objective=(
        "Relier l'amplitude thermique annuelle à la distance à la mer, à partir de "
        "températures réelles mesurées sur deux villes de même latitude."
    ),
    skills=(
        "Lire des valeurs dans une série de températures",
        "Calculer une amplitude (écart entre deux mois)",
        "Expliquer un résultat par un mécanisme physique (inertie thermique)",
    ),
    introduction=(
        "Brest et Strasbourg sont presque à la même latitude (48,4° N et 48,6° N). "
        "Pourtant leur hiver n'a rien d'égal. Les données ERA5 de 1991 à 2020 vont "
        "vous permettre de le mesurer, puis de l'expliquer."
    ),
    default_cities=("Brest", "Strasbourg"),
    variables=("2m_temperature",),
    chart="climato",
    keywords=("amplitude", "inertie", "océan", "continent"),
    teacher_tip=(
        "Faites d'abord formuler une hypothèse au tableau avant d'afficher la "
        "normale mensuelle. Le passage de la mesure à l'explication mécanique est "
        "le cœur de la séance : ne le faites pas à la place des élèves."
    ),
    steps=(
        Step(
            title="Mesurer l'hiver",
            instruction=(
                "Quelle est la température moyenne du mois le plus froid à Brest "
                "et à Strasbourg ?"
            ),
            expected=(
                "Brest : 7,9 °C en février, son mois le plus froid. Strasbourg : "
                "2,4 °C en janvier. L'écart hivernal n'est donc que de 5,5 °C alors "
                "que les deux villes sont à la même latitude."
            ),
            hint="Cherchez le point le plus bas de chaque courbe, puis lisez sa valeur.",
            chart="climato",
            minutes=5,
        ),
        Step(
            title="Calculer l'amplitude",
            instruction=(
                "De combien de degrés la température monte-t-elle, à chaque ville, "
                "entre son mois le plus froid et son mois le plus chaud ?"
            ),
            expected=(
                "Brest : 8,8 °C (de 7,9 °C en février à 16,7 °C en août). "
                "Strasbourg : 17,9 °C (de 2,4 °C en janvier à 20,3 °C en juillet). "
                "L'amplitude de Strasbourg est donc le double de celle de Brest. "
                "Ce calcul — mois le plus chaud moins mois le plus froid — est "
                "l'amplitude thermique annuelle."
            ),
            hint="Amplitude = température du mois le plus chaud − température du mois le plus froid.",
            chart="climato",
            minutes=7,
        ),
        Step(
            title="Expliquer l'écart",
            instruction=(
                "Qu'est-ce qui explique que deux villes de même latitude présentent "
                "des amplitudes aussi différentes ?"
            ),
            expected=(
                "L'eau se réchauffe et se refroidit beaucoup plus lentement que la "
                "roche : l'océan tempère le littoral toute l'année (inertie "
                "thermique), alors que la terre continentale chauffe vite en été et "
                "refroidit vite en hiver."
            ),
            hint="Comparez le temps nécessaire pour chauffer un litre d'eau et une pierre de même masse.",
            chart="climato",
            minutes=8,
        ),
        Step(
            title="Prévoir puis vérifier",
            instruction=(
                "Quelle amplitude thermique annuelle prédis-tu pour Marseille, "
                "ville méditerranéenne ?"
            ),
            expected=(
                "Une amplitude de l'ordre de 14 à 15 °C, soit bien plus qu'à Brest : "
                "la mer tempère l'hiver (9 °C en janvier) mais l'été reste chaud "
                "(23,5 °C en août). Vérification à faire afficher ensuite "
                "(Brest 8,8 °C < Marseille 14,5 °C < Strasbourg 17,9 °C)."
            ),
            hint="Marseille est en bord de mer, mais à 43° N : son été est plus chaud que celui de Brest.",
            chart="climato",
            minutes=5,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 2. Cycle de l'eau
# --------------------------------------------------------------------------- #

CYCLE_EAU = Activity(
    key="cycle_eau",
    title="Cycle de l'eau : d'où viennent les précipitations ?",
    levels="5e · 4e",
    duration="55 min",
    subject="SVT · Physique-chimie (changements d'état)",
    objective=(
        "Relier évaporation, condensation et précipitations aux cumuls mesurés, et "
        "distinguer un régime méditerranéen d'un régime équatorial de mousson."
    ),
    skills=(
        "Construire et lire un diagramme ombrothermique",
        "Identifier un changement d'état à partir de données",
        "Comparer des cumuls mensuels et annuels",
    ),
    introduction=(
        "Marseille et Dakar reçoivent des pluies très différentes, non pas parce "
        "qu'il pleut « plus » quelque part, mais parce que l'eau tombe à des "
        "moments différents de l'année. Le diagramme ombrothermique rassemble "
        "température et pluie sur douze mois."
    ),
    default_cities=("Marseille", "Dakar"),
    variables=("2m_temperature", "total_precipitation"),
    chart="ombro",
    keywords=("mousson", "ombrothermie", "méditerranéen", "cumul"),
    teacher_tip=(
        "Rappeler l'expérience de la serre : air chaud chargé de vapeur qui se "
        "refroidit et se condense. Le nuage et la pluie ne sont que cela, à "
        "l'échelle d'un continent. Insister sur la différence entre cumul annuel "
        "et répartition mensuelle : c'est la confusion la plus fréquente."
    ),
    steps=(
        Step(
            title="Repérer le minimum",
            instruction=(
                "Dans quel mois Marseille reçoit-elle le moins de précipitations ?"
            ),
            expected=(
                "En juillet : environ 10 mm seulement, ce qui correspond à une "
                "sécheresse estivale franche. Le régime est méditerranéen."
            ),
            hint="Regardez les barres de pluie : la plus courte indique le mois le plus sec.",
            chart="ombro",
            minutes=4,
        ),
        Step(
            title="Confronter chaleur et pluie",
            instruction=(
                "Le mois le plus chaud de Marseille est-il aussi le plus humide ?"
            ),
            expected=(
                "Non : juillet-août sont à la fois les mois les plus chauds "
                "(environ 23 °C) et les plus secs (10 et 15 mm). C'est l'inverse "
                "de ce que produit la mousson."
            ),
            hint="Comparez la courbe de température et les barres de pluie pour le même mois.",
            chart="ombro",
            minutes=5,
        ),
        Step(
            title="Comparer les totaux",
            instruction=(
                "Quelle ville, Marseille ou Dakar, reçoit le plus d'eau sur une "
                "année entière ?"
            ),
            expected=(
                "Marseille : environ 600 mm par an, contre seulement 280 mm à "
                "Dakar. Mais surtout, la répartition est à l'opposé : Dakar "
                "concentre 250 mm sur trois mois (juillet-septembre), alors que "
                "Marseille étale sa pluie sur l'automne et l'hiver (octobre à "
                "décembre : 240 mm) et reste sèche en été."
            ),
            hint="Additionnez les douze cumuls mensuels : c'est le cumul annuel.",
            chart="ombro",
            minutes=6,
        ),
        Step(
            title="Expliquer la saison des pluies",
            instruction=(
                "Pourquoi les pluies de Dakar tombent-elles surtout pendant "
                "l'été boréal (juillet-septembre), alors que Marseille reste "
                "sèche à la même période ?"
            ),
            expected=(
                "En juillet-septembre, l'été boréal réchauffe l'Atlantique "
                "tropical : l'eau s'évapore, l'air chaud chargé de vapeur "
                "s'élève, se refroidit et se condense — c'est la mousson "
                "ouest-africaine, qui apporte 250 mm à Dakar en trois mois. À "
                "Marseille, l'été est dominé par une atmosphère stable et sèche : "
                "l'air chaud y reste au sol, il ne s'élève pas, donc il ne se "
                "condense pas."
            ),
            hint="Reliez les mots « évaporation », « condensation » et « ascendance » aux deux villes.",
            chart="ombro",
            minutes=8,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 3. Réchauffement climatique
# --------------------------------------------------------------------------- #

RECHAUFFEMENT = Activity(
    key="rechauffement",
    title="Mesurer le réchauffement climatique avec des données",
    levels="4e · 3e",
    duration="55 min",
    subject="SVT · Mathématiques",
    objective=(
        "Quantifier la hausse des températures par décennie, à partir de moyennes "
        "annuelles et d'anomalies, puis formuler une conclusion prudente."
    ),
    skills=(
        "Calculer un écart à une moyenne de référence (normale)",
        "Lire une tendance en tant que valeur par décennie",
        "Distinguer variabilité naturelle et tendance de fond",
    ),
    introduction=(
        "Une année froide n'invalide pas un réchauffement, et une année chaude ne "
        "le prouve pas à elle seule. Seule la comparaison de périodes entières, "
        "rapportées à une même normale, permet de parler d'évolution du climat."
    ),
    default_cities=("Paris", "Strasbourg"),
    variables=("2m_temperature",),
    chart="annual",
    source="auto",
    keywords=("anomalie", "normale", "tendance", "décennie"),
    difficulty=2,
    teacher_tip=(
        "Insister sur la normale 1991-2020 de l'OMM : comparer une période à "
        "elle-même est la seule méthode qui rende les chiffres comparables entre "
        "villes et entre pays. Faire écrire aux élèves la phrase de conclusion "
        "avant de révéler le corrigé."
    ),
    steps=(
        Step(
            title="Calculer la hausse observée",
            instruction=(
                "De combien la température moyenne annuelle de Paris a-t-elle "
                "augmenté entre le début et la fin de la période affichée ?"
            ),
            expected=(
                "Les dix premières années (1940-1949) donnent 10,7 °C de moyenne "
                "annuelle, les dix dernières (2015-2024) 12,2 °C : Paris a donc "
                "gagné environ 1,6 °C sur la période affichée. On retient "
                "l'ordre de grandeur — un degré et demi environ — plus qu'un "
                "chiffre unique."
            ),
            hint="Comparez la moyenne des dix premières années à celle des dix dernières.",
            chart="annual",
            minutes=7,
        ),
        Step(
            title="Quantifier par décennie",
            instruction=(
                "De combien la température augmente-t-elle, en moyenne, chaque "
                "décennie à Paris ?"
            ),
            expected=(
                "Environ +0,2 °C par décennie sur 1940-2024 (la régression "
                "linéaire affichée donne +0,21 °C par décennie). La hausse n'est "
                "pas régulière : elle est nulle, voire négative, jusqu'aux années "
                "1980 puis s'accélère nettement depuis. La valeur exacte figure "
                "dans le tableau d'indices."
            ),
            hint="La tendance est une droite : son coefficient directeur donne l'évolution par an, multiplié par 10.",
            chart="annual",
            minutes=6,
        ),
        Step(
            title="Écarter un contre-exemple",
            instruction=(
                "Pourquoi une seule année froide suffit-elle à convaincre certains "
                "que « le climat ne change pas » ?"
            ),
            expected=(
                "Parce qu'on compare deux années isolées au lieu de comparer des "
                "décennies : la variabilité naturelle d'une année à l'autre "
                "(environ ±0,5 à 1 °C) est du même ordre que la tendance sur une "
                "seule décennie. Seule une moyenne longue fait apparaître la tendance."
            ),
            hint="Comparez l'écart d'une année à l'autre avec la tendance sur dix ans.",
            chart="anomalies",
            minutes=8,
        ),
        Step(
            title="Rédiger la conclusion",
            instruction=(
                "Écris une phrase qui dit ce que ces données permettent d'affirmer "
                "sur le climat de Paris."
            ),
            expected=(
                "Exemple attendu : « Sur la période 1940-2024, la température "
                "moyenne annuelle de Paris a augmenté d'environ 0,2 °C par "
                "décennie, soit +1,6 °C entre les années 1940 et les années "
                "2020, avec une accélération depuis les années 1980. » La "
                "phrase doit citer une période, une grandeur et une valeur."
            ),
            hint="Une conclusion scientifique cite toujours une période, une grandeur mesurée et une valeur.",
            chart="anomalies",
            minutes=8,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 4. Cartes climatiques
# --------------------------------------------------------------------------- #

CARTES = Activity(
    key="cartes_climatiques",
    title="Lire une carte climatique sans se tromper",
    levels="4e · 3e",
    duration="55 min",
    subject="Géographie · SVT",
    objective=(
        "Lire une carte de températures ou de précipitations, choisir une échelle "
        "de couleurs honnête, et distinguer un climat d'une situation de météo."
    ),
    skills=(
        "Lire une carte thématique et son dégradé de couleurs",
        "Choisir une échelle de couleurs non trompeuse",
        "Distinguer une moyenne longue d'une situation ponctuelle",
    ),
    introduction=(
        "Une carte de climat n'est jamais « la météo » : c'est une moyenne "
        "calculée sur de longues périodes. Changer le mois ou la variable change "
        "radicalement la carte — c'est tout l'intérêt de la comparer."
    ),
    default_cities=("Paris",),
    variables=("2m_temperature", "total_precipitation"),
    chart="map",
    keywords=("carte", "isotherme", "normal", "climat"),
    difficulty=2,
    teacher_tip=(
        "Faire alterner janvier et juillet avant de commenter : c'est le "
        "contraste entre les deux cartes qui fait comprendre l'effet continent "
        "et l'effet de mer. Insister sur le fait qu'une carte de moyenne n'est "
        "pas une carte du temps."
    ),
    steps=(
        Step(
            title="Lire la normale de janvier",
            instruction=(
                "Quelle région européenne est la plus froide en janvier selon la "
                "carte des températures ?"
            ),
            expected=(
                "Le nord-est de l'Europe (Russie occidentale, Finlande, Scandinavie "
                "intérieure), avec des moyennes mensuelles souvent sous 0 °C, "
                "voire sous −10 °C. Les côtes atlantiques restent très nettement "
                "plus chaudes à même latitude."
            ),
            hint="Cherchez la couleur la plus froide du dégradé, puis situez-la sur la carte.",
            chart="map",
            minutes=6,
        ),
        Step(
            title="Comparer janvier et juillet",
            instruction=(
                "Que se passe-t-il pour la Méditerranée entre la carte de janvier "
                "et celle de juillet ?"
            ),
            expected=(
                "La Méditerranée passe d'un hiver doux (moyennes de l'ordre de "
                "10 °C sur le bassin en janvier) à un été très chaud (environ "
                "25 °C en moyenne en juillet, plus de 35 °C sur certains "
                "rivages). L'effet de mer limite l'hiver, pas l'été : "
                "l'amplitude y est donc plus faible qu'à l'intérieur des terres, "
                "mais l'été y fait partie des plus chauds d'Europe."
            ),
            hint="Comparez la même zone sur les deux cartes et notez les deux valeurs.",
            chart="map",
            minutes=7,
        ),
        Step(
            title="Choisir la bonne échelle",
            instruction=(
                "Une carte qui utilise deux degrés de couleur par cran rend-elle "
                "mieux les contrastes qu'une carte à dix crans ?"
            ),
            expected=(
                "Non : un pas trop gros (2 °C) masque les variations locales ; un "
                "pas trop fin (0,2 °C) noie l'information dans trop de nuances. "
                "Le bon choix dépend de l'ampleur des écarts à montrer — et il "
                "doit être indiqué sur la carte."
            ),
            hint="Posez la question inverse : que voit-on si chaque cran vaut 10 °C ?",
            chart="map",
            minutes=6,
        ),
        Step(
            title="Climat ou météo ?",
            instruction=(
                "Une carte de températures de trois mois suffit-elle à décrire le "
                "climat d'un pays ?"
            ),
            expected=(
                "Non : le climat se décrit sur au moins trente ans (normale OMM "
                "1991-2020). Trois mois relèvent de la météo, c'est-à-dire de "
                "l'état ponctuel de l'atmosphère."
            ),
            hint="Combien d'années l'OMM utilise-t-elle pour définir une normale climatique ?",
            chart="map",
            minutes=5,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 5. Pression et vent
# --------------------------------------------------------------------------- #

VENT_PRESSION = Activity(
    key="vent_pression",
    title="Pression atmosphérique et direction du vent",
    levels="3e · 4e",
    duration="55 min",
    subject="Physique-chimie · SVT",
    objective=(
        "Relier les zones de hautes et de basses pressions à la circulation du "
        "vent, et comprendre pourquoi l'air se met en mouvement."
    ),
    skills=(
        "Lire une carte de pression et ses isobares",
        "Interpréter des vecteurs vent",
        "Relier une différence de pression et un mouvement de l'air",
    ),
    introduction=(
        "Le vent n'est rien d'autre que de l'air en mouvement sous l'effet d'une "
        "différence de pression. La carte de normale de janvier montre cette "
        "mécanique sur toute l'Europe de l'Ouest."
    ),
    default_cities=("Paris",),
    variables=("mean_sea_level_pressure",),
    chart="map",
    source="cds",
    keywords=("pression", "vent", "isobare", "gradient"),
    difficulty=3,
    teacher_tip=(
        "Rappeler que le vent ne franchit pas perpendiculairement les isobares : "
        "la rotation de la Terre le dévie (force de Coriolis), ce qui explique le "
        "tourbillon autour des dépressions de l'hémisphère nord."
    ),
    steps=(
        Step(
            title="Repérer la valeur de référence",
            instruction=(
                "Quelle est la valeur habituelle de la pression atmosphérique au "
                "niveau de la mer ?"
            ),
            expected=(
                "Environ 1013 hPa. C'est la valeur de référence autour de laquelle "
                "oscillent les hautes pressions (1020 à 1040 hPa) et les basses "
                "pressions (980 à 1000 hPa)."
            ),
            hint="La valeur se lit sur la légende de la carte, entre les deux extrêmes.",
            chart="map",
            minutes=4,
        ),
        Step(
            title="Localiser les systèmes",
            instruction=(
                "Où se trouvent les hautes pressions sur la carte de janvier, et "
                "où se trouvent les basses pressions ?"
            ),
            expected=(
                "Les hautes pressions occupent l'Atlantique subtropical et "
                "l'Afrique du Nord-Ouest (maximum de la carte : 1024 hPa vers "
                "35° N, 20° O) ; les basses pressions se concentrent sur "
                "l'Atlantique nord et à l'ouest de l'Islande (minimum : 996 hPa "
                "vers 63° N). L'Europe occidentale, vers 1019 hPa, se situe "
                "entre les deux."
            ),
            hint="Les hautes pressions portent des couleurs chaudes, les basses des couleurs froides.",
            chart="map",
            minutes=6,
        ),
        Step(
            title="Relier pression et vent",
            instruction=(
                "Dans quelle direction l'air se déplace-t-il spontanément entre "
                "une zone de hautes pressions et une zone de basses pressions ?"
            ),
            expected=(
                "Des hautes vers les basses : c'est le gradient de pression qui "
                "accélère l'air. Ensuite, la rotation de la Terre le fait tourner "
                "autour des dépressions dans l'hémisphère nord."
            ),
            hint="Retournez le raisonnement : que se passerait-il si la pression était partout identique ?",
            chart="map",
            minutes=7,
        ),
        Step(
            title="Vérifier avec les flèches",
            instruction=(
                "Les flèches de vent de la carte suivent-elles la direction "
                "prédite à l'étape précédente ?"
            ),
            expected=(
                "Oui, à condition de tenir compte de la déviation : les flèches ne "
                "vont pas droit de l'anticyclone vers la dépression, elles "
                "s'enroulent le long des isobares, dans le sens des aiguilles "
                "d'une montre autour d'une hauteur."
            ),
            hint="Suivez une flèche placée sur une isobare et observez son angle avec celle-ci.",
            chart="map",
            minutes=7,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 6. Latitude et rayonnement
# --------------------------------------------------------------------------- #

LATITUDE = Activity(
    key="latitude",
    title="Latitude et température : pourquoi fait-il froid aux pôles ?",
    levels="4e · 3e",
    duration="55 min",
    subject="Physique-chimie · SVT · Géographie",
    objective=(
        "Relier la baisse des températures à la latitude en confrontant une "
        "prédiction écrite à des mesures réelles de quatre villes."
    ),
    skills=(
        "Prévoir avant de mesurer, puis confronter",
        "Classer des valeurs et interpréter un écart",
        "Rédiger une conclusion fondée sur des données",
    ),
    introduction=(
        "Quatre villes, quatre latitudes : Dakar (15° N), Paris (49° N), "
        "Reykjavik (64° N) et Longyearbyen (78° N). Vous allez d'abord prédire "
        "leurs températures de janvier, puis les vérifier."
    ),
    default_cities=("Dakar", "Paris", "Reykjavik", "Longyearbyen"),
    variables=("2m_temperature",),
    chart="climato",
    keywords=("latitude", "rayonnement", "obliquité", "saison"),
    difficulty=2,
    teacher_tip=(
        "Dérouler l'activité en deux temps : la prédiction écrite d'abord, la "
        "donnée ensuite. C'est la confrontation entre les deux qui produit "
        "l'apprentissage — pas le graphique lui-même."
    ),
    steps=(
        Step(
            title="Prédire sans regarder",
            instruction=(
                "Classe ces quatre villes de la plus chaude à la plus froide pour "
                "le mois de janvier, sans consulter les données."
            ),
            expected=(
                "Classement attendu : Dakar > Paris > Reykjavik > Longyearbyen. "
                "L'élève écrit son classement au brouillon et le conserve : il "
                "servira de comparaison à l'étape suivante."
            ),
            hint="Pense à la latitude de chaque ville (15°, 49°, 64°, 78° N).",
            chart="none",
            minutes=5,
        ),
        Step(
            title="Vérifier avec les mesures",
            instruction=(
                "Quelle ville est la plus chaude en janvier, et de combien "
                "dépasse-t-elle Paris ?"
            ),
            expected=(
                "Dakar, avec 21,5 °C de moyenne en janvier, contre 4,3 °C à "
                "Paris : un écart de 17 °C pour 34 degrés de latitude. Longyearbyen, "
                "elle, descend à −13,6 °C."
            ),
            hint="Lis la température de janvier sur la courbe de chaque ville.",
            chart="climato",
            minutes=6,
        ),
        Step(
            title="Identifier la surprise",
            instruction=(
                "Pourquoi Reykjavik est-elle moins froide que ne le laissait "
                "prévoir sa latitude ?"
            ),
            expected=(
                "Reykjavik (64° N) affiche −0,3 °C en janvier, alors que la "
                "latitude seule la placerait nettement plus bas : 14 degrés "
                "séparent seulement Longyearbyen (−13,6 °C) et l'Islande, pourtant "
                "un écart de 13 °C les oppose. L'océan Atlantique nord et le "
                "courant du Gulf Stream y transportent la chaleur. La latitude "
                "n'explique pas tout."
            ),
            hint="Compare sa latitude à celle de Longyearbyen, qui pourtant n'est pas beaucoup plus au nord.",
            chart="climato",
            minutes=7,
        ),
        Step(
            title="Formuler le mécanisme",
            instruction=(
                "Pourquoi reçoit-on moins d'énergie solaire quand la latitude "
                "augmente ?"
            ),
            expected=(
                "Plus on approche des pôles, plus les rayons arrivent de biais : "
                "la même énergie est répartie sur une surface plus grande, et "
                "elle traverse une atmosphère plus épaisse. L'échauffement est "
                "donc moindre."
            ),
            hint="Imagine un faisceau de lampe torche dirigé droit puis incliné sur le sol.",
            chart="climato",
            minutes=8,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 7. Avant / après
# --------------------------------------------------------------------------- #

AVANT_APRES = Activity(
    key="avant_apres",
    title="Comparer deux périodes : a-t-il vraiment changé ?",
    levels="4e · 3e",
    duration="55 min",
    subject="Mathématiques · SVT · Géographie",
    objective=(
        "Comparer deux périodes séparées de plusieurs décennies et interpréter "
        "la différence moyenne obtenue."
    ),
    skills=(
        "Comparer deux moyennes d'échantillons de taille differente",
        "Interpréter un écart en tant qu'anomalie",
        "Distinguer fluctuations et changement de régime",
    ),
    introduction=(
        "Choisissez deux périodes de trente ans séparées par au moins un "
        "siècle : la différence entre les deux moyennes est l'anomalie qui vous "
        "intéresse, et elle se mesure mois par mois."
    ),
    default_cities=("Paris", "Marseille"),
    variables=("2m_temperature",),
    chart="compare",
    keywords=("comparaison", "période", "anomalie", "moyenne"),
    difficulty=2,
    teacher_tip=(
        "Faire remarquer que l'écart n'est pas le même en hiver et en été : "
        "le réchauffement n'est pas uniforme sur l'année. C'est un point que les "
        "manuels omettent souvent."
    ),
    steps=(
        Step(
            title="Choisir les périodes",
            instruction=(
                "Quelles deux périodes de trente ans faut-il comparer pour mesurer "
                "le changement depuis le début du XXe siècle ?"
            ),
            expected=(
                "Par exemple 1901-1930 (ou 1941-1970, première période "
                "disponible ici) contre 1991-2020 (la normale OMM actuelle). Les "
                "deux périodes doivent avoir la même durée pour être comparables."
            ),
            hint="Deux périodes comparables ont le même nombre d'années.",
            chart="compare",
            minutes=5,
        ),
        Step(
            title="Mesurer l'écart moyen",
            instruction=(
                "De combien la température moyenne annuelle de Paris diffère-t-elle "
                "entre les deux périodes ?"
            ),
            expected=(
                "Pour Paris : 10,5 °C en 1941-1970 contre 11,5 °C en 1991-2020, "
                "soit un écart d'environ +1 °C. À Marseille, le même calcul donne "
                "+0,9 °C. Les valeurs exactes des deux moyennes s'affichent sous "
                "le graphique."
            ),
            hint="La moyenne des deux périodes est affichée sous le graphique : soustrayez-les.",
            chart="compare",
            minutes=6,
        ),
        Step(
            title="Regarder le détail mensuel",
            instruction=(
                "L'écart entre les deux périodes est-il le même en janvier et en "
                "juillet ?"
            ),
            expected=(
                "Non : à Paris, l'écart atteint +1,8 °C en janvier mais seulement "
                "+1,1 °C en juillet, et tombe à près de zéro en septembre. Le "
                "réchauffement est donc positif sur les douze mois, mais inégal "
                "d'un mois à l'autre. Le détail mensuel se lit dans le graphique "
                "de gauche."
            ),
            hint="Compare les deux barres du même mois dans le graphique mensuel.",
            chart="compare",
            minutes=7,
        ),
        Step(
            title="Conclure",
            instruction=(
                "Peut-on affirmer, à partir de ces deux périodes, que le climat de "
                "Paris a changé ?"
            ),
            expected=(
                "Oui : l'écart est positif sur les douze mois (de +0,0 à +1,8 °C) "
                "et d'environ +1 °C en moyenne annuelle sur trente ans, ce qui "
                "dépasse largement la variabilité naturelle d'une année à "
                "l'autre. La conclusion doit préciser les périodes comparées et "
                "la valeur de l'écart."
            ),
            hint="Une bonne conclusion cite les deux périodes, la valeur de l'écart et son unité.",
            chart="compare",
            minutes=7,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 8. Jours de chaleur
# --------------------------------------------------------------------------- #

CANICULE = Activity(
    key="canicule",
    title="Compter les jours de chaleur : un indicateur est un choix",
    levels="3e · 4e",
    duration="55 min",
    subject="SVT · Mathématiques · EPS",
    objective=(
        "Compter des journées de forte chaleur avec un seuil explicite, puis "
        "mesurer l'effet du choix de ce seuil sur le résultat."
    ),
    skills=(
        "Définir un critère de comptage et le justifier",
        "Manipuler des données journalières",
        "Mesurer la sensibilité d'un indicateur à son seuil",
    ),
    introduction=(
        "« Il y a eu 30 jours de canicule » : ce chiffre n'existe pas sans une "
        "définition. En changeant le seuil ou la durée de la nuit, le nombre "
        "change du tout au tout — c'est ce que vous allez mesurer."
    ),
    default_cities=("Marseille", "Paris"),
    variables=("2m_temperature",),
    chart="heat",
    source="cds",
    keywords=("canicule", "seuil", "journalier", "santé"),
    difficulty=3,
    teacher_tip=(
        "L'indicateur est un choix, pas une donnée : c'est la leçon de cette "
        "activité, à prolonger par un débat sur les seuils d'alerte canicule de "
        "Météo-France et le rôle de la vigilance sanitaire."
    ),
    steps=(
        Step(
            title="Formuler une hypothèse",
            instruction=(
                "Combien de journées dont la température dépasse 35 °C attends-tu "
                "à Marseille sur la période affichée ?"
            ),
            expected=(
                "L'élève annonce un nombre avant tout calcul ; la réponse est "
                "notée au tableau pour être confrontée au résultat. Les hypothèses "
                "sont en général sous-estimées."
            ),
            hint="Aide-toi du graphique des températures moyennes mensuelles de l'été.",
            chart="heat",
            minutes=5,
        ),
        Step(
            title="Compter et vérifier",
            instruction=(
                "Combien de journées ont réellement dépassé 35 °C, et à quel "
                "écart ta prédiction se situe-t-elle ?"
            ),
            expected=(
                "Le comptage réel (seuil à 35 °C sur les maximums diurnes) se "
                "situe en général au-dessus des prédictions : plusieurs dizaines "
                "de journées sur une période récente, avec un maximum pendant les "
                "étés 2003, 2019 et 2022."
            ),
            hint="Compare ton nombre à celui affiché sous le graphique.",
            chart="heat",
            minutes=7,
        ),
        Step(
            title="Changer la définition",
            instruction=(
                "Que devient le nombre de jours si l'on exige en plus une nuit "
                "dont le minimum dépasse 20 °C ?"
            ),
            expected=(
                "Le comptage chute nettement : une journée très chaude suivie "
                "d'une nuit fraîche ne constitue plus une nuit de canicule. Le "
                "second critère retient l'impact sanitaire réel, celui du corps "
                "qui ne peut pas se refroidir."
            ),
            hint="Une journée sans repos nocturne est plus dangereuse qu'un pic diurne isolé.",
            chart="heat",
            minutes=7,
        ),
        Step(
            title="Déduire une règle",
            instruction=(
                "Que faut-il publier avec un nombre de jours de canicule pour "
                "qu'il constitue un indicateur solide ?"
            ),
            expected=(
                "Le seuil exact, la variable utilisée (maximum ou minimum), la "
                "période et la station ou le maille considérée — publiés une fois "
                "pour toutes et utilisés à l'identique d'une ville à l'autre et "
                "d'une année à l'autre."
            ),
            hint="Un indicateur qu'on ne peut pas comparer n'est pas un indicateur.",
            chart="heat",
            minutes=6,
        ),
    ),
)


ACTIVITIES: list[Activity] = [
    OCEAN_CONTINENT,
    CYCLE_EAU,
    RECHAUFFEMENT,
    CARTES,
    VENT_PRESSION,
    LATITUDE,
    AVANT_APRES,
    CANICULE,
]

_BY_KEY = {a.key: a for a in ACTIVITIES}


def get(key: str) -> Activity:
    """Renvoie une activité par sa clé, avec message d'erreur explicite."""
    if key not in _BY_KEY:
        raise KeyError(f"Activité inconnue : {key!r}. Disponibles : {sorted(_BY_KEY)}")
    return _BY_KEY[key]


def list_activities(*, with_answers: bool = False) -> list[dict[str, Any]]:
    """Toutes les activités (les corrigés ne sortent qu'avec le code enseignant)."""
    return [a.as_dict(with_answers=with_answers) for a in ACTIVITIES]
