"""وفرة 888 — Flask application factory."""
import os
from pathlib import Path

from flask import Flask

from . import db as db_module
from .config import Config


def _load_dotenv_if_present(root: Path) -> None:
    """Tiny manual .env loader (no external dependency needed)."""
    env_path = root / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def create_app(config_object: type[Config] | None = None) -> Flask:
    root = Path(__file__).resolve().parent.parent
    _load_dotenv_if_present(root)

    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
    )
    app.config.from_object(config_object or Config)

    db_module.init_app(app)

    from .routes import register_blueprints

    register_blueprints(app)

    @app.context_processor
    def inject_globals():
        from .constitution import VISION_SHORT

        return {"vision_short": VISION_SHORT}

    return app
