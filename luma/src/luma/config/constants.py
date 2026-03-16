"""Constants."""

# API endpoints
JIKAN_API_BASE = "https://api.jikan.moe/v4"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

# Quality check constants
MIN_SCORE = 1.0
MAX_SCORE = 10.0
MIN_EPISODES = 1
MAX_EPISODES = 2000
MIN_YEAR = 1900

# Matching thresholds
MIN_CONFIDENCE = 0.5
HIGH_CONFIDENCE = 0.9

# File paths
DEFAULT_DB_PATH = "data/anime.db"
DEFAULT_CHECKPOINT_PATH = "data/checkpoint.json"
DEFAULT_OUTPUT_DIR = "output"
