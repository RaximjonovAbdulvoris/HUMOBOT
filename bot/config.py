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
    from bot.template_cards import generated_directory
    # Original sample images installed on the server take precedence over the
    # synthetic cards. The four-sided car sample is a single legacy image.
    original_names = (name, 'car_sides') if name.startswith('car_') else (name,)
    for original_name in original_names:
        for ext in ('jpg', 'jpeg', 'png', 'webp'):
            path = os.path.join(TEMPLATES_DIR, f'{original_name}.{ext}')
            if os.path.isfile(path):
                return path
    generated = generated_directory() / f"{name}.png"
    if generated.exists():
        return str(generated)
    return None
