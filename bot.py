# ==========================================
# TELEGRAM BOT V2: АНАЛИЗ INSTAGRAM + ИДЕИ
# ==========================================
# Новая версия: собирает анкету, ищет залетные рилсы, генерирует идеи под пользователя
 
import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Optional
 
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
import aiohttp
 
# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
# ===== КОНСТАНТЫ =====
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8000')
 
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не установлен в переменных окружения!")
 
# ===== ЭТАПЫ ДИАЛОГА (Conversation states) =====
CHOOSE_ACTION = 1
PROFILE_NAME = 2
PROFILE_NICHE = 3
PROFILE_AUDIENCE = 4
PROFILE_VOICE = 5
PROFILE_SUCCESSFUL = 6
REQUESTING_IDEAS = 7
 
# ===== /start - ПЕРВЫЙ КОНТАКТ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Когда пользователь пишет /start
    Проверяем есть ли у него профиль
    Если есть - показываем меню
    Если нет - показываем приветствие
    """
    
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BACKEND_URL}/user/{user_id}") as resp:
                if resp.status == 200:
                    await show_main_menu(update, context)
                else:
                    await show_welcome(update, context, user_name)
    except Exception as e:
        logger.error(f"Ошибка при проверке пользователя: {e}")
        await show_welcome(update, context, user_name)
 
async def show_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE, user_name: str):
    """
    Приветствие для новых пользователей
    """
    
    text = f"""
🎬 Привет, {user_name}!
 
Я — ReelsAI, твой AI-помощник для вирусных идей Reels.
 
🔥 Вот что я делаю:
✅ Анализирую залетные рилсы в ТВОЕЙ нише прямо сейчас
✅ Выделяю что работает (хук, звук, структура)
✅ Адаптирую под ТВой tone of voice и фишки
✅ Выдаю готовые идеи которые ты сможешь повторить
 
💡 Результат: идеи которые реально дают 100K+ просмотров
 
Давай создадим твой профиль?
    """
    
    keyboard = [
        [InlineKeyboardButton("✅ Создать профиль", callback_data="create_profile")],
        [InlineKeyboardButton("📖 Как это работает?", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup)
 
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Главное меню для пользователя с профилем
    """
    
    text = """
🎬 Главное меню
 
Что хочешь делать?
    """
    
    keyboard = [
        [InlineKeyboardButton("💡 Получить актуальные идеи", callback_data="get_ideas")],
        [InlineKeyboardButton("👤 Мои профили", callback_data="my_profiles")],
        [InlineKeyboardButton("➕ Новый профиль", callback_data="create_profile")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
 
# ===== СОЗДАНИЕ ПРОФИЛЯ: АНКЕТА =====
 
async def create_profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало создания профиля
    """
    
    context.user_data['creating_profile'] = True
    
    text = """
📝 Окей, давай создадим твой профиль!
 
Я задам несколько вопросов и узнаю всё о тебе.
 
❓ ВОПРОС 1:
Как называется твой аккаунт? Или что ты хочешь назвать?
 
Например: "Мой блог о путешествиях" или "@reelsai_life"
    """
    
    await update.callback_query.edit_message_text(text)
    return PROFILE_NAME
 
async def profile_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Пользователь ввёл название аккаунта
    """
    
    profile_name = update.message.text
    context.user_data['profile_name'] = profile_name
    
    text = """
✅ Супер!
 
❓ ВОПРОС 2:
Какая у тебя НИША? Что ты постишь?
 
Например: "Лайфстайл", "Доноры", "СММ", "Путешествия", "Бьюти", "Бизнес"
 
Это важно чтобы я искал актуальные идеи именно в твоей нише!
    """
    
    await update.message.reply_text(text)
    return PROFILE_NICHE
 
async def profile_niche_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Пользователь указал нишу
    """
    
    niche = update.message.text
    context.user_data['profile_niche'] = niche
    
    text = """
✅ Классно!
 
❓ ВОПРОС 3:
Кто твоя целевая аудитория?
 
Например: "Девушки 18-25", "Мамы", "Предприниматели", "Спортсмены"
 
Это поможет мне искать идеи для твоей аудитории
    """
    
    await update.message.reply_text(text)
    return PROFILE_AUDIENCE
 
async def profile_audience_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Пользователь указал аудиторию
    """
    
    audience = update.message.text
    context.user_data['profile_audience'] = audience
    
    text = """
✅ Отлично!
 
❓ ВОПРОС 4:
Как ТЫ пишешь? Опиши свой стиль в 1-2 предложениях.
 
Это ОЧЕНЬ важно! Это твой "tone of voice"
 
Примеры:
- "Неформально, как подруга, много эмодзи и шуток"
- "Прямолинейно, по делу, без воды, профессионально"
- "Сленг, молодёжный, зажигаю, шумно"
- "Спокойно, мудро, помогаю людям"
    """
    
    await update.message.reply_text(text)
    return PROFILE_VOICE
 
async def profile_voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Пользователь описал свой стиль письма
    """
    
    voice = update.message.text
    context.user_data['profile_voice'] = voice
    
    text = """
✅ Мне это нравится!
 
❓ ВОПРОС 5 (ПОСЛЕДНИЙ):
Какая у тебя ФИШКА? Чем ты выделяешься среди других?
 
Это то что делает твой контент уникальным.
 
Примеры:
- "Я рассказываю личные истории очень честно"
- "Я даю практические советы которые работают"
- "Мой контент смешной и неожиданный"
- "Я показываю закулисье и реальность"
- "Я очень визуальный, красивые кадры"
    """
    
    await update.message.reply_text(text)
    return PROFILE_SUCCESSFUL
 
async def profile_fleshy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Пользователь описал свою фишку
    """
    
    user_id = update.effective_user.id
    fleshy = update.message.text
    
    profile_data = {
        'name': context.user_data.get('profile_name', ''),
        'niche': context.user_data.get('profile_niche', ''),
        'audience': context.user_data.get('profile_audience', ''),
        'voice': context.user_data.get('profile_voice', ''),
        'fleshy': fleshy,
        'created_at': datetime.now().isoformat()
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BACKEND_URL}/profile/create",
                json={
                    'user_id': user_id,
                    'profile_data': profile_data
                }
            ) as resp:
                if resp.status == 201:
                    result = await resp.json()
                    context.user_data['current_profile_id'] = result['profile_id']
                    
                    text = f"""
✅ ПРОФИЛЬ СОЗДАН!
 
🎯 Вот что я про тебя знаю:
• Аккаунт: {profile_data['name']}
• Ниша: {profile_data['niche']}
• Аудитория: {profile_data['audience']}
• Стиль: {profile_data['voice']}
• Фишка: {profile_data['fleshy']}
 
🚀 Теперь я буду искать актуальные идеи СПЕЦИАЛЬНО ДЛЯ ТЕБЯ!
 
Каждый раз когда ты попросишь идеи:
1. Я ищу залетные рилсы в твоей нише
2. Анализирую что работает
3. Адаптирую под ТВОЙ стиль и фишку
4. Выдаю готовые идеи
 
Давай попробуем?
                    """
                    
                    keyboard = [
                        [InlineKeyboardButton("💡 Получить идеи", callback_data="get_ideas")],
                        [InlineKeyboardButton("➕ Ещё профиль", callback_data="create_profile")],
                        [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(text, reply_markup=reply_markup)
                    return ConversationHandler.END
    
    except Exception as e:
        logger.error(f"Ошибка при сохранении профиля: {e}")
        await update.message.reply_text("❌ Ошибка. Попробуй ещё раз.")
        return PROFILE_SUCCESSFUL
 
# ===== ПОЛУЧЕНИЕ ИДЕЙ =====
 
async def get_ideas_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Пользователь нажал "Получить идеи"
    """
    
    user_id = update.effective_user.id
    
    await update.callback_query.answer("⏳ Ищу актуальные залетные рилсы...", show_alert=False)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BACKEND_URL}/ideas/generate",
                params={'user_id': user_id}
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    await show_ideas(update, context, result['ideas'])
                else:
                    await update.callback_query.edit_message_text(
                        "❌ Ошибка при генерации. Попробуй ещё раз."
                    )
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.callback_query.edit_message_text(
            "❌ Что-то пошло не так. Попробуй позже."
        )
 
async def show_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE, ideas: list):
    """
    Показываем сгенерированные идеи
    """
    
    if not ideas or len(ideas) == 0:
        await update.callback_query.edit_message_text(
            "❌ Не получилось найти идеи. Попробуй ещё раз."
        )
        return
    
    idea = ideas[0]
    
    text = f"""
💡 ИДЕЯ #1
 
🎬 {idea.get('title', 'Название')}
 
🪝 ХУК (первые 0.5 сек):
{idea.get('hook', '')}
 
🎭 СЦЕНАРИЙ (как снимать):
{idea.get('scenario', '')}
 
🎵 ЗВУК/МУЗЫКА:
{idea.get('sound', '')}
 
⚡ ПОЧЕМУ ЭТО РАБОТАЕТ:
{idea.get('why_viral', '')}
 
📊 ИСТОЧНИК:
{idea.get('views', '100K+')} просмотров
 
#️⃣ ХЭШТЕГИ:
{' '.join(['#' + tag for tag in idea.get('hashtags', [])])}
    """
    
    keyboard = [
        [InlineKeyboardButton("➡️ Следующая", callback_data="next_idea")],
        [InlineKeyboardButton("❤️ Сохранить", callback_data="save_idea")],
        [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    context.user_data['current_ideas'] = ideas
    context.user_data['current_idea_index'] = 0
    
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
 
# ===== КНОПКИ =====
 
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка всех кнопок
    """
    
    query = update.callback_query
    await query.answer()
    
    if query.data == "create_profile":
        return await create_profile_start(update, context)
    
    elif query.data == "get_ideas":
        return await get_ideas_callback(update, context)
    
    elif query.data == "my_profiles":
        await query.edit_message_text("👤 Твои профили:\n\n(список)")
    
    elif query.data == "main_menu":
        await show_main_menu(update, context)
    
    elif query.data == "help":
        text = """
❓ КАК ЭТО РАБОТАЕТ?
 
1️⃣ ТЫ СОЗДАЁШЬ ПРОФИЛЬ
   Говоришь свою нишу, стиль, фишку
 
2️⃣ Я УЧУСЬ О ТЕБЕ
   Запоминаю как ты пишешь, что тебя выделяет
 
3️⃣ Я ИЩУ В ИНСТАГРАМЕ
   Каждый раз ищу залетные рилсы в ТВОЕЙ нише
 
4️⃣ Я АНАЛИЗИРУЮ ЧТО РАБОТАЕТ
   Хук, звук, структура, текст - всё
 
5️⃣ Я АДАПТИРУЮ ПОД ТЕБЯ
   Беру рабочие форматы и переделываю под твой стиль
 
6️⃣ ТЫ ПОЛУЧАЕШЬ ИДЕИ
   На основе ДОКАЗАННЫХ форматов которые дают 100K+
 
📊 РЕЗУЛЬТАТ:
Актуальные идеи которые реально работают в твоей нише!
        """
        
        keyboard = [
            [InlineKeyboardButton("✅ Создать профиль", callback_data="create_profile")],
            [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
 
# ===== ГЛАВНАЯ ФУНКЦИЯ =====
 
async def main():
    """
    Запуск бота
    """
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_profile_start, pattern="create_profile")],
        states={
            PROFILE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_name_handler)],
            PROFILE_NICHE: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_niche_handler)],
            PROFILE_AUDIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_audience_handler)],
            PROFILE_VOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_voice_handler)],
            PROFILE_SUCCESSFUL: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_fleshy_handler)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    await application.run_polling()
 
if __name__ == '__main__':
    asyncio.run(main())
 
