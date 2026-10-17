"""Operator approval gate for brand applications before Google Sheets export."""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler

from bot.background_ocr import control_lock
from bot.queue_moves import checkpoint

logger = logging.getLogger(__name__)


def review_keyboard(code):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton('✔️ Tasdiqlansin', callback_data=f'brand-review:approve:{code}'),
        InlineKeyboardButton('❌ To‘g‘ri kelmadi', callback_data=f'brand-review:reject:{code}'),
    ]])


def stage_review(context, data, code, region, group_id, text, applicant_id):
    reviews = context.bot_data.setdefault('brand_reviews', {})
    review = reviews.setdefault(code, {
        'code': code, 'region': region, 'group_id': str(group_id),
        'message_id': None, 'text': text, 'status': 'pending',
        'applicant_id': applicant_id,
        'fields': {key: str(data.get(key, '')) for key in (
            'b_name', 'b_phone', 'b_model', 'b_year', 'b_color', 'b_plate')},
    })
    if review['group_id'] != str(group_id) or review['region'] != region:
        raise ValueError('Application review route changed')
    return review


def status_text(review):
    labels = {
        'pending': '⏳ Ko‘rib chiqilmoqda · Google Sheetsga yuborilmagan',
        'approved': '✔️ Tasdiqlandi · Google Sheetsga yuborilmoqda',
        'exported': '✔️ Tasdiqlandi va Google Sheetsga to‘ldirildi',
        'rejected': '❌ To‘g‘ri kelmadi · Google Sheetsga yuborilmaydi',
    }
    return review['text'] + '\n\n<b>Operator qarori:</b> ' + labels[review['status']]


async def sync_status(context, review):
    """The group post is the durable, visible source of the decision."""
    if (not review.get('message_id') or review.get('group_deleted')
            or review.get('displayed_status') == review['status']):
        return
    try:
        await context.bot.edit_message_text(
            chat_id=review['group_id'], message_id=review['message_id'],
            text=status_text(review), parse_mode='HTML',
            reply_markup=review_keyboard(review['code']) if review['status'] == 'pending' else None,
        )
        review['displayed_status'] = review['status']
        await checkpoint(context)
    except BadRequest as error:
        if 'not modified' in str(error).lower():
            review['displayed_status'] = review['status']
            await checkpoint(context)
        else:
            logger.warning('Brand review post update pending (%s)', type(error).__name__)
    except Exception as error:
        logger.warning('Brand review post update pending (%s)', type(error).__name__)


async def sync_all(context):
    for review in context.bot_data.get('brand_reviews', {}).values():
        if review['status'] != 'pending':
            await sync_status(context, review)
            await notify_applicant(context, review)
            if review['status'] == 'rejected' and not review.get('group_deleted') and review.get('message_id'):
                try:
                    await context.bot.delete_message(chat_id=review['group_id'], message_id=review['message_id'])
                    review['group_deleted'] = True
                    await checkpoint(context)
                except Exception as error:
                    logger.warning('Rejected brand post cleanup pending (%s)', type(error).__name__)


async def notify_applicant(context, review):
    if review.get('applicant_notified') or not review.get('applicant_id'):
        return
    if review['status'] == 'rejected':
        text = ('Arizangiz ko‘rib chiqildi. Afsuski, avtomobilingiz yoki yuborgan '
                'ma’lumotlaringiz brendlash talablariga mos kelmagani uchun arizangiz '
                'tasdiqlanmadi.\n\nSavollar bo‘lsa, +998 78 113 80 81 raqamiga murojaat qiling.')
    elif review['status'] in ('approved', 'exported'):
        text = ('Arizangiz ko‘rib chiqildi va brendlash uchun tasdiqlandi. '
                'Tez orada siz bilan bog‘lanamiz.\n\nSavollar bo‘lsa, '
                '+998 78 113 80 81 raqamiga murojaat qiling.')
    else:
        return
    try:
        await context.bot.send_message(chat_id=review['applicant_id'],
                                       text=f"Ariza {review['code']}\n\n{text}")
        review['applicant_notified'] = True
        await checkpoint(context)
    except Exception as error:
        logger.warning('Brand applicant notice pending (%s)', type(error).__name__)


async def on_review(update, context):
    query = update.callback_query
    if not query or not query.message:
        return
    parts = (query.data or '').split(':', 2)
    if len(parts) != 3 or parts[1] not in ('approve', 'reject'):
        await query.answer('Noto‘g‘ri amal.', show_alert=True)
        return
    _, action, code = parts
    chat, user = update.effective_chat, update.effective_user
    if not chat or chat.type not in ('group', 'supergroup') or not user or getattr(query.message, 'sender_chat', None):
        await query.answer('Operator aniqlanmadi.', show_alert=True)
        return
    async with control_lock(chat.id, query.message.message_id):
        review = context.bot_data.get('brand_reviews', {}).get(code)
        if (not review or review.get('group_id') != str(chat.id)
                or review.get('message_id') != query.message.message_id):
            await query.answer('Bu ariza topilmadi yoki tugma eskirgan.', show_alert=True)
            return
        try:
            member = await context.bot.get_chat_member(chat.id, user.id)
        except Exception:
            await query.answer('Operator huquqini tekshirib bo‘lmadi.', show_alert=True)
            return
        if member.status not in ('administrator', 'creator'):
            await query.answer('Faqat guruh administratori qaror qabul qiladi.', show_alert=True)
            return
        if review['status'] != 'pending':
            await query.answer('Bu ariza bo‘yicha qaror allaqachon qabul qilingan.', show_alert=True)
            await sync_status(context, review)
            await notify_applicant(context, review)
            return
        if action == 'approve':
            from bot.brand_sheets import enqueue
            outbox = context.bot_data.setdefault('brand_sheets_outbox', {})
            previous = dict(outbox[code]) if code in outbox else None
            try:
                enqueue(context, review['fields'], user, code, review['region'],
                        kind='brand', approved=True)
            except ValueError:
                await query.answer('Sheets navbatini yaratib bo‘lmadi.', show_alert=True)
                return
            review['status'] = 'approved'
        else:
            # A legacy unapproved item must never be exported after rejection.
            item = context.bot_data.get('brand_sheets_outbox', {}).get(code)
            if item and item.get('status') == 'pending':
                item['status'] = 'rejected'
            review['status'] = 'rejected'
        if not await checkpoint(context):
            review['status'] = 'pending'
            if action == 'approve':
                if previous is None:
                    outbox.pop(code, None)
                else:
                    outbox[code] = previous
            elif item and item.get('status') == 'rejected':
                item['status'] = 'pending'
            await query.answer('Qarorni saqlab bo‘lmadi. Administrator tekshirsin.', show_alert=True)
            return
        await query.answer('Tasdiqlandi.' if action == 'approve' else 'To‘g‘ri kelmadi.')
        await sync_status(context, review)
        await notify_applicant(context, review)
        if action == 'reject':
            try:
                await context.bot.delete_message(chat_id=chat.id, message_id=review['message_id'])
                review['group_deleted'] = True
                await checkpoint(context)
            except Exception as error:
                logger.warning('Rejected brand post cleanup pending (%s)', type(error).__name__)


def handler():
    return CallbackQueryHandler(on_review, pattern=r'^brand-review:(?:approve|reject):HM-\d{6,}$')
