"""resume-ats -- score a resume against a job description the way an ATS would.

    from resume_ats import score_text
    report = score_text(resume_text, job_description_text)
    print(report.total, report.band)
"""

from __future__ import annotations

__version__ = "1.0.0"

from .extract import Document, ExtractionError, extract, from_string
from .jd import JobDescription, parse as parse_job_description
from .resume import Resume, parse as parse_resume
from .score import ScoreReport, score

__all__ = [
    "__version__",
    "Document",
    "ExtractionError",
    "JobDescription",
    "Resume",
    "ScoreReport",
    "extract",
    "from_string",
    "parse_job_description",
    "parse_resume",
    "score",
    "score_text",
    "score_files",
]


def score_text(resume_text: str, jd_text: str) -> ScoreReport:
    """Score raw resume text against raw job-description text."""
    return score(from_string(resume_text), parse_job_description(jd_text))


def score_files(resume_path: str, jd_path: str) -> ScoreReport:
    """Score a resume file against a job-description file."""
    return score(extract(resume_path), parse_job_description(extract(jd_path).text))
