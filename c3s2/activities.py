"""
Banque d'activités pédagogiques — réécrite pour C3S².

Charte de rédaction appliquée à **toutes** les étapes (48 consignes) :

1. **Une seule question par étape**, avec un livrable explicite : l'élève sait
   s'il doit donner un nombre, une comparaison, une explication ou une phrase
   rédigée (« indique les deux valeurs », « calcule… », « rédige une phrase… »).
2. **Verbe d'action en tête** : relever, lire, calculer, comparer, expliquer,
   relier, prévoir, rédiger, conclure — jamais une question floue ouverte.
3. **Aucune réponse dans la consigne.** Les données de départ (valeurs lues sur
   un document difficile à lire finement, périodes étudiées) peuvent être
   données ; le résultat attendu, lui, ne figure jamais dans l'énoncé.
4. **On décrit le climat, pas la courbe** : la consigne porte sur des
   températures, des pluies, des amplitudes, des évolutions réelles, et non
   sur la forme graphique.
5. **Progression dans l'activité** : repérage/description → calcul →
   mise en relation → synthèse rédigée.

Chaque étape expose `expected` (corrigé), `hint` (piste) et `chart`
(l'affichage à projeter), afin que la fiche et la donnée restent indissociables.
Les étapes 3 et 4 portent en outre un **second document** (`chart2`) distinct du
premier : chaque activité fait donc interpréter au moins deux documents.
Les activités `rechauffement` et `elnino` portent en plus un `exam` : un sujet
type brevet (contexte, documents numérotés, questions de difficulté croissante).
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
    #: Identifiant de carte (`public/assets/maps`) quand `chart == "map"`.
    map_id: str = ""
    #: Second document à interpréter sur cette étape ("" = aucun).
    chart2: str = ""
    #: Carte du second document, quand `chart2 == "map"`.
    map2_id: str = ""
    #: Fichier du second document, quand `chart2` est `schema` ou `figure`
    #: (sous `public/assets/schemas/` ou `public/assets/figures/`).
    file2: str = ""


@dataclass
class ExamDoc:
    """Un document numéroté d'un sujet type brevet (Document 1, 2, 3…)."""

    number: int
    title: str
    body: str
    #: `annual`, `anomalies`, `figure`, `table` ou `none`.
    chart: str = "none"
    #: Nom du PNG sous `public/assets/figures/` si `chart == "figure"`.
    file: str = ""
    caption: str = ""
    #: Si `chart == "table"` : première ligne = en-têtes de colonnes.
    table: tuple[tuple[str, ...], ...] = ()


@dataclass
class ExamQuestion:
    """Une question de sujet, numérotée, avec barème et attendu."""

    #: « 1 », « 2 », « 3 », « 4 » — ordre croissant de difficulté.
    id: str
    #: Nature de la compétence évaluée (connaissance, données, rédaction…).
    skill: str
    text: str
    #: Barème en points.
    points: int
    #: Ce qui est attendu de l'élève (réservé à l'enseignant).
    attendu: str
    #: Corrigé rédigé (réservé à l'enseignant).
    expected: str


@dataclass
class Exam:
    """Sujet type brevet ajouté à une activité (mise en situation + documents)."""

    contexte: str
    rappel: str
    documents: tuple[ExamDoc, ...]
    questions: tuple[ExamQuestion, ...]
    theme: str
    sources: tuple[str, ...] = ()
    #: Durée indicative du sujet, en minutes.
    duration: int = 25

    @property
    def points_total(self) -> int:
        return sum(q.points for q in self.questions)

    def as_dict(self, *, with_answers: bool = False) -> dict[str, Any]:
        """Forme JSON ; attendus et corrigés ne sortent qu'avec le code."""
        questions = []
        for q in self.questions:
            item: dict[str, Any] = {
                "id": q.id,
                "skill": q.skill,
                "text": q.text,
                "points": q.points,
            }
            if with_answers:
                item["attendu"] = q.attendu
                item["expected"] = q.expected
            questions.append(item)
        return {
            "contexte": self.contexte,
            "rappel": self.rappel,
            "theme": self.theme,
            "duration": self.duration,
            "points": self.points_total,
            "sources": list(self.sources),
            "documents": [
                {
                    "number": d.number,
                    "title": d.title,
                    "body": d.body,
                    "chart": d.chart,
                    "file": d.file,
                    "caption": d.caption,
                    "table": [list(row) for row in d.table],
                }
                for d in self.documents
            ],
            "questions": questions,
        }


#: Verbes admis en tête d'une question de sujet (racines, sans accent).
QUESTION_STEMS = (
    "relev", "lis", "calc", "compar", "expli", "rel", "pred", "redig",
    "concl", "decri", "identif", "localis", "justif", "observ", "constat",
    "class", "range", "additionn", "suppos", "suis", "choisis", "indiq",
    "donn", "note", "dis", "propose", "repere", "disting", "defin",
)


def _stem(word: str) -> str:
    """Premier mot d'une phrase, ramené à une racine sans accent ni majuscule."""
    import unicodedata

    word = word.strip("«»\"' ").lower()
    decomposed = unicodedata.normalize("NFKD", word)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def validate_exam(exam: Exam) -> list[str]:
    """Contrôle qualité d'un sujet (E1–E8) : renvoie la liste des défauts."""
    problems: list[str] = []
    if len(exam.contexte.strip()) < 180:
        problems.append("E1 : le contexte fait moins de 180 caractères")
    if not exam.rappel.strip():
        problems.append("E1 : le rappel de consignes est absent")
    if len(exam.documents) < 3:
        problems.append("E2 : moins de trois documents")
    numbers = [d.number for d in exam.documents]
    if numbers != list(range(1, len(numbers) + 1)):
        problems.append("E2 : documents mal numérotés")
    if len(exam.questions) < 3:
        problems.append("E3 : moins de trois questions")
    points = 0
    for q in exam.questions:
        words = q.text.replace(",", " ").split()[:10]
        stems = [_stem(w) for w in words]
        if not any(any(s.startswith(v) for v in QUESTION_STEMS) for s in stems):
            problems.append(f"E4 : question {q.id} sans verbe d'action ({words[:2]!r})")
        if not q.attendu.strip() or not q.expected.strip():
            problems.append(f"E5 : question {q.id} sans attendu ou sans corrigé")
        if q.points < 1:
            problems.append(f"E6 : question {q.id} sans barème")
        points += q.points
    if not 8 <= points <= 30:
        problems.append(f"E6 : barème total hors plage ({points} points)")
    ids = [q.id for q in exam.questions]
    if ids != sorted(ids, key=int):
        problems.append("E7 : questions non classées par difficulté croissante")
    if not exam.sources:
        problems.append("E8 : sources absentes")
    return problems



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
    difficulty: int = 1
    #: Source de données requise : `auto` laisse l'application choisir.
    source: str = "auto"
    keywords: tuple[str, ...] = ()
    #: Sujet type brevet en plus des quatre étapes (optionnel).
    exam: Exam | None = None

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
                "map_id": step.map_id,
                "chart2": step.chart2,
                "map2_id": step.map2_id,
                "file2": step.file2,
            }
            if with_answers:
                item["expected"] = step.expected
            steps.append(item)
        payload: dict[str, Any] = {
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
            "difficulty": self.difficulty,
            "source": self.source,
            "keywords": list(self.keywords),
            "steps": steps,
            "n_steps": len(self.steps),
        }
        if self.exam is not None:
            payload["exam"] = self.exam.as_dict(with_answers=with_answers)
        return payload


# --------------------------------------------------------------------------- #
# 1. Océan / continent
# --------------------------------------------------------------------------- #

OCEAN_CONTINENT = Activity(
    key="ocean_continent",
    title="Brest ou Strasbourg : pourquoi n'ont-elles pas le même climat ?",
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
    steps=(
        Step(
            title="Relever l'hiver",
            instruction=(
                "Relève sur la normale mensuelle la température du mois le plus "
                "froid de Brest, puis celle de Strasbourg : donne les deux valeurs "
                "et le mois correspondant."
            ),
            expected=(
                "Brest : 7,9 °C en février, son mois le plus froid. Strasbourg : "
                "2,4 °C en janvier. L'écart hivernal n'est donc que de 5,5 °C alors "
                "que les deux villes sont à la même latitude."
            ),
            hint="Le mois le plus froid est celui dont la valeur est la plus basse ; lis ensuite sa valeur sur l'axe.",
            chart="climato",
            minutes=5,
        ),
        Step(
            title="Calculer l'amplitude",
            instruction=(
                "Calcule l'amplitude thermique annuelle de chaque ville (mois le "
                "plus chaud moins mois le plus froid) et donne les deux résultats "
                "en degrés Celsius."
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
                "Explique en deux phrases pourquoi Brest et Strasbourg, presque à "
                "la même latitude, ont des amplitudes thermiques si différentes : "
                "appuie-toi sur la normale mensuelle puis sur la carte de janvier, "
                "et cite le mécanisme physique en cause."
            ),
            expected=(
                "L'eau se réchauffe et se refroidit beaucoup plus lentement que la "
                "roche : l'océan tempère le littoral toute l'année (inertie "
                "thermique), alors que la terre continentale chauffe vite en été et "
                "refroidit vite en hiver."
            ),
            hint="Comparez le temps nécessaire pour chauffer un litre d'eau et une pierre de même masse.",
            chart="climato",
            chart2="map",
            map2_id="t2m_janvier",
            minutes=8,
        ),
        Step(
            title="Prévoir puis vérifier",
            instruction=(
                "Prédis l'amplitude thermique de Marseille avant de la faire "
                "afficher, puis vérifie ta prédiction avec la normale mensuelle "
                "et la carte de janvier : se trouve-t-elle bien entre celles de "
                "Brest et de Strasbourg ?"
            ),
            expected=(
                "Une amplitude de l'ordre de 14 à 15 °C, soit bien plus qu'à Brest : "
                "la mer tempère l'hiver (9 °C en janvier) mais l'été reste chaud "
                "(23,5 °C en août). Vérification à faire afficher ensuite "
                "(Brest 8,8 °C < Marseille 14,5 °C < Strasbourg 17,9 °C)."
            ),
            hint="Marseille est en bord de mer, mais à 43° N : son été est bien plus chaud que celui de Brest.",
            chart="climato",
            chart2="map",
            map2_id="t2m_janvier",
            minutes=5,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 2. Cycle de l'eau
# --------------------------------------------------------------------------- #

CYCLE_EAU = Activity(
    key="cycle_eau",
    title="Marseille et Dakar : d'où vient la pluie ?",
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
    steps=(
        Step(
            title="Repérer le minimum",
            instruction=(
                "Repère sur le diagramme ombrothermique le mois le plus sec de "
                "Marseille : indique son nom et son cumul en millimètres."
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
                "Compare la courbe de température et les barres de pluie de "
                "Marseille en juillet : le mois le plus chaud est-il aussi le plus "
                "humide ? Réponds par oui ou non, puis justifie avec les valeurs."
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
                "Additionne les douze cumuls mensuels de Marseille, puis ceux de "
                "Dakar, et replace tes totaux sur la carte des pluies de juillet : "
                "laquelle des deux villes reçoit le plus d'eau sur une année ?"
            ),
            expected=(
                "Marseille : environ 600 mm par an, contre seulement 280 mm à "
                "Dakar. Mais surtout, la répartition est à l'opposé : Dakar "
                "concentre 250 mm sur trois mois (juillet-septembre), alors que "
                "Marseille étale sa pluie sur l'automne et l'hiver (octobre à "
                "décembre : 240 mm) et reste sèche en été."
            ),
            hint="Cumul annuel = somme des douze cumuls mensuels.",
            chart="ombro",
            chart2="map",
            map2_id="tp_juillet",
            minutes=6,
        ),
        Step(
            title="Expliquer la saison des pluies",
            instruction=(
                "Explique pourquoi Dakar reçoit l'essentiel de ses pluies de "
                "juillet à septembre alors que Marseille reste sèche en été, en "
                "te servant de la carte des pluies de juillet : mobilise "
                "évaporation, condensation et ascendance de l'air."
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
            chart2="map",
            map2_id="tp_juillet",
            minutes=8,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 3. Réchauffement climatique
# --------------------------------------------------------------------------- #

EXAM_RECHAUFFEMENT = Exam(
    contexte=(
        "Depuis le milieu du XXe siècle, la température moyenne de la surface "
        "de la Terre augmente : c'est le réchauffement climatique. Pour savoir "
        "si une ville en est touchée, on ne regarde jamais une année isolée, "
        "mais des moyennes calculées sur de longues périodes. La station "
        "étudiée ici est Paris, à partir des données ERA5 du service "
        "Copernicus (C3S) : 85 ans de températures moyennes annuelles, de "
        "1940 à 2024, complétées par les écarts de chaque année par rapport à "
        "la normale climatique 1991-2020 de l'Organisation météorologique "
        "mondiale."
    ),
    rappel=(
        "À l'aide des documents ci-dessous et de vos connaissances, répondez "
        "aux questions dans l'ordre. Rédigez des phrases complètes : une valeur "
        "donnée sans justification n'est pas acceptée."
    ),
    documents=(
        ExamDoc(
            number=1,
            title="Moyennes annuelles de température à Paris, 1940-2024",
            body=(
                "Chaque point est la moyenne des douze mois d'une année. Le "
                "trait en pointillés est la tendance calculée sur les 85 "
                "années de la série."
            ),
            chart="annual",
            caption="Moyennes annuelles 1940-2024 et tendance — Paris (ERA5).",
        ),
        ExamDoc(
            number=2,
            title="Écart de chaque année à la normale 1991-2020",
            body=(
                "L'anomalie est l'écart entre la moyenne d'une année et la "
                "moyenne de la période de référence 1991-2020 (11,5 °C pour "
                "Paris). Les barres au-dessus de zéro sont des années plus "
                "chaudes que la normale, celles en dessous des années plus "
                "froides."
            ),
            chart="anomalies",
            caption="Anomalie annuelle par rapport à 1991-2020 — Paris (ERA5).",
        ),
        ExamDoc(
            number=3,
            title="Moyennes décennales de température à Paris",
            body=(
                "Moyenne de chaque période de dix années, arrondie au dixième "
                "de degré ; la dernière ligne couvre les dix dernières années "
                "de la série."
            ),
            chart="table",
            caption="Valeurs calculées à partir des moyennes annuelles ERA5.",
            table=(
                ("Période", "Moyenne annuelle"),
                ("1940-1949", "10,7 °C"),
                ("1950-1959", "10,5 °C"),
                ("1960-1969", "10,4 °C"),
                ("1970-1979", "10,3 °C"),
                ("1980-1989", "10,4 °C"),
                ("1990-1999", "11,1 °C"),
                ("2000-2009", "11,5 °C"),
                ("2010-2019", "11,7 °C"),
                ("2015-2024", "12,2 °C"),
            ),
        ),
    ),
    questions=(
        ExamQuestion(
            id="1",
            skill="Connaissances — définir",
            text="Définir ce qu'est le climat, en le distinguant de la météo.",
            points=2,
            attendu=(
                "Deux idées attendues : la météo décrit l'état de "
                "l'atmosphère à un instant donné ou sur quelques jours ; le "
                "climat décrit les conditions moyennes sur au moins trente ans."
            ),
            expected=(
                "Le climat est l'état moyen de l'atmosphère sur une longue "
                "période (au moins trente ans, comme la normale 1991-2020), "
                "alors que la météo décrit l'état de l'atmosphère à un moment "
                "donné ou sur quelques jours."
            ),
        ),
        ExamQuestion(
            id="2",
            skill="Données — décrire un document",
            text=(
                "Décrire, à l'aide du document 1, l'évolution de la "
                "température moyenne annuelle de Paris entre 1940 et 2024."
            ),
            points=3,
            attendu=(
                "L'élève doit constater deux phases : une série stable ou "
                "légèrement en baisse jusque vers les années 1970 (autour de "
                "10,3 à 10,7 °C), puis une hausse nette et continue à partir "
                "des années 1980. Il doit s'appuyer sur des valeurs lues dans "
                "le document et ne pas se contenter d'écrire « ça monte »."
            ),
            expected=(
                "La moyenne annuelle de Paris stagne, puis baisse légèrement "
                "jusque vers les années 1970 (autour de 10,3 à 10,7 °C), puis "
                "augmente nettement à partir des années 1980 pour dépasser "
                "12 °C dans les années 2020 : la hausse n'est donc pas "
                "régulière, elle s'accélère sur la fin de la série."
            ),
        ),
        ExamQuestion(
            id="3",
            skill="Données — exploiter et calculer",
            text=(
                "À l'aide des documents 2 et 3, relever les valeurs qui "
                "permettent de quantifier le réchauffement de Paris, puis "
                "calculer l'écart entre la moyenne de 1941-1970 et celle de "
                "1991-2020."
            ),
            points=6,
            attendu=(
                "Relevé attendu : 1941-1970 = 10,5 °C ; 1991-2020 = 11,5 °C ; "
                "écart = +1,0 °C (0,96 °C exactement). On valorise aussi : la "
                "tendance de +0,2 °C par décennie (document 1), 1940-1949 = "
                "10,7 °C contre 2010-2019 = 11,7 °C (écart de 1,0 °C), les "
                "anomalies positives après 1980 et l'anomalie record de +1,4 °C "
                "en 2023 (document 2)."
            ),
            expected=(
                "Document 3 : la moyenne de 1941-1970 vaut 10,5 °C et celle de "
                "1991-2020 vaut 11,5 °C, soit un écart d'environ +1,0 °C "
                "(0,96 °C). On retrouve le même écart avec les décennies : "
                "1940-1949 = 10,7 °C contre 2010-2019 = 11,7 °C. Document 2 : "
                "les anomalies deviennent systématiquement positives à partir "
                "des années 1990, avec un maximum de +1,4 °C en 2023, année la "
                "plus chaude de la série."
            ),
        ),
        ExamQuestion(
            id="4",
            skill="Rédaction — expliquer et conclure",
            text=(
                "À l'aide des trois documents et de vos connaissances, "
                "expliquer pourquoi une seule année froide ne permet pas de "
                "contredire la tendance observée, puis rédiger une conclusion "
                "d'au moins trois phrases sur l'évolution du climat de Paris."
            ),
            points=5,
            attendu=(
                "Partie 1 : l'amplitude interannuelle (de −2,0 °C en 1963 à "
                "+1,4 °C en 2023) est bien plus grande que la tendance d'une "
                "seule décennie (+0,2 °C) ; seules des moyennes de trente ans "
                "sont significatives. Partie 2 : une conclusion qui cite la "
                "période, la grandeur et les valeurs, avec une rédaction "
                "correcte en phrases complètes."
            ),
            expected=(
                "1) Les anomalies annuelles vont de −2,0 °C (1963) à +1,4 °C "
                "(2023), soit près de 3,5 °C d'écart d'une année à l'autre, "
                "alors que la tendance ne vaut que +0,2 °C par décennie : "
                "comparer deux années isolées ne dit rien sur la tendance, il "
                "faut comparer des moyennes longues. 2) Exemple de conclusion : "
                "« Entre la période 1941-1970 et la période 1991-2020, la "
                "température moyenne annuelle de Paris est passée de 10,5 °C à "
                "11,5 °C, soit +1,0 °C, avec une tendance de +0,2 °C par "
                "décennie sur 1940-2024 qui s'accélère depuis les années "
                "1980. »"
            ),
        ),
    ),
    theme=(
        "La planète Terre, l'environnement et l'action humaine — le "
        "changement climatique (cycle 4)"
    ),
    sources=(
        "ERA5 — Copernicus Climate Change Service (C3S/CAMS)",
        "Normale climatique 1991-2020 — Organisation météorologique mondiale",
    ),
    duration=25,
)


RECHAUFFEMENT = Activity(
    key="rechauffement",
    title="Paris se réchauffe-t-il vraiment ?",
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
    exam=EXAM_RECHAUFFEMENT,
    steps=(
        Step(
            title="Calculer la hausse observée",
            instruction=(
                "Calcule l'écart entre la moyenne annuelle des dix premières "
                "années affichées (1940-1949) et celle des dix dernières "
                "(2015-2024) à Paris : de combien la température a-t-elle changé ?"
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
                "Lis la valeur de la tendance affichée sur le graphique : de "
                "combien la température moyenne annuelle de Paris augmente-t-elle "
                "par décennie ?"
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
                "Détermine si une seule année froide peut contredire la tendance "
                "mesurée sur 85 ans, en comparant l'amplitude des anomalies d'une "
                "année à l'autre et la hausse obtenue sur dix ans."
            ),
            expected=(
                "Non : on comparerait deux années isolées au lieu de comparer des "
                "décennies. Les anomalies vont de −2,0 °C (1963) à +1,4 °C (2023), "
                "soit près de 3,5 °C d'écart d'une année à l'autre, tandis que la "
                "tendance ne vaut que +0,2 °C par décennie : seule une moyenne "
                "longue fait apparaître la tendance de fond."
            ),
            hint="Compare l'écart entre deux années voisines et la hausse sur dix ans.",
            chart="anomalies",
            minutes=8,
        ),
        Step(
            title="Rédiger la conclusion",
            instruction=(
                "Rédige une phrase de conclusion qui cite la période étudiée, la "
                "grandeur mesurée, la valeur de la tendance et son évolution "
                "récente."
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
    title="Lire une carte des températures de l'Europe",
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
    steps=(
        Step(
            title="Lire la normale de janvier",
            instruction=(
                "Localise sur la carte de janvier la région la plus froide "
                "d'Europe, puis donne sa gamme de températures moyennes "
                "mensuelles."
            ),
            expected=(
                "Le nord-est de l'Europe (Russie occidentale, Finlande, Scandinavie "
                "intérieure), avec des moyennes mensuelles souvent sous 0 °C, "
                "voire sous −10 °C. Les côtes atlantiques restent très nettement "
                "plus chaudes à même latitude."
            ),
            hint="Cherchez la couleur la plus froide du dégradé, puis situez-la sur la carte.",
            chart="map",
            map_id="t2m_janvier",
            minutes=6,
        ),
        Step(
            title="Comparer janvier et juillet",
            instruction=(
                "Relève la température moyenne du bassin méditerranéen en janvier "
                "puis en juillet : de combien augmente-t-elle ?"
            ),
            expected=(
                "Environ 10 °C en janvier contre 26 °C en juillet sur le même "
                "point du bassin, soit près de +16 °C. L'hiver reste doux grâce à "
                "l'inertie de la mer, mais l'été devient très chaud, avec plus de "
                "35 °C sur les rivages les plus exposés du sud."
            ),
            hint="Comparez la même zone sur les deux cartes et notez les deux valeurs.",
            chart="map",
            map_id="t2m_juillet",
            minutes=7,
        ),
        Step(
            title="Choisir la bonne échelle",
            instruction=(
                "Choisis entre un pas de couleur de 2 °C et un pas de 10 °C pour "
                "afficher les températures de janvier, et justifie ton choix."
            ),
            expected=(
                "Un pas de 2 °C rend mieux les contrastes qu'un pas de 10 °C, qui "
                "masquerait les variations locales ; en revanche, un pas trop fin "
                "(0,2 °C) multiplierait les nuances sans apporter d'information "
                "nouvelle. Le bon choix dépend de l'ampleur des écarts à montrer et "
                "doit toujours être indiqué sur la légende."
            ),
            hint="Posez la question inverse : que voit-on si chaque cran vaut 10 °C ?",
            chart="map",
            map_id="t2m_juillet",
            minutes=6,
        ),
        Step(
            title="Climat ou météo ?",
            instruction=(
                "Détermine si une carte construite sur trois mois suffit à "
                "décrire le climat d'un pays, en rappelant la définition d'une "
                "normale climatique."
            ),
            expected=(
                "Non : le climat se décrit sur au moins trente ans (normale OMM "
                "1991-2020). Trois mois relèvent de la météo, c'est-à-dire de "
                "l'état ponctuel de l'atmosphère."
            ),
            hint="Combien d'années l'OMM utilise-t-elle pour définir une normale climatique ?",
            chart="map",
            map_id="t2m_janvier",
            minutes=5,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 5. Pression et vent
# --------------------------------------------------------------------------- #

VENT_PRESSION = Activity(
    key="vent_pression",
    title="Pourquoi le vent souffle-t-il ?",
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
    steps=(
        Step(
            title="Repérer la valeur de référence",
            instruction=(
                "Relève la pression au niveau de la mer affichée sur l'Europe "
                "occidentale : à quelle valeur se situe-t-elle ?"
            ),
            expected=(
                "Vers 1019 hPa sur l'Europe occidentale, très proche de la valeur "
                "de référence de 1013 hPa (moyenne au niveau de la mer). C'est "
                "autour d'elle que s'organisent les hautes pressions (1020 à "
                "1040 hPa) et les basses pressions (980 à 1000 hPa)."
            ),
            hint="La valeur se lit sur la légende de la carte, entre les deux extrêmes.",
            chart="map",
            map_id="mslp_janvier",
            minutes=4,
        ),
        Step(
            title="Localiser les systèmes",
            instruction=(
                "Localise sur la carte le maximum et le minimum de pression : "
                "donne leurs valeurs et leur position."
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
            map_id="mslp_janvier",
            minutes=6,
        ),
        Step(
            title="Relier pression et vent",
            instruction=(
                "Indique dans quel sens l'air se déplace entre une zone de hautes "
                "pressions et une zone de basses pressions : nomme la force qui le "
                "met en mouvement."
            ),
            expected=(
                "Des hautes vers les basses : c'est le gradient de pression qui "
                "accélère l'air. Ensuite, la rotation de la Terre le fait tourner "
                "autour des dépressions dans l'hémisphère nord."
            ),
            hint="Retournez le raisonnement : que se passerait-il si la pression était partout identique ?",
            chart="map",
            map_id="vent_janvier",
            minutes=7,
        ),
        Step(
            title="Vérifier avec les flèches",
            instruction=(
                "Suis une flèche de vent tracée près d'une isobare : décrit-elle "
                "un trajet direct des hautes vers les basses pressions, ou un "
                "autre mouvement ?"
            ),
            expected=(
                "Les flèches ne vont pas droit : elles s'enroulent le long des "
                "isobares à un angle par rapport au gradient de pression, en "
                "tournant dans le sens des aiguilles d'une montre autour d'une "
                "hauteur et en sens inverse autour d'une dépression. Le mouvement "
                "de fond reste bien dirigé des hautes vers les basses pressions, "
                "mais la rotation de la Terre le dévie."
            ),
            hint="Suivez une flèche placée sur une isobare et observez son angle avec celle-ci.",
            chart="map",
            map_id="vent_janvier",
            minutes=7,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 6. Latitude et rayonnement
# --------------------------------------------------------------------------- #

LATITUDE = Activity(
    key="latitude",
    title="Pourquoi fait-il froid aux pôles ?",
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
    steps=(
        Step(
            title="Prédire sans regarder",
            instruction=(
                "Classe les quatre villes de la plus chaude à la plus froide pour "
                "janvier, en utilisant uniquement leurs latitudes : note ton "
                "classement au brouillon."
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
                "Relève les températures moyennes de janvier à Dakar et à Paris, "
                "puis calcule l'écart entre les deux."
            ),
            expected=(
                "Dakar, avec 21,5 °C de moyenne en janvier, contre 4,3 °C à "
                "Paris : un écart de 17 °C pour 34 degrés de latitude. Longyearbyen, "
                "elle, affiche −13,6 °C."
            ),
            hint="Lis la température de janvier sur la courbe de chaque ville.",
            chart="climato",
            minutes=6,
        ),
        Step(
            title="Identifier la surprise",
            instruction=(
                "Relève les températures de janvier à Reykjavik et à "
                "Longyearbyen, puis compare-les à leurs latitudes à l'aide du "
                "schéma des rayons : l'écart de température est-il proportionnel "
                "à l'écart de latitude ?"
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
            chart2="schema",
            file2="rayons_solaires.png",
            minutes=7,
        ),
        Step(
            title="Formuler le mécanisme",
            instruction=(
                "Explique en deux phrases, à partir du schéma des rayons, "
                "pourquoi on reçoit moins d'énergie solaire quand la latitude "
                "augmente."
            ),
            expected=(
                "Plus on approche des pôles, plus les rayons arrivent de biais : "
                "la même énergie est répartie sur une surface plus grande, et "
                "elle traverse une atmosphère plus épaisse. L'échauffement est "
                "donc moindre."
            ),
            hint="Imagine un faisceau de lampe torche dirigé droit puis incliné sur le sol.",
            chart="climato",
            chart2="schema",
            file2="rayons_solaires.png",
            minutes=8,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 7. Avant / après
# --------------------------------------------------------------------------- #

AVANT_APRES = Activity(
    key="avant_apres",
    title="Paris a-t-il changé ? Comparons deux époques",
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
    steps=(
        Step(
            title="Choisir les périodes",
            instruction=(
                "Indique les deux périodes de trente ans comparables que tu peux "
                "étudier (les données commencent en 1940)."
            ),
            expected=(
                "Par exemple 1941-1970 (première période complète de trente ans "
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
                "Calcule l'écart entre la moyenne 1941-1970 et la moyenne "
                "1991-2020 à Paris, puis donne les deux moyennes et leur écart."
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
                "Compare l'écart des deux périodes mois par mois, sur le "
                "graphique mensuel puis sur la série annuelle : est-il le même "
                "en janvier, en juillet et en septembre ?"
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
            chart2="annual",
            minutes=7,
        ),
        Step(
            title="Conclure",
            instruction=(
                "Rédige une conclusion qui cite les deux périodes comparées, la "
                "valeur de l'écart moyen et le signe de cet écart, en te "
                "servant de la série annuelle."
            ),
            expected=(
                "Exemple attendu : « À Paris, la température moyenne passe de "
                "10,5 °C sur 1941-1970 à 11,5 °C sur 1991-2020, soit un écart "
                "moyen d'environ +1 °C. » L'écart est positif sur les douze mois "
                "(de +0,0 à +1,8 °C), donc il dépasse la variabilité naturelle "
                "d'une année à l'autre. La conclusion doit préciser les périodes "
                "comparées et la valeur de l'écart."
            ),
            hint="Une bonne conclusion cite les deux périodes, la valeur de l'écart et son unité.",
            chart="compare",
            chart2="annual",
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
            chart2="climato",
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
            chart2="climato",
            minutes=6,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 9. Pluies d'Europe (cartes de précipitations)
# --------------------------------------------------------------------------- #

PLUIES_EUROPE = Activity(
    key="pluies_europe",
    title="Où pleut-il en Europe, en hiver et en été ?",
    levels="4e · 3e",
    duration="55 min",
    subject="Géographie · SVT",
    objective=(
        "Lire un cumul mensuel sur une carte, comparer janvier et juillet, puis "
        "relier les contrastes au relief et à la circulation atmosphérique."
    ),
    skills=(
        "Lire un cumul mensuel sur une carte et sa légende",
        "Comparer deux cartes saisonnières avec des valeurs",
        "Relier pluie, relief et flux d'ouest",
    ),
    introduction=(
        "En janvier, la côte ouest de la Norvège reçoit près de 300 mm pendant "
        "que Marseille n'en reçoit guère plus de 50. En juillet, l'Andalousie "
        "tombe à 4 mm pendant que les Alpes dépassent 150 mm. Deux cartes "
        "suffisent à raconter l'Europe des pluies."
    ),
    default_cities=("Brest", "Marseille"),
    variables=("total_precipitation",),
    chart="map",
    keywords=("précipitations", "carte", "relief", "saison"),
    difficulty=2,
    steps=(
        Step(
            title="Décrire janvier",
            instruction=(
                "Calcule le rapport entre le cumul de janvier sur la côte ouest "
                "de la Norvège (environ 293 mm) et celui de Marseille "
                "(environ 57 mm) : combien de fois plus d'eau reçoit le nord ?"
            ),
            expected=(
                "293 ÷ 57 ≈ 5 : la côte norvégienne reçoit cinq fois plus d'eau "
                "que Marseille en janvier. Le nord-ouest atlantique est la "
                "région la plus arrosée d'Europe en hiver, exposée de plein "
                "fouet aux flux d'ouest."
            ),
            hint="Rapport = grande valeur divisée par petite valeur.",
            chart="map",
            map_id="tp_janvier",
            minutes=5,
        ),
        Step(
            title="Comparer les saisons",
            instruction=(
                "Calcule la baisse des pluies entre janvier et juillet à "
                "Marseille puis en Écosse (hautes terres, vers 56° N) : où la "
                "baisse est-elle la plus forte, en valeur absolue et en "
                "pourcentage ?"
            ),
            expected=(
                "Marseille : de 57 à 21 mm, soit −36 mm et −63 %. Écosse "
                "(56° N, 4° O) : de 120 à 94 mm, soit −26 mm et −22 %. La baisse "
                "est donc plus forte à Marseille dans l'absolu comme en "
                "proportion : le sud s'assèche franchement l'été pendant que le "
                "nord-ouest reste arrosé toute l'année."
            ),
            hint="Baisse en mm = janvier − juillet ; en proportion = baisse ÷ janvier.",
            chart="map",
            map_id="tp_juillet",
            minutes=7,
        ),
        Step(
            title="Mettre en relation avec le relief",
            instruction=(
                "Confronte les cumuls de juillet des Alpes, de Marseille et de "
                "l'Andalousie, puis compare-les à leurs cumuls de janvier : que "
                "se passe-t-il en montagne ?"
            ),
            expected=(
                "Les Alpes sont plus arrosées en juillet (153 mm) qu'en janvier "
                "(139 mm), alors que Marseille passe de 57 à 21 mm et "
                "l'Andalousie de quelques dizaines de millimètres à 4 mm : c'est "
                "l'inverse du reste du sud. L'air chaud des basses couches est "
                "forcé de s'élever sur le relief, il se refroidit et se "
                "condense — orages et averses d'été. Le relief fabrique de la "
                "pluie là où la plaine reste sèche."
            ),
            hint="Compare aussi janvier et juillet sur les Alpes (139 contre 153 mm).",
            chart="map",
            map_id="tp_juillet",
            minutes=7,
        ),
        Step(
            title="Expliquer le contraste nord-sud",
            instruction=(
                "Explique pourquoi les pluies d'été s'effondrent au sud de "
                "l'Europe (Sicile et Andalousie) alors que le nord-ouest, lui, "
                "reste arrosé."
            ),
            expected=(
                "Au nord-ouest, les flux d'ouest chargés d'humidité balaient les "
                "reliefs toute l'année : l'Écosse garde 94 mm en juillet et la "
                "pluie ne s'arrête jamais vraiment. Au sud, l'été installe une "
                "atmosphère stable et subsidente (anticyclone) : la Sicile tombe "
                "à quelques millimètres seulement et l'Andalousie à 4 mm, car "
                "l'air ne s'élève pas et ne se condense donc pas. Même saison, "
                "trois régimes : océanique, méditerranéen, montagnard."
            ),
            hint="Relie « flux d'ouest », « relief » et « air stable » aux trois régions.",
            chart="map",
            map_id="tp_janvier",
            minutes=8,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 10. Régimes du monde (équatorial, tempéré, polaire)
# --------------------------------------------------------------------------- #

REGIMES_MONDE = Activity(
    key="regimes_monde",
    title="Singapour, Paris, Longyearbyen : trois climats à comparer",
    levels="5e · 4e",
    duration="55 min",
    subject="SVT · Géographie",
    objective=(
        "Comparer trois normales annuelles (1°, 49° et 78° N) et relier "
        "amplitude et moyenne annuelles à la latitude."
    ),
    skills=(
        "Lire une normale mensuelle pour trois villes",
        "Calculer une amplitude et classer",
        "Relier amplitude, moyenne annuelle et latitude",
    ),
    introduction=(
        "Singapour (1° N), Paris (49° N), Longyearbyen (78° N) : trois latitudes, "
        "trois climats. Les douze moyennes mensuelles de chaque ville racontent "
        "leur année — à vous de les chiffrer."
    ),
    default_cities=("Singapore", "Paris", "Longyearbyen"),
    variables=("2m_temperature",),
    chart="climato",
    keywords=("régime", "amplitude", "latitude", "équateur"),
    difficulty=1,
    steps=(
        Step(
            title="Décrire l'année",
            instruction=(
                "Relève pour chaque ville la température moyenne de janvier puis "
                "celle de juillet : donne les six valeurs en degrés Celsius."
            ),
            expected=(
                "Singapour : 26,1 °C en janvier et 27,5 °C en juillet. Paris : "
                "4,3 °C et 19,6 °C. Longyearbyen : −13,6 °C et 5,4 °C. "
                "Première leçon : à l'équateur, janvier et juillet se ressemblent."
            ),
            hint="Janvier : mois 1 ; juillet : mois 7. Lis chaque valeur sur l'axe.",
            chart="climato",
            minutes=5,
        ),
        Step(
            title="Calculer et classer",
            instruction=(
                "Calcule l'amplitude thermique annuelle des trois villes et "
                "classe-les de la plus stable à la plus contrastée."
            ),
            expected=(
                "Singapour : 1,7 °C (27,9 − 26,1). Paris : 15,3 °C (19,6 − 4,3). "
                "Longyearbyen : 19,7 °C (5,4 − (−14,3)). Classement : Singapour "
                "< Paris < Longyearbyen. L'amplitude est multipliée par plus de "
                "dix entre l'équateur et le cercle polaire."
            ),
            hint="Amplitude = mois le plus chaud − mois le plus froid.",
            chart="climato",
            minutes=6,
        ),
        Step(
            title="Mettre en relation",
            instruction=(
                "Range les trois villes par latitude croissante, puis relie "
                "chacune de leurs amplitudes à sa latitude et à sa moyenne "
                "annuelle, en confrontant la normale mensuelle et le diagramme "
                "ombrothermique : que remarques-tu ?"
            ),
            expected=(
                "L'amplitude croît avec la latitude pendant que la moyenne "
                "annuelle chute (27,1 °C à Singapour, 11,5 °C à Paris, −6,0 °C à "
                "Longyearbyen). Chaleur constante toute l'année : régime "
                "équatorial. Quatre saisons marquées : régime tempéré océanique. "
                "Hiver long et très froid, été bref : régime polaire."
            ),
            hint="Range les trois villes par latitude croissante et regarde les deux colonnes.",
            chart="climato",
            chart2="ombro",
            minutes=7,
        ),
        Step(
            title="Expliquer",
            instruction=(
                "Explique, en te servant du diagramme ombrothermique des trois "
                "villes, pourquoi l'amplitude thermique de Singapour est presque "
                "dix fois plus faible que celle de Longyearbyen."
            ),
            expected=(
                "À l'équateur, le Soleil culmine toujours haut à midi, en "
                "janvier comme en juillet : l'énergie reçue ne varie presque "
                "pas. À 78° N, l'obliquité fait tout basculer : nuit polaire "
                "l'hiver (aucune énergie), jour polaire l'été sous un soleil "
                "rasant. Même Soleil, deux géométries."
            ),
            hint="Pense à la hauteur du Soleil à midi en janvier et en juillet dans chaque ville.",
            chart="climato",
            chart2="ombro",
            minutes=8,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 11. Portrait climatique (synthèse sur une ville au choix)
# --------------------------------------------------------------------------- #

PORTRAIT_CLIMAT = Activity(
    key="portrait_climat",
    title="Décris le climat de Bordeaux",
    levels="4e · 3e",
    duration="55 min",
    subject="SVT · Géographie · Français",
    objective=(
        "Construire le portrait chiffré complet d'une ville (froid, chaud, "
        "amplitude, pluie) et le résumer en une phrase argumentée."
    ),
    skills=(
        "Extraire quatre nombres d'une normale mensuelle",
        "Comparer deux villes avec les mêmes indicateurs",
        "Rédiger une synthèse chiffrée",
    ),
    introduction=(
        "Bordeaux : océanique ou méditerranéen ? Les douze moyennes de "
        "température et les douze cumuls de pluie tranchent. À la fin, tu "
        "rédigeras son portrait en une seule phrase — avec quatre nombres."
    ),
    default_cities=("Bordeaux",),
    variables=("2m_temperature", "total_precipitation"),
    chart="climato",
    keywords=("portrait", "synthèse", "régime", "Bordeaux"),
    difficulty=2,
    steps=(
        Step(
            title="Décrire les températures",
            instruction=(
                "Relève le mois le plus froid et le mois le plus chaud de "
                "Bordeaux ainsi que leurs températures moyennes."
            ),
            expected=(
                "Janvier : 6,7 °C, mois le plus froid. Juillet et août : "
                "21,6 °C, mois les plus chauds. Un hiver doux et un été chaud, "
                "sans excès dans les deux sens."
            ),
            hint="Le mois le plus froid est celui dont la valeur est la plus basse.",
            chart="climato",
            minutes=5,
        ),
        Step(
            title="Chiffrer l'eau",
            instruction=(
                "Calcule le cumul annuel de pluie de Bordeaux et repère son mois "
                "le plus sec : donne les deux valeurs."
            ),
            expected=(
                "Environ 820 mm par an, répartis sur les douze mois (de 53 à "
                "84 mm par mois). Le mois le plus sec est juillet avec 53 mm : "
                "il n'y a pas de vraie saison sèche, seulement un creux estival."
            ),
            hint="Cumul annuel = somme des douze cumuls mensuels.",
            chart="ombro",
            minutes=6,
        ),
        Step(
            title="Comparer à un témoin",
            instruction=(
                "Additionne les pluies de l'été (juin, juillet, août) de "
                "Bordeaux puis de Marseille : quelle ville a l'été le plus sec ?"
            ),
            expected=(
                "Marseille, et de loin : 47 mm en trois mois d'été contre "
                "181 mm à Bordeaux, avec un juillet à 10 mm contre 53 mm. Les "
                "amplitudes sont pourtant presque identiques (14,5 contre "
                "15,0 °C). Même chaleur estivale, deux régimes de pluie : "
                "Bordeaux reste océanique, Marseille est méditerranéenne."
            ),
            hint="Additionne juin, juillet et août de chaque ville.",
            chart="ombro",
            minutes=7,
        ),
        Step(
            title="Rédiger le portrait",
            instruction=(
                "Rédige en une phrase le portrait climatique de Bordeaux en "
                "citant quatre valeurs : froid, chaud, amplitude, pluie annuelle."
            ),
            expected=(
                "Exemple attendu : « À Bordeaux, la température diminue jusqu'à "
                "6,7 °C en janvier et augmente jusqu'à 21,6 °C l'été, soit une amplitude de "
                "15,0 °C, avec 820 mm de pluie répartis sur l'année : un climat "
                "océanique à été chaud. » La phrase doit contenir les quatre "
                "nombres et le nom du régime."
            ),
            hint="Une phrase scientifique cite toujours des valeurs, pas des impressions.",
            chart="climato",
            minutes=8,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 12. Vents et courants : Bordeaux et Montréal
# --------------------------------------------------------------------------- #

VENTS_COURANTS = Activity(
    key="vents_courants",
    title="Bordeaux et Montréal : pourquoi le même été mais pas le même hiver ?",
    levels="4e · 3e",
    duration="55 min",
    subject="SVT · Géographie",
    objective=(
        "Comparer deux villes de même latitude et expliquer l'écart de leurs "
        "hivers par les vents d'ouest et les courants (Gulf Stream, Labrador)."
    ),
    skills=(
        "Lire une normale mensuelle pour deux villes",
        "Calculer une amplitude et comparer",
        "Lire un schéma de courants et le relier aux températures",
    ),
    introduction=(
        "Bordeaux (44,8° N) et Montréal (45,5° N) : même latitude, même été "
        "à 21,5 °C… mais 16 °C d'écart en janvier. Les vents d'ouest traversent "
        "l'Atlantique d'ouest en est : que transportent-ils vers chaque rive ?"
    ),
    default_cities=("Bordeaux", "Montréal"),
    variables=("2m_temperature",),
    chart="climato",
    keywords=("courants", "vents", "Gulf Stream", "Labrador"),
    difficulty=2,
    steps=(
        Step(
            title="Décrire l'écart",
            instruction=(
                "Relève la température moyenne de janvier à Bordeaux puis à "
                "Montréal, et calcule l'écart entre les deux."
            ),
            expected=(
                "6,7 − (−9,1) = 15,8 °C, soit environ 16 °C d'écart pour un seul "
                "degré de latitude. L'hiver n'a rien d'égal alors que les deux "
                "villes sont à la même latitude."
            ),
            hint="Écart = valeur la plus haute moins valeur la plus basse.",
            chart="climato",
            minutes=5,
        ),
        Step(
            title="Calculer et comparer",
            instruction=(
                "Calcule l'amplitude thermique annuelle de Bordeaux et de "
                "Montréal, puis compare leurs températures estivales : que "
                "remarques-tu ?"
            ),
            expected=(
                "Bordeaux : 15,0 °C (de 6,7 à 21,6 °C). Montréal : 30,7 °C "
                "(de −9,1 à 21,5 °C) : le double. Pourtant les étés sont "
                "identiques (21,6 contre 21,5 °C) : tout l'écart vient de l'hiver."
            ),
            hint="Amplitude = mois le plus chaud moins mois le plus froid.",
            chart="climato",
            minutes=6,
        ),
        Step(
            title="Lire la carte des courants",
            instruction=(
                "Suis sur le schéma la flèche chaude du Gulf Stream et la flèche "
                "froide du Labrador : vers quelle rive de l'Atlantique chacune se "
                "dirige-t-elle ?"
            ),
            expected=(
                "Le Gulf Stream (rouge) remonte le long de la côte américaine "
                "puis traverse vers l'Europe : il réchauffe la rive de "
                "Bordeaux. Le courant du Labrador (bleu) descend de l'Arctique "
                "le long du Canada jusqu'à Terre-Neuve : il refroidit la rive "
                "de Montréal."
            ),
            hint="Le rouge transporte de la chaleur vers l'est, le bleu du froid vers le sud.",
            chart="schema",
            minutes=7,
        ),
        Step(
            title="Expliquer",
            instruction=(
                "Explique pourquoi Bordeaux et Montréal, à la même latitude, ont "
                "des hivers si différents alors que leurs étés sont presque "
                "identiques."
            ),
            expected=(
                "À Bordeaux, les vents d'ouest arrivent chargés de la chaleur "
                "du Gulf Stream et de la dérive nord-atlantique : l'hiver reste "
                "à 6,7 °C. À Montréal, ces mêmes vents ont traversé un continent "
                "glacé, et le courant froid du Labrador baigne la côte : "
                "l'hiver tombe à −9,1 °C. L'été, le continent chauffe des deux "
                "côtés : 21,5 °C partout. Même latitude ne veut pas dire même "
                "climat."
            ),
            hint="Relie « vents d'ouest », « Gulf Stream » et « Labrador » aux deux hivers.",
            chart="climato",
            minutes=8,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# 13. El Niño : le Pacifique se réchauffe (2025-2026)
# --------------------------------------------------------------------------- #

EXAM_ELNINO = Exam(
    contexte=(
        "Depuis le printemps 2026, les eaux de surface du Pacifique tropical "
        "se réchauffent au-dessus de leur valeur habituelle : les médias "
        "parlent d'El Niño. Ce phénomène naturel déplace la zone de pluies la "
        "plus intense de la planète et peut provoquer sécheresses et "
        "inondations à l'autre bout du monde. Pour le suivre, les "
        "climatologues utilisent une zone de référence située au centre du "
        "Pacifique équatorial, la boîte Niño 3.4 (5° N–5° S, 170° O–120° O), "
        "dont la température de surface est mesurée par les satellites et par "
        "des bouées automatiques. Les documents s'appuient sur les relevés "
        "mensuels ERA5 de cette boîte, rapportés à la normale 1991-2020."
    ),
    rappel=(
        "À l'aide des documents ci-dessous et de vos connaissances, répondez "
        "aux questions dans l'ordre. Rédigez des phrases complètes : une valeur "
        "donnée sans justification n'est pas acceptée."
    ),
    documents=(
        ExamDoc(
            number=1,
            title="Températures mensuelles de la boîte Niño 3.4 en 2025 et 2026",
            body=(
                "Chaque point est la moyenne mensuelle de la température de "
                "surface de la zone. La courbe 2026 ne couvre que les huit "
                "premiers mois de l'année."
            ),
            chart="figure",
            file="elnino_1.png",
            caption="Température mensuelle de la boîte Niño 3.4 (ERA5, données réelles).",
        ),
        ExamDoc(
            number=2,
            title="Anomalies mensuelles 2025 et 2026",
            body=(
                "L'anomalie compare chaque mois à la moyenne du même mois sur "
                "la période 1991-2020 : zéro correspond à la normale. Les "
                "barres au-dessus de zéro sont des mois plus chauds que la "
                "normale, celles en dessous des mois plus froids ; le seuil de "
                "+0,5 °C, maintenu plusieurs mois de suite, caractérise un "
                "épisode El Niño."
            ),
            chart="figure",
            file="elnino_2.png",
            caption="Écart de chaque mois à la normale 1991-2020 (ERA5).",
        ),
        ExamDoc(
            number=3,
            title="Repères de température",
            body=(
                "Valeurs arrondies au dixième de degré, lues dans les séries "
                "mensuelles ERA5 de la boîte Niño 3.4."
            ),
            chart="table",
            caption="Normale 1991-2020 et relevés mensuels cités dans le sujet.",
            table=(
                ("Repère", "Valeur"),
                ("Normale moyenne annuelle 1991-2020", "27,1 °C"),
                ("Normale de août 1991-2020", "26,9 °C"),
                ("Août 2025", "26,5 °C"),
                ("Août 2026", "29,5 °C"),
                ("Anomalie moyenne de l'hiver 2023-2024", "+1,8 °C"),
                ("Anomalie de décembre 2023", "+2,0 °C"),
            ),
        ),
    ),
    questions=(
        ExamQuestion(
            id="1",
            skill="Connaissances — définir",
            text="Définir ce qu'est un épisode El Niño.",
            points=2,
            attendu=(
                "Réchauffement anormal et temporaire des eaux de surface du "
                "Pacifique équatorial centre-est, mesuré par une anomalie "
                "positive durable de la boîte Niño 3.4."
            ),
            expected=(
                "El Niño est un réchauffement anormal et temporaire des eaux "
                "de surface du centre et de l'est du Pacifique équatorial, "
                "caractérisé par une anomalie positive de température de la "
                "boîte Niño 3.4 maintenue sur plusieurs mois (au-delà de "
                "+0,5 °C)."
            ),
        ),
        ExamQuestion(
            id="2",
            skill="Données — décrire un document",
            text=(
                "Décrire, à l'aide du document 1, l'évolution des températures "
                "de la boîte Niño 3.4 entre 2025 et 2026."
            ),
            points=3,
            attendu=(
                "Deux phases attendues : 2025 reste stable autour de 26 à "
                "27 °C ; 2026 monte régulièrement de 26,0 °C en janvier à "
                "29,5 °C en août. L'élève doit citer au moins deux valeurs "
                "et distinguer les deux années."
            ),
            expected=(
                "En 2025, la température reste proche de 26,5 °C toute "
                "l'année. En 2026, elle progresse sans interruption : 26,0 °C "
                "en janvier puis 29,5 °C en août, soit +3,5 °C en sept mois. "
                "La comparaison d'août à août donne 29,5 − 26,5 = 3,0 °C en un "
                "an."
            ),
        ),
        ExamQuestion(
            id="3",
            skill="Données — exploiter et calculer",
            text=(
                "À l'aide du document 3, calculer l'écart entre août 2025 et "
                "août 2026, puis l'anomalie du mois d'août 2026 par rapport à "
                "la normale de référence, et dire si la boîte est en situation "
                "d'El Niño."
            ),
            points=6,
            attendu=(
                "Calculs attendus : 29,5 − 26,5 = +3,0 °C d'un août à "
                "l'autre ; 29,5 − 26,9 = +2,6 °C (ou +2,7 °C si l'on utilise "
                "la normale non arrondie de 26,85 °C). Conclusion attendue : "
                "anomalie très supérieure au seuil de +0,5 °C, donc la boîte "
                "est bien en situation d'El Niño ; on valorise la mention des "
                "mois consécutifs et du document 2."
            ),
            expected=(
                "Écart d'un août à l'autre : 29,5 − 26,5 = 3,0 °C. Anomalie "
                "d'août 2026 : 29,5 − 26,9 = +2,6 °C (≈ +2,7 °C avec la "
                "normale exacte de 26,85 °C), soit très au-dessus du seuil de "
                "+0,5 °C. La boîte Niño 3.4 est donc bien en situation "
                "d'El Niño : le réchauffement dépasse la normale depuis "
                "plusieurs mois."
            ),
        ),
        ExamQuestion(
            id="4",
            skill="Rédaction — expliquer et appliquer",
            text=(
                "À l'aide des documents et de vos connaissances, expliquer le "
                "mécanisme d'El Niño (alizés, eau chaude, remontée d'eau "
                "froide), puis donner une conséquence possible sur les pluies "
                "d'une région du monde."
            ),
            points=5,
            attendu=(
                "Partie 1 : normalement les alizés poussent l'eau chaude vers "
                "l'ouest et permettent la remontée d'eau froide au large du "
                "Pérou ; quand ils faiblissent, l'eau chaude reflue vers "
                "l'est et la surface se réchauffe. Partie 2 : une conséquence "
                "cohérente, par exemple pluies déplacées vers le centre-est du "
                "Pacifique, sécheresse en Indonésie, pluies excessives en "
                "Amérique du Sud. Réponse rédigée en phrases complètes."
            ),
            expected=(
                "En temps normal, les alizés poussent l'eau chaude de surface "
                "vers l'ouest (Indonésie) et laissent remonter l'eau froide "
                "des profondeurs au large du Pérou. Quand les alizés "
                "faiblissent, l'eau chaude reflue vers l'est, la remontée "
                "d'eau froide s'arrête et la surface se réchauffe sur des "
                "milliers de kilomètres : c'est El Niño. Conséquences : la "
                "zone de convection et les pluies intenses se déplacent vers "
                "le centre et l'est du Pacifique — sécheresse en Indonésie et "
                "en Australie, pluies très abondantes sur le littoral "
                "péruvien."
            ),
        ),
    ),
    theme=(
        "La planète Terre, l'environnement et l'action humaine — océan et "
        "atmosphère, variabilité climatique (cycle 4)"
    ),
    sources=(
        "ERA5 — Copernicus Climate Change Service (C3S/CAMS)",
        "Normale 1991-2020 de la boîte Niño 3.4 calculée sur les relevés ERA5",
    ),
    duration=25,
)


ELNINO = Activity(
    key="elnino",
    title="El Niño : quand l'océan Pacifique se réchauffe",
    levels="4e · 3e",
    duration="55 min",
    subject="SVT · Géographie",
    objective=(
        "Mesurer le réchauffement du Pacifique équatorial entre 2025 et 2026 "
        "et expliquer le mécanisme d'El Niño (alizés, eau chaude, upwelling)."
    ),
    skills=(
        "Lire une température de surface océanique",
        "Calculer une anomalie par rapport à une normale",
        "Expliquer El Niño par l'affaiblissement des alizés",
    ),
    introduction=(
        "En août 2026, le Pacifique équatorial affiche des températures "
        "supérieures à tout ce que la normale 1991-2020 permet d'attendre : "
        "El Niño est de retour. Les mesures de la boîte Niño 3.4 "
        "(5° N–5° S, 170° O–120° O) vont vous permettre de mesurer ce "
        "réchauffement, de le comparer à la normale, puis d'en chercher la "
        "cause — un vent qui faiblit."
    ),
    default_cities=(),
    variables=("sea_surface_temperature",),
    chart="figure",
    keywords=("El Niño", "océan", "anomalie", "alizés"),
    difficulty=3,
    exam=EXAM_ELNINO,
    steps=(
        Step(
            title="Décrire l'écart",
            instruction=(
                "Calcule, d'après la figure, l'écart de température entre "
                "août 2025 (26,5 °C) et août 2026 (29,5 °C) dans la boîte "
                "Niño 3.4."
            ),
            expected=(
                "29,5 − 26,5 = 3,0 °C en un an, pour le même mois et la même "
                "zone. Sur un océan, un tel écart en douze mois est considérable : "
                "c'est la signature d'El Niño."
            ),
            hint="Écart = valeur 2026 moins valeur 2025, pour le même mois.",
            chart="figure",
            minutes=5,
        ),
        Step(
            title="Comparer les années",
            instruction=(
                "Calcule l'anomalie moyenne de 2025, puis celle de 2026, par "
                "rapport à la normale 1991-2020 : que constates-tu ?"
            ),
            expected=(
                "2025 est légèrement plus froide que la normale (−0,4 °C en "
                "moyenne), tandis que 2026 est nettement plus chaude (+0,9 °C "
                "sur janvier-août, jusqu'à +2,7 °C en août). Le Pacifique "
                "bascule : un épisode El Niño se met en place en 2026."
            ),
            hint="Anomalie = valeur mesurée moins normale 1991-2020 du même mois.",
            chart="figure",
            minutes=7,
        ),
        Step(
            title="Replacer dans l'histoire récente",
            instruction=(
                "Compare sur la chronologie 2023-2026 l'anomalie de l'hiver "
                "2023-2024 à celle de 2026 : que partagent ces deux périodes ?"
            ),
            expected=(
                "Les deux sont des El Niño : l'hiver 2023-2024 affichait "
                "+1,8 °C d'anomalie moyenne (jusqu'à +2,0 °C en décembre), et "
                "2026 repart sur la même trajectoire. Entre les deux, 2024-2025 "
                "reste proche de zéro : El Niño alterne avec des années neutres "
                "ou froides (La Niña), il ne dure jamais."
            ),
            hint="Un hiver El Niño dépasse durablement +0,5 °C d'anomalie.",
            chart="figure",
            minutes=7,
        ),
        Step(
            title="Expliquer l'origine",
            instruction=(
                "Rédige un paragraphe qui explique le mécanisme d'El Niño : ce "
                "que font normalement les alizés, ce qui change quand ils "
                "faiblissent, et la conséquence sur la température de surface."
            ),
            expected=(
                "En temps normal, les alizés poussent l'eau chaude de surface "
                "vers l'ouest (Indonésie) et font remonter l'eau froide des "
                "profondeurs au large du Pérou. Quand les alizés faiblissent, "
                "l'eau chaude reflue vers l'est, la remontée d'eau froide "
                "s'arrête, et la surface se réchauffe sur des milliers de "
                "kilomètres : c'est El Niño, et son origine est un vent qui "
                "faiblit."
            ),
            hint="Que se passe-t-il au Pérou si l'eau chaude de l'ouest revient vers l'est ?",
            chart="figure",
            minutes=8,
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
    PLUIES_EUROPE,
    REGIMES_MONDE,
    PORTRAIT_CLIMAT,
    VENTS_COURANTS,
    ELNINO,
]
# NOTE : l'activité CANICULE (jours de chaleur, données journalières) est
# temporairement retirée du catalogue en attendant la préparation des données
# journalières (`python scripts/prepare_data.py heat --cities Marseille,Paris`).
# Son code est conservé ci-dessous pour réactivation.

_BY_KEY = {a.key: a for a in ACTIVITIES}


def get(key: str) -> Activity:
    """Renvoie une activité par sa clé, avec message d'erreur explicite."""
    if key not in _BY_KEY:
        raise KeyError(f"Activité inconnue : {key!r}. Disponibles : {sorted(_BY_KEY)}")
    return _BY_KEY[key]


def list_activities(*, with_answers: bool = False) -> list[dict[str, Any]]:
    """Toutes les activités (les corrigés ne sortent qu'avec le code enseignant)."""
    return [a.as_dict(with_answers=with_answers) for a in ACTIVITIES]
