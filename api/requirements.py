"""Roles, requirements, weights and rubric anchors. Edit here to change scoring.

After changing weights or thresholds, call POST /api/recompute to re-score stored
candidates without calling Gemini.

kind: "model"    -> scored 0-5 by Gemini from the resume
      "computed" -> scored in Python (experience years, location)
Weights per role must total exactly 100 (asserted in tests).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Req:
    id: str
    label: str
    short: str
    weight: int
    anchors: tuple  # (score 0, scores 1-2, scores 3-4, score 5)
    kind: str = "model"
    core: bool = False


PM_REQS = [
    Req("PM1", "First-PM / 0-to-1 builder who works without structure", "0-to-1", 18, (
        "only mature-company maintenance roles, no building from scratch",
        "startup or small company but joined an established product",
        "built a feature area or process in a young company",
        "first or only PM, founding team, or launched a product from zero in an early-stage company; built process where none existed"), core=True),
    Req("PM2", "Ships, kills and learns in short cycles", "Shipping", 16, (
        "duties listed, no shipped outcomes",
        "some launches named, no outcomes or cycle time",
        "several shipped features with outcomes and some iteration shown",
        "ships repeatedly in short cycles with metrics and mentions killed or pivoted work and the learning"), core=True),
    Req("PM3", "Outcome focus: features customers adopt unprompted", "Adoption", 10, (
        "no usage or outcome information",
        "launches mentioned without usage results",
        "at least one feature with an adoption, usage or retention metric",
        "multiple features with quantified organic adoption or retention outcomes")),
    Req("PM4", "Roadmap ownership and clear prioritisation", "Roadmap", 14, (
        "no roadmap or priority-setting mentioned",
        "contributed to a roadmap; decisions made by others",
        "owned a roadmap or backlog and sequenced work with engineering",
        "owned the roadmap end to end with an explicit prioritisation approach and stated trade-offs"), core=True),
    Req("PM5", "Works directly with engineering on what, order and why", "Eng partner", 8, (
        "no engineering collaboration shown",
        "worked with engineers in general terms",
        "wrote specs or PRDs and ran sprint planning",
        "defined what to build, in what order and why, with a multi-sprint planning horizon and delivery outcomes")),
    Req("PM6", "Curiosity about ground-level operations; logistics advantage", "Ops curiosity", 14, (
        "no operational or logistics exposure",
        "adjacent B2B SaaS only, no ops-heavy users",
        "ops-heavy products (workflow, field ops, marketplaces, ERP) or ops-adjacent roles",
        "logistics, freight or supply-chain product work, or time spent with operations teams where the work happens"), core=True),
    Req("PM7", "Customer discovery", "Discovery", 8, (
        "no customer contact mentioned",
        "feedback or surveys only",
        "regular user interviews or customer calls that influenced decisions",
        "structured discovery with named insights that changed what was built")),
    Req("PM8", "Builds PM rhythms: prioritisation, measurement, communication", "Rhythms", 7, (
        "no process or metrics mentioned",
        "followed existing process",
        "introduced some process, metrics or documentation",
        "created PM practices from scratch (how to prioritise, track whether something worked, communicate decisions)")),
    Req("PM9", "PM experience 2-4 years", "Experience", 3, ("", "", "", ""), kind="computed"),
    Req("PM10", "Mumbai-based or willing to relocate; in-office", "Location", 2, ("", "", "", ""), kind="computed"),
]

SPM_REQS = [
    Req("SP1", "Owned a product area without senior PMs above", "Ownership", 15, (
        "individual contributor on someone else's product",
        "led features inside an area owned by a senior PM",
        "owned a product area with some autonomy but limited scope",
        "sole or lead PM owning an area end to end with no senior PM above them (reported to a CPO or founder)"), core=True),
    Req("SP2", "Platform, integration or complex-technical-environment products", "Platform", 16, (
        "consumer or simple standalone product only",
        "used APIs or integrations as a feature, not as the product",
        "worked on integrations, APIs or data products with technical depth",
        "owned a platform, integration layer or product that works inside complex systems (ERP, partner or carrier APIs, data flows)"), core=True),
    Req("SP3", "Makes calls in ambiguity and lives with the consequences; no committee", "Judgement", 12, (
        "decisions not visible",
        "decisions described but made by committee or others",
        "clear calls with some reasoning and outcomes",
        "owned hard calls with stated trade-offs and consequences, including reversals or mistakes acknowledged"), core=True),
    Req("SP4", "Build vs configure vs stay-away judgement", "Build/config", 8, (
        "no such decisions shown",
        "mentions build-or-buy in passing",
        "made build, buy or configure decisions with reasons",
        "clear point of view on what to build, configure or refuse, with examples of scope refused and why")),
    Req("SP5", "Shipped integration or platform work with commercial impact", "Commercial impact", 10, (
        "no integration or platform outcomes",
        "integrations shipped without business results",
        "integration work tied to customer or revenue results",
        "integration or platform work that opened a new customer segment, unblocked a stalled deal or measurably moved revenue or retention"), core=True),
    Req("SP6", "Early-stage experience; rules not yet written", "Early-stage", 8, (
        "large mature companies only",
        "short stint or late-stage startup",
        "seed to Series B product role",
        "multiple early-stage roles or founder experience in environments without defined rules")),
    Req("SP7", "Logistics, supply chain or operations-heavy domain", "Domain", 8, (
        "no logistics or operations exposure",
        "adjacent B2B or ops-light domain",
        "ops-heavy domain (manufacturing, fulfilment, ERP)",
        "logistics, freight, 3PL or supply-chain product experience")),
    Req("SP8", "Cross-functional alignment; roadmap sales, engineering and ops all trust", "Alignment", 8, (
        "no cross-team work mentioned",
        "worked with other teams on delivery",
        "roadmap aligned across engineering, sales or customer success",
        "aligned sales, engineering and ops on integration or roadmap decisions with a stable roadmap and outcomes")),
    Req("SP9", "Reliability and data-quality standards", "Reliability", 4, (
        "no mention",
        "quality mentioned in passing",
        "worked on reliability, accuracy or data-quality metrics",
        "drove SLAs, uptime or data-quality standards that customers depend on")),
    Req("SP10", "Builds the PM function: practices, frameworks, ways of working", "PM function", 7, (
        "no evidence",
        "followed existing process",
        "introduced frameworks or mentored PMs",
        "defined PM practices, hired or led PMs, set decision frameworks and standards")),
    Req("SP11", "PM experience 5-8 years", "Experience", 2, ("", "", "", ""), kind="computed"),
    Req("SP12", "Mumbai-based or willing to relocate; in-office", "Location", 2, ("", "", "", ""), kind="computed"),
]

PM_CONTEXT = """Kargo - Mumbai - Series A. Product Manager. Full-time, in-office, Mumbai. Reports to the Founder.
Kargo builds software for mid-sized freight forwarders and 3PLs: shipment tracking, documentation and carrier coordination, replacing spreadsheets and WhatsApp chains. Series A, 40 people scaling to 70.
Why the role exists: one product, a growing customer base and no PM function yet. The person will be the first PM at Kargo, focused on the core operations platform.
Owns: the product roadmap for the core operations platform; customer discovery; working directly with engineering on what gets built, in what order and why; the rhythms a PM function needs (how to prioritise, track whether something worked, communicate decisions).
Success at 6 months: shipped at least two features customers use unprompted; can state the three most important things to build next and why; engineering knows what it is building three sprints out; has spent time inside freight forwarding operations.
Looking for: 2-4 years of PM experience, ideally at a company building for the first time rather than maintaining; comfort operating without structure; evidence of shipping, killing and learning in short cycles; genuine curiosity about ground-level operations; Mumbai-based or willing to relocate (in-office)."""

SPM_CONTEXT = """Kargo - Mumbai - Series A. Senior Product Manager. Full-time, in-office, Mumbai. Reports to the Founder.
Software for mid-sized freight forwarders and 3PLs. The product is growing more complex: more carrier integrations, customer-specific configurations, more data flowing between Kargo and customer systems. This person owns the harder parts of the platform and will be the most senior PM.
Owns: the integration and data layer (carrier systems, port portals, ERP environments, freight management tools); hard architectural product calls (what to build, configure, or stay away from); reliability and data-quality standards; working across sales, engineering and customer operations; defining the practices and decision frameworks of the PM function.
Success at 6 months: an integration roadmap that engineering, sales and the founder trust and that is stable; at least one major integration shipped that opened a new customer segment or unblocked a stalled deal; a defensible build vs configure vs avoid point of view; clearer standards for good PM work.
Looking for: 5-8 years of PM experience with clear evidence of owning a product area without senior PMs above; platform, integration or complex-environment products; proven ability to make calls in ambiguity (no committee); early-stage experience; familiarity with operations-heavy industries (logistics, supply chain) as a genuine advantage; Mumbai-based or willing to relocate (in-office)."""

ROLES = {
    "PM": {"code": "PM", "name": "Product Manager", "short": "PM", "context": PM_CONTEXT, "requirements": PM_REQS,
           "experience_id": "PM9", "location_id": "PM10"},
    "SPM": {"code": "SPM", "name": "Senior Product Manager", "short": "Sr PM", "context": SPM_CONTEXT, "requirements": SPM_REQS,
            "experience_id": "SP11", "location_id": "SP12"},
}


def get_role(code: str) -> dict:
    if code not in ROLES:
        raise KeyError(code)
    return ROLES[code]


def model_requirements(code: str):
    return [r for r in ROLES[code]["requirements"] if r.kind == "model"]
