from pathlib import Path

ROOT=Path(__file__).resolve().parent
COURSES_DIR=ROOT/'data'/'courses'
LEARNER_DB_URL = f"sqlite:///{(ROOT / 'data' / 'learner.db').as_posix()}"

WEB_DIST_DIR=Path(__file__).resolve().parent/'web'/'dist'