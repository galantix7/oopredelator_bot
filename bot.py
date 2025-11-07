import telebot
import random
import datetime
import time
import os
from flask import Flask
from threading import Thread
from telebot import types
from telebot.types import InlineQueryResultArticle, InputTextMessageContent

import database
import utils

# --- Токен и инициализация ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# Антифлуд для статистики (в памяти)
last_stats_message = {}

# Установка меню команд
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

# Обработчик /start и /play
@bot.message_handler(commands=['start', 'play'])
def send_choice_menu(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Антифлуд: удаляем команду /start или /play
    try:
        bot.delete_message(chat_id, message.message_id)
        print(f"Удалена команда {message.message_id} от {user_id}")
    except telebot.apihelper.ApiTelegramException as e:
        print(f"Не смог удалить команду /start или /play (нет прав?): {e}")
    
    # Отправляем главное меню
    bot.send_message(
        chat_id,
        utils.MAIN_MENU_TEXT,
        reply_markup=utils.create_main_menu_markup()
    )

# Обработчик /groupstats
@bot.message_handler(commands=['groupstats'])
def handle_group_stats_command(message):
    send_group_stats(message.chat.id, message.message_id, is_callback=False)

def send_group_stats(chat_id, message_id, is_callback=False):
    today_str = str(datetime.date.today())
    try:
        # Удаляем команду /groupstats (если не колбэк)
        if not is_callback:
            try:
                bot.delete_message(chat_id, message_id)
                print(f"Удалена команда /groupstats {message_id}")
            except telebot.apihelper.ApiTelegramException as e:
                print(f"Не смог удалить команду /groupstats (нет прав?): {e}")
        
        # Удаляем старое сообщение со статистикой (антифлуд)
        if chat_id in last_stats_message:
            try:
                bot.delete_message(chat_id, last_stats_message[chat_id])
                print(f"Удален старый отчет {last_stats_message[chat_id]}")
            except telebot.apihelper.ApiTelegramException:
                pass
            del last_stats_message[chat_id]

        # Получаем статистику из БД
        stats_for_this_chat_dict = database.get_chat_statistics(chat_id, today_str)
        if not stats_for_this_chat_dict:
            text = f"Статистика за {today_str} в этом чате еще не собрана. \nНажмите /start и сыграйте!"
            if is_callback:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=utils.create_back_to_menu_markup())
            else:
                bot.send_message(chat_id, text)
            return

        # Формируем отчет
        report_lines = [f"📊 Статистика ИГР в этом чате за {today_str}:\n"]
        sorted_users_list = sorted(stats_for_this_chat_dict.items(), key=lambda item: item[1]['krasavchik'], reverse=True)
        for user_id, data in sorted_users_list:
            user_name_safe = utils.safe_html(data['name'])
            best_streak = data.get('roulette_best_streak', 0)
            roulette_stat_str = f" | Рулетка: 🏆 {best_streak}" if best_streak > 0 else ""
            size = data.get('size', 0)
            size_stat_str = f" | Размер: 🍆 {size} см" if size > 0 else ""
            report_lines.append(f" - {user_name_safe}: Красавчик {data['krasavchik']}%, Лох {data['loh']}%{size_stat_str}{roulette_stat_str}")

        # Главные игроки
        king_data = max(stats_for_this_chat_dict.values(), key=lambda d: d['krasavchik'])
        loser_data = max(stats_for_this_chat_dict.values(), key=lambda d: d['loh'])
        luckiest_data = max(stats_for_this_chat_dict.values(), key=lambda d: d.get('roulette_best_streak', 0))
        biggest_data = max(stats_for_this_chat_dict.values(), key=lambda d: d.get('size', 0))

        report_lines.append(f"\n👑 Царь Красавчиков сегодня: {utils.safe_html(king_data['name'])} ({king_data['krasavchik']}%)")
        report_lines.append(f"🤦‍♂️ Главный Лох дня: {utils.safe_html(loser_data['name'])} ({loser_data['loh']}%)")
        if luckiest_data.get('roulette_best_streak', 0) > 0:
            report_lines.append(f"🏆 Король Удачи: {utils.safe_html(luckiest_data['name'])} (выжил {luckiest_data['roulette_best_streak']} раз подряд!)")
        if biggest_data.get('size', 0) > 0:
            report_lines.append(f"🍆 Главный Гигант: {utils.safe_html(biggest_data['name'])} ({biggest_data['size']} см)")

        final_report = "\n".join(report_lines)

        # Отправляем или меняем сообщение
        if is_callback:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=final_report,
                parse_mode="HTML",
                reply_markup=utils.create_back_to_menu_markup()
            )
        else:
            stats_msg = bot.send_message(chat_id, final_report, parse_mode="HTML")
            last_stats_message[chat_id] = stats_msg.message_id

    except Exception as e:
        print(f"!!! ОШИБКА в send_group_stats: {e}")
        try:
            bot.send_message(chat_id, "Ой, что-то пошло не так при подсчете статистики...")
        except Exception:
            pass

# Обработчик команды /go (создать опрос)
@bot.message_handler(commands=['go'])
def create_poll_handler(message):
    chat_id = message.chat.id
    creator_id = message.from_user.id
    question = message.text[len('/go '):].strip()
    if not question:
        bot.send_message(chat_id, "Вы не задали вопрос! \nПример: `/go Кто идет в кино?`", parse_mode="Markdown")
        return
    try:
        initial_poll_data = {
            'question': question,
            'votes': {'going': {}, 'not_going': {}}
        }
        poll_text = utils.format_poll_text(initial_poll_data)
        markup = utils.create_poll_markup()
        poll_message = bot.send_message(chat_id, poll_text, parse_mode="HTML", reply_markup=markup)
        database.create_poll(poll_message.message_id, chat_id, question, creator_id)
    except Exception as e:
        print(f"!!! ОШИБКА в create_poll_handler: {e}")
        bot.send_message(chat_id, "Ой, не смог создать опрос...")

# Обработчик inline запросов
@bot.inline_handler(func=lambda query: True)
def handle_inline_query(query):
    user_id = query.from_user.id
    user_name = utils.safe_html(query.from_user.first_name)
    today_str = str(datetime.date.today())
    results = []
    try:
        chat_id = database.get_last_active_chat(user_id)
        stats = database.get_user_stats_for_inline(user_id, chat_id, today_str)
        if stats:
            kras_percent = stats.get('krasavchik', 0)
            results.append(InlineQueryResultArticle(
                id='1', title=f"Поделиться % Красавчика ({kras_percent}%)",
                description=utils.get_krasavchik_comment(kras_percent),
                input_message_content=InputTextMessageContent(f"⚡ {user_name} сегодня красавчик на {kras_percent}%!")
            ))
            loh_percent = stats.get('loh', 0)
            results.append(InlineQueryResultArticle(
                id='2', title=f"Поделиться % Лоха ({loh_percent}%)",
                description=utils.get_loh_comment(loh_percent),
                input_message_content=InputTextMessageContent(f"⚡ {user_name} сегодня лох на {loh_percent}%.")
            ))
            size = stats.get('size', 0)
            results.append(InlineQueryResultArticle(
                id='3', title=f"Поделиться Размером (🍆 {size} см)",
                description=utils.get_size_comment(size),
                input_message_content=InputTextMessageContent(f"⚡ {user_name} измерил свой размер: 🍆 {size} см!")
            ))
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

# Главный обработчик callback кнопок
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    today_str = str(datetime.date.today())
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    user_name = call.from_user.first_name
    try:
        # Обработка опроса
        if call.data.startswith('poll_'):
            poll_data = database.get_poll_data(message_id)
            if not poll_data:
                bot.answer_callback_query(call.id, "Этот опрос уже закрыт.", show_alert=True)
                return
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
                final_text = utils.format_poll_text(poll_data)
                final_text = f"ОПРОС ЗАВЕРШЕН:\n{final_text}"
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, parse_mode="HTML", reply_markup=None)
                database.delete_poll(message_id)
                return
            if poll_data:
                new_text = utils.format_poll_text(poll_data)
                new_markup = utils.create_poll_markup()
                try:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=new_text, parse_mode="HTML", reply_markup=new_markup)
                except telebot.apihelper.ApiTelegramException as e:
                    if "message is not modified" in str(e):
                        pass
                    else:
                        raise e
                return

        # Игровое меню
        current_stats = database.get_or_create_user_stats(user_id, chat_id, user_name, today_str)
        if current_stats['name'] != user_name:
            database.update_user_stats(user_id, chat_id, today_str, 'name', user_name)
        bot.answer_callback_query(call.id)

        # Кнопка "Назад"
        if call.data == "go_back_to_menu":
            current_streak = current_stats.get('roulette_current_streak', 0)
            best_streak = current_stats.get('roulette_best_streak', 0)
            if current_streak > best_streak:
                database.update_user_stats(user_id, chat_id, today_str, 'roulette_best_streak', current_streak)
            database.update_user_stats(user_id, chat_id, today_str, 'roulette_current_streak', 0)
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=utils.MAIN_MENU_TEXT, reply_markup=utils.create_main_menu_markup())
            return

        # Статистика
        if call.data == "show_group_stats":
            send_group_stats(chat_id, message_id, is_callback=True)
            return

        # Игры Красавчик, Лох, Размер
        is_game_played = False
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

        # Рулетка
        elif call.data == "roulette_play_next":
            is_game_played = True
            current_streak = current_stats.get('roulette_current_streak', 0)
            current_chance = current_streak + 1
            max_chance = 6

            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🌀 Кручу барабан... (Шанс {current_chance}/{max_chance})")
                time.sleep(0.6)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🔫 Приставляю к виску...")
                time.sleep(0.6)
            except telebot.apihelper.ApiTelegramException:
                pass

            shot = random.randint(1, max_chance)
            is_dead = (shot <= current_chance)

            if is_dead:
                final_text = f"💥 БАМ! ({current_chance}/{max_chance}). Твоя удача кончилась на {current_chance}-м выстреле!"
                if current_streak > current_stats['roulette_best_streak']:
                    database.update_user_stats(user_id, chat_id, today_str, 'roulette_best_streak', current_streak)
                database.update_user_stats(user_id, chat_id, today_str, 'roulette_current_streak', 0)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, reply_markup=utils.create_back_to_menu_markup())
            else:
                new_streak = current_streak + 1
                database.update_user_stats(user_id, chat_id, today_str, 'roulette_current_streak', new_streak)
                continue_markup = types.InlineKeyboardMarkup(row_width=1)
                if new_streak == max_chance - 1:
                    final_text = f"💨 Щелк! ({current_chance}/{max_chance}). НЕВЕРОЯТНО! Ты выжил... \nНо в барабане 100% остался 1 патрон."
                    continue_btn = types.InlineKeyboardButton(f"Сделать выстрел (Шанс 6/6)", callback_data="roulette_play_next")
                else:
                    final_text = f"💨 Щелк! ({current_chance}/{max_chance}). Пронесло... Рискнешь еще?"
                    continue_btn = types.InlineKeyboardButton(f"Играть дальше (Шанс {new_streak + 1}/{max_chance})", callback_data="roulette_play_next")
                stop_btn = types.InlineKeyboardButton(f"🚫 Хватит (сохранить серию: {new_streak})", callback_data="go_back_to_menu")
                continue_markup.add(continue_btn, stop_btn)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, reply_markup=continue_markup)

        # Обновление последнего активного чата
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
        traceback.print_exc()

# Веб-сервер для RENDER
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

# Запуск
print("Инициализация базы данных...")
database.init_db()

print("Запуск веб-сервера...")
start_server()

print("Запуск бота...")
bot.polling(none_stop=True)
