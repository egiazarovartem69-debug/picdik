import telebot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import sqlite3
import re
from datetime import datetime, timedelta
import time
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = '8791314159:AAEkTRKl6ki13fR1yEkeNzRn4gxMM2neKW0'
bot = telebot.TeleBot(TOKEN)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('group_admin.db')
    c = conn.cursor()
    
    # Таблица настроек групп
    c.execute('''CREATE TABLE IF NOT EXISTS group_settings
                 (group_id INTEGER PRIMARY KEY,
                  group_name TEXT,
                  admin_ids TEXT,
                  swear_action TEXT DEFAULT 'mute',
                  swear_duration INTEGER DEFAULT 1,
                  spam_action TEXT DEFAULT 'mute',
                  spam_duration INTEGER DEFAULT 1,
                  spam_message_limit INTEGER DEFAULT 3,
                  spam_time_window INTEGER DEFAULT 5,
                  job_spam_action TEXT DEFAULT 'ban',
                  job_spam_duration INTEGER DEFAULT 1440)''')
    
    # Таблица пользовательских матов
    c.execute('''CREATE TABLE IF NOT EXISTS custom_swear_words
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  group_id INTEGER,
                  word TEXT,
                  added_by INTEGER,
                  added_date TIMESTAMP,
                  FOREIGN KEY(group_id) REFERENCES group_settings(group_id))''')
    
    # Таблица пользовательских ключей для спам-работы
    c.execute('''CREATE TABLE IF NOT EXISTS custom_job_spam_words
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  group_id INTEGER,
                  word TEXT,
                  added_by INTEGER,
                  added_date TIMESTAMP,
                  FOREIGN KEY(group_id) REFERENCES group_settings(group_id))''')
    
    # Таблица для антиспама
    c.execute('''CREATE TABLE IF NOT EXISTS message_tracking
                 (user_id INTEGER,
                  group_id INTEGER,
                  message_count INTEGER DEFAULT 1,
                  first_message_time TIMESTAMP,
                  last_message_time TIMESTAMP,
                  PRIMARY KEY (user_id, group_id))''')
    
    # Таблица забаненных/замученных пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS restricted_users
                 (user_id INTEGER,
                  group_id INTEGER,
                  restriction_type TEXT,
                  until TIMESTAMP,
                  reason TEXT,
                  PRIMARY KEY (user_id, group_id))''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

# База стандартных матов
DEFAULT_SWEAR_WORDS = [
    'бля', 'хуй', 'пизд', 'ебл', 'ебат', 'сука', 'блять', 'нахуй',
    'пиздец', 'ебан', 'залупа', 'мудак', 'гандон', 'пидор', 'шлюха',
    'пох', 'хер', 'манда', 'петух', 'елда', 'срать', 'говно', 'жопа'
]

# База ключевых слов для спам-работы (РАСШИРЕННАЯ)
DEFAULT_JOB_SPAM_WORDS = [
    # Работа и заработок
    'работа', 'заработок', 'зароботок', 'заработать', 'зарплата',
    'вакансия', 'требуются', 'нужны люди', 'ищем сотрудников',
    'работа на дому', 'удаленная работа', 'работа в интернете',
    'подработка', 'дополнительный доход', 'пассивный доход',
    'легкий заработок', 'быстрый заработок', 'высокий доход',
    'работа без вложений', 'заработок без опыта',
    'работа для студентов', 'работа для мам в декрете',
    
    # Контакты
    'пиши в лс', 'стучи в лс', 'напиши в личку', 'пиши в личку',
    'телеграм @', 'тг @', 'тг канал', 'ссылка в профиле',
    'вацап', 'whatsapp', 'watsapp', 'telegram', 'номер телефона',
    'звони', 'позвони', 'напиши мне', 'свяжись со мной',
    
    # Закладки и наркотики
    'закладк', 'кладмен', 'курьер', 'доставщик',
    'меф', 'скорость', 'соль', 'спайс', 'микс',
    'кристаллы', 'шишки', 'бошки', 'трава', 'зелье',
    'заряды', 'товар', 'клад', 'приход',
    
    # Казино и ставки
    'казино', 'казик', 'вулкан', 'вавада', 'joycasino',
    'ставки', 'тотализатор', 'пари', 'bet', 'бет',
    'игровые автоматы', 'покер', 'рулетка',
    
    # Финансовые пирамиды
    'инвестиции', 'инвестировать', 'пассивный доход',
    'финансовая независимость', 'бизнес с нуля',
    'миллион', 'миллиард', 'разбогатеть',
    
    # Криптовалюты
    'крипта', 'криптовалюта', 'bitcoin', 'btc', 'eth',
    'майнинг', 'кран', 'airdrop', 'раздача крипты',
    
    # Реферальные системы
    'реферал', 'реферальная ссылка', 'реферальная программа',
    'партнерская программа', 'приглашай друзей',
    'за каждого друга', 'за приведенных',
    
    # Общие спам-фразы
    'легкие деньги', 'быстрые деньги', 'много денег',
    'доход от', 'пассивно', 'работай дома',
    'гибкий график', 'свободный график',
    'без начальников', 'сам себе хозяин',
    'не вкладывай', 'осторожно', 'проверено',
    'форекс', 'forex', 'трейдер', 'трейдинг',
    'инвестор', 'инвестирование',
]

# Вспомогательные функции
def is_user_admin(user_id, group_id):
    """Проверяет, является ли пользователь админом группы"""
    try:
        member = bot.get_chat_member(group_id, user_id)
        return member.status in ['administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking admin status for user {user_id}: {e}")
        return False

def is_bot_admin(group_id):
    """Проверяет, является ли бот администратором группы"""
    try:
        bot_member = bot.get_chat_member(group_id, bot.get_me().id)
        return bot_member.status in ['administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking bot admin status: {e}")
        return False

def add_admin_to_group(group_id, user_id, group_name=None):
    """Добавляет пользователя как админа группы в настройках"""
    conn = sqlite3.connect('group_admin.db')
    c = conn.cursor()
    
    c.execute('SELECT admin_ids, group_name FROM group_settings WHERE group_id = ?', (group_id,))
    result = c.fetchone()
    
    if result:
        admin_ids = result[0].split(',') if result[0] else []
        if str(user_id) not in admin_ids:
            admin_ids.append(str(user_id))
            c.execute('UPDATE group_settings SET admin_ids = ? WHERE group_id = ?',
                     (','.join(admin_ids), group_id))
    else:
        c.execute('INSERT INTO group_settings (group_id, group_name, admin_ids) VALUES (?, ?, ?)',
                 (group_id, group_name or f"Group_{group_id}", str(user_id)))
    
    conn.commit()
    conn.close()

def get_group_settings(group_id):
    """Получает настройки группы"""
    conn = sqlite3.connect('group_admin.db')
    c = conn.cursor()
    c.execute('SELECT * FROM group_settings WHERE group_id = ?', (group_id,))
    settings = c.fetchone()
    conn.close()
    return settings

def update_group_setting(group_id, setting, value):
    """Обновляет конкретную настройку группы"""
    conn = sqlite3.connect('group_admin.db')
    c = conn.cursor()
    c.execute(f'UPDATE group_settings SET {setting} = ? WHERE group_id = ?', (value, group_id))
    conn.commit()
    conn.close()
    logger.info(f"Updated {setting}={value} for group {group_id}")

def get_swear_words(group_id):
    """Получает список матов для группы (стандартные + пользовательские)"""
    conn = sqlite3.connect('group_admin.db')
    c = conn.cursor()
    c.execute('SELECT word FROM custom_swear_words WHERE group_id = ?', (group_id,))
    custom_words = [row[0] for row in c.fetchall()]
    conn.close()
    
    return DEFAULT_SWEAR_WORDS + custom_words

def get_job_spam_words(group_id):
    """Получает список ключей спам-работы (стандартные + пользовательские)"""
    conn = sqlite3.connect('group_admin.db')
    c = conn.cursor()
    c.execute('SELECT word FROM custom_job_spam_words WHERE group_id = ?', (group_id,))
    custom_words = [row[0] for row in c.fetchall()]
    conn.close()
    
    return DEFAULT_JOB_SPAM_WORDS + custom_words

def add_custom_swear_word(group_id, word, user_id):
    """Добавляет пользовательское матное слово"""
    conn = sqlite3.connect('group_admin.db')
    c = conn.cursor()
    
    c.execute('SELECT id FROM custom_swear_words WHERE group_id = ? AND word = ?', (group_id, word.lower()))
    if not c.fetchone():
        c.execute('INSERT INTO custom_swear_words (group_id, word, added_by, added_date) VALUES (?, ?, ?, ?)',
                 (group_id, word.lower(), user_id, datetime.now().isoformat()))
        conn.commit()
        result = True
    else:
        result = False
    
    conn.close()
    return result

def add_custom_job_spam_word(group_id, word, user_id):
    """Добавляет пользовательское ключевое слово для спам-работы"""
    conn = sqlite3.connect('group_admin.db')
    c = conn.cursor()
    
    c.execute('SELECT id FROM custom_job_spam_words WHERE group_id = ? AND word = ?', (group_id, word.lower()))
    if not c.fetchone():
        c.execute('INSERT INTO custom_job_spam_words (group_id, word, added_by, added_date) VALUES (?, ?, ?, ?)',
                 (group_id, word.lower(), user_id, datetime.now().isoformat()))
        conn.commit()
        result = True
    else:
        result = False
    
    conn.close()
    return result

def remove_custom_swear_word(group_id, word):
    """Удаляет пользовательское матное слово"""
    conn = sqlite3.connect('group_admin.db')
    c = conn.cursor()
    c.execute('DELETE FROM custom_swear_words WHERE group_id = ? AND word = ?', (group_id, word.lower()))
    conn.commit()
    conn.close()

def remove_custom_job_spam_word(group_id, word):
    """Удаляет пользовательское ключевое слово спам-работы"""
    conn = sqlite3.connect('group_admin.db')
    c = conn.cursor()
    c.execute('DELETE FROM custom_job_spam_words WHERE group_id = ? AND word = ?', (group_id, word.lower()))
    conn.commit()
    conn.close()

def apply_restriction(user_id, group_id, restriction_type, duration, reason=""):
    """Применяет ограничение к пользователю"""
    if not is_bot_admin(group_id):
        logger.warning(f"Cannot apply restriction: bot is not admin in group {group_id}")
        return False
    
    until = datetime.now() + timedelta(minutes=duration)
    
    conn = sqlite3.connect('group_admin.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO restricted_users (user_id, group_id, restriction_type, until, reason) VALUES (?, ?, ?, ?, ?)',
             (user_id, group_id, restriction_type, until.isoformat(), reason))
    conn.commit()
    conn.close()
    
    try:
        if restriction_type == 'ban':
            bot.ban_chat_member(group_id, user_id, until_date=until)
            logger.info(f"Banned user {user_id} in group {group_id} for {duration} min. Reason: {reason}")
            return True
        elif restriction_type == 'mute':
            bot.restrict_chat_member(group_id, user_id, until_date=until, can_send_messages=False)
            logger.info(f"Muted user {user_id} in group {group_id} for {duration} min. Reason: {reason}")
            return True
    except Exception as e:
        logger.error(f"Error applying restriction: {e}")
        return False

def check_spam(user_id, group_id):
    """Проверяет на спам (повторяющиеся сообщения)"""
    conn = sqlite3.connect('group_admin.db')
    c = conn.cursor()
    
    settings = get_group_settings(group_id)
    if not settings:
        conn.close()
        return False
    
    spam_limit = settings[7]  # spam_message_limit
    time_window = settings[8]  # spam_time_window
    
    now = datetime.now()
    
    c.execute('SELECT message_count, first_message_time FROM message_tracking WHERE user_id = ? AND group_id = ?',
             (user_id, group_id))
    result = c.fetchone()
    
    if result:
        count, first_time = result
        first_time = datetime.fromisoformat(first_time)
        
        if (now - first_time) > timedelta(minutes=time_window):
            c.execute('UPDATE message_tracking SET message_count = 1, first_message_time = ? WHERE user_id = ? AND group_id = ?',
                     (now.isoformat(), user_id, group_id))
            conn.commit()
            conn.close()
            return False
        
        if count >= spam_limit:
            conn.close()
            return True
        
        c.execute('UPDATE message_tracking SET message_count = message_count + 1 WHERE user_id = ? AND group_id = ?',
                 (user_id, group_id))
    else:
        c.execute('INSERT INTO message_tracking (user_id, group_id, message_count, first_message_time) VALUES (?, ?, 1, ?)',
                 (user_id, group_id, now.isoformat()))
    
    conn.commit()
    conn.close()
    return False

def contains_swear_words(text, swear_words):
    """Проверяет, содержит ли текст маты"""
    if not text:
        return False
    text_lower = text.lower()
    for word in swear_words:
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, text_lower) or word in text_lower:
            return True
    return False

def contains_job_spam(text, job_spam_words):
    """Проверяет, содержит ли текст спам-предложение работы"""
    if not text:
        return False
    text_lower = text.lower()
    
    # Проверяем по ключевым словам
    for word in job_spam_words:
        if word in text_lower:
            logger.info(f"Found job spam word '{word}' in text: {text[:50]}...")
            return True
    
    # Проверяем на наличие ссылок и контактов
    contact_patterns = [
        r'@\w+',  # юзернеймы
        r't\.me/\w+',  # телеграм ссылки
        r'https?://t\.me/\w+',
        r'whatsapp\.com',
        r'wa\.me/\w+',
        r'\+?\d[\d\-\(\) ]{8,}\d',  # номера телефонов
    ]
    
    for pattern in contact_patterns:
        if re.search(pattern, text_lower):
            logger.info(f"Found contact pattern in text: {text[:50]}...")
            return True
    
    return False

# Обработчики команд
@bot.message_handler(commands=['start'])
def start(message: Message):
    bot.reply_to(message, "👋 Привет! Я бот-администратор для групп.\n\n"
                          "Мои возможности:\n"
                          "• Фильтр мата с настраиваемыми санкциями\n"
                          "• Антиспам с настраиваемыми санкциями\n"
                          "• Анти-спам работа (блокировка спам-предложений работы)\n"
                          "• Личный кабинет для настройки\n\n"
                          "Добавьте меня в группу и сделайте администратором, "
                          "чтобы я начал работать!")

@bot.message_handler(commands=['admin'])
def admin_panel(message: Message):
    """Личный кабинет администратора"""
    if message.chat.type == 'private':
        bot.reply_to(message, "❌ Эта команда работает только в группах!")
        return
    
    user_id = message.from_user.id
    group_id = message.chat.id
    
    if not is_user_admin(user_id, group_id):
        bot.reply_to(message, "❌ Только администраторы группы могут использовать эту команду!")
        return
    
    if not is_bot_admin(group_id):
        bot.reply_to(message, "❌ Я не являюсь администратором группы!\n\n"
                              "Чтобы я мог работать:\n"
                              "1. Откройте информацию о группе\n"
                              "2. Нажмите 'Администраторы'\n"
                              "3. Добавьте бота\n"
                              "4. Дайте мне права:\n"
                              "   • Удаление сообщений\n"
                              "   • Блокировка пользователей\n"
                              "   • Ограничение прав\n\n"
                              "После этого напишите /admin снова")
        return
    
    add_admin_to_group(group_id, user_id, message.chat.title)
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📝 Настройки мата", callback_data="swear_settings"),
        InlineKeyboardButton("📊 Настройки спама", callback_data="spam_settings"),
        InlineKeyboardButton("💼 Анти-спам работа", callback_data="job_spam_settings"),
        InlineKeyboardButton("📚 Список матов", callback_data="list_swear"),
        InlineKeyboardButton("📋 Спам-слова работы", callback_data="list_job_spam"),
        InlineKeyboardButton("➕ Добавить слово", callback_data="add_word_menu"),
        InlineKeyboardButton("➖ Удалить слово", callback_data="remove_word_menu"),
        InlineKeyboardButton("ℹ️ Текущие настройки", callback_data="current_settings"),
        InlineKeyboardButton("🔄 Проверить права", callback_data="check_permissions")
    )
    
    bot.send_message(
        message.chat.id,
        f"👑 Панель администратора группы '{message.chat.title}'\n\n"
        f"✅ Я являюсь администратором и готов работать!\n"
        f"Выберите действие:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call: CallbackQuery):
    """Обработчик callback-запросов"""
    user_id = call.from_user.id
    group_id = call.message.chat.id
    
    if not is_user_admin(user_id, group_id):
        bot.answer_callback_query(call.id, "❌ Только администраторы могут это делать!")
        return
    
    settings = get_group_settings(group_id)
    if not settings:
        add_admin_to_group(group_id, user_id)
        settings = get_group_settings(group_id)
    
    # НАСТРОЙКИ МАТА
    if call.data == "swear_settings":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔇 Мут", callback_data="swear_action_mute"),
            InlineKeyboardButton("⛔️ Бан", callback_data="swear_action_ban"),
            InlineKeyboardButton("⏱ Длительность", callback_data="swear_duration"),
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin")
        )
        
        current_action = settings[3] if settings else "mute"
        current_duration = settings[4] if settings else "1"
        action_text = "🔇 Мут" if current_action == 'mute' else "⛔️ Бан"
        
        bot.edit_message_text(
            f"⚙️ Настройки фильтра мата\n\n"
            f"Текущее действие: {action_text}\n"
            f"Длительность: {current_duration} мин.\n\n"
            "Выберите действие для настройки:",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data == "swear_action_mute":
        update_group_setting(group_id, "swear_action", "mute")
        bot.answer_callback_query(call.id, "✅ Действие изменено на Мут")
        call.data = "swear_settings"
        callback_handler(call)
    
    elif call.data == "swear_action_ban":
        update_group_setting(group_id, "swear_action", "ban")
        bot.answer_callback_query(call.id, "✅ Действие изменено на Бан")
        call.data = "swear_settings"
        callback_handler(call)
    
    elif call.data == "swear_duration":
        markup = InlineKeyboardMarkup(row_width=3)
        markup.add(
            InlineKeyboardButton("1 мин", callback_data="swear_dur_1"),
            InlineKeyboardButton("5 мин", callback_data="swear_dur_5"),
            InlineKeyboardButton("10 мин", callback_data="swear_dur_10"),
            InlineKeyboardButton("30 мин", callback_data="swear_dur_30"),
            InlineKeyboardButton("1 час", callback_data="swear_dur_60"),
            InlineKeyboardButton("◀️ Назад", callback_data="swear_settings")
        )
        
        bot.edit_message_text(
            "⏱ Выберите длительность наказания за мат (в минутах):",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data.startswith("swear_dur_"):
        duration = int(call.data.split("_")[2])
        update_group_setting(group_id, "swear_duration", duration)
        bot.answer_callback_query(call.id, f"✅ Длительность изменена на {duration} минут")
        call.data = "swear_settings"
        callback_handler(call)
    
    # НАСТРОЙКИ СПАМА (повторяющиеся сообщения)
    elif call.data == "spam_settings":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔇 Мут", callback_data="spam_action_mute"),
            InlineKeyboardButton("⛔️ Бан", callback_data="spam_action_ban"),
            InlineKeyboardButton("⏱ Длительность", callback_data="spam_duration"),
            InlineKeyboardButton("📊 Лимиты", callback_data="spam_limits"),
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin")
        )
        
        current_action = settings[5] if settings else "mute"
        current_duration = settings[6] if settings else "1"
        current_limit = settings[7] if settings else "3"
        current_window = settings[8] if settings else "5"
        action_text = "🔇 Мут" if current_action == 'mute' else "⛔️ Бан"
        
        bot.edit_message_text(
            f"⚙️ Настройки антиспама (повторяющиеся сообщения)\n\n"
            f"Текущее действие: {action_text}\n"
            f"Длительность: {current_duration} мин.\n"
            f"Лимит сообщений: {current_limit} за {current_window} мин.\n\n"
            "Выберите действие для настройки:",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data == "spam_action_mute":
        update_group_setting(group_id, "spam_action", "mute")
        bot.answer_callback_query(call.id, "✅ Действие изменено на Мут")
        call.data = "spam_settings"
        callback_handler(call)
    
    elif call.data == "spam_action_ban":
        update_group_setting(group_id, "spam_action", "ban")
        bot.answer_callback_query(call.id, "✅ Действие изменено на Бан")
        call.data = "spam_settings"
        callback_handler(call)
    
    elif call.data == "spam_duration":
        markup = InlineKeyboardMarkup(row_width=3)
        markup.add(
            InlineKeyboardButton("1 мин", callback_data="spam_dur_1"),
            InlineKeyboardButton("5 мин", callback_data="spam_dur_5"),
            InlineKeyboardButton("10 мин", callback_data="spam_dur_10"),
            InlineKeyboardButton("30 мин", callback_data="spam_dur_30"),
            InlineKeyboardButton("1 час", callback_data="spam_dur_60"),
            InlineKeyboardButton("◀️ Назад", callback_data="spam_settings")
        )
        
        bot.edit_message_text(
            "⏱ Выберите длительность наказания за спам (в минутах):",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data.startswith("spam_dur_"):
        duration = int(call.data.split("_")[2])
        update_group_setting(group_id, "spam_duration", duration)
        bot.answer_callback_query(call.id, f"✅ Длительность изменена на {duration} минут")
        call.data = "spam_settings"
        callback_handler(call)
    
    elif call.data == "spam_limits":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📨 Лимит сообщений", callback_data="spam_msg_limit"),
            InlineKeyboardButton("⏱ Временное окно", callback_data="spam_time_window"),
            InlineKeyboardButton("◀️ Назад", callback_data="spam_settings")
        )
        
        bot.edit_message_text(
            "📊 Настройка лимитов спама\n\n"
            "• Лимит сообщений - сколько сообщений можно отправить\n"
            "• Временное окно - за какой период (в минутах)",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data == "spam_msg_limit":
        markup = InlineKeyboardMarkup(row_width=3)
        markup.add(
            InlineKeyboardButton("2", callback_data="spam_limit_2"),
            InlineKeyboardButton("3", callback_data="spam_limit_3"),
            InlineKeyboardButton("4", callback_data="spam_limit_4"),
            InlineKeyboardButton("5", callback_data="spam_limit_5"),
            InlineKeyboardButton("7", callback_data="spam_limit_7"),
            InlineKeyboardButton("10", callback_data="spam_limit_10"),
            InlineKeyboardButton("◀️ Назад", callback_data="spam_limits")
        )
        
        bot.edit_message_text(
            "📨 Выберите максимальное количество сообщений:",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data.startswith("spam_limit_"):
        limit = int(call.data.split("_")[2])
        update_group_setting(group_id, "spam_message_limit", limit)
        bot.answer_callback_query(call.id, f"✅ Лимит сообщений изменен на {limit}")
        call.data = "spam_limits"
        callback_handler(call)
    
    elif call.data == "spam_time_window":
        markup = InlineKeyboardMarkup(row_width=3)
        markup.add(
            InlineKeyboardButton("1 мин", callback_data="spam_window_1"),
            InlineKeyboardButton("3 мин", callback_data="spam_window_3"),
            InlineKeyboardButton("5 мин", callback_data="spam_window_5"),
            InlineKeyboardButton("10 мин", callback_data="spam_window_10"),
            InlineKeyboardButton("15 мин", callback_data="spam_window_15"),
            InlineKeyboardButton("30 мин", callback_data="spam_window_30"),
            InlineKeyboardButton("◀️ Назад", callback_data="spam_limits")
        )
        
        bot.edit_message_text(
            "⏱ Выберите временное окно (в минутах):",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data.startswith("spam_window_"):
        window = int(call.data.split("_")[2])
        update_group_setting(group_id, "spam_time_window", window)
        bot.answer_callback_query(call.id, f"✅ Временное окно изменено на {window} минут")
        call.data = "spam_limits"
        callback_handler(call)
    
    # НАСТРОЙКИ СПАМ-РАБОТЫ
    elif call.data == "job_spam_settings":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔇 Мут", callback_data="job_spam_action_mute"),
            InlineKeyboardButton("⛔️ Бан", callback_data="job_spam_action_ban"),
            InlineKeyboardButton("⏱ Длительность", callback_data="job_spam_duration"),
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin")
        )
        
        current_action = settings[9] if len(settings) > 9 else "ban"
        current_duration = settings[10] if len(settings) > 10 else 1440
        action_text = "🔇 Мут" if current_action == 'mute' else "⛔️ Бан"
        
        if current_duration == 999999:
            duration_text = "НАВСЕГДА"
        else:
            hours = current_duration / 60
            duration_text = f"{current_duration} мин. ({hours:.1f} ч.)"
        
        bot.edit_message_text(
            f"⚙️ Настройки анти-спам работа\n\n"
            f"Блокировка спам-предложений работы, наркотиков, казино и т.д.\n\n"
            f"Текущее действие: {action_text}\n"
            f"Длительность: {duration_text}\n\n"
            "Выберите действие для настройки:",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data == "job_spam_action_mute":
        update_group_setting(group_id, "job_spam_action", "mute")
        bot.answer_callback_query(call.id, "✅ Действие изменено на Мут")
        call.data = "job_spam_settings"
        callback_handler(call)
    
    elif call.data == "job_spam_action_ban":
        update_group_setting(group_id, "job_spam_action", "ban")
        bot.answer_callback_query(call.id, "✅ Действие изменено на Бан")
        call.data = "job_spam_settings"
        callback_handler(call)
    
    elif call.data == "job_spam_duration":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("1 час", callback_data="job_spam_dur_60"),
            InlineKeyboardButton("6 часов", callback_data="job_spam_dur_360"),
            InlineKeyboardButton("12 часов", callback_data="job_spam_dur_720"),
            InlineKeyboardButton("1 день", callback_data="job_spam_dur_1440"),
            InlineKeyboardButton("3 дня", callback_data="job_spam_dur_4320"),
            InlineKeyboardButton("7 дней", callback_data="job_spam_dur_10080"),
            InlineKeyboardButton("Навсегда", callback_data="job_spam_dur_999999"),
            InlineKeyboardButton("◀️ Назад", callback_data="job_spam_settings")
        )
        
        bot.edit_message_text(
            "⏱ Выберите длительность наказания для спам-работы:",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data.startswith("job_spam_dur_"):
        duration = int(call.data.split("_")[3])
        update_group_setting(group_id, "job_spam_duration", duration)
        
        if duration == 999999:
            bot.answer_callback_query(call.id, "✅ Наказание: НАВСЕГДА")
        else:
            hours = duration / 60
            bot.answer_callback_query(call.id, f"✅ Длительность изменена на {duration} мин. ({hours:.1f} часов)")
        
        call.data = "job_spam_settings"
        callback_handler(call)
    
    # СПИСКИ СЛОВ
    elif call.data == "list_swear":
        swear_words = get_swear_words(group_id)
        custom_words = []
        
        conn = sqlite3.connect('group_admin.db')
        c = conn.cursor()
        c.execute('SELECT word FROM custom_swear_words WHERE group_id = ?', (group_id,))
        custom_words = [row[0] for row in c.fetchall()]
        conn.close()
        
        text = "📚 Список отслеживаемых матов:\n\n"
        text += "🔹 Стандартные:\n"
        text += ", ".join(DEFAULT_SWEAR_WORDS) + "\n\n"
        
        if custom_words:
            text += "🔸 Добавленные пользователем:\n"
            text += ", ".join(custom_words)
        else:
            text += "🔸 Добавленные пользователем: пока нет"
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin"))
        
        bot.edit_message_text(
            text,
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data == "list_job_spam":
        job_spam_words = get_job_spam_words(group_id)
        custom_words = []
        
        conn = sqlite3.connect('group_admin.db')
        c = conn.cursor()
        c.execute('SELECT word FROM custom_job_spam_words WHERE group_id = ?', (group_id,))
        custom_words = [row[0] for row in c.fetchall()]
        conn.close()
        
        text = "📋 Список ключевых слов для спам-работы:\n\n"
        text += "🔹 Стандартные (первые 30):\n"
        text += ", ".join(DEFAULT_JOB_SPAM_WORDS[:30]) + "...\n\n"
        
        if custom_words:
            text += "🔸 Добавленные пользователем:\n"
            text += ", ".join(custom_words)
        else:
            text += "🔸 Добавленные пользователем: пока нет"
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin"))
        
        bot.edit_message_text(
            text,
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    # МЕНЮ ДОБАВЛЕНИЯ СЛОВ
    elif call.data == "add_word_menu":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("➕ Мат", callback_data="add_swear"),
            InlineKeyboardButton("➕ Спам-работа", callback_data="add_job_spam"),
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin")
        )
        
        bot.edit_message_text(
            "➕ Добавление слов\n\n"
            "Выберите тип слова для добавления:",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data == "add_swear":
        msg = bot.send_message(
            group_id,
            "✏️ Отправьте слово, которое хотите добавить в список МАТОВ:"
        )
        bot.register_next_step_handler(msg, process_add_swear, group_id)
    
    elif call.data == "add_job_spam":
        msg = bot.send_message(
            group_id,
            "✏️ Отправьте слово/фразу, которое хотите добавить в список СПАМ-РАБОТЫ:"
        )
        bot.register_next_step_handler(msg, process_add_job_spam, group_id)
    
    # МЕНЮ УДАЛЕНИЯ СЛОВ
    elif call.data == "remove_word_menu":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("➖ Мат", callback_data="remove_swear"),
            InlineKeyboardButton("➖ Спам-работа", callback_data="remove_job_spam"),
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin")
        )
        
        bot.edit_message_text(
            "➖ Удаление слов\n\n"
            "Выберите тип слова для удаления:",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data == "remove_swear":
        conn = sqlite3.connect('group_admin.db')
        c = conn.cursor()
        c.execute('SELECT word FROM custom_swear_words WHERE group_id = ?', (group_id,))
        custom_words = [row[0] for row in c.fetchall()]
        conn.close()
        
        if not custom_words:
            bot.answer_callback_query(call.id, "❌ Нет пользовательских матов для удаления!")
            return
        
        markup = InlineKeyboardMarkup(row_width=1)
        for word in custom_words:
            markup.add(InlineKeyboardButton(f"❌ {word}", callback_data=f"del_swear_{word}"))
        markup.add(InlineKeyboardButton("◀️ Назад", callback_data="remove_word_menu"))
        
        bot.edit_message_text(
            "Выберите мат для удаления:",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data.startswith("del_swear_"):
        word = call.data[10:]
        remove_custom_swear_word(group_id, word)
        bot.answer_callback_query(call.id, f"✅ Мат '{word}' удален")
        call.data = "list_swear"
        callback_handler(call)
    
    elif call.data == "remove_job_spam":
        conn = sqlite3.connect('group_admin.db')
        c = conn.cursor()
        c.execute('SELECT word FROM custom_job_spam_words WHERE group_id = ?', (group_id,))
        custom_words = [row[0] for row in c.fetchall()]
        conn.close()
        
        if not custom_words:
            bot.answer_callback_query(call.id, "❌ Нет пользовательских слов спам-работы для удаления!")
            return
        
        markup = InlineKeyboardMarkup(row_width=1)
        for word in custom_words:
            markup.add(InlineKeyboardButton(f"❌ {word}", callback_data=f"del_jobspam_{word}"))
        markup.add(InlineKeyboardButton("◀️ Назад", callback_data="remove_word_menu"))
        
        bot.edit_message_text(
            "Выберите слово для удаления:",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data.startswith("del_jobspam_"):
        word = call.data[12:]
        remove_custom_job_spam_word(group_id, word)
        bot.answer_callback_query(call.id, f"✅ Слово '{word}' удалено из спам-работы")
        call.data = "list_job_spam"
        callback_handler(call)
    
    # ТЕКУЩИЕ НАСТРОЙКИ
    elif call.data == "current_settings":
        if not settings:
            bot.answer_callback_query(call.id, "❌ Настройки не найдены")
            return
        
        swear_action = "🔇 Мут" if settings[3] == 'mute' else "⛔️ Бан"
        spam_action = "🔇 Мут" if settings[5] == 'mute' else "⛔️ Бан"
        job_action = "🔇 Мут" if settings[9] == 'mute' else "⛔️ Бан"
        
        job_duration = settings[10]
        if job_duration == 999999:
            job_duration_text = "НАВСЕГДА"
        else:
            hours = job_duration / 60
            job_duration_text = f"{job_duration} мин. ({hours:.1f} ч.)"
        
        text = f"ℹ️ Текущие настройки группы:\n\n"
        text += f"🔹 Фильтр мата:\n"
        text += f"  • Действие: {swear_action}\n"
        text += f"  • Длительность: {settings[4]} мин.\n\n"
        text += f"🔸 Антиспам (повторы):\n"
        text += f"  • Действие: {spam_action}\n"
        text += f"  • Длительность: {settings[6]} мин.\n"
        text += f"  • Лимит: {settings[7]} сообщений за {settings[8]} мин.\n\n"
        text += f"🔹 Анти-спам работа:\n"
        text += f"  • Действие: {job_action}\n"
        text += f"  • Длительность: {job_duration_text}"
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin"))
        
        bot.edit_message_text(
            text,
            group_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif call.data == "check_permissions":
        if is_bot_admin(group_id):
            bot.answer_callback_query(call.id, "✅ Бот является администратором!")
        else:
            bot.answer_callback_query(call.id, "❌ Бот НЕ является администратором!")
    
    elif call.data == "back_to_admin":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📝 Настройки мата", callback_data="swear_settings"),
            InlineKeyboardButton("📊 Настройки спама", callback_data="spam_settings"),
            InlineKeyboardButton("💼 Анти-спам работа", callback_data="job_spam_settings"),
            InlineKeyboardButton("📚 Список матов", callback_data="list_swear"),
            InlineKeyboardButton("📋 Спам-слова работы", callback_data="list_job_spam"),
            InlineKeyboardButton("➕ Добавить слово", callback_data="add_word_menu"),
            InlineKeyboardButton("➖ Удалить слово", callback_data="remove_word_menu"),
            InlineKeyboardButton("ℹ️ Текущие настройки", callback_data="current_settings"),
            InlineKeyboardButton("🔄 Проверить права", callback_data="check_permissions")
        )
        
        bot.edit_message_text(
            f"👑 Панель администратора\n\nВыберите действие:",
            group_id,
            call.message.message_id,
            reply_markup=markup
        )

def process_add_swear(message: Message, group_id):
    """Обработка добавления нового матного слова"""
    if not is_user_admin(message.from_user.id, group_id):
        bot.reply_to(message, "❌ Только администраторы могут это делать!")
        return
    
    word = message.text.strip().lower()
    
    if len(word) < 2:
        bot.reply_to(message, "❌ Слово слишком короткое!")
        return
    
    if word in DEFAULT_SWEAR_WORDS:
        bot.reply_to(message, f"❌ Слово '{word}' уже есть в стандартном списке!")
        return
    
    if add_custom_swear_word(group_id, word, message.from_user.id):
        bot.reply_to(message, f"✅ Слово '{word}' добавлено в список матов!")
    else:
        bot.reply_to(message, f"❌ Слово '{word}' уже есть в списке!")

def process_add_job_spam(message: Message, group_id):
    """Обработка добавления нового ключевого слова для спам-работы"""
    if not is_user_admin(message.from_user.id, group_id):
        bot.reply_to(message, "❌ Только администраторы могут это делать!")
        return
    
    word = message.text.strip().lower()
    
    if len(word) < 2:
        bot.reply_to(message, "❌ Слово слишком короткое!")
        return
    
    if word in DEFAULT_JOB_SPAM_WORDS:
        bot.reply_to(message, f"❌ Слово '{word}' уже есть в стандартном списке!")
        return
    
    if add_custom_job_spam_word(group_id, word, message.from_user.id):
        bot.reply_to(message, f"✅ Слово '{word}' добавлено в список спам-работы!")
    else:
        bot.reply_to(message, f"❌ Слово '{word}' уже есть в списке!")

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_chat_member(message: Message):
    """Обработка добавления бота в группу"""
    for member in message.new_chat_members:
        if member.id == bot.get_me().id:
            logger.info(f"Bot added to group {message.chat.id}")
            bot.reply_to(
                message,
                "👋 Спасибо что добавили меня в группу!\n"
                "Для работы мне нужны права администратора.\n"
                "После назначения админом используйте /admin для настройки."
            )
            
            if message.from_user:
                add_admin_to_group(message.chat.id, message.from_user.id, message.chat.title)

@bot.message_handler(content_types=['left_chat_member'])
def handle_left_chat_member(message: Message):
    """Обработка удаления бота из группы"""
    if message.left_chat_member.id == bot.get_me().id:
        logger.info(f"Bot removed from group {message.chat.id}")
        conn = sqlite3.connect('group_admin.db')
        c = conn.cursor()
        c.execute('DELETE FROM group_settings WHERE group_id = ?', (message.chat.id,))
        c.execute('DELETE FROM custom_swear_words WHERE group_id = ?', (message.chat.id,))
        c.execute('DELETE FROM custom_job_spam_words WHERE group_id = ?', (message.chat.id,))
        c.execute('DELETE FROM message_tracking WHERE group_id = ?', (message.chat.id,))
        c.execute('DELETE FROM restricted_users WHERE group_id = ?', (message.chat.id,))
        conn.commit()
        conn.close()

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message: Message):
    """Обработка всех текстовых сообщений"""
    if message.chat.type == 'private':
        return
    
    if message.text.startswith('/'):
        return
    
    user_id = message.from_user.id
    group_id = message.chat.id
    
    if not is_bot_admin(group_id):
        return
    
    if is_user_admin(user_id, group_id):
        return
    
    # Проверка на существующие ограничения
    conn = sqlite3.connect('group_admin.db')
    c = conn.cursor()
    c.execute('SELECT until FROM restricted_users WHERE user_id = ? AND group_id = ?', (user_id, group_id))
    restricted = c.fetchone()
    
    if restricted:
        until = datetime.fromisoformat(restricted[0])
        if datetime.now() < until:
            conn.close()
            try:
                bot.delete_message(group_id, message.message_id)
            except:
                pass
            return
        else:
            c.execute('DELETE FROM restricted_users WHERE user_id = ? AND group_id = ?', (user_id, group_id))
            conn.commit()
    conn.close()
    
    settings = get_group_settings(group_id)
    if not settings:
        return
    
    # 1. ПРОВЕРКА НА СПАМ-РАБОТУ (самое строгое наказание)
    job_spam_words = get_job_spam_words(group_id)
    if contains_job_spam(message.text, job_spam_words):
        action = settings[9] if len(settings) > 9 else "ban"
        duration = settings[10] if len(settings) > 10 else 1440
        
        logger.warning(f"⚠️ JOB SPAM: User {user_id} posted job spam in group {group_id}!")
        
        if apply_restriction(user_id, group_id, action, duration, "Спам-работа"):
            try:
                bot.delete_message(group_id, message.message_id)
                
                if duration == 999999:
                    duration_text = "НАВСЕГДА"
                else:
                    hours = duration / 60
                    duration_text = f"{duration} мин. ({hours:.1f} ч.)"
                
                bot.send_message(
                    group_id,
                    f"🚫 ПОЛЬЗОВАТЕЛЬ {message.from_user.first_name} ЗАБЛОКИРОВАН\n"
                    f"Причина: спам-предложение работы\n"
                    f"Наказание: {action} на {duration_text}"
                )
            except Exception as e:
                logger.error(f"Error handling job spam: {e}")
        return
    
    # 2. ПРОВЕРКА НА МАТ
    if message.text:
        swear_words = get_swear_words(group_id)
        if contains_swear_words(message.text, swear_words):
            action = settings[3]
            duration = settings[4]
            
            if apply_restriction(user_id, group_id, action, duration, "Мат"):
                try:
                    bot.delete_message(group_id, message.message_id)
                    bot.send_message(
                        group_id,
                        f"🚫 Пользователь {message.from_user.first_name} получил {action} на {duration} мин. за мат!"
                    )
                except Exception as e:
                    logger.error(f"Error handling swear: {e}")
            return
    
    # 3. ПРОВЕРКА НА СПАМ (повторяющиеся сообщения)
    if check_spam(user_id, group_id):
        action = settings[5]
        duration = settings[6]
        
        if apply_restriction(user_id, group_id, action, duration, "Спам (повторы)"):
            try:
                bot.delete_message(group_id, message.message_id)
                bot.send_message(
                    group_id,
                    f"🚫 Пользователь {message.from_user.first_name} получил {action} на {duration} мин. за спам!"
                )
            except Exception as e:
                logger.error(f"Error handling spam: {e}")
        return

# Запуск бота
if __name__ == '__main__':
    init_db()
    logger.info("=" * 50)
    logger.info("Бот запущен!")
    logger.info("Токен: " + TOKEN)
    logger.info("Нажмите Ctrl+C для остановки")
    logger.info("=" * 50)
    
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"Ошибка: {e}")