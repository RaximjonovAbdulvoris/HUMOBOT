"""Offline-engine preflight; optional synthetic image test, never uses Telegram."""
import argparse
import asyncio
import base64
from io import BytesIO
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.document_ocr import check_local_engine, local_client, local_model, read_local


async def check(smoke):
    model = local_model()
    async with local_client() as client:
        await check_local_engine(client, model)
        print(f'Local vision model ready: {model}', flush=True)
        if smoke:
            from PIL import Image, ImageDraw, ImageFont
            image = Image.new('RGB', (1400, 300), 'white')
            font = ImageFont.load_default(size=64)
            ImageDraw.Draw(image).text((35, 100), 'PINFL: 12345678901234', font=font, fill='black')
            buffer = BytesIO()
            image.save(buffer, 'JPEG', quality=95)
            started = time.monotonic()
            result = await read_local(client, model,
                [base64.b64encode(buffer.getvalue()).decode('ascii')], ('pinfl',), ('synthetic_test',))
            if result.get('pinfl') != '12345678901234':
                raise ValueError('Synthetic image reading did not match; do not enable OCR yet')
            print(f'Synthetic image read correctly in {time.monotonic() - started:.1f}s. '
                  'Real document accuracy still needs operator verification.', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    try:
        asyncio.run(check(args.smoke))
    except Exception as error:
        print(f'Local OCR check failed ({type(error).__name__}). '
              'Check ollama service, installed model, available RAM and timeout.', flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
