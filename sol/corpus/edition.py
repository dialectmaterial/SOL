"""Audited Cambridge edition metadata and the shared abbreviated outline.

The anchor tables are source evidence for the one-time importer, not a second
canonical corpus. Reading uses the permanent structure and IDs in Markdown.
"""

from __future__ import annotations

from pathlib import Path

from sol.core.models import Node


# This index is specific to the Cambridge di Giovanni edition supplied with the
# project. Its printed page 7 is PDF page 80; page 827 begins the editor's
# appendix, so it is deliberately outside the readable corpus.
PDF_FILENAME = "Hegel-SOL.pdf"
FIRST_TEXT_PAGE = 80
LAST_TEXT_PAGE = 826
PRINTED_PAGE_OFFSET = 73


# Directories are divisions that contain further divisions. Files are passages
# attached to the heading that begins them. Numeric prefixes are display names,
# not claims about Hegel's own numbering; they keep `ls` in reading order.
# 1. Book index: the published TOC, followed by verified internal headings.
BEING = Node(
    "BEING",
    "Doctrine of Being (Book One)",
    7,
    (
        Node("00-preface-to-the-first-edition.txt", "Preface to the first edition", 7),
        Node("01-preface-to-the-second-edition.txt", "Preface to the second edition", 11),
        Node("02-introduction.txt", "Introduction", 23),
        Node("03-with-what-must-the-beginning-of-science-be-made.txt", "With what must the beginning of science be made?", 45),
        Node("04-general-division-of-being.txt", "General division of being", 56),
        Node(
            "05-determinateness-quality",
            "Section I: Determinateness (Quality)",
            58,
            (
                Node("01-being.txt", "Chapter 1: Being", 59),
                Node("02-existence.txt", "Chapter 2: Existence", 83),
                Node("03-being-for-itself.txt", "Chapter 3: Being-for-itself", 126),
            ),
        ),
        Node(
            "06-magnitude-quantity",
            "Section II: Magnitude (Quantity)",
            152,
            (
                Node("01-quantity.txt", "Chapter 1: Quantity", 154),
                Node("02-quantum.txt", "Chapter 2: Quantum", 168),
                Node("03-ratio-or-the-quantitative-relation.txt", "Chapter 3: Ratio or the quantitative relation", 271),
            ),
        ),
        Node(
            "07-measure",
            "Section III: Measure",
            282,
            (
                Node("01-specific-quantity.txt", "Chapter 1: Specific quantity", 288),
                Node("02-real-measure.txt", "Chapter 2: Real measure", 302),
                Node("03-the-becoming-of-essence.txt", "Chapter 3: The becoming of essence", 326),
            ),
        ),
    ),
)

ESSENCE = Node(
    "ESSENCE",
    "Doctrine of Essence (Book Two)",
    337,
    (
        Node(
            "01-essence-as-reflection-within",
            "Section I: Essence as reflection within",
            340,
            (
                Node("01-shine.txt", "Chapter 1: Shine", 341),
                Node("02-the-essentialities-or-the-determinations-of-reflection.txt", "Chapter 2: The essentialities or the determinations of reflection", 354),
                Node("03-ground.txt", "Chapter 3: Ground", 386),
            ),
        ),
        Node(
            "02-appearance",
            "Section II: Appearance",
            418,
            (
                Node("01-concrete-existence.txt", "Chapter 1: Concrete existence", 420),
                Node("02-appearance.txt", "Chapter 2: Appearance", 437),
                Node("03-the-essential-relation.txt", "Chapter 3: The essential relation", 449),
            ),
        ),
        Node(
            "03-actuality",
            "Section III: Actuality",
            465,
            (
                Node("01-the-absolute.txt", "Chapter 1: The absolute", 466),
                Node("02-actuality.txt", "Chapter 2: Actuality", 477),
                Node("03-the-absolute-relation.txt", "Chapter 3: The absolute relation", 489),
            ),
        ),
    ),
)

CONCEPT = Node(
    "CONCEPT",
    "Doctrine of the Concept (Volume Two / Subjective Logic)",
    507,
    (
        Node("00-foreword.txt", "Foreword", 507),
        Node("01-of-the-concept-in-general.txt", "Of the concept in general", 508),
        Node("02-division.txt", "Division", 526),
        Node(
            "03-subjectivity",
            "Section I: Subjectivity",
            528,
            (
                Node("01-the-concept.txt", "Chapter 1: The concept", 529),
                Node("02-judgment.txt", "Chapter 2: Judgment", 550),
                Node("03-the-syllogism.txt", "Chapter 3: The syllogism", 588),
            ),
        ),
        Node(
            "04-objectivity",
            "Section II: Objectivity",
            625,
            (
                Node("01-mechanism.txt", "Chapter 1: Mechanism", 631),
                Node("02-chemism.txt", "Chapter 2: Chemism", 645),
                Node("03-teleology.txt", "Chapter 3: Teleology", 651),
            ),
        ),
        Node(
            "05-the-idea",
            "Section III: The idea",
            670,
            (
                Node("01-life.txt", "Chapter 1: Life", 676),
                Node("02-the-idea-of-cognition.txt", "Chapter 2: The idea of cognition", 689),
                Node("03-the-absolute-idea.txt", "Chapter 3: The absolute idea", 735),
            ),
        ),
    ),
)

# Verified against this edition's headings, including their positions within
# the printed page. No classifier or inferred philosophical hierarchy is used.
SUBDIVISIONS = {
    59: (
        ("A", "Being", 59, 169.0),
        ("B", "Nothing", 59, 333.9),
        ("C", "Becoming", 59, 486.4),
    ),
    83: (
        ("A", "Existence as such", 83, 324.5),
        ("B", "Finitude", 90, 212.4),
        ("C", "Infinity", 108, 412.8),
    ),
    126: (
        ("A", "Being-for-itself as such", 126, 474.0),
        ("B", "The one and the many", 132, 411.7),
        ("C", "Repulsion and attraction", 138, 62.9),
    ),
    154: (
        ("A", "Pure quantity", 154, 181.5),
        ("B", "Continuous and discrete magnitude", 165, 438.6),
        ("C", "The limiting of quantity", 167, 249.8),
    ),
    168: (
        ("A", "Number", 168, 324.5),
        ("B", "Extensive and intensive quantum", 182, 125.2),
        ("C", "Quantitative infinity", 190, 100.3),
    ),
    271: (
        ("A", "The direct ratio", 272, 262.2),
        ("B", "The inverse ratio", 274, 62.9),
        ("C", "The ratio of powers", 278, 62.9),
    ),
    288: (
        ("A", "The specific quantum", 288, 336.9),
        ("B", "Specifying measure", 291, 355.6),
        ("C", "The being-for-itself in measure", 298, 275.7),
    ),
    302: (
        ("A", "The relation of independent measures", 303, 212.4),
        ("B", "Nodal lines of measure-relations", 318, 474.4),
        ("C", "The measureless", 323, 187.5),
    ),
    326: (
        ("A", "Absolute indifference", 326, 181.5),
        ("B", "Indifference as inverse ratio of its factors", 327, 63.1),
        ("C", "Transition into essence", 333, 486.4),
    ),
    341: (
        ("A", "The essential and the unessential", 341, 287.1),
        ("B", "Shine", 342, 312.0),
        ("C", "Reflection", 345, 411.7),
    ),
    354: (
        ("A", "Identity", 356, 274.7),
        ("B", "Difference", 361, 175.0),
        ("C", "Contradiction", 374, 224.8),
    ),
    386: (
        ("A", "Absolute ground", 389, 64.3),
        ("B", "Determinate ground", 397, 361.9),
        ("C", "Condition", 410, 62.9),
    ),
    420: (
        ("A", "The thing and its properties", 423, 137.6),
        ("B", "The constitution of the thing out of matters", 430, 361.9),
        ("C", "Dissolution of the thing", 432, 449.1),
    ),
    437: (
        ("A", "The law of appearance", 438, 449.1),
        ("B", "The world of appearance and the world-in-itself", 443, 150.1),
        ("C", "The dissolution of appearance", 447, 63.1),
    ),
    449: (
        ("A", "The relation of whole and parts", 450, 424.2),
        ("B", "The relation of force and its expression", 455, 187.5),
        ("C", "Relation of outer and inner", 460, 62.9),
    ),
    466: (
        ("A", "The exposition of the absolute", 466, 436.6),
        ("B", "The absolute attribute", 469, 199.9),
        ("C", "The mode of the absolute", 470, 312.0),
    ),
    477: (
        ("A", "Contingency or formal actuality, possibility, and necessity", 478, 371.6),
        ("B", "Relative necessity or real actuality, possibility, and necessity", 482, 62.9),
        ("C", "Absolute necessity", 485, 462.0),
    ),
    489: (
        ("A", "The relation of substantiality", 490, 125.2),
        ("B", "The relation of causality", 492, 436.7),
        ("C", "Reciprocity of action", 503, 150.1),
    ),
    529: (
        ("A", "The universal concept", 530, 175.0),
        ("B", "The particular concept", 534, 162.6),
        ("C", "The singular", 546, 187.5),
    ),
    550: (
        ("A", "The judgment of existence", 557, 187.5),
        ("B", "The judgment of reflection", 568, 411.7),
        ("C", "The judgment of necessity", 575, 175.0),
        ("D", "The judgment of the concept", 581, 462.2),
    ),
    588: (
        ("A", "The syllogism of existence", 590, 195.9),
        ("B", "The syllogism of reflection", 609, 62.7),
        ("C", "The syllogism of necessity", 617, 249.8),
    ),
    631: (
        ("A", "The mechanical object", 631, 499.1),
        ("B", "The mechanical process", 634, 177.5),
        ("C", "Absolute mechanism", 640, 499.4),
    ),
    645: (
        ("A", "The chemical object", 645, 260.1),
        ("B", "The process", 646, 361.9),
        ("C", "Transition of chemism", 649, 150.1),
    ),
    651: (
        ("A", "The subjective purpose", 657, 150.1),
        ("B", "The means", 659, 274.7),
        ("C", "The realized purpose", 662, 99.1),
    ),
    676: (
        ("A", "The living individual", 679, 224.9),
        ("B", "The life-process", 684, 62.9),
        ("C", "The genus", 686, 414.2),
    ),
    689: (
        ("A", "The idea of the true", 697, 175.0),
        ("B", "The idea of the good", 729, 187.5),
    ),
    735: (),  # No A/B/C subdivision in this final chapter.
}

# Requested verified next-level headings. Keys identify (chapter, major letter).
# Unlike small-cap A/B/C headings, the source displays these lower-case letters
# or Arabic numerals. Existence/B/c has a deeper Greek alpha/beta/gamma level;
# that further level is intentionally not included here.
SECOND_LEVEL = {
    (59, "C"): (
        ("1", "Unity of being and nothing", 59, 508.2),
        ("2", "The moments of becoming", 80, 259.1),
        ("3", "Sublation of becoming", 81, 147.0),
    ),
    (83, "A"): (
        ("a", "Existence in general", 83, 421.0),
        ("b", "Quality", 84, 495.8),
        ("c", "Something", 88, 297.0),
    ),
    (83, "B"): (
        ("a", "Something and an other", 90, 470.9),
        ("b", "Determination, constitution, and limit", 95, 256.4),
        ("c", "Finitude", 101, 105.7),
    ),
    (83, "C"): (
        ("a", "The infinite in general", 109, 259.1),
        ("b", "Alternating determination of finite and infinite", 110, 134.5),
        ("c", "Affirmative infinity", 114, 59.8),
    ),
    (126, "A"): (
        ("a", "Existence and being-for-itself", 127, 359.3),
        ("b", "Being-for-one", 128, 59.7),
        ("c", "The one", 132, 134.5),
    ),
    (126, "B"): (
        ("a", "The one within", 133, 171.9),
        ("b", "The one and the void", 133, 458.4),
        ("c", "Many ones", 135, 321.4),
    ),
    (126, "C"): (
        ("a", "Exclusion of the one", 138, 84.7),
        ("b", "The one one of attraction", 141, 59.8),
        ("c", "The connection of repulsion and attraction", 142, 97.2),
    ),
    (354, "B"): (
        ("1", "Absolute difference", 361, 196.8),
        ("2", "Diversity", 362, 321.4),
        ("3", "Opposition", 367, 433.5),
    ),
    (550, "A"): (
        ("a", "The positive judgment", 557, 446.0),
        ("b", "The negative judgment", 562, 59.9),
        ("c", "The infinite judgment", 567, 209.3),
    ),
    (550, "B"): (
        ("a", "The singular judgment", 570, 217.6),
        ("b", "The particular judgment", 570, 425.2),
        ("c", "The universal judgment", 572, 171.9),
    ),
    (550, "C"): (
        ("a", "The categorical judgment", 575, 358.8),
        ("b", "The hypothetical judgment", 576, 458.4),
        ("c", "The disjunctive judgment", 578, 122.1),
    ),
    (550, "D"): (
        ("a", "The assertoric judgment", 583, 159.4),
        ("b", "The problematic judgment", 584, 209.3),
        ("c", "The apodictic judgment", 585, 433.5),
    ),
    (689, "A"): (
        ("a", "Analytic cognition", 700, 134.5),
        ("b", "Synthetic cognition", 706, 411.3),
    ),
}

THIRD_LEVEL = {
    (689, "A", "b"): (
        ("1", "Definition", 708, 53.8),
        ("2", "Division", 713, 190.9),
        ("3", "The theorem", 718, 190.8),
    ),
}

ROOT = Node("", "The Science of Logic", 7, (BEING, ESSENCE, CONCEPT))


def default_pdf() -> Path:
    """Look in the working directory first, then preserve the user's sources layout."""
    direct = Path.cwd() / PDF_FILENAME
    local_source = Path.cwd() / "sources" / PDF_FILENAME
    return direct if direct.is_file() or not local_source.is_file() else local_source
