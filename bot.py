import telebot
import random
import datetime
import time 
import os
from flask import Flask
from threading import Thread
from telebot import types
from telebot.types import InlineQueryResultArticle, InputTextMessageContent

# <<< ИЗМЕНЕНИЕ: Импортируем наши новые модули
import database
import utils 

# --- Токен и Инициализация ---
BOT_TOKEN = os.environ.get('BOT_TOKEN') 
bot = telebot.TeleBot(BOT_TOKEN)

# <<< ИЗМЕНЕНИЕ: Антифлуд для статистики (остается в памяти)
# Это нормально, т.к. нестрашно, если он сбросится при перезапуске
last_stats_message = {}


# --- Установка меню команд ---
try:
    bot_commands = [
        types.BotCommand("start", "▶️ Старт / Игры (Личное меню)"),
        types.BotCommand("groupstats", "📊 Статистика игр"),
        types.BotCommand("go", "📣 Создать опрос (Кто идет?)") 
    ]
    bot.set_my_commands(bot_commands) 
    print("Меню команд (возможно) обновлено!")
except Exception as e:
    print(f"Ошибка установки меню команд: {e}")

# --- Обработчик /start ---
# <<< ИЗМЕНЕНИЕ: СИЛЬНО УПРОЩЕНО
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

    # 2. (УДАЛЕНО) Вся логика `user_menus` и `menu_owners` удалена.
    
    # 3. Отправляем новое меню
    bot.send_message(
        chat_id, 
        utils.MAIN_MENU_TEXT, 
        reply_markup=utils.create_main_menu_markup()
    )

# --- Обработчик /groupstats ---
# <<< ИЗМЕНЕНИЕ: Добавлена ваша новая функция (кнопка "Назад")
@bot.message_handler(commands=['groupstats'])
def handle_group_stats_command(message):
    """
    Обрабатывает команду /groupstats, отправляя НОВОЕ сообщение.
    """
    # Вызываем общую функцию, но говорим ей, что это НЕ колбэк
    send_group_stats(message.chat.id, message.message_id, is_callback=False)

def send_group_stats(chat_id, message_id, is_callback=False):
    """
    Универсальная функция для отправки статистики.
    Если is_callback=True, она ИЗМЕНИТ сообщение, добавив кнопку "Назад".
    Если is_callback=False (это команда /groupstats), она отправит НОВОЕ сообщение.
    """
    today_str = str(datetime.date.today())

    try:
        # 1. Антифлуд: Удаляем команду /groupstats (только если это не колбэк)
        if not is_callback:
            try:
                bot.delete_message(chat_id, message_id)
                print(f"Удалена команда /groupstats {message_id}")
            except telebot.apihelper.ApiTelegramException as e:
                print(f"Не смог удалить команду /groupstats (нет прав?): {e}")
        
        # 2. Антифлуд: Удаляем СТАРЫЙ отчет бота
        if chat_id in last_stats_message:
            try:
                bot.delete_message(chat_id, last_stats_message[chat_id])
                print(f"Удален старый отчет {last_stats_message[chat_id]}")
            except telebot.apihelper.ApiTelegramException: pass
            if chat_id in last_stats_message: # Проверяем, не удалил ли его другой поток
                 del last_stats_message[chat_id]
            
        # 3. Получаем статистику из БД
        stats_for_this_chat_dict = database.get_chat_statistics(chat_id, today_str)
        
        if not stats_for_this_chat_dict:
            text = f"Статистика за {today_str} в этом чате еще не собрана. \nНажмите /start и сыграйте!"
            if is_callback:
                # Если это колбэк, меняем сообщение и добавляем кнопку "Назад"
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=utils.create_back_to_menu_markup())
            else:
                # Если это команда, просто отправляем
                bot.send_message(chat_id, text)
            return
            
        # 4. Формируем основной список
        report_lines = [f"📊 Статистика ИГР в этом чате за {today_str}:\n"]
        
        sorted_users_list = sorted(stats_for_this_chat_dict.items(), key=lambda item: item[1]['krasavchik'], reverse=True)
        
        for user_id, data in sorted_users_list:
            user_name_safe = utils.safe_html(data['name'])
            
            best_streak = data.get('roulette_best_streak', 0)
            roulette_stat_str = f" | Рулетка: 🏆 {best_streak}" if best_streak > 0 else ""
            
            size = data.get('size', 0)
            size_stat_str = f" | Размер: 🍆 {size} см" if size > 0 else ""

            report_lines.append(f" - <b>{user_name_safe}</b>: Красавчик {data['krasavchik']}%, Лох {data['loh']}%{size_stat_str}{roulette_stat_str}")
            
        # 5. Находим "Королей"
        king_data = max(stats_for_this_chat_dict.values(), key=lambda d: d['krasavchik'])
        loser_data = max(stats_for_this_chat_dict.values(), key=lambda d: d['loh'])
        luckiest_data = max(stats_for_this_chat_dict.values(), key=lambda d: d.get('roulette_best_streak', 0))
        biggest_data = max(stats_for_this_chat_dict.values(), key=lambda d: d.get('size', 0))

        report_lines.append(f"\n👑 <b>Царь Красавчиков сегодня:</b> {utils.safe_html(king_data['name'])} ({king_data['krasavchik']}%)")
        report_lines.append(f"🤦‍♂️ <b>Главный Лох дня:</b> {utils.safe_html(loser_data['name'])} ({loser_data['loh']}%)")
        
        if luckiest_data.get('roulette_best_streak', 0) > 0:
            report_lines.append(f"🏆 <b>Король Удачи:</b> {utils.safe_html(luckiest_data['name'])} (выжил {luckiest_data['roulette_best_streak']} раз подряд!)")

        if biggest_data.get('size', 0) > 0:
            report_lines.append(f"🍆 <b>Главный Гигант:</b> {utils.safe_html(biggest_data['name'])} ({biggest_data['size']} см)")
            
        final_report = "\n".join(report_lines)
        
        # 6. <<< НОВАЯ ЛОГИКА ОТПРАВКИ >>>
        if is_callback:
            # Это был клик по кнопке "Статистика" - МЕНЯЕМ сообщение
            bot.edit_message_text(
                chat_id=chat_id, 
                message_id=message_id, 
                text=final_report, 
                parse_mode="HTML",
                reply_markup=utils.create_back_to_menu_markup() # Добавляем кнопку "Назад"
            )
        else:
            # Это была команда /groupstats - ОТПРАВЛЯЕМ новое
            stats_msg = bot.send_message(chat_id, final_report, parse_mode="HTML")
            last_stats_message[chat_id] = stats_msg.message_id # Сохраняем для антифлуда

    except Exception as e:
        print(f"!!! ОШИБКА в send_group_stats: {e}")
        try:
            bot.send_message(chat_id, "Ой, что-то пошло не так при подсчете статистики...")
        except Exception: pass


# --- ОБРАБОТЧИК ОПРОСОВ /go ---
# <<< ИЗМЕНЕНИЕ: Используем `database.py`
@bot.message_handler(commands=['go'])
def create_poll_handler(message):
    chat_id = message.chat.id
    creator_id = message.from_user.id
    
    question = message.text[len('/go '):].strip()
    
    if not question:
        bot.send_message(chat_id, "Вы не задали вопрос! \nПример: `/go Кто идет в кино?`", parse_mode="Markdown")
        return
        
    try:
        # 1. "Пустые" данные для форматирования
        initial_poll_data = {
            'question': question,
            'votes': {'going': {}, 'not_going': {}}
        }
        
        poll_text = utils.format_poll_text(initial_poll_data)
        markup = utils.create_poll_markup()
        
        poll_message = bot.send_message(chat_id, poll_text, parse_mode="HTML", reply_markup=markup)
        
        # 2. Сохраняем опрос в БД
        database.create_poll(poll_message.message_id, chat_id, question, creator_id)
        
    except Exception as e:
        print(f"!!! ОШИБКА в create_poll_handler: {e}")
        bot.send_message(chat_id, "Ой, не смог создать опрос...")


# --- ОБРАБОТЧИК INLINE РЕЖИМА ---
# <<< ИЗМЕНЕНИЕ: Используем `database.py`
@bot.inline_handler(func=lambda query: True)
def handle_inline_query(query):
    user_id = query.from_user.id
    user_name = utils.safe_html(query.from_user.first_name)
    today_str = str(datetime.date.today())
    results = []

    try:
        # 1. Найти последнюю активную сессию пользователя
        chat_id = database.get_last_active_chat(user_id)
        
        # 2. Проверить, есть ли у него сегодняшняя статистика в этом чате
        stats = database.get_user_stats_for_inline(user_id, chat_id, today_str)
        
        if stats:
            # A. Красавчик
            kras_percent = stats.get('krasavchik', 0)
            results.append(InlineQueryResultArticle(
                id='1', title=f"Поделиться % Красавчика ({kras_percent}%)", 
                description=utils.get_krasavchik_comment(kras_percent),
                input_message_content=InputTextMessageContent(f"⚡ {user_name} сегодня красавчик на {kras_percent}%!")
            ))
            
            # B. Лох
            loh_percent = stats.get('loh', 0)
            results.append(InlineQueryResultArticle(
                id='2', title=f"Поделиться % Лоха ({loh_percent}%)", 
                description=utils.get_loh_comment(loh_percent),
                input_message_content=InputTextMessageContent(f"⚡ {user_name} сегодня лох на {loh_percent}%.")
            ))
            
            # C. Размер
            size = stats.get('size', 0)
            results.append(InlineQueryResultArticle(
                id='3', title=f"Поделиться Размером (🍆 {size} см)", 
                description=utils.get_size_comment(size),
                input_message_content=InputTextMessageContent(f"⚡ {user_name} измерил свой размер: 🍆 {size} см!")
            ))
            
            # D. Рулетка
            streak = stats.get('roulette_best_streak', 0)
            results.append(InlineQueryResultArticle(
                id='4', title=f"Поделиться рекордом в Рулетке (🏆 {streak})", 
                description=f"Лучшая серия выживания: {streak}",
                input_message_content=InputTextMessageContent(f"⚡ {user_name} поставил(а) рекорд в рулетке: 🏆 {streak} выстрелов подряд!")
            ))
            
        else:
            results.append(InlineQueryResultArticle(
                id='1', title="Нет данных для шеринга", 
                description="Напишите /start в группе, чтобы сначала сыграть!",
                input_message_content=InputTextMessageContent(f"{user_name}, я не могу найти твою статистику. Сыграй в группе!")
            ))
            
        bot.answer_inline_query(query.id, results, cache_time=10)

    except Exception as e:
        print(f"!!! ОШИБКА в handle_inline_query: {e}")


# --- ОСНОВНОЙ ОБРАБОТчик КНОПОК ---
# <<< ИЗМЕНЕНИЕ: Полностью переписан
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    
    today_str = str(datetime.date.today())
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    user_name = call.from_user.first_name 
    
    try:
        # --- ОБРАБОТКА ОПРОСА ---
        if call.data.startswith('poll_'):
            
            # 1. Находим данные опроса в БД
            poll_data = database.get_poll_data(message_id)
            if not poll_data:
                bot.answer_callback_query(call.id, "Этот опрос уже закрыт.", show_alert=True)
                return

            # 2. Обрабатываем нажатие
            if call.data == "poll_go":
                poll_data = database.update_poll_vote(message_id, user_id, user_name, 'go')
                bot.answer_callback_query(call.id, "Вы записались! 👍")
                
            elif call.data == "poll_pass":
                poll_data = database.update_poll_vote(message_id, user_id, user_name, 'pass')
                bot.answer_callback_query(call.id, "Вы 'пасуете' 👎")
                
            elif call.data == "poll_close":
                if user_id != poll_data['creator_id']:
                    bot.answer_callback_query(call.id, "Закрыть опрос может только его создатель!", show_alert=True)
                    return
                
                # Закрываем опрос
                final_text = utils.format_poll_text(poll_data)
                final_text = f"<b>ОПРОС ЗАВЕРШЕН:</b>\n{final_text}"
                
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, parse_mode="HTML", reply_markup=None)
                database.delete_poll(message_id) # Удаляем опрос из БД
                return

            # 3. Обновляем ТЕКСТ сообщения с новым списком имен
            if poll_data:
                new_text = utils.format_poll_text(poll_data)
                new_markup = utils.create_poll_markup()
                
                try:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=new_text, parse_mode="HTML", reply_markup=new_markup)
                except telebot.apihelper.ApiTelegramException as e:
                    if "message is not modified" in str(e): pass
                    else: raise e
            return 
        
        # --- ОБРАБОТКА ИГРОВОГО МЕНЮ ---
        
        # --- Получение статистики ИГРОКА ---
        # <<< ИЗМЕНЕНИЕ: Вся логика создания/поиска заменена ОДНОЙ строкой
        current_stats = database.get_or_create_user_stats(user_id, chat_id, user_name, today_str)
        
        # Обновляем имя в БД, если юзер его сменил
        if current_stats['name'] != user_name:
            database.update_user_stats(user_id, chat_id, today_str, 'name', user_name)

        # Отвечаем на колбэк, чтобы пропали "часики"
        bot.answer_callback_query(call.id)

        # --- ОБРАБОТКА КНОПКИ "НАЗАД" ---
        if call.data == "go_back_to_menu":
            # Сохраняем лучший результат рулетки, если текущий - лучше
            current_streak = current_stats.get('roulette_current_streak', 0)
            best_streak = current_stats.get('roulette_best_streak', 0)
            
            if current_streak > best_streak:
                database.update_user_stats(user_id, chat_id, today_str, 'roulette_best_streak', current_streak)
            
            # Сбрасываем текущую игру
            database.update_user_stats(user_id, chat_id, today_str, 'roulette_current_streak', 0)
            
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=utils.MAIN_MENU_TEXT,
                reply_markup=utils.create_main_menu_markup()
            )
            return

        # --- ОБРАБОТКА КНОПKI СТАТИСТИКИ ---
        # <<< ИЗМЕНЕНИЕ: Теперь она меняет текущее меню
        if call.data == "show_group_stats":
            send_group_stats(chat_id, message_id, is_callback=True)
            return

        # --- ОБРАБОТКА ИГР (Красавчик, Лох, Размер) ---
        # <<< ИЗМЕНЕНИЕ: Вынесены в `utils.show_game_animation`
        
        is_game_played = False # Флаг для `user_last_active_chat`
        
        if call.data == "ask_krasavchik":
            percent = current_stats['krasavchik']
            final_text = utils.get_krasavchik_comment(percent)
            utils.show_game_animation(bot, call, "😎 Красавчик", final_text, units="%", emoji="🎲")
            is_game_played = True 
            
        elif call.data == "ask_loh":
            percent = current_stats['loh']
            final_text = utils.get_loh_comment(percent)
            utils.show_game_animation(bot, call, "😅 Лох", final_text, units="%", emoji="🎲")
            is_game_played = True

        elif call.data == "ask_size":
            size = current_stats['size']
            final_text = utils.get_size_comment(size)
            utils.show_game_animation(bot, call, "🍆 Мой размер", final_text, units=" см", min_val=1, max_val=30, emoji="📏")
            is_game_played = True
        
        # --- ОБРАБОТКА РУЛЕТКИ ---
        # <<< ИЗМЕНЕНИЕ: Обновляет БД вместо словаря
        
        elif call.data == "roulette_play_next":
            is_game_played = True # Рулетка - это тоже игра
            current_streak = current_stats.get('roulette_current_streak', 0)
            current_chance = current_streak + 1
            max_chance = 6
            
            # (Анимация)
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🌀 Кручу барабан... (Шанс {current_chance}/{max_chance})")
                time.sleep(0.6)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🔫 Приставляю к виску...")
                time.sleep(0.6)
            except telebot.apihelper.ApiTelegramException: pass 

            shot = random.randint(1, max_chance)
            is_dead = (shot <= current_chance)
            
            if is_dead: 
                final_text = f"💥 БАМ! ({current_chance}/{max_chance}). Твоя удача кончилась на {current_chance}-м выстреле!"
                
                # Сохраняем ЛУЧШУЮ серию (это была серия *до* этого выстрела)
                if current_streak > current_stats['roulette_best_streak']:
                    database.update_user_stats(user_id, chat_id, today_str, 'roulette_best_streak', current_streak)
                
                # Сбрасываем ТЕКУЩУЮ серию
                database.update_user_stats(user_id, chat_id, today_str, 'roulette_current_streak', 0)
                
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, reply_markup=utils.create_back_to_menu_markup())
                
            else: # ВЫЖИЛ
                # Увеличиваем текущую серию В БД
                new_streak = current_streak + 1
                database.update_user_stats(user_id, chat_id, today_str, 'roulette_current_streak', new_streak)
                
                continue_markup = types.InlineKeyboardMarkup(row_width=1)
                
                if new_streak == max_chance - 1: # Т.е. серия стала 5 (5/6)
                    final_text = f"💨 Щелк! ({current_chance}/{max_chance}). НЕВЕРОЯТНО! Ты выжил... \nНо в барабане 100% остался 1 патрон."
                    continue_btn = types.InlineKeyboardButton(f"Сделать выстрел (Шанс 6/6)", callback_data="roulette_play_next")
                else:
                    final_text = f"💨 Щелк! ({current_chance}/{max_chance}). Пронесло... Рискнешь еще?"
                    continue_btn = types.InlineKeyboardButton(f"Играть дальше (Шанс {new_streak + 1}/{max_chance})", callback_data="roulette_play_next")
                
                stop_btn = types.InlineKeyboardButton(f"🚫 Хватит (сохранить серию: {new_streak})", callback_data="go_back_to_menu")
                continue_markup.add(continue_btn, stop_btn)
                
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, reply_markup=continue_markup)
        
        # --- Обновление "Последнего чата" ---
        if is_game_played:
            database.update_last_active_chat(user_id, chat_id)

    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" in str(e):
            pass 
        else:
            print(f"Произошла ошибка (возможно, сообщение удалено): {e}")
    except Exception as e:
        print(f"!!! КРИТИЧЕСКАЯ ОШИБКА в handle_callback_query: {e}")
        import traceback
        traceback.print_exc() # Печатаем полную ошибку


# --- Веб-сервер для RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Я жив, бот работает!"

def run():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

def start_server():
    t = Thread(target=run)
    t.start()

# --- Запуск ---
print("Инициализация базы данных...")
database.init_db() # <<< ИЗМЕНЕНИЕ: Запускаем БД при старте
print("Запуск веб-сервера...")
start_server()
print("Запуск бота...")
bot.polling(none_stop=True)
