import telebot
import random
import datetime
import time 
from telebot import types
# --- ИЗМЕНЕНИЕ ЗДЕСЬ (v20) ---
from telebot.types import InlineQueryResultArticle, InputTextMessageContent
# --- Конец v20 ---

# --- НОВОЕ ДЛЯ RENDER (v17) ---
import os
from flask import Flask
from threading import Thread
# --- Конец v17 ---

# --- Вставьте сюда ваш токен от @BotFather ---
# !!! ВАЖНО: Мы оставим это пустым, так как Render добавит токен сам
BOT_TOKEN = os.environ.get('BOT_TOKEN') 
# ----------------------------------------------

# --- Создаем объект бота ---
bot = telebot.TeleBot(BOT_TOKEN)

# --- ИДЕЯ №5: Устанавливаем МЕНЮ КОМАНД (кнопка "Меню") ---
try:
    bot_commands = [
        types.BotCommand("start", "▶️ Старт / Игры (Личное меню)"),
        types.BotCommand("groupstats", "📊 Статистика игр"),
        types.BotCommand("go", "📣 Создать опрос (Кто идет?)") 
    ]
    
    # Меню будет устанавливаться при каждом запуске, это нормально для Render
    bot.set_my_commands(bot_commands) 
    
    print("Меню команд (возможно) обновлено!")
    
except Exception as e:
    print(f"Ошибка установки меню команд: {e}")
# -----------------------------------------------------------


# --- Наши "хранилища" данных в памяти ---
user_daily_stats = {} # Для "Градусника" и "Рулетки"
polls_data = {}       # Для ОПРОСОВ

# (v18) "Личные" меню
menu_owners = {}
user_menus = {}

# (v19) Антифлуд статистики
last_stats_message = {}

# --- ИЗМЕНЕНИЕ ЗДЕСЬ (v20) ---
# { user_id: chat_id }
# Хранит, в каком чате юзер играл в последний раз
user_last_active_chat = {}
# --- Конец v20 ---


# --- Тексты для удобства ---
MAIN_MENU_TEXT = "Докажи, что не терпила!:"

# --- ИДЕЯ №2: Функции "Градусника" ---

def get_krasavchik_comment(percent):
    """Возвращает смешной комментарий в зависимости от процента красоты."""
    if percent <= 20:
        return f"Сегодня я красавчик на {percent}%... 😅 (Лучше без зеркала)"
    elif percent <= 50:
        return f"Сегодня я красавчик на {percent}%! 😎 (Вполне себе, сойдет)"
    elif percent <= 80:
        return f"Сегодня я красавчик на {percent}%! 🔥 (Заявка на успех!)"
    else: # 81-100
        return f"Сегодня я красавчик на {percent}%! 👑 (ДА ТЫ КОРОЛЬ!)"

def get_loh_comment(percent):
    """Возвращает смешной комментарий в зависимости от процента "лоха"."""
    if percent <= 20:
        return f"Сегодня я лох всего на {percent}%! 🎉 (Ты в безопасности!)"
    elif percent <= 50:
        return f"Сегодня я лох на {percent}%. (Ну, бывает и хуже...)"
    elif percent <= 80:
        return f"Сегодня я лох на {percent}%... 😬 (Осторожнее, есть риски)"
    else: # 81-100
        return f"Сегодня я лох на {percent}%! 🤦‍♂️ (КОМБО! Лучше не рисковать)"

# --- Новая функция для "Измерителя" (v16) ---
def get_size_comment(cm):
    """Возвращает смешной комментарий в зависимости от размера."""
    if cm <= 5:
        return f"Сегодня у меня {cm} см... 🔬 (Микроскоп в студию!)"
    elif cm <= 10:
        return f"Сегодня у меня {cm} см. (Скромненько, но со вкусом)"
    elif cm <= 18:
        return f"Сегодня у меня {cm} см! 📏 (Золотая середина!)"
    elif cm <= 25:
        return f"Сегодня у меня {cm} см! 🔥 (Ого! Впечатляет!)"
    else: # 26-30
        return f"Сегодня у меня {cm} см! 🦄 (ГИГАНТ! Ты существуешь?!)"


# --- Функции для меню (v16) ---
def create_main_menu_markup():
    markup = types.InlineKeyboardMarkup(row_width=2) 
    btn1 = types.InlineKeyboardButton(
        "Красавчик 😎", 
        callback_data="ask_krasavchik"
    )
    btn2 = types.InlineKeyboardButton(
        "Лох 😅", 
        callback_data="ask_loh"
    )
    # Новая кнопка "Измерителя"
    btn5 = types.InlineKeyboardButton(
        "Мой размер 🍆", 
        callback_data="ask_size"
    )
    btn3 = types.InlineKeyboardButton(
        "📊 Статистика", 
        callback_data="show_group_stats"
    )
    btn4 = types.InlineKeyboardButton(
        "🇺🇦 Русская рулетка", 
        callback_data="roulette_play_next" 
    )
    
    markup.add(btn1, btn2, btn5, btn3, btn4)
    return markup

# --- Обработчик /start (v19) ---
@bot.message_handler(commands=['start', 'play'])
def send_choice_menu(message):
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # 1. Антифлуд: Удаляем команду /start
    try:
        bot.delete_message(chat_id, message.message_id)
        print(f"Удалена команда {message.message_id} от {user_id}")
    except telebot.apihelper.ApiTelegramException as e:
        print(f"Не смог удалить команду /start (нет прав?): {e}")

    # 2. Антифлуд: Проверяем, есть ли у юзера старое меню
    if user_id in user_menus:
        old_menu_id = user_menus[user_id]
        # Пытаемся удалить старое меню
        try:
            bot.delete_message(chat_id, old_menu_id)
            print(f"Удалено старое меню {old_menu_id} для {user_id}")
        except telebot.apihelper.ApiTelegramException as e:
            print(f"Не смог удалить старое меню (уже удалено?): {e}")
        
        # Удаляем старые записи
        if old_menu_id in menu_owners:
            del menu_owners[old_menu_id]
        del user_menus[user_id]

    # 3. Отправляем новое меню
    new_menu_msg = bot.send_message(
        chat_id, 
        MAIN_MENU_TEXT, 
        reply_markup=create_main_menu_markup()
    )
    
    # 4. Привязываем меню к пользователю
    new_menu_id = new_menu_msg.message_id
    menu_owners[new_menu_id] = user_id
    user_menus[user_id] = new_menu_id
    
    print(f"Создано новое меню {new_menu_id} для {user_id}")


# --- Обработчик команды /groupstats (v19) ---
@bot.message_handler(commands=['groupstats'])
def send_group_stats(message):
    chat_id = message.chat.id
    today_str = str(datetime.date.today())

    try:
        # 1. Антифлуд: Удаляем команду /groupstats
        try:
            bot.delete_message(chat_id, message.message_id)
            print(f"Удалена команда /groupstats {message.message_id}")
        except telebot.apihelper.ApiTelegramException as e:
            print(f"Не смог удалить команду /groupstats (нет прав?): {e}")
        
        # 2. Антифлуд: Удаляем СТАРЫЙ отчет бота
        if chat_id in last_stats_message:
            try:
                bot.delete_message(chat_id, last_stats_message[chat_id])
                print(f"Удален старый отчет {last_stats_message[chat_id]}")
            except telebot.apihelper.ApiTelegramException as e:
                print(f"Не смог удалить старый отчет (уже удален?): {e}")

        # 3. Проверяем, это личная переписка или группа
        if message.chat.type == "private":
            bot.send_message(chat_id, "Эта команда предназначена для групповых чатов. Просто нажми /start, чтобы узнать *свои* проценты.")
            return
            
        # 4. Проверяем, есть ли данные за сегодня по этому чату
        if chat_id not in user_daily_stats or user_daily_stats[chat_id]['date'] != today_str:
            bot.send_message(chat_id, f"Статистика за {today_str} в этом чате еще не собрана. \nНажмите /start и сыграйте!")
            return
            
        # 5. Словарь со статистикой этого чата
        stats_for_this_chat_dict = user_daily_stats[chat_id]['users']
        
        if not stats_for_this_chat_dict:
            bot.send_message(chat_id, "Пока никто не играл сегодня в этом чате. \nНажмите /start, чтобы быть первым!")
            return
            
        # 6. Формируем основной список
        report_lines = [f"📊 Статистика ИГР в этом чате за {today_str}:\n"]
        
        # Сортируем по "красавчику"
        sorted_users_list = sorted(stats_for_this_chat_dict.items(), key=lambda item: item[1]['krasavchik'], reverse=True)
        
        for user_id, data in sorted_users_list:
            # Используем .replace() для безопасности HTML
            user_name_safe = data['name'].replace('<', '&lt;').replace('>', '&gt;')
            
            # Собираем статистику по рулетке
            best_streak = data.get('roulette_best_streak', 0)
            roulette_stat_str = ""
            if best_streak > 0:
                roulette_stat_str = f" | Рулетка: 🏆 {best_streak} подряд"
            
            # Собираем статистику по "Размеру"
            size = data.get('size', 0)
            size_stat_str = ""
            if size > 0:
                size_stat_str = f" | Размер: 🍆 {size} см"

            report_lines.append(f" - <b>{user_name_safe}</b>: Красавчик {data['krasavchik']}%, Лох {data['loh']}%{size_stat_str}{roulette_stat_str}")
            
        # 7. Находим "Королей"
        king_data = max(stats_for_this_chat_dict.values(), key=lambda user_data: user_data['krasavchik'])
        loser_data = max(stats_for_this_chat_dict.values(), key=lambda user_data: user_data['loh'])
        
        # 8. Готовим имена для HTML
        king_name_safe = king_data['name'].replace('<', '&lt;').replace('>', '&gt;')
        loser_name_safe = loser_data['name'].replace('<', '&lt;').replace('>', '&gt;')
        
        # 9. Добавляем номинации в отчет
        report_lines.append(f"\n👑 <b>Царь Красавчиков сегодня:</b> {king_name_safe} ({king_data['krasavchik']}%)")
        report_lines.append(f"🤦‍♂️ <b>Главный Лох дня:</b> {loser_name_safe} ({loser_data['loh']}%)")

        # Находим "Короля Удачи"
        luckiest_data = max(stats_for_this_chat_dict.values(), key=lambda user_data: user_data.get('roulette_best_streak', 0))
        if luckiest_data.get('roulette_best_streak', 0) > 0:
            luckiest_name_safe = luckiest_data['name'].replace('<', '&lt;').replace('>', '&gt;')
            report_lines.append(f"🏆 <b>Король Удачи:</b> {luckiest_name_safe} (выжил {luckiest_data['roulette_best_streak']} раз подряд!)")

        # Находим "Главного Гиганта"
        biggest_data = max(stats_for_this_chat_dict.values(), key=lambda user_data: user_data.get('size', 0))
        if biggest_data.get('size', 0) > 0:
            biggest_name_safe = biggest_data['name'].replace('<', '&lt;').replace('>', '&gt;')
            report_lines.append(f"🍆 <b>Главный Гигант:</b> {biggest_name_safe} ({biggest_data['size']} см)")
            
        # 10. Отправляем НОВЫЙ отчет и СОХРАНЯЕМ его ID
        stats_msg = bot.send_message(chat_id, "\n".join(report_lines), parse_mode="HTML")
        last_stats_message[chat_id] = stats_msg.message_id

    except Exception as e:
        # Добавляем отлов ошибок, чтобы бот не падал
        print(f"!!! ОШИБКА в send_group_stats: {e}")
        bot.send_message(message.chat.id, "Ой, что-то пошло не так при подсчете статистики...")


# --- ОБРАБОТЧИК ОПРОСОВ /go (v17) ---

def format_poll_text(poll_data):
    """
    Вспомогательная функция для генерации ТЕКСТА опроса
    со списками имен.
    """
    question = poll_data['question']
    
    # Собираем списки имен
    names_going = [name.replace('<', '&lt;').replace('>', '&gt;') for name in poll_data['going'].values()]
    names_not_going = [name.replace('<', '&lt;').replace('>', '&gt;') for name in poll_data['not_going'].values()]
    
    text_going = " - (пока нет)"
    if names_going:
        text_going = "\n".join([f" - <b>{name}</b>" for name in names_going])
        
    text_not_going = " - (пока нет)"
    if names_not_going:
        text_not_going = "\n".join([f" - {name}" for name in names_not_going]) # Менее важно, не выделяем
        
    final_text = f"📣 <b>ОПРОС:</b> {question.replace('<', '&lt;').replace('>', '&gt;')}\n" \
                 f"--------------------\n" \
                 f"👍 <b>Идут ({len(names_going)}):</b>\n{text_going}\n\n" \
                 f"👎 <b>Пас ({len(names_not_going)}):</b>\n{text_not_going}"
                 
    return final_text

def create_poll_markup(poll_data):
    """
    Вспомогательная функция для генерации КНОПОК опроса
    (теперь она не меняет счетчики, они в тексте)
    """
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_go = types.InlineKeyboardButton(f"Я иду! 👍", callback_data="poll_go")
    btn_pass = types.InlineKeyboardButton(f"Я пас 👎", callback_data="poll_pass")
    btn_close = types.InlineKeyboardButton("🔒 Закрыть опрос", callback_data="poll_close")
    markup.add(btn_go, btn_pass, btn_close)
    return markup

@bot.message_handler(commands=['go'])
def create_poll_handler(message):
    chat_id = message.chat.id
    creator_id = message.from_user.id
    
    # Мы НЕ удаляем команду /go, так как в ней содержится вопрос!
    
    # Получаем текст вопроса (всё, что после /go )
    question = message.text[len('/go '):].strip()
    
    # Проверка, что вопрос не пустой
    if not question:
        bot.send_message(chat_id, "Вы не задали вопрос! \nПример: `/go Кто идет в кино?`", parse_mode="Markdown")
        return
        
    try:
        # 1. Создаем "пустые" данные для опроса
        poll_data = {
            'question': question,
            'creator_id': creator_id,
            'going': {}, # Теперь это словарь {user_id: 'name'}
            'not_going': {} # Теперь это словарь {user_id: 'name'}
        }
        
        # 2. Генерируем текст и кнопки
        poll_text = format_poll_text(poll_data)
        markup = create_poll_markup(poll_data)
        
        # 3. Отправляем сообщение с опросом
        poll_message = bot.send_message(chat_id, poll_text, parse_mode="HTML", reply_markup=markup)
        
        # 4. Сохраняем опрос в наше хранилище, используя ID сообщения как ключ
        polls_data[poll_message.message_id] = poll_data
        
    except Exception as e:
        print(f"!!! ОШИБКА в create_poll_handler: {e}")
        bot.send_message(chat_id, "Ой, не смог создать опрос...")

# --- Конец v17 ---


# --- ИЗМЕНЕНИЕ ЗДЕСЬ (v20) ---
# --- НОВЫЙ ОБРАБОТЧИК INLINE РЕЖИМА ---
@bot.inline_query_handler(func=lambda query: True)
def handle_inline_query(query):
    user_id = query.from_user.id
    user_name = query.from_user.first_name.replace('<', '&lt;').replace('>', '&gt;')
    today_str = str(datetime.date.today())
    results = []

    try:
        # 1. Найти последнюю активную сессию пользователя
        chat_id = user_last_active_chat.get(user_id)
        
        # 2. Проверить, есть ли у него сегодняшняя статистика в этом чате
        stats = None
        if chat_id:
            if (chat_id in user_daily_stats and 
                user_daily_stats[chat_id]['date'] == today_str and
                user_id in user_daily_stats[chat_id]['users']):
                stats = user_daily_stats[chat_id]['users'][user_id]
        
        # 3. Если статистика НАЙДЕНА, генерируем 4 результата
        if stats:
            # A. Красавчик
            kras_percent = stats.get('krasavchik', 0)
            kras_title = f"Поделиться % Красавчика ({kras_percent}%)"
            kras_msg = f"⚡ {user_name} сегодня красавчик на {kras_percent}%!"
            results.append(
                InlineQueryResultArticle(
                    id='1', 
                    title=kras_title, 
                    description=get_krasavchik_comment(kras_percent),
                    input_message_content=InputTextMessageContent(kras_msg)
                )
            )
            
            # B. Лох
            loh_percent = stats.get('loh', 0)
            loh_title = f"Поделиться % Лоха ({loh_percent}%)"
            loh_msg = f"⚡ {user_name} сегодня лох на {loh_percent}%."
            results.append(
                InlineQueryResultArticle(
                    id='2', 
                    title=loh_title, 
                    description=get_loh_comment(loh_percent),
                    input_message_content=InputTextMessageContent(loh_msg)
                )
            )
            
            # C. Размер
            size = stats.get('size', 0)
            size_title = f"Поделиться Размером (🍆 {size} см)"
            size_msg = f"⚡ {user_name} измерил свой размер: 🍆 {size} см!"
            results.append(
                InlineQueryResultArticle(
                    id='3', 
                    title=size_title, 
                    description=get_size_comment(size),
                    input_message_content=InputTextMessageContent(size_msg)
                )
            )
            
            # D. Рулетка
            streak = stats.get('roulette_best_streak', 0)
            roulette_title = f"Поделиться рекордом в Рулетке (🏆 {streak})"
            roulette_msg = f"⚡ {user_name} поставил(а) рекорд в рулетке: 🏆 {streak} выстрелов подряд!"
            results.append(
                InlineQueryResultArticle(
                    id='4', 
                    title=roulette_title, 
                    description=f"Лучшая серия выживания: {streak}",
                    input_message_content=InputTextMessageContent(roulette_msg)
                )
            )
            
        # 4. Если статистика НЕ НАЙДЕНА (не играл, или бот перезагрузился)
        else:
            results.append(
                InlineQueryResultArticle(
                    id='1', 
                    title="Нет данных для шеринга", 
                    description="Напишите /start в группе, чтобы сначала сыграть!",
                    input_message_content=InputTextMessageContent(f"{user_name}, я не могу найти твою статистику. Сыграй в группе!")
                )
            )
            
        # Отвечаем на запрос
        # cache_time=10 - кэшируем результат всего на 10 секунд
        bot.answer_inline_query(query.id, results, cache_time=10)

    except Exception as e:
        print(f"!!! ОШИБКА в handle_inline_query: {e}")
# --- Конец v20 ---


# --- ОСНОВНОЙ ОБРАБОТчик КНОПОК (ИЗМЕНЕН v20) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """
    Обрабатывает ВСЕ нажатия на инлайн-кнопки.
    """
    
    today_str = str(datetime.date.today())
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    user_name = call.from_user.first_name 

    try:
        # --- ОБРАБОТКА ОПРОСА (v17) ---
        # Опросы - ПУБЛИЧНЫЕ, их может нажимать любой.
        if call.data.startswith('poll_'):
            
            # 1. Находим данные опроса (по ID сообщения)
            poll_data = polls_data.get(message_id)
            if not poll_data:
                # Это старый опрос, кнопки уже неактивны
                bot.answer_callback_query(call.id, "Этот опрос уже закрыт.", show_alert=True)
                return

            # 2. Обрабатываем нажатие
            if call.data == "poll_go":
                poll_data['going'][user_id] = user_name
                poll_data['not_going'].pop(user_id, None) # Убираем, если передумал
                bot.answer_callback_query(call.id, "Вы записались! 👍")
                
            elif call.data == "poll_pass":
                poll_data['not_going'][user_id] = user_name
                poll_data['going'].pop(user_id, None) # Убираем, если передумал
                bot.answer_callback_query(call.id, "Вы 'пасуете' 👎")
                
            elif call.data == "poll_close":
                # Проверяем, что это создатель
                if user_id != poll_data['creator_id']:
                    bot.answer_callback_query(call.id, "Закрыть опрос может только его создатель!", show_alert=True)
                    return
                
                # Закрываем опрос
                final_text = format_poll_text(poll_data) # Форматируем с именами
                final_text = f"<b>ОПРОС ЗАВЕРШЕН:</b>\n{final_text}" # Добавляем заголовок
                             
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, parse_mode="HTML", reply_markup=None)
                # Удаляем опрос из памяти
                del polls_data[message_id]
                return

            # 3. Обновляем ТЕКСТ сообщения с новым списком имен
            new_text = format_poll_text(poll_data)
            new_markup = create_poll_markup(poll_data)
            
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=new_text, parse_mode="HTML", reply_markup=new_markup)
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" in str(e):
                    pass # Игнорируем, если пользователь 2 раза нажал одно и то же
                else:
                    raise e # Поднимаем другую ошибку
            return # Выходим, т.к. это был опрос
            
        # --- Конец блока ОПРОСОВ (v17) ---

        
        # --- ПРОВЕРКА "ВЛАДЕЛЬЦА" МЕНЮ (v18) ---
        # Если это не опрос, значит, это игровое меню. Проверим, кто его нажал.
        
        owner_id = menu_owners.get(message_id)
        
        # Если меню не найдено в "базе" (например, бот перезагрузился)
        if not owner_id:
            bot.answer_callback_query(call.id, "Это игровое меню устарело. Напишите /start", show_alert=True)
            return
            
        # Если нажал НЕ владелец
        if owner_id != user_id:
            bot.answer_callback_query(call.id, "Это не твое меню! Напиши /start, чтобы получить свое.", show_alert=True)
            return
        
        # --- Конец v18 ---


        # (Если это не кнопка опроса, продолжаем как обычно)
        bot.answer_callback_query(call.id)
        
        # --- ИДЕЯ №3 + ИДЕЯ №5: Логика статистики (адаптирована под группы) ---
        
        # 1. Проверяем, есть ли запись для этого ЧАТА
        if chat_id not in user_daily_stats:
            user_daily_stats[chat_id] = {'date': today_str, 'users': {}}
            
        # 2. Проверяем, не устарела ли дата для этого ЧАТА
        if user_daily_stats[chat_id]['date'] != today_str:
            user_daily_stats[chat_id] = {'date': today_str, 'users': {}}
            
        # 3. Проверяем, есть ли у ПОЛЬЗОВАТЕЛЯ % в ЭТОМ ЧАТЕ
        if user_id not in user_daily_stats[chat_id]['users']:
            user_daily_stats[chat_id]['users'][user_id] = {
                'krasavchik': random.randint(0, 100),
                'loh': random.randint(0, 100),
                'name': user_name,
                'size': random.randint(1, 30), # Добавляем генерацию размера
                'roulette_best_streak': 0,    
                'roulette_current_streak': 0  
            }

        # Теперь у нас 100% есть актуальные данные
        current_stats = user_daily_stats[chat_id]['users'][user_id]
        
        # Убедимся, что у старых пользователей есть новые поля
        if 'roulette_best_streak' not in current_stats:
            current_stats['roulette_best_streak'] = 0
        if 'roulette_current_streak' not in current_stats:
            current_stats['roulette_current_streak'] = 0
        if 'size' not in current_stats:
             current_stats['size'] = random.randint(1, 30) # Добавляем для тех, кто играл до v16

        
        # Готовим клавиатуру "Назад" (для "смерти" или выхода)
        back_markup = types.InlineKeyboardMarkup(row_width=1)
        back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data="go_back_to_menu")
        back_markup.add(back_btn)


        # --- ОБРАБОТКА КНОПКИ "НАЗАД" (v14) ---
        if call.data == "go_back_to_menu":
            # Когда выходим из рулетки, надо сохранить счет
            current_streak = current_stats.get('roulette_current_streak', 0)
            if current_streak > current_stats.get('roulette_best_streak', 0):
                current_stats['roulette_best_streak'] = current_streak
            # Сбрасываем текущую игру
            current_stats['roulette_current_streak'] = 0
            
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=MAIN_MENU_TEXT,
                reply_markup=create_main_menu_markup()
            )
            return

        # --- ОБРАБОТКА КНОПKI СТАТИСТИКИ (v11) ---
        if call.data == "show_group_stats":
            # Вызываем функцию, которая ОТПРАВИТ новое сообщение
            send_group_stats(call.message)
            return

        # --- ИДЕЯ №6: АНИМАЦИЯ РУЛЕТКИ (v16) ---
        
        final_text = ""
        animation_prefix = ""
        is_standard_roulette_animation = False 
        is_size_animation = False # Новый флаг для анимации "Размера"
        # --- ИЗМЕНЕНИЕ ЗДЕСЬ (v20) ---
        is_game_played = False # Флаг, что игра была сыграна
        # --- Конец v20 ---

        
        if call.data == "ask_krasavchik":
            percent = current_stats['krasavchik']
            final_text = get_krasavchik_comment(percent)
            animation_prefix = "😎 Красавчик"
            is_standard_roulette_animation = True 
            is_game_played = True # (v20)
            
        elif call.data == "ask_loh":
            percent = current_stats['loh']
            final_text = get_loh_comment(percent)
            animation_prefix = "😅 Лох"
            is_standard_roulette_animation = True 
            is_game_played = True # (v20)
        
        elif call.data == "ask_size":
            size = current_stats['size']
            final_text = get_size_comment(size)
            animation_prefix = "🍆 Мой размер"
            is_size_animation = True # Включаем новую анимацию
            is_game_played = True # (v20)
        
        elif call.data == "roulette_play_next":
            
            # 1. Получаем текущую серию
            current_streak = current_stats.get('roulette_current_streak', 0)
            current_chance = current_streak + 1
            max_chance = 6
            
            # (Анимация)
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🌀 Кручу барабан... (Шанс {current_chance}/{max_chance})")
                time.sleep(0.6)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🔫 Приставляю к виску...")
                time.sleep(0.6)
            except telebot.apihelper.ApiTelegramException: pass # Игнорируем ошибки

            # 2. Считаем результат
            shot = random.randint(1, max_chance)
            is_dead = (shot <= current_chance)
            
            if is_dead: 
                final_text = f"💥 БАМ! ({current_chance}/{max_chance}). Твоя удача кончилась на {current_chance}-м выстреле!"
                
                # Сохраняем ЛУЧШУЮ серию (это была серия *до* этого выстрела)
                if current_streak > current_stats['roulette_best_streak']:
                    current_stats['roulette_best_streak'] = current_streak
                # Сбрасываем ТЕКУЩУЮ серию
                current_stats['roulette_current_streak'] = 0
                
                # Показываем результат и кнопку "Назад"
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, reply_markup=back_markup)
                
                # --- ИЗМЕНЕНИЕ ЗДЕСЬ (v20) ---
                user_last_active_chat[user_id] = chat_id # Запоминаем чат
                # --- Конец v20 ---
                return # Выходим из функции

            else: # ВЫЖИЛ
                # Увеличиваем текущую серию
                current_stats['roulette_current_streak'] += 1
                new_streak = current_stats['roulette_current_streak']
                
                # Готовим кнопки "Продолжить" / "Стоп"
                continue_markup = types.InlineKeyboardMarkup(row_width=1)
                
                # Проверяем, не был ли это 5-й (последний удачный) выстрел
                if new_streak == max_chance - 1: # Т.е. серия стала 5 (5/6)
                    final_text = f"💨 Щелк! ({current_chance}/{max_chance}). НЕВЕРОЯТНО! Ты выжил... \nНо в барабане 100% остался 1 патрон."
                    # Кнопка на 6-й, 100% смертельный выстрел
                    continue_btn = types.InlineKeyboardButton(f"Сделать выстрел (Шанс 6/6)", callback_data="roulette_play_next")
                else:
                    final_text = f"💨 Щелк! ({current_chance}/{max_chance}). Пронесло... Рискнешь еще?"
                    continue_btn = types.InlineKeyboardButton(f"Играть дальше (Шанс {new_streak + 1}/{max_chance})", callback_data="roulette_play_next")
                
                # Кнопка "Забрать выигрыш"
                stop_btn = types.InlineKeyboardButton(f"🚫 Хватит (сохранить серию: {new_streak})", callback_data="go_back_to_menu")
                continue_markup.add(continue_btn, stop_btn)
                
                # Показываем результат и 2 кнопки
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, reply_markup=continue_markup)
                
                # --- ИЗМЕНЕНИЕ ЗДЕСЬ (v20) ---
                user_last_active_chat[user_id] = chat_id # Запоминаем чат
                # --- Конец v20 ---
                return # Выходим из функции
            
            
        # Если была нажата одна из кнопок "Градусника" или "Размера"
        if final_text:
            
            # Анимация для "Градусников"
            if is_standard_roulette_animation:
                # Запускаем анимацию (6 "прокруток")
                for i in range(6): 
                    try:
                        fake_percent = random.randint(0, 100)
                        emoji = "🎰" if i < 5 else "🎲" 
                        
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=f"{emoji} {animation_prefix}: Кручу... {fake_percent}%"
                        )
                        time.sleep(0.4) # Пауза 0.4 секунды
                    
                    except telebot.apihelper.ApiTelegramException as e:
                        if "message is not modified" in str(e): pass 
                        else: print(f"Ошибка в цикле анимации: {e}")
            
            # Новая анимация для "Размера"
            elif is_size_animation:
                 # Запускаем анимацию (6 "прокруток")
                for i in range(6): 
                    try:
                        fake_size = random.randint(1, 30)
                        emoji = "🎰" if i < 5 else "📏" 
                        
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=f"{emoji} {animation_prefix}: Измеряю... {fake_size} см"
                        )
                        time.sleep(0.4) # Пауза 0.4 секунды
                    
                    except telebot.apihelper.ApiTelegramException as e:
                        if "message is not modified" in str(e): pass 
                        else: print(f"Ошибка в цикле анимации: {e}")
                    
            # Показываем финальный результат
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=final_text,
                reply_markup=back_markup
            )
            
            # --- ИЗМЕНЕНИЕ ЗДЕСЬ (v20) ---
            # Если игра была сыграна (Красавчик, Лох, Размер),
            # запоминаем этот чат как последний активный
            if is_game_played:
                user_last_active_chat[user_id] = chat_id
            # --- Конец v20 ---

    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" in str(e):
            pass 
        else:
            print(f"Произошла ошибка (возможно, сообщение удалено): {e}")

# --- НОВОЕ ДЛЯ RENDER (v17) ---
# Этот код запустит Flask-сервер в отдельном потоке
# чтобы "обмануть" Render и не дать ему "уснуть"
app = Flask(__name__)

@app.route('/')
def home():
    # Ответ "Пингеру"
    return "Я жив, бот работает!"

def run():
    # Render сам выдаст порт в переменной $PORT
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

def start_server():
    # Запускаем веб-сервер в отдельном потоке
    t = Thread(target=run)
    t.start()
# --- Конец v17 ---

# Запускаем бота
print("Starting the web server to keep bot alive...")
start_server()
print("Starting the bot polling...")
bot.polling(none_stop=True)
