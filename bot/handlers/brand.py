import logging
from bot.application_ids import application_code
from bot.presentation import contact_button, menu_button, send_brand_sticker
from html import escape as h

from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.handlers.start import (
    MENU_BRAND,
    MENU_SPECTRE,
    cancel,
    main_keyboard,
    require_region,
)
from bot.regions import (
    application_group,
    clear_application,
    get_region,
    region_name,
)
from bot.subscription import require_subscription, subscription_keyboard

logger = logging.getLogger(__name__)

BRAND_WARN, BRAND_NAME, BRAND_PHONE, BRAND_MODEL, BRAND_YEAR, BRAND_COLOR, BRAND_PLATE = range(100, 107)
BRAND_JOIN = 107
CONTINUE_BTN = "✅ Davom etish"
CONTINUE_KB = ReplyKeyboardMarkup([[menu_button(CONTINUE_BTN, icon="READY")]], resize_keyboard=True, one_time_keyboard=True)
BRAND_JOIN_KEYBOARD = subscription_keyboard("brand:check_membership")
SPECTRE_JOIN_KEYBOARD = subscription_keyboard("spectre:check_membership")

WARN_TEXT = (
    "⚠️ *DIQQAT! BRENDLASH SHARTLARI:*\n\n"
    "❌ SPARK — brendlanmaydi\n"
    "❌ NEXIA 3 — brendlanmaydi\n"
    "❌ Yili 2015 va undan past mashinalar — brendlanmaydi\n\n"
    "✅ Boshqa mashinalar (yili 2016 va undan yuqori) — brendlanadi\n\n"
    "_SPARK va NEXIA 3 yili nechi bo‘lishidan qat’i nazar BREND qilinmaydi._\n"
    "_2016 dan past mashinalar ham brend qilinmaydi._\n\n"
    "Davom etish uchun pastdagi knopkani bosing."
)


def _regional_keyboard(context):
    return main_keyboard(get_region(context))


async def _require_region(update, context, allowed_regions=None) -> bool:
    return await require_region(update, context, allowed_regions)


def _kind(context) -> str:
    return context.user_data.get("_application_kind", "brand")


def _kind_title(kind: str) -> str:
    return "Spectre Energy" if kind == "spectre" else "Brend"


def _branch_title(context) -> str:
    return f"{region_name(get_region(context))} — {_kind_title(_kind(context))}"


async def _send_name_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"📍 *{_branch_title(context)} arizasi*\n\n"
        "Iltimos, *ism va familiyangizni* yozing:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )


async def _destination_error(update, context, kind: str) -> None:
    region = get_region(context)
    label = _kind_title(kind)
    await update.effective_message.reply_text(
        f"⚠️ {region_name(region)} uchun {label} arizasi hozircha sozlanmagan.\n"
        "Iltimos, birozdan keyin qayta urinib ko‘ring.",
        reply_markup=_regional_keyboard(context),
    )


async def _start_application(
    update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str
) -> int:
    if not await _require_region(update, context):
        return ConversationHandler.END
    region = get_region(context)
    # Preserve the selected branch, but never carry partial fields into a
    # newly selected application.
    clear_application(context)
    context.user_data["_application_kind"] = kind
    if not application_group(region, kind):
        await _destination_error(update, context, kind)
        clear_application(context)
        return ConversationHandler.END
    return await check_membership(update, context)


async def start_brand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _start_application(update, context, "brand")


async def start_spectre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _start_application(update, context, "spectre")


async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    kind = _kind(context)
    callback = "spectre:check_membership" if kind == "spectre" else "brand:check_membership"
    # The user may have changed branches while the subscription prompt was
    # open.  Validate both branch and destination before collecting data.
    if not await _require_region(update, context):
        return ConversationHandler.END
    region = get_region(context)
    if not application_group(region, kind):
        if update.callback_query:
            await update.callback_query.answer()
        await _destination_error(update, context, kind)
        clear_application(context)
        return ConversationHandler.END
    if not await require_subscription(update, context, callback_data=callback):
        return BRAND_JOIN
    clear_application(context)
    context.user_data["_application_kind"] = kind
    context.user_data["_application_region"] = region
    if kind == "spectre":
        # Spectre asks the same fields as Brand, but has no Brand eligibility
        # restrictions or warning text.
        await _send_name_prompt(update, context)
        return BRAND_NAME
    await update.effective_message.reply_text(
        f"📍 *{region_name(region)} — Brend arizasi*\n\n"
        f"{WARN_TEXT}",
        parse_mode="Markdown",
        reply_markup=CONTINUE_KB,
    )
    return BRAND_WARN


async def brand_warn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _send_name_prompt(update, context)
    return BRAND_NAME


async def brand_warn_wrong(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        f"❗ Iltimos, *{CONTINUE_BTN}* knopkasini bosing:",
        parse_mode="Markdown", reply_markup=CONTINUE_KB,
    )
    return BRAND_WARN


async def brand_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.message.text or "").strip()
    if len(name) < 3:
        await update.message.reply_text("❗ Iltimos, to‘liq ism familiyangizni yozing:")
        return BRAND_NAME
    context.user_data["b_name"] = name
    keyboard = ReplyKeyboardMarkup(
        [[contact_button("Raqamni jo‘natish")]],
        resize_keyboard=True, one_time_keyboard=True,
    )
    await update.message.reply_text(
        f"📍 *{_branch_title(context)}*\n"
        "📞 Telefon raqamingizni jo‘nating:",
        parse_mode="Markdown", reply_markup=keyboard,
    )
    context.user_data["_brand_state"] = BRAND_PHONE
    return BRAND_PHONE


async def brand_get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.contact.phone_number if update.message.contact else (update.message.text or "").strip()
    if len(phone) < 7 or not any(char.isdigit() for char in phone):
        await update.message.reply_text("❗ To‘g‘ri telefon raqamini kiriting (masalan: +998901234567):")
        return BRAND_PHONE
    context.user_data["b_phone"] = phone
    await update.message.reply_text(
        f"📍 *{_branch_title(context)}*\n"
        "🚗 Mashinangizning *rusumini (modelini)* yozing:",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data["_brand_state"] = BRAND_MODEL
    return BRAND_MODEL


async def brand_get_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    model = (update.message.text or "").strip()
    if len(model) < 2:
        await update.message.reply_text("❗ Iltimos, mashina rusumini yozing:")
        return BRAND_MODEL
    context.user_data["b_model"] = model
    await update.message.reply_text(
        f"📍 *{_branch_title(context)}*\n"
        "📅 Mashinangizning *yilini* yozing:",
        parse_mode="Markdown",
    )
    return BRAND_YEAR


async def brand_get_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    year = (update.message.text or "").strip()
    if not year.isdigit() or not 1990 <= int(year) <= 2030:
        await update.message.reply_text("❗ To‘g‘ri yil kiriting (masalan: 2018):")
        return BRAND_YEAR
    context.user_data["b_year"] = year
    await update.message.reply_text(
        f"📍 *{_branch_title(context)}*\n"
        "🎨 Mashinangizning *rangini* yozing:",
        parse_mode="Markdown",
    )
    return BRAND_COLOR


async def brand_get_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    color = (update.message.text or "").strip()
    if len(color) < 2:
        await update.message.reply_text("❗ Iltimos, mashina rangini yozing:")
        return BRAND_COLOR
    context.user_data["b_color"] = color
    await update.message.reply_text(
        f"📍 *{_branch_title(context)}*\n"
        "🔢 Mashinangizning *davlat raqamini* yozing:",
        parse_mode="Markdown",
    )
    return BRAND_PLATE


async def brand_get_plate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data.get("_delivery_uncertain"):
        await update.message.reply_text(
            "⚠️ Oldingi yuborish natijasi noma’lum. Takroriy ariza yubormaslik uchun "
            "operator bilan bog‘laning. Ma’lumotlaringiz saqlandi."
        )
        return BRAND_PLATE
    plate = (update.message.text or "").strip().upper()
    if len(plate) < 5 or not any(char.isalnum() for char in plate):
        await update.message.reply_text("❗ To‘g‘ri davlat raqamini kiriting (masalan: 01A123BC):")
        return BRAND_PLATE

    data = context.user_data
    data["b_plate"] = plate
    user = update.effective_user
    display = f"@{user.username}" if user.username else user.full_name
    user_link = f'<a href="tg://user?id={user.id}">{h(display)}</a>'
    kind = _kind(context)
    if not await _require_region(update, context):
        return ConversationHandler.END
    region = get_region(context)
    if data.get("_application_region") != region:
        clear_application(context)
        await update.message.reply_text(
            "⚠️ Hudud almashtirilgani uchun eski ariza bekor qilindi. "
            "Yangi hudud uchun arizani qayta boshlang.",
            reply_markup=_regional_keyboard(context),
        )
        return ConversationHandler.END
    # Recheck immediately before sending; an unset destination must never
    # silently route this application to Namangan.
    group_id = application_group(region, kind)
    if not group_id:
        await _destination_error(update, context, kind)
        clear_application(context)
        return ConversationHandler.END

    user = update.effective_user
    display = f"@{user.username}" if user.username else user.full_name
    user_link = f'<a href="tg://user?id={user.id}">{h(display)}</a>'
    branch_title = _kind_title(kind)
    branch_icon = "⚡" if kind == "spectre" else "🎨"
    code = application_code(data)
    text = (
        f"Ariza: <code>{code}</code>\n"
        f"{branch_icon} <b>{h(region_name(region))} — YANGI {h(branch_title.upper())} ARIZA</b>\n\n"
        f"👤 Foydalanuvchi: {user_link}\n"
        f"🪪 FIO: {h(data['b_name'])}\n"
        f"📞 Tel: {h(data['b_phone'])}\n"
        f"🚗 Model: {h(data['b_model'])}\n"
        f"📅 Yili: {h(data['b_year'])}\n"
        f"🎨 Rangi: {h(data['b_color'])}\n"
        f"🔢 Davlat raqami: {h(data['b_plate'])}"
    )
    try:
        from bot.queue_moves import checkpoint
        review = None
        from bot.brand_review import stage_review, review_keyboard, status_text
        review = stage_review(context, data, code, region, group_id, text, user.id, kind=kind)
        if not await checkpoint(context):
            raise RuntimeError('Review state could not be saved')
        if not data.get('_brand_group_message'):
            message = await context.bot.send_message(
                chat_id=group_id,
                text=status_text(review) if review else text,
                parse_mode=ParseMode.HTML,
                reply_markup=review_keyboard(code) if review else None)
            data['_brand_group_message'] = message.message_id
        review['message_id'] = data['_brand_group_message']
        review['displayed_status'] = 'pending'
        if not await checkpoint(context):
            raise RuntimeError('Review message could not be saved')
    except Exception as error:
        logger.warning("Brand submission failed (%s)", type(error).__name__)
        if isinstance(error, NetworkError) and not isinstance(error, BadRequest):
            context.user_data["_delivery_uncertain"] = True
            await update.message.reply_text(
                "⚠️ Aloqa uzildi; ariza yetib borgani tasdiqlanmadi. "
                "Ma’lumotlar saqlandi. Qayta ariza yuborishdan oldin operator bilan bog‘laning."
            )
            return BRAND_PLATE
        await update.message.reply_text(
            "⚠️ Ariza yuborilmadi. Ma’lumotlar saqlandi. "
            "Qayta urinish uchun davlat raqamini yana yuboring yoki /cancel bosing."
        )
        return BRAND_PLATE

    await send_brand_sticker(update.message, "SUCCESS")
    await update.message.reply_text(
        f"Ariza kodi: `{code}`\n\n"
        "✅ *Arizangiz qabul qilindi*\n\n"
        f"{region_name(region)} — {_kind_title(kind)} arizangiz qabul qilindi. "
        "Tez orada operatorlarimiz bog‘lanadi.",
        parse_mode="Markdown", reply_markup=_regional_keyboard(context),
    )
    clear_application(context)
    return ConversationHandler.END


async def wrong_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❗ Iltimos, javobni matn ko‘rinishida yozing:")
    return context.user_data.get("_brand_state", BRAND_NAME)


def _text_state(handler, state):
    async def tracked(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info("Brand form update: update=%s state=%s",
                    getattr(update, 'update_id', None), state)
        next_state = await handler(update, context)
        logger.info("Brand form transition: update=%s from=%s to=%s",
                    getattr(update, 'update_id', None), state, next_state)
        if next_state != ConversationHandler.END:
            context.user_data["_brand_state"] = next_state
        return next_state
    return [
        MessageHandler(filters.TEXT & ~filters.COMMAND, tracked),
        MessageHandler(~filters.COMMAND, wrong_text),
    ]


def build_brand_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE & filters.Regex(r"^(?:🎨 )?Brend Ariza$"),
                start_brand,
            ),
            MessageHandler(
                filters.ChatType.PRIVATE & filters.Regex(r"^(?:⚡ )?Spectre Energyga ariza$"),
                start_spectre,
            ),
        ],
        states={
            BRAND_JOIN: [
                # Both application types use the same shared subscription
                # gate; the callback's prefix is selected from user_data.
                CallbackQueryHandler(
                    check_membership,
                    pattern=r"^(?:brand|spectre):check_membership$",
                ),
                MessageHandler(~filters.COMMAND, check_membership),
            ],
            BRAND_WARN: [
                MessageHandler(filters.Regex(r"^(?:✅ )?Davom etish$"), brand_warn),
                MessageHandler(~filters.COMMAND, brand_warn_wrong),
            ],
            BRAND_NAME: _text_state(brand_get_name, BRAND_NAME),
            BRAND_PHONE: [
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), brand_get_phone),
                MessageHandler(~filters.COMMAND, wrong_text),
            ],
            BRAND_MODEL: _text_state(brand_get_model, BRAND_MODEL),
            BRAND_YEAR: _text_state(brand_get_year, BRAND_YEAR),
            BRAND_COLOR: _text_state(brand_get_color, BRAND_COLOR),
            BRAND_PLATE: _text_state(brand_get_plate, BRAND_PLATE),
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", cancel)],
        allow_reentry=True,
    )
