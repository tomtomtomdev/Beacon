"""HeuristicClassifier: title-driven category (multi-label) + level from title/years.

Table-driven — a spot-check miss becomes a new row here, never a branch in the classifier.
The precision cases (desc-ignored, ai-native-not-aiml, no-ml-in-html) lock in the slice-3
decision to read category from the title only, since body copy is boilerplate-contaminated.
"""

from datetime import UTC, datetime

import pytest

from beacon.adapters.classify.heuristic import HeuristicClassifier
from beacon.domain.classification import Category, Level
from beacon.domain.job import NormalizedJob


def _job(title: str, description: str = "") -> NormalizedJob:
    return NormalizedJob(
        source_id="greenhouse:test",
        external_id="1",
        title=title,
        url="https://example.com/1",
        description=description,
        location_raw="Remote",
        country=None,
        city=None,
        posted_at=datetime(2026, 7, 1, tzinfo=UTC),
        content_hash="hash",
    )


# Category is read from the TITLE only (body copy is boilerplate-contaminated — see
# heuristic.py). Every expected category must therefore be derivable from the title.
CATEGORY_CASES = [
    ("ios-title", "Senior iOS Engineer", "Ship features to users", {Category.IOS}),
    ("android-title", "Android Developer", "Join the mobile team", {Category.ANDROID}),
    ("android-aosp", "AOSP Engineer", "Platform work", {Category.ANDROID}),  # real Adyen title
    ("flutter-title", "Flutter Engineer", "Cross-platform apps", {Category.FLUTTER}),
    ("aiml-ml-engineer", "ML Engineer", "Train and serve models", {Category.AI_ML}),
    ("aiml-ai-engineer", "AI Engineer", "Build agents", {Category.AI_ML}),
    ("backend-title", "Backend Engineer", "Own our services", {Category.BACKEND}),
    # Spot-check misses (real Adyen/Agoda titles): space-form "Back End", Java, SRE, infra.
    ("backend-space", "Back End Software Engineer", "", {Category.BACKEND}),
    ("backend-java", "Software Engineer (Java)", "", {Category.BACKEND}),
    ("infra-sre", "Senior Site Reliability Engineer", "", {Category.INFRA}),
    ("infra-infrastructure", "Staff Infrastructure Engineer", "", {Category.INFRA}),
    # Coverage misses found in the 2026-08-18 corpus spot-check (real Databricks/Agoda/
    # OpenAI/Stripe titles): named backend specialisms the table did not carry.
    ("backend-distributed", "Software Engineer, Distributed Systems", "", {Category.BACKEND}),
    ("infra-networking", "Senior Software Engineer - Networking", "", {Category.INFRA}),
    (
        "backend-database",
        "Senior Software Engineer - Database Engine Internals",
        "",
        {Category.BACKEND},
    ),
    ("backend-kernel", "TPU Kernel Engineer", "", {Category.BACKEND}),
    ("backend-python", "Agentic Python Engineer", "", {Category.BACKEND}),
    ("infra-platform-eng", "Senior Data Platform Engineer", "", {Category.INFRA}),
    ("aiml-applied-ai-engineer", "Senior Applied AI Engineer", "", {Category.AI_ML}),
    ("aiml-applied-ai-scientist", "Staff Applied AI Scientist", "", {Category.AI_ML}),
    ("frontend-title", "Frontend Engineer", "Build the web UI", {Category.FRONTEND}),
    ("frontend-space", "Lead Software Engineer - Front End", "", {Category.FRONTEND}),
    ("frontend-typescript", "Principal Engineer (TypeScript)", "", {Category.FRONTEND}),
    ("frontend-nextjs", "Manager of the Technical Staff - Next.js", "", {Category.FRONTEND}),
    ("frontend-ui-engineer", "UI Engineer II", "", {Category.FRONTEND}),
    ("fullstack-title", "Full-Stack Engineer", "End to end", {Category.FULLSTACK}),
    ("multi-ios-aiml", "iOS ML Engineer", "On-device models", {Category.IOS, Category.AI_ML}),
    (
        "multi-ios-android",
        "iOS and Android Engineer",
        "Both platforms",
        {Category.IOS, Category.ANDROID},
    ),
    # "ml" must fire on the word, never inside "html". (Slice 23: a developer is now software.)
    ("no-ml-in-html", "HTML Email Developer", "Hand-write HTML", {Category.SOFTWARE}),
    # Precision: description tech NEVER contaminates category — the title is a sales role.
    ("desc-ignored", "Account Executive", "We build LLMs with PyTorch and Django", set()),
    # Bare "ai" was removed so AI-company sales titles don't read as ML roles.
    ("ai-native-not-aiml", "Account Executive, AI Native", "Sell to AI startups", set()),
    # Honest empty: nothing matched (LLM fallback cleans residue in slice 9).
    ("empty", "Project Manager", "Own the roadmap and stakeholders", set()),
    # Precision guards for candidates REJECTED in the 2026-08-18 spot-check: these tokens
    # read as tech but head mostly go-to-market titles in the corpus, so the table carries
    # the narrow phrase ("platform engineer") and never the bare word ("platform").
    ("bare-platform-not-backend", "Cloud Partner Enablement Lead", "", set()),
    ("bare-aws-not-backend", "AWS Specialist Seller, Strategic Pursuits", "", set()),
    ("bare-web-not-frontend", "Manager, Web Engineering", "", set()),
    # A plain SWE title names no specialism. Until slice 23 that was honest residue for the
    # LLM tier; since 2026-10-10 it is the `software` fallback — every engineering role is in
    # scope, and 721 open postings were invisible to the category filter for want of it.
    ("plain-swe-is-software", "Senior Software Engineer", "", {Category.SOFTWARE}),
    # "Applied AI" is an org/team name at Anthropic and OpenAI, so it heads architect, GTM
    # and ops titles too — the same trap bare "ai" was removed for. Only the role-form
    # phrases ("applied ai engineer"/"scientist") are in the table.
    # (Slice 23: still not ai-ml — an Applied AI Architect is customer-facing `solutions`.)
    (
        "applied-ai-architect-not-aiml",
        "Applied AI Architect, Commercial",
        "",
        {Category.SOLUTIONS},
    ),
    ("applied-ai-ops-not-aiml", "Strategy & Operations, Applied AI - AMER", "", set()),
    # 2026-08-26 spot check: SWIFT the interbank network is not Swift the language. The
    # vocabulary's homograph guard drops it in a payments context with no iOS sibling
    # keyword, and keeps it when one is there.
    # (Slice 23: still not ios — it is now `solutions`, via "integration engineer".)
    (
        "swift-the-payment-network-not-ios",
        "SWIFT Payments Integration Engineer",
        "",
        {Category.SOLUTIONS},
    ),
    ("swift-in-an-ios-payments-title", "iOS Engineer, Payments (Swift)", "", {Category.IOS}),
    # --- Slice 23 (2026-10-10): all of engineering. Real titles from the open '' residue. ---
    # Guards first: non-engineering stays honestly empty — the widening must not reach it.
    ("guard-counsel", "Corporate Counsel", "", set()),
    ("guard-ae", "Account Executive Enterprise EMEA", "", set()),
    ("guard-preschool-teacher", "Förskollärare till Parkdala förskola", "", set()),
    ("guard-partner-dev", "Partner Development Manager, Strategic Payment Partnerships", "", set()),
    ("guard-designer", "Product Designer", "", set()),
    ("guard-training", "Head of Technical Training", "", set()),
    ("guard-finance-data-ai", "Senior Finance Specialist (Data & AI)", "", set()),
    ("guard-business-developer", "Business Developer, Nordics", "", set()),
    ("guard-affarsutvecklare", "Affärsutvecklare", "", set()),
    ("guard-abuse", "Abuse Investigator", "", set()),
    # software — the fallback: fires only when no specific category does.
    ("software-plain", "Software Engineer, Payments and Risk", "", {Category.SOFTWARE}),
    ("software-staff", "Staff Software Engineer, RL Environments", "", {Category.SOFTWARE}),
    ("software-developer", "Software Developer", "", {Category.SOFTWARE}),
    ("software-swe-fellow", "SWE Fellow - Human Frontier Collective (US)", "", {Category.SOFTWARE}),
    ("software-yields-to-ios", "Senior Software Engineer, iOS", "", {Category.IOS}),
    ("software-mjukvaruutvecklare", "Mjukvaruutvecklare", "", {Category.SOFTWARE}),
    ("software-utvecklare", "Utvecklare till vårt team i Malmö", "", {Category.SOFTWARE}),
    ("software-systemutvecklare-java", "Systemutvecklare Java", "", {Category.BACKEND}),
    # Symbol-edged stacks: aliased before matching, since \b cannot sit against "+" or "#".
    ("backend-dotnet", "Senior .NET Software Engineer", "", {Category.BACKEND}),
    ("backend-csharp", "C# Engineer", "", {Category.BACKEND}),
    ("backend-cpp", "C++ Developer, Low Latency", "", {Category.BACKEND}),
    # data
    ("data-engineer", "Data Engineer", "", {Category.DATA}),
    ("data-analytics-engineer", "Senior Analytics Engineer", "", {Category.DATA}),
    ("data-scientist", "Data Scientist, Growth", "", {Category.DATA}),
    # security
    ("security-ops", "Security Operations Engineer II", "", {Category.SECURITY}),
    ("security-appsec", "Senior Application Security Engineer", "", {Category.SECURITY}),
    ("security-detection", "Detection Engineer", "", {Category.SECURITY}),
    # embedded
    ("embedded-software", "Embedded Software Engineer", "", {Category.EMBEDDED}),
    ("embedded-firmware", "Firmware Engineer", "", {Category.EMBEDDED}),
    ("embedded-fpga", "FPGA Design Engineer", "", {Category.EMBEDDED}),
    # qa
    ("qa-engineer", "QA Engineer", "", {Category.QA}),
    ("qa-sdet", "SDET II", "", {Category.QA}),
    ("qa-automation", "Senior Test Automation Engineer", "", {Category.QA}),
    # eng-mgmt
    (
        "eng-mgmt-em",
        "Engineering Manager, Payments (AirCover Insurance Platform)",
        "",
        {Category.ENG_MGMT},
    ),
    ("eng-mgmt-head", "Head of Engineering", "", {Category.ENG_MGMT}),
    ("eng-mgmt-vp", "VP of Engineering", "", {Category.ENG_MGMT}),
    ("eng-mgmt-ios", "Engineering Manager, iOS", "", {Category.ENG_MGMT, Category.IOS}),
    # solutions — engineering-adjacent, kept separate so it can be filtered out.
    ("solutions-se", "Sr. Solutions Engineer", "", {Category.SOLUTIONS}),
    (
        "solutions-fde",
        "Forward Deployed Engineer, Agentic Platform (Europe)",
        "",
        {Category.SOLUTIONS},
    ),
    ("solutions-it-support", "IT Support Engineer, Executive Support", "", {Category.SOLUTIONS}),
    ("solutions-devrel", "Developer Advocate", "", {Category.SOLUTIONS}),
    # 2026-10-10 dry run over the live residue: misfires the first table made...
    (
        "guard-tpm-developer-experience",
        "Senior Manager, Technical Program Management (Data, Reliability & Developer Experience)",
        "",
        set(),
    ),
    ("guard-pm-data-engineering", "Sr. Product Manager, Data Engineering", "", set()),
    ("guard-pm-robotics", "Senior Product Manager, Robotics Operations", "", set()),
    (
        "guard-compliance-qa",
        "Senior Manager, Global Quality Assurance (AML/KYC/TM/Fraud Risk)",
        "",
        set(),
    ),
    ("guard-qa-evaluator", "AI Trainer Image QA Evaluator", "", set()),
    # ...and engineering families it missed.
    ("software-product-engineer", "Senior / Staff Product Engineer", "", {Category.SOFTWARE}),
    ("software-mobile-engineer", "Senior Mobile Engineer", "", {Category.SOFTWARE}),
    ("software-staff-engineer", "Staff Engineer - Business Spend", "", {Category.SOFTWARE}),
    (
        "aiml-research-engineer",
        "Research Engineer, Production Model Post-Training",
        "",
        {Category.AI_ML},
    ),
    ("aiml-mle", "Research MLE (Training Optimization)", "", {Category.AI_ML}),
    ("infra-cloud-engineer", "Senior Cloud Engineer, V&V Platform", "", {Category.INFRA}),
    ("solutions-field", "Field Engineer, Data Engine", "", {Category.SOLUTIONS}),
    ("solutions-implementation", "Consultant Implementation Engineer", "", {Category.SOLUTIONS}),
    ("solutions-ps", "Professional Services Engineer II - West", "", {Category.SOLUTIONS}),
    ("solutions-integration", "Integration Engineer, Metronome", "", {Category.SOLUTIONS}),
    (
        "solutions-presales-em",
        "Pre-sales Engineering Manager (Retail & CPG)",
        "",
        {Category.ENG_MGMT, Category.SOLUTIONS},
    ),
    ("eng-mgmt-manager-comma", "Sr. Manager, Engineering - Search", "", {Category.ENG_MGMT}),
    ("eng-mgmt-lead-manager", "Engineering Lead/Manager, Risk", "", {Category.ENG_MGMT}),
    ("eng-mgmt-leader", "Engineering Leader -  Payments APAC", "", {Category.ENG_MGMT}),
    (
        "eng-mgmt-director-swe",
        "Director, Software Engineering (AI Workflows & Ecosystem)",
        "",
        {Category.ENG_MGMT},
    ),
    ("qa-quality-engineer", "Staff Quality Engineer", "", {Category.QA}),
    ("qa-sqa", "Software Quality Assurance Engineer", "", {Category.QA}),
    ("qa-lead", "Lead QA Engineer", "", {Category.QA}),
    ("security-threat-intel", "Senior Threat Intelligence Engineer", "", {Category.SECURITY}),
    ("embedded-silicon", "Silicon Engineer", "", {Category.EMBEDDED}),
    ("embedded-signal-integrity", "Signal Integrity Engineer", "", {Category.EMBEDDED}),
    # Second dry run: a distributor's sales rep is not pre-sales engineering...
    ("guard-presales-rep", "Pre-Sales (FMCG - Ninja Mart) - Seremban", "", set()),
    # ...and the clusters still left in the residue.
    (
        "solutions-sa-plural",
        "Manager, Delivery Solutions Architects - Toronto, ON",
        "",
        {Category.SOLUTIONS},
    ),
    ("solutions-applied-ai-architects", "Manager, Applied AI Architects", "", {Category.SOLUTIONS}),
    ("solutions-deployment", "Software Deployment Engineer", "", {Category.SOLUTIONS}),
    ("infra-release", "Release Engineer | Consumer Devices", "", {Category.INFRA}),
    ("security-privacy", "Privacy Engineer", "", {Category.SECURITY}),
    ("data-bi-engineer", "Senior Business Intelligence Engineer", "", {Category.DATA}),
    ("eng-mgmt-team-lead", "(RD) Senior Engineering Team Lead", "", {Category.ENG_MGMT}),
    ("software-senior-engineer", "Senior Engineer, Finance Systems", "", {Category.SOFTWARE}),
    ("software-staff-engineers", "Staff Engineers (Elixir)", "", {Category.SOFTWARE}),
    # Slice 24: infra splits out of backend. The six rows above that once read backend
    # (sre, infrastructure, networking, platform, cloud, release) now read infra.
    ("infra-devops", "DevOps Engineer", "", {Category.INFRA}),
    ("infra-kubernetes", "Kubernetes Engineer", "", {Category.INFRA}),
    (
        "infra-systems-engineer",
        "(Infra) Senior Systems Engineer - Contact Center",
        "",
        {Category.INFRA},
    ),
    ("infra-sre-acronym", "SRE, Payments", "", {Category.INFRA}),
    ("infra-network-engineer", "Network Engineer", "", {Category.INFRA}),
    ("infra-reliability", "Reliability Engineer, Storage", "", {Category.INFRA}),
    ("infra-production", "Production Engineer", "", {Category.INFRA}),
    ("infra-build", "Build Engineer, Developer Productivity", "", {Category.INFRA}),
    ("infra-platform-engineering", "Manager, Platform Engineering", "", {Category.INFRA}),
    # Live spot-check misses 2026-10-10 (real Adyen/Agoda titles).
    ("infra-cicd", "Senior CI/CD Engineer", "", {Category.INFRA}),
    ("infra-sysadmin", "Senior System Administrator (Storage Engineer)", "", {Category.INFRA}),
    ("infra-sysadmin-short", "Linux Sysadmin", "", {Category.INFRA}),
    ("data-bi-developer", "Business Intelligence Developer, RTA", "", {Category.DATA}),
    # Backend keeps languages, frameworks, databases and systems internals...
    ("backend-stays-golang", "Golang Engineer", "", {Category.BACKEND}),
    ("backend-stays-distributed", "Distributed Systems Engineer", "", {Category.BACKEND}),
    (
        "backend-operating-systems",
        "Operating Systems Engineer, Linux Kernel",
        "",
        {Category.BACKEND},
    ),
    ("software-systems-engineer", "Principal Software Systems Engineer", "", {Category.SOFTWARE}),
    ("aiml-ai-systems-engineer", "AI Systems Engineer, Codex Agents", "", {Category.AI_ML}),
    ("infra-it-systems", "IT Systems Engineer, Client Platform", "", {Category.INFRA}),
    ("guard-finance-systems-not-infra", "Finance Systems Engineer, Tax", "", set()),
    # ...and a title naming both carries both.
    (
        "backend-and-infra",
        "Backend Engineer, Infrastructure",
        "",
        {Category.BACKEND, Category.INFRA},
    ),
    ("python-sre-is-infra-and-backend", "Python SRE", "", {Category.BACKEND, Category.INFRA}),
]


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [(t, d, e) for _, t, d, e in CATEGORY_CASES],
    ids=[cid for cid, *_ in CATEGORY_CASES],
)
def test_category_classification(title: str, description: str, expected: set[Category]) -> None:
    result = HeuristicClassifier().classify(_job(title, description))

    assert result.categories == frozenset(expected)


LEVEL_CASES = [
    ("senior-title", "Senior iOS Engineer", "", Level.SENIOR),
    ("staff-title", "Staff Software Engineer", "", Level.STAFF),
    ("lead-title", "Lead Backend Engineer", "", Level.LEAD),
    ("principal-title", "Principal Engineer", "", Level.PRINCIPAL),
    ("junior-title", "Junior Developer", "", Level.JUNIOR),
    ("intern-title", "Engineering Intern", "", Level.INTERN),
    ("sr-abbrev", "Sr. Software Engineer", "", Level.SENIOR),
    ("years-to-senior", "Engineer III", "5+ years of experience required", Level.SENIOR),
    ("most-senior-wins", "Senior Staff Engineer", "", Level.STAFF),
    ("bare-unspecified", "Software Engineer", "Join our team", Level.UNSPECIFIED),
]


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [(t, d, e) for _, t, d, e in LEVEL_CASES],
    ids=[cid for cid, *_ in LEVEL_CASES],
)
def test_level_classification(title: str, description: str, expected: Level) -> None:
    result = HeuristicClassifier().classify(_job(title, description))

    assert result.level == expected
