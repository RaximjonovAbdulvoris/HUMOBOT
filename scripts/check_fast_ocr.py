"""Measure actual local Tesseract execution using synthetic data, not private documents."""
import asyncio
from io import BytesIO
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.fast_ocr import engine_info, image_view, recognize, parse_fields


async def check():
    from PIL import Image, ImageDraw, ImageFont
    binary, languages = await engine_info()
    image = Image.new('RGB', (1600, 650), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=52)
    for index, text in enumerate(('3. TEST CITY 01.02.1990', '4b. 01.02.2030',
                                  '4d. 12345678901234', '5. AB1234567')):
        draw.text((60, 60 + index * 130), text, fill='black', font=font)
    buffer = BytesIO()
    image.save(buffer, 'PNG')
    started = time.monotonic()
    prepared, width, height = image_view(buffer.getvalue())
    words = await recognize(binary, languages, prepared)
    result = parse_fields(words, 'license_front', width, height)
    expected = dict(pinfl='12345678901234', birth_date='01.02.1990', birth_place='TEST CITY',
                    license_expiry='01.02.2030', license_number='AB1234567')
    if any(result.get(key) != value for key, value in expected.items()):
        raise ValueError('Synthetic labelled fields did not all match')
    print(f'Fast OCR: five synthetic fields verified in {time.monotonic() - started:.2f}s. '
          f'Languages: {languages}. Real document accuracy must still be checked.', flush=True)


if __name__ == '__main__':
    try:
        asyncio.run(check())
    except Exception as error:
        print(f'Fast OCR check failed ({type(error).__name__}); check engine/language installation.', flush=True)
        raise SystemExit(1)
