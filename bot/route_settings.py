"""Non-secret, local routing overrides shared by the bot and its terminal CLI."""
import json
import os
import re
import tempfile
from pathlib import Path

TASHKENT_KEYS = {
    "driver1": "TASHKENT_DRIVER_GROUP_1",
    "driver2": "TASHKENT_DRIVER_GROUP_2",
    "brand": "TASHKENT_BRAND_GROUP",
    "spectre": "TASHKENT_SPECTRE_GROUP",
    "archive": "TASHKENT_ARCHIVE_GROUP",
}

NAMANGAN_KEYS = {
    "spectre": "NAMANGAN_SPECTRE_GROUP",
}

ROUTE_KEYS = {*TASHKENT_KEYS.values(), *NAMANGAN_KEYS.values()}


def settings_path() -> Path:
    directory = os.environ.get("PERSIST_DIR") or str(Path(__file__).resolve().parent.parent)
    return Path(directory) / "bot_routes.json"


def validate(key: str, value: str) -> str:
    if key not in ROUTE_KEYS:
        raise ValueError("Noma'lum guruh sozlamasi.")
    if not isinstance(value, str):
        raise ValueError(f"{key}: ID matn ko'rinishida bo'lishi kerak.")
    value = value.strip()
    if value == "" and key == TASHKENT_KEYS["driver2"]:
        return value
    if not re.fullmatch(r"-[1-9][0-9]*", value):
        raise ValueError(f"{key}: manfiy raqamli guruh ID kiriting, masalan -1001234567890.")
    return value


def read_settings() -> dict[str, str]:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path.name} o'qilmadi; faylni tekshiring.") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: JSON obyekt bo'lishi kerak.")
    return {key: validate(key, value) for key, value in data.items()}


def destination(key: str) -> str:
    """Explicit terminal settings override env; omitted keys still use env."""
    data = read_settings()
    return data[key] if key in data else os.environ.get(key, "").strip()


def save_settings(updates: dict[str, str]) -> None:
    data = read_settings()
    data.update({key: validate(key, value) for key, value in updates.items()})
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".bot_routes-",
            suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)