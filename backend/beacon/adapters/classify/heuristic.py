"""HeuristicClassifier — category/level from the job title (+ years from the body).

Implements the Classifier port over the shared domain vocabulary (domain/vocabulary.py);
the sibling LLMClassifier (slice 9) shares the port and upgrades only the empty-category
residue this leaves. The adapter owns the *policy* (which text feeds which extractor); the
word-boundary matching itself is the domain's, reused by the resume matcher (§11).
"""

from beacon.domain.classification import Classification
from beacon.domain.job import NormalizedJob
from beacon.domain.vocabulary import extract_categories, resolve_level


class HeuristicClassifier:
    def classify(self, job: NormalizedJob) -> Classification:
        # Category is read from the TITLE only. Descriptions are marketing-laden — an
        # AI company's every posting says "LLM", a fintech's says "backend" — so matching
        # the body cross-contaminates unrelated roles (proven in the slice-3 spot-check).
        # The title names the role; ambiguous/empty residue is the LLM fallback's job (slice 9).
        # Level reads the explicit token from the title, but years-of-experience (role-specific,
        # not boilerplate) may come from the body.
        level = resolve_level(level_text=job.title, years_text=f"{job.title}\n{job.description}")
        return Classification(categories=extract_categories(job.title), level=level)
