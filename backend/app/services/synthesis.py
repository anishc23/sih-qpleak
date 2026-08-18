"""Question synthesis: duplicate detection, blueprint-driven selection, variation.

Honest description of what this is, because it matters for the pitch:

  * The similarity engine is real TF-IDF with cosine similarity, implemented
    here in ~80 lines of Python. It is not a stub and not a call to a hosted
    model. It genuinely finds near-duplicate questions.
  * The selection engine is a real constrained optimiser over an explicit
    scoring function with a seeded RNG, so a demo reproduces exactly.
  * The variation engine is a deterministic, rule-based paraphraser. It is
    labelled as such everywhere in the UI. It is NOT a language model, and the
    project does not pretend it is. An optional LLM path exists behind
    LLM_API_KEY, but the demo never requires it.

Why this reduces leak risk (the actual claim): a setter who contributed a
question cannot predict whether it will be selected, against which competitors,
or in which wording. That is a probabilistic reduction in predictability, not a
guarantee, and the documentation says so.
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

# Common English + exam-domain words carry no discriminating signal.
_STOPWORDS = frozenset(
    """
    a an the and or but if then else of in on at to for from by with without
    is are was were be been being do does did doing have has had having
    this that these those it its as not no can could should would will shall
    what which who whom whose when where why how explain describe define
    write give state list discuss consider following given using use used
    question answer marks mark example examples illustrate briefly
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens with stopwords and 1-character noise removed."""
    return [
        t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1
    ]


def term_frequencies(tokens: Sequence[str]) -> dict[str, float]:
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {term: count / total for term, count in counts.items()}


def inverse_document_frequencies(documents: Sequence[Sequence[str]]) -> dict[str, float]:
    n = len(documents)
    if n == 0:
        return {}
    doc_freq: Counter[str] = Counter()
    for doc in documents:
        doc_freq.update(set(doc))
    # Smoothed IDF; +1 keeps terms present in every document from vanishing.
    return {term: math.log((n + 1) / (df + 1)) + 1.0 for term, df in doc_freq.items()}


def tfidf_vector(tokens: Sequence[str], idf: dict[str, float]) -> dict[str, float]:
    return {term: tf * idf.get(term, 1.0) for term, tf in term_frequencies(tokens).items()}


def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    # Iterate the smaller vector for the dot product.
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    dot = sum(weight * large.get(term, 0.0) for term, weight in small.items())
    if dot == 0.0:
        return 0.0
    norm_a = math.sqrt(sum(w * w for w in a.values()))
    norm_b = math.sqrt(sum(w * w for w in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ----------------------------------------------------------------------
# Candidate model
# ----------------------------------------------------------------------


@dataclass
class Candidate:
    """One approved question offered to the selection engine."""

    question_id: int
    question_uid: str
    text: str
    subject: str
    topic: str
    difficulty: str
    question_type: str
    marks: int
    creator_uid: str
    tokens: list[str] = field(default_factory=list)
    vector: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.tokens:
            self.tokens = tokenize(self.text)


@dataclass
class DuplicatePair:
    left_uid: str
    right_uid: str
    similarity: float
    risk: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "left": self.left_uid,
            "right": self.right_uid,
            "similarity": round(self.similarity, 4),
            "risk": self.risk,
        }


def risk_band(similarity: float, threshold: float) -> str:
    if similarity >= max(threshold, 0.85):
        return "HIGH"
    if similarity >= threshold:
        return "MEDIUM"
    if similarity >= threshold * 0.7:
        return "LOW"
    return "NEGLIGIBLE"


def build_vectors(candidates: Sequence[Candidate]) -> dict[str, float]:
    """Fit IDF over the pool and attach a TF-IDF vector to each candidate."""
    idf = inverse_document_frequencies([c.tokens for c in candidates])
    for candidate in candidates:
        candidate.vector = tfidf_vector(candidate.tokens, idf)
    return idf


def find_duplicates(
    candidates: Sequence[Candidate], threshold: float
) -> list[DuplicatePair]:
    """All candidate pairs at or above the low-risk band, worst first."""
    if not candidates:
        return []
    if not candidates[0].vector:
        build_vectors(candidates)

    pairs: list[DuplicatePair] = []
    floor = threshold * 0.7
    for i, left in enumerate(candidates):
        for right in candidates[i + 1 :]:
            score = cosine_similarity(left.vector, right.vector)
            if score >= floor:
                pairs.append(
                    DuplicatePair(
                        left.question_uid, right.question_uid, score, risk_band(score, threshold)
                    )
                )
    pairs.sort(key=lambda p: p.similarity, reverse=True)
    return pairs


# ----------------------------------------------------------------------
# Blueprint
# ----------------------------------------------------------------------


@dataclass
class Blueprint:
    question_count: int
    total_marks: int
    difficulty: dict[str, float]  # percentages, e.g. {"EASY": 30, ...}
    topics: dict[str, float]
    types: dict[str, float] | None = None

    @classmethod
    def from_model(cls, exam, blueprint_row) -> "Blueprint":
        return cls(
            question_count=exam.question_count,
            total_marks=exam.total_marks,
            difficulty=json.loads(blueprint_row.difficulty_distribution),
            topics=json.loads(blueprint_row.topic_distribution),
            types=json.loads(blueprint_row.type_distribution)
            if blueprint_row.type_distribution
            else None,
        )

    def target_counts(self, distribution: dict[str, float]) -> dict[str, int]:
        """Convert percentages into integer question counts that sum exactly."""
        raw = {k: (v / 100.0) * self.question_count for k, v in distribution.items()}
        counts = {k: int(math.floor(v)) for k, v in raw.items()}
        remainder = self.question_count - sum(counts.values())
        # Hand out leftovers to the largest fractional parts (largest remainder method).
        order = sorted(raw, key=lambda k: raw[k] - math.floor(raw[k]), reverse=True)
        for key in order:
            if remainder <= 0:
                break
            counts[key] += 1
            remainder -= 1
        return counts


# ----------------------------------------------------------------------
# Selection
# ----------------------------------------------------------------------


@dataclass
class SelectionResult:
    selected: list[Candidate]
    reasons: dict[str, str]
    scores: dict[str, float]
    duplicates: list[DuplicatePair]
    compliance: dict[str, Any]
    report: dict[str, Any]


class SynthesisEngine:
    """Deterministic given the same pool, blueprint and seed."""

    def __init__(self, *, seed: int, duplicate_threshold: float) -> None:
        self.seed = seed
        self.duplicate_threshold = duplicate_threshold

    def select(self, candidates: Sequence[Candidate], blueprint: Blueprint) -> SelectionResult:
        rng = random.Random(self.seed)
        pool = list(candidates)
        build_vectors(pool)
        duplicates = find_duplicates(pool, self.duplicate_threshold)

        difficulty_targets = blueprint.target_counts(blueprint.difficulty)
        topic_targets = blueprint.target_counts(blueprint.topics)

        difficulty_filled: Counter[str] = Counter()
        topic_filled: Counter[str] = Counter()
        creator_used: Counter[str] = Counter()

        selected: list[Candidate] = []
        reasons: dict[str, str] = {}
        scores: dict[str, float] = {}
        marks_target = blueprint.total_marks

        # Shuffle first so that equal-scoring candidates are not ordered by id --
        # otherwise a setter could predict selection from submission order.
        rng.shuffle(pool)

        while len(selected) < blueprint.question_count and pool:
            best: Candidate | None = None
            best_score = -math.inf
            best_reason = ""

            for candidate in pool:
                score, reason = self._score(
                    candidate,
                    selected=selected,
                    difficulty_targets=difficulty_targets,
                    difficulty_filled=difficulty_filled,
                    topic_targets=topic_targets,
                    topic_filled=topic_filled,
                    creator_used=creator_used,
                    marks_target=marks_target,
                    marks_so_far=sum(c.marks for c in selected),
                    remaining_slots=blueprint.question_count - len(selected),
                )
                # Tiny deterministic jitter breaks exact ties unpredictably.
                score += rng.random() * 1e-6
                if score > best_score:
                    best, best_score, best_reason = candidate, score, reason

            if best is None:
                break

            selected.append(best)
            scores[best.question_uid] = round(best_score, 4)
            reasons[best.question_uid] = best_reason
            difficulty_filled[best.difficulty] += 1
            topic_filled[best.topic] += 1
            creator_used[best.creator_uid] += 1
            pool.remove(best)

        compliance = self._compliance(
            selected, blueprint, difficulty_targets, topic_targets, duplicates
        )
        report = {
            "seed": self.seed,
            "pool_size": len(candidates),
            "selected_count": len(selected),
            "distinct_contributors": len({c.creator_uid for c in selected}),
            "duplicate_pairs_detected": len(duplicates),
            "high_risk_duplicates": sum(1 for d in duplicates if d.risk == "HIGH"),
            "duplicate_threshold": self.duplicate_threshold,
            "method": "TF-IDF cosine similarity + constrained greedy selection",
        }
        return SelectionResult(selected, reasons, scores, duplicates, compliance, report)

    def _score(
        self,
        candidate: Candidate,
        *,
        selected: Sequence[Candidate],
        difficulty_targets: dict[str, int],
        difficulty_filled: Counter[str],
        topic_targets: dict[str, int],
        topic_filled: Counter[str],
        creator_used: Counter[str],
        marks_target: int,
        marks_so_far: int,
        remaining_slots: int,
    ) -> tuple[float, str]:
        """score = topic_fit + difficulty_fit + marks_fit + diversity - duplicate_penalty"""
        notes: list[str] = []

        difficulty_need = difficulty_targets.get(candidate.difficulty, 0) - difficulty_filled[
            candidate.difficulty
        ]
        difficulty_fit = 3.0 if difficulty_need > 0 else -4.0
        if difficulty_need > 0:
            notes.append(f"fills {candidate.difficulty.lower()} quota ({difficulty_need} left)")
        else:
            notes.append(f"{candidate.difficulty.lower()} quota already met")

        topic_need = topic_targets.get(candidate.topic, 0) - topic_filled[candidate.topic]
        topic_fit = 3.0 if topic_need > 0 else -3.0
        if topic_need > 0:
            notes.append(f"fills {candidate.topic} quota ({topic_need} left)")

        # Marks fit: prefer candidates that keep us on pace for the total.
        ideal_per_slot = (marks_target - marks_so_far) / max(remaining_slots, 1)
        marks_fit = 2.0 - min(2.0, abs(candidate.marks - ideal_per_slot) / 3.0)

        # Diversity: penalise leaning on one contributor. This is an anti-leak
        # control -- spreading authorship shrinks any single setter's knowledge
        # of the final paper.
        diversity = 2.0 - min(2.0, creator_used[candidate.creator_uid] * 0.9)
        if creator_used[candidate.creator_uid] >= 2:
            notes.append(f"contributor {candidate.creator_uid} already used")

        duplicate_penalty = 0.0
        for chosen in selected:
            sim = cosine_similarity(candidate.vector, chosen.vector)
            if sim >= self.duplicate_threshold:
                duplicate_penalty += 8.0 * sim
                notes.append(f"near-duplicate of {chosen.question_uid} ({sim:.0%})")
            elif sim >= self.duplicate_threshold * 0.7:
                duplicate_penalty += 1.5 * sim

        total = topic_fit + difficulty_fit + marks_fit + diversity - duplicate_penalty
        return total, "; ".join(notes)

    def _compliance(
        self,
        selected: Sequence[Candidate],
        blueprint: Blueprint,
        difficulty_targets: dict[str, int],
        topic_targets: dict[str, int],
        duplicates: Sequence[DuplicatePair],
    ) -> dict[str, Any]:
        def pct(actual: Counter[str], targets: dict[str, int]) -> float:
            if not targets:
                return 100.0
            # Fraction of each quota actually met, averaged over quotas.
            met = sum(min(actual.get(k, 0), v) for k, v in targets.items())
            total = sum(targets.values())
            return round(100.0 * met / total, 1) if total else 100.0

        difficulty_actual = Counter(c.difficulty for c in selected)
        topic_actual = Counter(c.topic for c in selected)
        marks_total = sum(c.marks for c in selected)

        selected_uids = {c.question_uid for c in selected}
        residual = [
            d for d in duplicates
            if d.left_uid in selected_uids and d.right_uid in selected_uids
        ]
        worst = max((d.similarity for d in residual), default=0.0)

        marks_compliance = (
            100.0
            if blueprint.total_marks == 0
            else round(
                max(0.0, 100.0 - abs(marks_total - blueprint.total_marks) * 100.0 / blueprint.total_marks),
                1,
            )
        )

        return {
            "difficulty_compliance": pct(difficulty_actual, difficulty_targets),
            "topic_compliance": pct(topic_actual, topic_targets),
            "marks_compliance": marks_compliance,
            "duplicate_risk": risk_band(worst, self.duplicate_threshold) if residual else "LOW",
            "worst_pair_similarity": round(worst, 4),
            "difficulty_targets": difficulty_targets,
            "difficulty_actual": dict(difficulty_actual),
            "topic_targets": topic_targets,
            "topic_actual": dict(topic_actual),
            "marks_target": blueprint.total_marks,
            "marks_actual": marks_total,
        }


# ----------------------------------------------------------------------
# Variation
# ----------------------------------------------------------------------

# Ordered rewrite rules. Each is a (pattern, replacement) applied to the stem of
# a question. They restate the instruction without touching the subject matter,
# the numbers, or the expected answer.
_STEM_REWRITES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^explain\s+", re.I), "Describe in detail "),
    (re.compile(r"^describe\s+", re.I), "Explain, with reasoning, "),
    (re.compile(r"^define\s+", re.I), "State a precise definition of "),
    (re.compile(r"^what\s+is\s+", re.I), "Identify and explain "),
    (re.compile(r"^what\s+are\s+", re.I), "Identify and explain "),
    (re.compile(r"^list\s+", re.I), "Enumerate "),
    (re.compile(r"^state\s+", re.I), "Set out "),
    (re.compile(r"^write\s+a\s+", re.I), "Construct a "),
    (re.compile(r"^write\s+", re.I), "Produce "),
    (re.compile(r"^compare\s+", re.I), "Contrast and compare "),
    (re.compile(r"^calculate\s+", re.I), "Determine, showing your working, "),
    (re.compile(r"^find\s+", re.I), "Determine "),
    (re.compile(r"^discuss\s+", re.I), "Critically discuss "),
    (re.compile(r"^derive\s+", re.I), "Derive, from first principles, "),
    (re.compile(r"^prove\s+", re.I), "Show formally that "),
    (re.compile(r"^implement\s+", re.I), "Provide an implementation of "),
    (re.compile(r"^differentiate\s+between\s+", re.I), "Distinguish between "),
]

_SUFFIX_BY_TYPE = {
    "SHORT_ANSWER": "Answer concisely.",
    "LONG_ANSWER": "Support your answer with appropriate detail.",
    "PROBLEM": "Show each step of your working.",
    "NUMERICAL": "State the final value with its units.",
    "MCQ": "Select the single best option.",
}


def generate_variation(
    text: str, *, question_type: str = "SHORT_ANSWER"
) -> tuple[str, str]:
    """Deterministic rule-based rewording. Returns (variation, method).

    Guarantees by construction: no number, identifier or technical term in the
    body is altered -- only the leading instruction verb is restated and a
    type-appropriate instruction is appended. The intended answer cannot change
    because the substantive clause is copied verbatim.
    """
    stem = text.strip()
    method = "template:identity"
    for pattern, replacement in _STEM_REWRITES:
        if pattern.search(stem):
            stem = pattern.sub(replacement, stem, count=1)
            method = f"template:{pattern.pattern}"
            break

    suffix = _SUFFIX_BY_TYPE.get(question_type)
    if suffix and suffix.lower() not in stem.lower():
        stem = stem.rstrip()
        if not stem.endswith((".", "?", "!")):
            stem += "."
        stem = f"{stem} {suffix}"

    return stem, method


def variation_similarity(original: str, variation: str) -> float:
    """How much meaning survived the rewrite. High is good -- it means the
    variation still asks the same thing."""
    docs = [tokenize(original), tokenize(variation)]
    idf = inverse_document_frequencies(docs)
    return cosine_similarity(tfidf_vector(docs[0], idf), tfidf_vector(docs[1], idf))


def make_engine(seed: int, duplicate_threshold: float) -> SynthesisEngine:
    return SynthesisEngine(seed=seed, duplicate_threshold=duplicate_threshold)


def candidates_from_questions(
    rows: Iterable[tuple[Any, str]],
) -> list[Candidate]:
    """Build candidates from (Question, decrypted_text) pairs."""
    out = []
    for question, text in rows:
        out.append(
            Candidate(
                question_id=question.id,
                question_uid=question.question_uid,
                text=text,
                subject=question.subject,
                topic=question.topic,
                difficulty=question.difficulty.value,
                question_type=question.question_type.value,
                marks=question.marks,
                creator_uid=question.creator.user_uid,
            )
        )
    return out
