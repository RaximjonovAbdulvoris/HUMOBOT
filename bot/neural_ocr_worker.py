"""Isolated local OCR worker. Images arrive in RAM; no network or document files."""
import asyncio
import base64
from io import BytesIO
import json
import re
import sys

from PIL import Image, ImageOps
from bot.document_ocr import FIELDS, normalize, guard_identifiers
from bot.fast_ocr import Word, DATE, SERIAL, recognize


def fields_from_rows(rows, source, width, height):
    values = {field: set() for field in FIELDS}
    def add(field, text):
        value = normalize({field: text})[field]
        if value:
            values[field].add(value)
    for word in rows:
        text = word.text.strip()
        if word.confidence < 90:
            continue
        if source.startswith(('passport_', 'license_')):
            for match in re.finditer(r'(?<![0-9])([0-9]{14})(?![0-9])', text):
                add('pinfl', match[1])
        if source == 'license_front':
            serial = re.fullmatch(r'5[.)]?\s*' + SERIAL, text)
            if serial:
                add('license_number', serial[1])
            birth = re.fullmatch(r'3[.)]?\s*(.+?)\s*' + DATE, text)
            if birth:
                add('birth_date', '.'.join(birth.groups()[1:]))
                add('birth_place', birth[1])
            expiry = re.search(r'4\s*[bвб][.)]?\s*' + DATE, text, re.I)
            if expiry:
                add('license_expiry', '.'.join(expiry.groups()))
        if source.startswith('tech_') and word.left >= .65 * width and word.top < .75 * height:
            serial = re.fullmatch(SERIAL, text.upper())
            if serial:
                add('vehicle_registration', serial[1])
    if source == 'license_front':
        # On the numbered licence, 4b (expiry) is directly right of 4a.
        # Require the 4a anchor and one intact date on the same text baseline.
        anchors = [w for w in rows if w.confidence >= 90 and re.fullmatch(r'4a[.)]?\s*' + DATE, w.text, re.I)]
        for anchor in anchors:
            for word in rows:
                if word.left <= anchor.left + anchor.width or word.confidence < 90:
                    continue
                if abs(word.top + word.height / 2 - anchor.top - anchor.height / 2) > max(anchor.height, word.height) * .5:
                    continue
                dates = list(re.finditer(DATE, word.text))
                if len(dates) == 1:
                    add('license_expiry', '.'.join(dates[0].groups()))
    return {key: next(iter(items)) if len(items) == 1 else None for key, items in values.items()}


def read_document(engine, raw, source):
    import numpy as np
    with Image.open(BytesIO(raw)) as opened:
        if opened.width * opened.height > 30_000_000:
            raise ValueError('Image too large')
        image = ImageOps.exif_transpose(opened).convert('RGB')
    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    result, _ = engine(np.array(ImageOps.invert(image))[:, :, ::-1].copy())
    words = []
    for box, text, confidence in result or []:
        left, top = min(p[0] for p in box), min(p[1] for p in box)
        words.append(Word(text, confidence * 100, left, top,
            max(p[0] for p in box) - left, max(p[1] for p in box) - top))
    values = fields_from_rows(words, source, image.width, image.height)
    if source == 'license_front' and not values['birth_date']:
        # Use the detected field-3 row, not fixed coordinates in a photograph.
        # Re-read only its date end. Never replace uncertain letters with digits.
        anchors = [w for w in words if w.confidence >= 75 and re.match(r'^3[.)]', w.text)]
        for word in anchors[:1]:
            box = (max(0, int(word.left + .72 * word.width) - 5), max(0, int(word.top) - 5),
                   min(image.width, int(word.left + word.width) + 6), min(image.height, int(word.top + word.height) + 5))
            region = image.crop(box)
            region = region.resize((region.width * 3, region.height * 3), Image.Resampling.LANCZOS)
            region = ImageOps.expand(region, 15, 'white')
            buffer = BytesIO()
            region.save(buffer, 'PNG')
            try:
                tokens = asyncio.run(asyncio.wait_for(recognize('/usr/bin/tesseract', 'eng', buffer.getvalue(), psm=7), 1.5))
                dates = {'.'.join(match.groups()) for token in tokens if token.confidence >= 80
                         for match in re.finditer(DATE, token.text)}
                if len(dates) == 1:
                    values['birth_date'] = normalize({'birth_date': dates.pop()})['birth_date']
            except (TimeoutError, OSError, RuntimeError):
                pass
    return guard_identifiers(values)[0]


def main():
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
    if '--check' in sys.argv:
        print(json.dumps({'ready': True}), flush=True)
        return
    payload = json.loads(sys.stdin.buffer.read(45_000_000))
    for item in payload:
        source = item['source']
        try:
            raw = base64.b64decode(item['image'], validate=True)
            if len(raw) > 5_000_000:
                raise ValueError('Image too large')
            values = read_document(engine, raw, source)
            print(json.dumps({'source': source, 'values': values}), flush=True)
        except Exception as error:
            print(json.dumps({'source': source, 'error': type(error).__name__}), flush=True)


if __name__ == '__main__':
    main()
