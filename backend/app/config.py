import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = ROOT / "backend" / ".env"
if _ENV_FILE.is_file():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _name, _value = _line.split("=", 1)
            os.environ.setdefault(_name.strip(), _value.strip().strip("\"'"))


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", ROOT / "data"))
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
    )
    llm_model: str = os.getenv("CHATBOT_MODELO", "claude-sonnet-5-5")
    chat_provider: str = os.getenv("CHAT_PROVIDER", "auto").lower()
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    top_k: int = int(os.getenv("TOP_K", "5"))
    min_score: float = float(os.getenv("MIN_SCORE", "0.2"))

    @property
    def inbox(self) -> Path:
        return self.data_dir / "inbox"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def manifest_path(self) -> Path:
        return self.data_dir / "manifest.db"

    def ensure_dirs(self) -> None:
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
