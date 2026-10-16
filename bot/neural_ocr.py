"""Bounded local neural OCR, isolated from bot credentials."""
import asyncio
import base64
import json
import logging
from pathlib import Path
import sys
import time
from weakref import WeakKeyDictionary
from bot.fast_ocr import environment
from bot.document_ocr import FIELDS, SOURCES, guard_identifiers, normalize

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
_GATES = WeakKeyDictionary()


async def worker(payload=None):
    gate = _GATES.setdefault(asyncio.get_running_loop(), asyncio.Semaphore(1))
    await asyncio.wait_for(gate.acquire(), timeout=2)
    try:
        return await _worker(payload)
    finally:
        gate.release()


async def _worker(payload=None):
    arguments = [sys.executable, '-m', 'bot.neural_ocr_worker']
    if payload is None:
        arguments.append('--check')
    process = await asyncio.create_subprocess_exec(*arguments, cwd=ROOT, env=dict(environment(), OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1"),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    output = []
    async def communicate():
        process.stdin.write(json.dumps(payload or []).encode())
        await process.stdin.drain()
        process.stdin.close()
        while line := await process.stdout.readline():
            output.append(json.loads(line))
        await process.wait()
    timed_out = False
    try:
        await asyncio.wait_for(communicate(), timeout=10)
    except asyncio.TimeoutError:
        timed_out = True
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    if process.returncode and not timed_out:
        raise RuntimeError('Local neural OCR worker failed')
    return output


async def engine_info():
    result = await worker()
    if result != [{'ready': True}]:
        raise RuntimeError('Local neural OCR not ready')


async def extract_documents(bot, data):
    start = time.monotonic()
    order = ('license_front', 'tech_back', 'passport_front', 'license_back', 'tech_front', 'passport_back')
    selected = [source for source in order if data.get(source)]
    async def download(source):
        file = await bot.get_file(data[source])
        if file.file_size and file.file_size > 5_000_000:
            raise ValueError('Image too large')
        image = await file.download_as_bytearray()
        if len(image) > 5_000_000:
            raise ValueError('Image too large')
        return {'source': source, 'image': base64.b64encode(image).decode('ascii')}
    downloaded = await asyncio.gather(*(asyncio.wait_for(download(s), timeout=6) for s in selected), return_exceptions=True)
    failed, payload = [], []
    for source, item in zip(selected, downloaded):
        if isinstance(item, BaseException):
            failed.append(source)
            logger.warning('Neural OCR download failed: source=%s error=%s', source, type(item).__name__)
        else:
            payload.append(item)
    rows = await worker(payload) if payload else []
    candidates = {key: set() for key in FIELDS}
    completed = set()
    for row in rows:
        source = row.get('source')
        if source not in selected or source in completed or 'error' in row:
            continue
        completed.add(source)
        values = normalize(row.get('values', {}))
        for key in SOURCES[source]:
            if values[key]:
                candidates[key].add(values[key])
    failed += [item['source'] for item in payload if item['source'] not in completed]
    values = {key: next(iter(items)) if len(items) == 1 else None for key, items in candidates.items()}
    values, rejected = guard_identifiers(values, data.get('car_plate'))
    logger.info('Neural OCR finished: seconds=%.2f fields=%s failed_sources=%s',
        time.monotonic() - start, sum(bool(v) for v in values.values()), len(failed))
    return {'backend': 'rapid', 'status': 'complete' if all(values.values()) and not failed else 'partial',
        'values': values, 'failed_sources': failed, 'rejected_fields': rejected,
        'conflicting_fields': [key for key, items in candidates.items() if len(items) > 1]}
