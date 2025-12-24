from pathlib import Path
from dotenv import load_dotenv

def load_repo_env(*, override: bool = True) -> Path:
    """
    Loads .env from repo root reliably from any script location.
    Repo root assumed to be parent of /scripts.
    """
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=env_path, override=override)
    return env_path
