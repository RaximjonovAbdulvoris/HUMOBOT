"""Deliver first, then enrich the existing control message with local OCR."""
import asyncio
import logging
from weakref import WeakKeyDictionary

from bot.document_ocr import SOURCES, extract_documents, format_summary, enabled

logger = logging.getLogger(__name__)
_LOCKS = WeakKeyDictionary()
_JOBS = WeakKeyDictionary()
PENDING_TEXT = '⏳ Mahalliy AI ma’lumotlarni o‘qimoqda. Operator hujjatlarni hoziroq ko‘rib chiqishi mumkin.'


def control_lock(chat_id, message_id):
    locks = _LOCKS.setdefault(asyncio.get_running_loop(), {})
    return locks.setdefault((int(chat_id), int(message_id)), asyncio.Lock())


def records(application, code, applicant_id):
    return [(key, record) for key, record in application.bot_data.get('applications', {}).items()
            if record.get('code') == code and record.get('applicant_id') == applicant_id
            and record.get('kind') == 'driver']


def current_record(application, code, applicant_id):
    matches = records(application, code, applicant_id)
    # A source may remain during failed cleanup. Follow the confirmed destination.
    destinations = [(key, record) for key, record in matches if not record.get('_transfer')]
    return destinations[-1] if destinations else None


def schedule_ocr(application, code, applicant_id):
    if not enabled() or application is None or not callable(getattr(application, 'create_task', None)):
        return
    jobs = _JOBS.setdefault(asyncio.get_running_loop(), {})
    key = (id(application), code, applicant_id)
    if key in jobs and not jobs[key].done():
        return
    task = application.create_task(enrich(application, code, applicant_id), name='local-ocr-enrichment')
    jobs[key] = task
    def finished(done):
        if jobs.get(key) is done:
            jobs.pop(key, None)
    task.add_done_callback(finished)


def cancel_if_removed(application, code, applicant_id):
    if application is None or records(application, code, applicant_id):
        return
    jobs = _JOBS.get(asyncio.get_running_loop(), {})
    task = jobs.get((id(application), code, applicant_id))
    if task is not None and task is not asyncio.current_task():
        task.cancel()


async def save(application):
    if application.persistence is not None:
        await application.update_persistence()
        await application.persistence.flush()


async def enrich(application, code, applicant_id):
    from bot.handlers.operator import build_operator_keyboard
    from bot.presentation import with_keyboard_fallback
    found = current_record(application, code, applicant_id)
    if found is None:
        return
    data = dict(found[1].get('ocr_input', {}))
    if not data:
        return
    try:
        result = await extract_documents(application.bot, data)
        # Resolve again after inference: the original record may have moved or vanished.
        while (found := current_record(application, code, applicant_id)) is not None:
            key, record = found
            async with control_lock(record['group_chat_id'], record['kb_msg_id']):
                latest = current_record(application, code, applicant_id)
                if latest is None:
                    return
                if latest[0] != key:
                    continue
                if record.get('deleted_source_ids') or record.get('archive_state', {}).get('kb'):
                    return
                text = record['ocr_prefix'] + format_summary(result) + record['ocr_suffix']
                progress = application.bot_data.get('progress_state', {}).get(key, False)
                await with_keyboard_fallback(application.bot.edit_message_text,
                    chat_id=record['group_chat_id'], message_id=record['kb_msg_id'], text=text,
                    parse_mode='HTML', reply_markup=build_operator_keyboard(
                        applicant_id, in_progress=progress, review=bool(record.get('queue_kind'))))
                record['ocr_status'] = 'complete'
                record['ocr_result'] = result
                record.pop('ocr_input', None)
                await save(application)
                return
    except asyncio.CancelledError:
        raise
    except Exception as error:
        # Do not log errors containing document text, bot credentials or provider bodies.
        logger.warning('Background OCR update unavailable (%s)', type(error).__name__)


async def resume_pending(context):
    application = context.application
    seen = set()
    for record in list(application.bot_data.get('applications', {}).values()):
        identity = (record.get('code'), record.get('applicant_id'))
        if identity in seen or not all(identity):
            continue
        seen.add(identity)
        if record.get('ocr_status') == 'pending' and record.get('ocr_input'):
            schedule_ocr(application, *identity)
