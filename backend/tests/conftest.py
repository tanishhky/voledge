import sys
from pathlib import Path

# Backend modules import each other by bare name (models, bkm_engine, ...),
# so tests need the backend dir itself on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
