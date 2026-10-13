import os

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

CHANNEL = os.environ.get("CHANNEL", "@WB_HUMO_TAXI")

DRIVER_GROUPS = [
    os.environ["DRIVER_GROUP_1"],
    os.environ["DRIVER_GROUP_2"],
]

BRAND_GROUP = os.environ["BRAND_GROUP"]

ARCHIVE_GROUP = os.environ.get("ARCHIVE_GROUP", "")

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def template_path(name: str) -> str | None:
    for ext in ("jpg", "jpeg", "png"):
        p = os.path.join(TEMPLATES_DIR, f"{name}.{ext}")
        if os.path.exists(p):
            return p
    return None
