from __future__ import annotations

from syllabus_expert.latexify import latexify_mcq
from syllabus_expert.models import MCQ

NEET_SECTIONS = (
    (1, 45, "Physics"),
    (46, 90, "Chemistry"),
    (91, 135, "Botany"),
    (136, 180, "Zoology"),
)

TOPIC_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Moment of Inertia, Radius of Gyration", ("radius of gyration", "moment of inertia", "radii of gyration")),
    ("Center of Mass", ("center of mass", "centre of mass")),
    ("Rolling Motion", ("pure rolling", "rolling without slipping", "rolling motion", "rolling")),
    ("Angular Momentum", ("angular momentum", "torque")),
    ("Rotational Kinetic Energy", ("rotational kinetic", "translational kinetic")),
    ("Projectile Motion", ("projectile",)),
    ("Carbocation Stability", ("carbocation", "hyperconjugation")),
    ("IUPAC Nomenclature", ("iupac", "nomenclature")),
    ("Hybridization", ("hybridization", "hybridised", "hybridized", "allene")),
    ("Inductive Effect", ("inductive effect",)),
    ("Chemical Kinetics", ("activation energy", "arrhenius", "half-life", "first-order", "zero order", "rate law")),
    ("Organic Estimation", ("kjeldahl", "carius", "liebig")),
    ("Isomerism", ("isomer", "metamerism")),
    ("Secondary Growth", ("heartwood", "phellogen", "bark", "spring wood", "autumn wood", "periderm")),
    ("Plant Anatomy", ("xylem", "phloem", "collenchyma", "monocot", "dicot", "vascular")),
    ("Taxonomy", ("binomial", "herbarium", "nomenclature", "taxonomic", "scientific name")),
    ("Human Health and Disease", ("plasmodium", "hiv", "heroin", "cocaine", "cancer", "immunity", "lymphoid", "amoebiasis", "malaria", "typhoid")),
    ("Cannabinoids", ("cannabinoid",)),
]


def infer_subject(number: str | int | None) -> str:
    try:
        value = int(str(number))
    except (TypeError, ValueError):
        return "General"
    for start, end, name in NEET_SECTIONS:
        if start <= value <= end:
            return name
    return "General"


def infer_topic(question: str, subject: str) -> str:
    lowered = question.lower()
    for topic, needles in TOPIC_RULES:
        if any(needle in lowered for needle in needles):
            return topic
    return f"General {subject}"


def enrich_mcq(mcq: MCQ) -> MCQ:
    if not mcq.subject:
        mcq.subject = infer_subject(mcq.number)
    if not mcq.topic:
        mcq.topic = infer_topic(mcq.question, mcq.subject or "General")
    if not mcq.difficulty:
        mcq.difficulty = "medium"
    latexify_mcq(mcq)
    return mcq
