"""Tunable thresholds and limits. Change values here only."""

RUBRIC_VERSION = "v1"

# Recommendation thresholds (weighted score, 0-100)
SHORTLIST_MIN = 70.0
HOLD_MIN = 55.0

# A resume with fewer than this many evidenced requirements is held, not rejected
MIN_EVIDENCED_REQUIREMENTS = 2

# Upload limits (Vercel request bodies are capped near 4.5 MB)
MAX_FILE_BYTES = 4 * 1024 * 1024
MIN_TEXT_CHARS = 200          # below this, send the PDF to Gemini as an image/file
MAX_TEXT_CHARS = 30000        # cost control
EVIDENCE_MAX_CHARS = 300

# Gemini
GEMINI_DEFAULT_MODEL = "gemini-3.8-flash"
GEMINI_TIMEOUT_S = 45
GEMINI_RETRIES = 2
GEMINI_BACKOFF_S = (1, 3)
GEMINI_TEMPERATURE = 0.1
GEMINI_HEALTH_CACHE_S = 60

# Storage
BUCKET = "resumes"
SIGNED_URL_TTL_S = 600

# Best-effort per-IP rate limit on /api/upload
UPLOAD_RATE_LIMIT_PER_MIN = 30

# Mumbai and its metropolitan region (lower-case substrings)
MUMBAI_REGION = (
    "mumbai", "bombay", "navi mumbai", "thane", "kalyan", "panvel", "vasai", "virar",
)

NOT_VERIFIABLE = "No verifiable quote"
NO_EVIDENCE = "No evidence found"
