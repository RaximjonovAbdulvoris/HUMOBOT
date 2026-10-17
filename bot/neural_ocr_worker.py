"""Isolated local OCR worker. Images arrive in RAM; no network or document files."""
import base64
from io import BytesIO
import json
import re
import sys

from PIL import Image, ImageOps
from bot.document_ocr import FIELDS, normalize, guard_identifiers
from bot.fast_ocr import Word, DATE, SERIAL


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
        if source.startswith('passport_'):
            for match in re.finditer(r'(?<![0-9])([0-9]{14})(?![0-9])', text):
                add('pinfl', match[1])
        if source == 'license_front':
            # A licence may contain other 14-digit identifiers. Only field 4d
            # is the applicant's PINFL; an unlabelled number is not enough.
            pinfl = re.fullmatch(r'4\s*[dд][.)]?\s*([0-9]{14})', text, re.I)
            if pinfl:
                add('pinfl', pinfl[1])
            serial = re.fullmatch(r'5[.)]?\s*' + SERIAL, text)
            if serial:
                add('license_number', serial[1])
            birth = re.fullmatch(r'3[.)]?\s*(.+?)\s*' + DATE, text)
            if birth:
                add('birth_date', '.'.join(birth.groups()[1:]))
                add('birth_place', clean_place(birth[1]) or '')
            expiry = re.search(r'4\s*[bвб][.)]?\s*' + DATE, text, re.I)
            if expiry:
                add('license_expiry', '.'.join(expiry.groups()))
        if source.startswith('tech_') and word.left >= .60 * width and word.top < .75 * height:
            serial = re.fullmatch(SERIAL, text.upper())
            if serial:
                add('vehicle_registration', serial[1])
    if source == 'license_front':
        # Some OCR layouts split the printed 4d label and number into two boxes.
        anchors = [w for w in rows if w.confidence >= 90 and
                   re.fullmatch(r'4\s*[dд][.)]?', w.text, re.I)]
        for anchor in anchors:
            for word in rows:
                if (word.confidence >= 90 and re.fullmatch(r'[0-9]{14}', word.text)
                        and 0 <= word.left - anchor.left - anchor.width < anchor.height * 5
                        and abs(word.top + word.height / 2 - anchor.top - anchor.height / 2)
                        <= max(anchor.height, word.height) * .5):
                    add('pinfl', word.text)
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


def clean_name(text):
    text = ' '.join(text.split()).strip(" .")
    if not 2 <= len(text) <= 140 or not re.fullmatch(r"[^\W\d_]+(?:[ '‘’ʼ`-][^\W\d_]+)*", text, re.UNICODE):
        return None
    return text


def clean_place(text):
    value = clean_name(text)
    if value:
        # Restore only a word boundary before a printed administrative suffix.
        # Do not complete, substitute, or spell-correct geographic names.
        value = re.sub(r'(?<=[A-Z])\s*(TUMANI|SHAHRI|VILOYATI|RESPUBLIKASI)$', r' \1', value)
    return value


def licence_name(words):
    # Numbered field 2 anchors the given name. Require one surname directly above,
    # aligned with it; do not pick the decorative region list at the card's right.
    anchors = [w for w in words if w.confidence >= 95 and re.fullmatch(r'2[.)]?', w.text)]
    if len(anchors) != 1:
        combined = [w for w in words if w.confidence >= 95 and re.match(r'^2[.)]?\s*[^\W\d_]', w.text)]
        if len(combined) != 1:
            return None
        given = combined[0]
        name = clean_name(re.sub(r'^2[.)]?\s*', '', given.text))
    else:
        anchor = anchors[0]
        candidates = [w for w in words if w.confidence >= 95 and clean_name(w.text)
            and 0 < w.left - anchor.left - anchor.width < anchor.height * 2
            and abs(w.top - anchor.top) < anchor.height * .5]
        if len(candidates) != 1:
            return None
        given = candidates[0]
        name = clean_name(given.text)
    surname_text = lambda w: clean_name(re.sub(r'^1[.)]?\s*', '', w.text))
    surnames = [w for w in words if w.confidence >= 95 and surname_text(w)
        and .6 * given.height < given.top - w.top < 1.8 * given.height
        and abs(w.left - given.left) < given.height * .5]
    if name and len(surnames) == 1:
        return clean_name(surname_text(surnames[0]) + ' ' + name)
    return None


def unanimous(readings):
    # Different confident readings remain unknown, even if a majority agrees.
    items = set(value for value in readings if value)
    return next(iter(items)) if len(items) == 1 and sum(bool(x) for x in readings) >= 3 else None


def refine_birth(engine, image, word):
    import numpy as np
    boundary = int(word.left + .7 * word.width)
    top, bottom = max(0, int(word.top) + 1), min(image.height, int(word.top + word.height) - 2)
    regions = {
        'birth_place': (max(0, round(word.left + .1 * word.width)), top, boundary - 1, bottom),
        'birth_date': (max(0, boundary), top, min(image.width, int(word.left + word.width) + 7), bottom),
    }
    result = {}
    for key, box in regions.items():
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        readings = []
        for scale in (2, 3, 4):
            region = image.crop(box)
            region = region.resize((region.width * scale, region.height * scale), Image.Resampling.BICUBIC)
            region = ImageOps.autocontrast(region.convert('L')).convert('RGB')
            rows, _ = engine(np.array(region)[:, :, ::-1].copy(), use_det=False, use_cls=False)
            if not rows or len(rows) != 1:
                readings.append(None)
                continue
            text, confidence = rows[0]
            if key == 'birth_date':
                # Formatting eight printed digits is permitted; never substitute
                # ambiguous O/I/S characters or infer a date from PINFL.
                digits = re.sub(r'[ ./-]', '', text)
                value = normalize({'birth_date': digits[:2]+'.'+digits[2:4]+'.'+digits[4:]})['birth_date'] if re.fullmatch(r'[0-9]{8}', digits) else None
                readings.append(value if confidence >= .90 else None)
            else:
                value = clean_place(text)
                readings.append(value if confidence >= .85 else None)
        result[key] = unanimous(readings)
    return result


def orientation_hint(result, technical=False):
    """Infer page rotation from detected text geometry, not phone EXIF alone."""
    from statistics import median
    tall = wide = 0
    ranks = {}
    for box, text, confidence in result or []:
        x = [point[0] for point in box]
        y = [point[1] for point in box]
        width, height = max(x) - min(x), max(y) - min(y)
        if len(text) >= 6 and confidence >= .6:
            tall += height > width * 1.5
            wide += width > height * 1.5
        match = re.match(r'^([0-9]{1,2})[.)]', text) if technical else re.match(r'^([1-5])(?:[a-d])?(?:[.)]|\s|(?=[A-Z]))', text, re.I)
        if match and confidence >= .85:
            ranks.setdefault(int(match[1]), []).append(sum(y) / len(y))
    if tall >= 3 and tall > wide * 1.5:
        return 90
    ordered = [(rank, median(centers)) for rank, centers in sorted(ranks.items())]
    inversions = sum(a[1] > b[1] for a, b in zip(ordered, ordered[1:]))
    if len(ordered) >= 3 and inversions >= 2 and inversions == len(ordered) - 1:
        return 180
    return 0


def read_document(engine, raw, source, emit=None):
    import numpy as np
    with Image.open(BytesIO(raw)) as opened:
        if opened.width * opened.height > 30_000_000:
            raise ValueError('Image too large')
        image = ImageOps.exif_transpose(opened).convert('RGB')
    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    result, _ = engine(np.array(ImageOps.invert(image))[:, :, ::-1].copy())
    if source == 'license_front' or source.startswith('tech_'):
        for _ in range(2):
            angle = orientation_hint(result, technical=source.startswith('tech_'))
            if not angle:
                break
            image = image.rotate(angle, expand=True)
            result, _ = engine(np.array(ImageOps.invert(image))[:, :, ::-1].copy())
    words = []
    for box, text, confidence in result or []:
        left, top = min(p[0] for p in box), min(p[1] for p in box)
        words.append(Word(text, confidence * 100, left, top,
            max(p[0] for p in box) - left, max(p[1] for p in box) - top))
    values = fields_from_rows(words, source, image.width, image.height)
    if source == 'license_front':
        values['full_name'] = licence_name(words)
        if emit:
            emit(guard_identifiers(values)[0])
        anchors = [w for w in words if w.confidence >= 75 and re.match(r'^3[.)]', w.text)]
        if len(anchors) == 1:
            refined = refine_birth(engine, image, anchors[0])
            for key, value in refined.items():
                # A narrow crop can read only part of a place name. The intact,
                # numbered field 3 has precedence when it already parsed cleanly.
                if value and not values[key]:
                    values[key] = value
    return guard_identifiers(values)[0]


def main():
    from bot.ocr_sandbox import restrict_worker
    restrict_worker()
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
    if '--check' in sys.argv:
        print(json.dumps({'ready': True}), flush=True)
        return
    payload = json.loads(sys.stdin.buffer.read(45_000_000))
    registration_found = False
    for item in payload:
        source = item['source']
        if source == 'tech_front' and registration_found:
            print(json.dumps({'source': source, 'values': {}, 'skipped': True, 'final': True}), flush=True)
            continue
        try:
            raw = base64.b64decode(item['image'], validate=True)
            if len(raw) > 5_000_000:
                raise ValueError('Image too large')
            values = read_document(engine, raw, source, emit=lambda partial: print(
                json.dumps({'source': source, 'values': partial, 'final': False}), flush=True))
            if source == 'tech_back' and values.get('vehicle_registration'):
                registration_found = True
            print(json.dumps({'source': source, 'values': values, 'final': True}), flush=True)
        except Exception as error:
            print(json.dumps({'source': source, 'error': type(error).__name__}), flush=True)


if __name__ == '__main__':
    main()
