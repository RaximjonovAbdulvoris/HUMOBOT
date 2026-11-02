"""Separate contest application; no other application route is reused."""
import re
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, filters

from bot.application_ids import application_code
from bot.handlers.start import MENU_KONKURS, cancel, main_keyboard
from bot.regions import clear_application
from bot.route_settings import destination
from bot.queue_moves import checkpoint

CITY, NAME, PHONE, ORDERS, DAY = range(300, 305)


async def begin(update: Update, context):
    clear_application(context)
    if not destination('KONKURS_GROUP'):
        await update.message.reply_text('Konkurs arizalari hozircha qabul qilinmayapti.')
        return ConversationHandler.END
    await update.message.reply_text('🎁 Konkurs uchun qaysi shahardansiz? Shahar nomini yozing:')
    return CITY


async def city(update: Update, context):
    value = (update.message.text or '').strip()
    if not re.fullmatch(r"[\w\s‘’'ʼ-]{2,80}", value, flags=re.UNICODE):
        await update.message.reply_text('Shahar nomini to‘liq yozing:')
        return CITY
    context.user_data['k_city'] = value
    await update.message.reply_text('Ism va familiyangizni yozing:')
    return NAME


async def name(update: Update, context):
    value = ' '.join((update.message.text or '').split())
    if len(value.split()) < 2 or len(value) > 100:
        await update.message.reply_text('Ism va familiyangizni birga yozing:')
        return NAME
    context.user_data['k_name'] = value
    await update.message.reply_text('Telefon raqamingizni yozing (masalan: 998901234567):')
    return PHONE


async def phone(update: Update, context):
    digits = re.sub(r'\D', '', update.message.contact.phone_number if update.message.contact else (update.message.text or ''))
    if len(digits) == 9:
        digits = '998' + digits
    if not re.fullmatch(r'998\d{9}', digits):
        await update.message.reply_text('Telefon raqamini 998 bilan boshlanadigan 12 ta raqamda yozing:')
        return PHONE
    context.user_data['k_phone'] = digits
    await update.message.reply_text('Nechta buyurtma bajargansiz? Faqat son yozing:')
    return ORDERS


async def orders(update: Update, context):
    value = (update.message.text or '').strip()
    if not re.fullmatch(r'\d{1,7}', value) or int(value) < 1:
        await update.message.reply_text('Bajarilgan buyurtmalar sonini musbat raqamda yozing:')
        return ORDERS
    context.user_data['k_orders'] = str(int(value))
    await update.message.reply_text('Qaysi sanada? KUN.OY.YIL shaklida yozing (masalan: 02.11.2026):')
    return DAY


async def day(update: Update, context):
    value = (update.message.text or '').strip()
    try:
        entered = datetime.strptime(value, '%d.%m.%Y').date()
        if entered.strftime('%d.%m.%Y') != value or entered > datetime.now(ZoneInfo('Asia/Tashkent')).date():
            raise ValueError('date')
    except ValueError:
        await update.message.reply_text('Sanani KUN.OY.YIL shaklida to‘g‘ri yozing:')
        return DAY
    data = context.user_data
    data['k_date'] = value
    group = destination('KONKURS_GROUP')
    if not group:
        await update.message.reply_text('Konkurs guruhi sozlanmagan. Ma’lumotlar saqlandi; keyinroq qayta urinib ko‘ring.')
        return DAY
    code = application_code(data)
    user = update.effective_user
    text = (f'🎁 <b>KONKURS ARIZASI</b> · <code>{code}</code>\n\n'
            f'👤 Arizachi: <a href="tg://user?id={user.id}">{escape(user.full_name)}</a>\n'
            f'Shahar: {escape(data["k_city"])}\n'
            f'Ism familiya: {escape(data["k_name"])}\n'
            f'Telefon: <code>{data["k_phone"]}</code>\n'
            f'Buyurtmalar soni: <code>{data["k_orders"]}</code>\n'
            f'Sana: <code>{value}</code>')
    from bot.brand_review import review_keyboard, stage_review, status_text
    review = stage_review(context, data, code, 'konkurs', group, text, user.id, kind='konkurs')
    # A timeout may mean Telegram accepted the post but its response was lost.
    # Never send the same application again until an operator reconciles it.
    if review.get('send_attempted'):
        await update.message.reply_text('Bu ariza yuborishga berilgan. Takror yubormang; holatini operator tekshiradi.')
        return DAY
    review['send_attempted'] = True
    if not await checkpoint(context):
        review.pop('send_attempted', None)
        await update.message.reply_text('Arizani saqlab bo‘lmadi. Keyinroq qayta urinib ko‘ring.')
        return DAY
    try:
        message = await context.bot.send_message(chat_id=group, text=status_text(review),
                                                 parse_mode='HTML', reply_markup=review_keyboard(code))
        review['message_id'] = message.message_id
        review['displayed_status'] = 'pending'
        if not await checkpoint(context):
            await update.message.reply_text('Ariza guruhga yuborildi, lekin saqlash tasdiqlanmadi. Takror yubormang; operatorga murojaat qiling.')
            return DAY
    except Exception:
        await update.message.reply_text('Yuborish natijasi noma’lum. Takror yubormasdan operatorga murojaat qiling.')
        return DAY
    await update.message.reply_text(f'✅ Konkurs arizangiz qabul qilindi. Kod: {code}', reply_markup=main_keyboard(None))
    clear_application(context)
    return ConversationHandler.END


def build_konkurs_conversation():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.ChatType.PRIVATE & filters.Regex(r'^Konkurs(?:🎁)?$'), begin)],
        states={CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, city)],
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
                PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), phone)],
                ORDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, orders)],
                DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, day)]},
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', cancel)],
        allow_reentry=True)
