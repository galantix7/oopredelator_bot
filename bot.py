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
polls_data = {}       # --- ИДЕЯ №15: Новое хранилище для ОПРОСОВ ---
                      # Структура: { message_id: {'question': '...', 'creator_id': ..., 'going': set(), 'not_going': set()} }


# --- Тексты для удобства ---
MAIN_MENU_TEXT = "Привет! Выбери, что хочешь узнать (сегодняшние замеры уже готовы):"

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
        "Узнать, какой я сегодня красавчик 😎", 
        callback_data="ask_krasavchik"
    )
    btn2 = types.InlineKeyboardButton(
        "Узнать, какой я сегодня лох 😅", 
        callback_data="ask_loh"
    )
    # Новая кнопка "Измерителя"
    btn5 = types.InlineKeyboardButton(
        "Узнать мой размер 🍆", 
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
        "Привет! Сейчас сгенерирую твои проценты на сегодня...", 
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

# --- ИДЕЯ №15: НОВЫЙ ОБРАБОТЧИК ОПРОСОВ /go ---
def create_poll_markup(poll_data):
    """
    Вспомогательная функция для генерации кнопок опроса с 
    актуальными счетчиками.
    """
    count_going = len(poll_data['going'])
    count_not_going = len(poll_data['not_going'])
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_go = types.InlineKeyboardButton(f"Я иду! 👍 [{count_going}]", callback_data="poll_go")
    btn_pass = types.InlineKeyboardButton(f"Я пас 👎 [{count_not_going}]", callback_data="poll_pass")
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
            'going': set(),
            'not_going': set()
        }
        
        # 2. Генерируем кнопки с [0] и [0]
        markup = create_poll_markup(poll_data)
        
        # 3. Отправляем сообщение с опросом
        poll_message = bot.send_message(chat_id, f"📣 **ОПРОС:** {question}", parse_mode="Markdown", reply_markup=markup)
        
        # 4. Сохраняем опрос в наше хранилище, используя ID сообщения как ключ
        polls_data[poll_message.message_id] = poll_data
        
    except Exception as e:
        print(f"!!! ОШИБКА в create_poll_handler: {e}")
        bot.send_message(chat_id, "Ой, не смог создать опрос...")

# --- ОСНОВНОЙ ОБРАБОТчик КНОПОК (v16) ---
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
        # --- ИДЕЯ №15: Обработка кнопок ОПРОСА "Кто идет?" ---
        if call.data.startswith('poll_'):
            
            # 1. Находим данные опроса (по ID сообщения)
            poll_data = polls_data.get(message_id)
            if not poll_data:
                # Это старый опрос, кнопки уже неактивны
                bot.answer_callback_query(call.id, "Этот опрос уже закрыт.", show_alert=True)
                return

            # 2. Обрабатываем нажатие
            if call.data == "poll_go":
                poll_data['going'].add(user_id)
                poll_data['not_going'].discard(user_id) # Убираем, если передумал
                bot.answer_callback_query(call.id, "Вы записались! 👍")
                
            elif call.data == "poll_pass":
                poll_data['not_going'].add(user_id)
                poll_data['going'].discard(user_id) # Убираем, если передумал
                bot.answer_callback_query(call.id, "Вы 'пасуете' 👎")
                
            elif call.data == "poll_close":
                # Проверяем, что это создатель
                if user_id != poll_data['creator_id']:
                    bot.answer_callback_query(call.id, "Закрыть опрос может только его создатель!", show_alert=True)
                    return
                
                # Закрываем опрос
                count_going = len(poll_data['going'])
                count_not_going = len(poll_data['not_going'])
                
                final_text = f"**ОПРОС ЗАВЕРШЕН:** {poll_data['question']}\n\n" \
                             f"👍 **Идут:** {count_going}\n" \
                             f"👎 **Пас:** {count_not_going}"
                             
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, parse_mode="Markdown", reply_markup=None)
                # Удаляем опрос из памяти
                del polls_data[message_id]
                return

            # 3. Обновляем кнопки с новым счетчиком
            new_markup = create_poll_markup(poll_data)
            bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=new_markup)
            return # Выходим, т.к. это был опрос
            
        # --- Конец блока ОПРОСОВ ---

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

        
        if call.data == "ask_krasavchik":
            percent = current_stats['krasavchik']
            final_text = get_krasavchik_comment(percent)
            animation_prefix = "😎 Красавчик"
            is_standard_roulette_animation = True 
            
        elif call.data == "ask_loh":
            percent = current_stats['loh']
            final_text = get_loh_comment(percent)
            animation_prefix = "😅 Лох"
            is_standard_roulette_animation = True 
        
        elif call.data == "ask_size":
            size = current_stats['size']
            final_text = get_size_comment(size)
            animation_prefix = "🍆 Мой размер"
            is_size_animation = True # Включаем новую анимацию
        
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
