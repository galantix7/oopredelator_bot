import telebot
import random
import datetime
import time 
from telebot import types

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
        types.BotCommand("start", "▶️ Старт / Игры"),
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

# --- ИЗМЕНЕНИЕ ЗДЕСЬ (v17) ---
polls_data = {}       # Структура: { message_id: {'question': '...', 'creator_id': ..., 'going': {user_id: 'name'}, 'not_going': {user_id: 'name'}} }
# --- Конец v17 ---


# --- Тексты для удобства ---
MAIN_MENU_TEXT = "Докажи, кто тут лошара:"

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
        "📊 Статистика дня", 
        callback_data="show_group_stats"
    )
    btn4 = types.InlineKeyboardButton(
        "🇺🇦 Русская рулетка", 
        callback_data="roulette_play_next" 
    )
    
    markup.add(btn1, btn2, btn5, btn3, btn4)
    return markup

# --- Обработчик /start ---
@bot.message_handler(commands=['start', 'play'])
def send_choice_menu(message):
    bot.send_message(
        message.chat.id, 
        "Ну че чепушили, поиграем?", 
    )
    # Сразу покажем главное меню
    bot.send_message(
        message.chat.id, 
        MAIN_MENU_TEXT, 
        reply_markup=create_main_menu_markup()
    )


# --- Обработчик команды /groupstats (v16) ---
@bot.message_handler(commands=['groupstats'])
def send_group_stats(message):
    chat_id = message.chat.id
    today_str = str(datetime.date.today())

    try:
        # Проверяем, это личная переписка или группа
        if message.chat.type == "private":
            bot.send_message(chat_id, "Эта команда предназначена для групповых чатов. Просто нажми /start, чтобы узнать *свои* проценты.")
            return
            
        # Проверяем, есть ли данные за сегодня по этому чату
        if chat_id not in user_daily_stats or user_daily_stats[chat_id]['date'] != today_str:
            bot.send_message(chat_id, f"Статистика за {today_str} в этом чате еще не собрана. \nНажмите /start и сыграйте!")
            return
            
        # Словарь со статистикой этого чата
        stats_for_this_chat_dict = user_daily_stats[chat_id]['users']
        
        if not stats_for_this_chat_dict:
            bot.send_message(chat_id, "Пока никто не играл сегодня в этом чате. \nНажмите /start, чтобы быть первым!")
            return
            
        # 1. Формируем основной список
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
            
        # 2. Находим "Королей"
        king_data = max(stats_for_this_chat_dict.values(), key=lambda user_data: user_data['krasavchik'])
        loser_data = max(stats_for_this_chat_dict.values(), key=lambda user_data: user_data['loh'])
        
        # 3. Готовим имена для HTML
        king_name_safe = king_data['name'].replace('<', '&lt;').replace('>', '&gt;')
        loser_name_safe = loser_data['name'].replace('<', '&lt;').replace('>', '&gt;')
        
        # 4. Добавляем номинации в отчет
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
            
        bot.send_message(chat_id, "\n".join(report_lines), parse_mode="HTML")

    except Exception as e:
        # Добавляем отлов ошибок, чтобы бот не падал
        print(f"!!! ОШИБКА в send_group_stats: {e}")
        bot.send_message(message.chat.id, "Ой, что-то пошло не так при подсчете статистики...")


# --- ИЗМЕНЕНИЕ ЗДЕСЬ (v17) ---
# --- ОБРАБОТЧИК ОПРОСОВ /go (ПОЛНОСТЬЮ ПЕРЕПИСАН) ---

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


# --- ОСНОВНОЙ ОБРАБОТчик КНОПОК (ИЗМЕНЕН v17) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """
    Обрабатывает ВСЕ нажатия на инлайн-кнопки.
    """
    
    # 1. Отвечаем на callback, чтобы у пользователя пропали "часики"
    # (кроме случаев с опросом, там спец-ответ)
    
    today_str = str(datetime.date.today())
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    user_name = call.from_user.first_name 

    try:
        # --- ИЗМЕНЕНИЕ ЗДЕСЬ (v17) ---
        # --- ОБРАБОТКА ОПРОСА (ПОЛНОСТЬЮ ПЕРЕПИСАНА) ---
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
                final_text = f"**ОПРОС ЗАВЕРШЕН:**\n{final_text}" # Добавляем заголовок
                             
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
                'roulette_best_streak':
