import telebot
import random
import datetime
import time
import logging
from telebot import types
from telebot.types import InlineQueryResultArticle, InputTextMessageContent
import os
from flask import Flask
from threading import Thread

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

user_daily_stats = {}
polls_data = {}
menu_owners = {}
user_menus = {}
last_stats_message = {}
user_last_active_chat = {}

MAIN_MENU_TEXT = "Докажи, что не терпила!:"

def escape_html(text):
    return str(text).replace('<', '&lt;').replace('>', '&gt;')

def get_comment(typ, value):
    if typ == "krasavchik":
        if value <= 20: return f"Сегодня я красавчик на {value}%... 😅 (Лучше без зеркала)"
        elif value <= 50: return f"Сегодня я красавчик на {value}%! 😎 (Вполне себе, сойдет)"
        elif value <= 80: return f"Сегодня я красавчик на {value}%! 🔥 (Заявка на успех!)"
        else: return f"Сегодня я красавчик на {value}%! 👑 (ДА ТЫ КОРОЛЬ!)"
    elif typ == "loh":
        if value <= 20: return f"Сегодня я лох всего на {value}%! 🎉 (Ты в безопасности!)"
        elif value <= 50: return f"Сегодня я лох на {value}%. (Ну, бывает и хуже...)"
        elif value <= 80: return f"Сегодня я лох на {value}%... 😬 (Осторожнее, есть риски)"
        else: return f"Сегодня я лох на {value}%! 🤦‍♂️ (КОМБО! Лучше не рисковать)"
    elif typ == "size":
        if value <= 5: return f"Сегодня у меня {value} см... 🔬 (Микроскоп в студию!)"
        elif value <= 10: return f"Сегодня у меня {value} см. (Скромненько, но со вкусом)"
        elif value <= 18: return f"Сегодня у меня {value} см! 📏 (Золотая середина!)"
        elif value <= 25: return f"Сегодня у меня {value} см! 🔥 (Ого! Впечатляет!)"
        else: return f"Сегодня у меня {value} см! 🦄 (ГИГАНТ! Ты существуешь?!)"

def update_user_daily_stats(chat_id, user_id, user_name):
    today = str(datetime.date.today())
    stats = user_daily_stats.setdefault(chat_id, {'date': today, 'users': {}})
    if stats['date'] != today:
        stats['date'] = today
        stats['users'] = {}
    stats['users'].setdefault(user_id, {
        'krasavchik': random.randint(0, 100),
        'loh': random.randint(0, 100),
        'name': user_name,
        'size': random.randint(1, 30),
        'roulette_best_streak': 0,
        'roulette_current_streak': 0
    })
    return stats['users'][user_id]

def create_main_menu_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Красавчик 😎", callback_data="ask_krasavchik"),
        types.InlineKeyboardButton("Лох 😅", callback_data="ask_loh"),
        types.InlineKeyboardButton("Мой размер 🍆", callback_data="ask_size"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="show_group_stats"),
        types.InlineKeyboardButton("🇺🇦 Русская рулетка", callback_data="roulette_play_next"),
    )
    return markup

try:
    bot.set_my_commands([
        types.BotCommand("start", "▶️ Старт / Игры (Личное меню)"),
        types.BotCommand("groupstats", "📊 Статистика игр"),
        types.BotCommand("go", "📣 Создать опрос (Кто идет?)")
    ])
    logging.info("Меню команд обновлено!")
except Exception as e:
    logging.error(f"Ошибка установки меню команд: {e}")

@bot.message_handler(commands=['start', 'play'])
def send_choice_menu(message):
    chat_id, user_id = message.chat.id, message.from_user.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        logging.warning(f"Не смог удалить команду /start: {e}")

    if user_id in user_menus:
        old_menu_id = user_menus[user_id]
        try: bot.delete_message(chat_id, old_menu_id)
        except Exception as e: logging.warning(f"Не смог удалить старое меню: {e}")
        menu_owners.pop(old_menu_id, None)
        user_menus.pop(user_id, None)

    new_menu_msg = bot.send_message(chat_id, MAIN_MENU_TEXT, reply_markup=create_main_menu_markup())
    menu_owners[new_menu_msg.message_id] = user_id
    user_menus[user_id] = new_menu_msg.message_id

@bot.message_handler(commands=['groupstats'])
def send_group_stats(message):
    chat_id = message.chat.id
    today_str = str(datetime.date.today())
    try:
        try: bot.delete_message(chat_id, message.message_id)
        except Exception as e: logging.warning(f"Не смог удалить команду /groupstats: {e}")

        if chat_id in last_stats_message:
            try: bot.delete_message(chat_id, last_stats_message[chat_id])
            except Exception as e: logging.warning(f"Не смог удалить старый отчет: {e}")

        if message.chat.type == "private":
            bot.send_message(chat_id, "Эта команда для групповых чатов. Просто нажми /start, чтобы узнать *свои* проценты.")
            return

        stats = user_daily_stats.get(chat_id)
        if not stats or stats['date'] != today_str or not stats['users']:
            bot.send_message(chat_id, "Статистика сегодня не собрана. Нажмите /start и сыграйте!")
            return

        sorted_users = sorted(stats['users'].items(), key=lambda item: item[1]['krasavchik'], reverse=True)
        lines = [f"📊 Статистика ИГР в этом чате за {today_str}:\n"]
        for _, data in sorted_users:
            name = escape_html(data['name'])
            roulette_stat = f" | Рулетка: 🏆 {data.get('roulette_best_streak', 0)} подряд" if data.get('roulette_best_streak', 0) else ""
            size_stat = f" | Размер: 🍆 {data.get('size', 0)} см" if data.get('size', 0) else ""
            lines.append(f" - <b>{name}</b>: Красавчик {data['krasavchik']}%, Лох {data['loh']}%{size_stat}{roulette_stat}")

        king = max(stats['users'].values(), key=lambda u: u['krasavchik'])
        loser = max(stats['users'].values(), key=lambda u: u['loh'])
        lines.append(f"\n👑 <b>Царь Красавчиков:</b> {escape_html(king['name'])} ({king['krasavchik']}%)")
        lines.append(f"🤦‍♂️ <b>Главный Лох дня:</b> {escape_html(loser['name'])} ({loser['loh']}%)")

        luckiest = max(stats['users'].values(), key=lambda u: u.get('roulette_best_streak', 0))
        if luckiest.get('roulette_best_streak', 0):
            lines.append(f"🏆 <b>Король Удачи:</b> {escape_html(luckiest['name'])} ({luckiest['roulette_best_streak']} подряд!)")
        biggest = max(stats['users'].values(), key=lambda u: u.get('size', 0))
        if biggest.get('size', 0):
            lines.append(f"🍆 <b>Главный Гигант:</b> {escape_html(biggest['name'])} ({biggest['size']} см)")
        stats_msg = bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
        last_stats_message[chat_id] = stats_msg.message_id
    except Exception as e:
        logging.error(f"ОШИБКА send_group_stats: {e}")
        bot.send_message(chat_id, "Ошибка при подсчете статистики...")

def format_poll_text(poll_data):
    question = escape_html(poll_data['question'])
    names_going = [escape_html(n) for n in poll_data['going'].values()]
    names_not_going = [escape_html(n) for n in poll_data['not_going'].values()]
    text_going = "\n".join([f" - <b>{n}</b>" for n in names_going]) if names_going else " - (пока нет)"
    text_not_going = "\n".join([f" - {n}" for n in names_not_going]) if names_not_going else " - (пока нет)"
    return (f"📣 <b>ОПРОС:</b> {question}\n--------------------\n"
            f"👍 <b>Идут ({len(names_going)}):</b>\n{text_going}\n\n"
            f"👎 <b>Пас ({len(names_not_going)}):</b>\n{text_not_going}")

def create_poll_markup(poll_data):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Я иду! 👍", callback_data="poll_go"),
        types.InlineKeyboardButton("Я пас 👎", callback_data="poll_pass"),
        types.InlineKeyboardButton("🔒 Закрыть опрос", callback_data="poll_close")
    )
    return markup

@bot.message_handler(commands=['go'])
def create_poll_handler(message):
    chat_id, creator_id = message.chat.id, message.from_user.id
    question = message.text[len('/go '):].strip()
    if not question:
        bot.send_message(chat_id, "Вы не задали вопрос! Пример: `/go Кто идет в кино?`", parse_mode="Markdown")
        return
    poll_data = {'question': question, 'creator_id': creator_id, 'going': {}, 'not_going': {}}
    poll_text = format_poll_text(poll_data)
    markup = create_poll_markup(poll_data)
    poll_message = bot.send_message(chat_id, poll_text, parse_mode="HTML", reply_markup=markup)
    polls_data[poll_message.message_id] = poll_data

@bot.inline_handler(func=lambda query: True)
def handle_inline_query(query):
    user_id = query.from_user.id
    user_name = escape_html(query.from_user.first_name)
    today_str = str(datetime.date.today())
    results = []
    chat_id = user_last_active_chat.get(user_id)
    stats = None
    if chat_id and chat_id in user_daily_stats and user_daily_stats[chat_id]['date'] == today_str:
        stats = user_daily_stats[chat_id]['users'].get(user_id)
    if stats:
        results.extend([
            InlineQueryResultArticle(
                id='1',
                title=f"Поделиться % Красавчика ({stats['krasavchik']}%)",
                description=get_comment("krasavchik", stats['krasavchik']),
                input_message_content=InputTextMessageContent(f"⚡ {user_name} сегодня красавчик на {stats['krasavchik']}%!")
            ),
            InlineQueryResultArticle(
                id='2',
                title=f"Поделиться % Лоха ({stats['loh']}%)",
                description=get_comment("loh", stats['loh']),
                input_message_content=InputTextMessageContent(f"⚡ {user_name} сегодня лох на {stats['loh']}%.")
            ),
            InlineQueryResultArticle(
                id='3',
                title=f"Поделиться Размером (🍆 {stats['size']} см)",
                description=get_comment("size", stats['size']),
                input_message_content=InputTextMessageContent(f"⚡ {user_name} измерил свой размер: 🍆 {stats['size']} см!")
            ),
            InlineQueryResultArticle(
                id='4',
                title=f"Поделиться рекордом в Рулетке (🏆 {stats['roulette_best_streak']})",
                description=f"Лучшая серия выживания: {stats['roulette_best_streak']}",
                input_message_content=InputTextMessageContent(f"⚡ {user_name} поставил(а) рекорд в рулетке: 🏆 {stats['roulette_best_streak']} выстрелов подряд!")
            ),
        ])
    else:
        results.append(
            InlineQueryResultArticle(
                id='1',
                title="Нет данных для шеринга",
                description="Напишите /start в группе, чтобы сначала сыграть!",
                input_message_content=InputTextMessageContent(f"{user_name}, я не могу найти твою статистику. Сыграй в группе!")
            )
        )
    bot.answer_inline_query(query.id, results, cache_time=10)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    today_str = str(datetime.date.today())
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    user_name = call.from_user.first_name
    try:
        if call.data.startswith('poll_'):
            poll_data = polls_data.get(message_id)
            if not poll_data:
                bot.answer_callback_query(call.id, "Этот опрос уже закрыт.", show_alert=True)
                return
            if call.data == "poll_go":
                poll_data['going'][user_id] = user_name
                poll_data['not_going'].pop(user_id, None)
            elif call.data == "poll_pass":
                poll_data['not_going'][user_id] = user_name
                poll_data['going'].pop(user_id, None)
            elif call.data == "poll_close":
                if user_id != poll_data['creator_id']:
                    bot.answer_callback_query(call.id, "Закрыть опрос может только его создатель!", show_alert=True)
                    return
                final_text = f"<b>ОПРОС ЗАВЕРШЕН:</b>\n{format_poll_text(poll_data)}"
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, parse_mode="HTML", reply_markup=None)
                polls_data.pop(message_id, None)
                return
            new_text = format_poll_text(poll_data)
            new_markup = create_poll_markup(poll_data)
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=new_text, parse_mode="HTML", reply_markup=new_markup)
            except Exception as e:
                if "message is not modified" not in str(e):
                    raise e
            return

        owner_id = menu_owners.get(message_id)
        if not owner_id or owner_id != user_id:
            bot.answer_callback_query(call.id, "Это не твое (или устаревшее) меню! Напиши /start.", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        stats = update_user_daily_stats(chat_id, user_id, user_name)
        back_markup = types.InlineKeyboardMarkup(row_width=1)
        back_markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="go_back_to_menu"))
        if call.data == "go_back_to_menu":
            if stats['roulette_current_streak'] > stats['roulette_best_streak']:
                stats['roulette_best_streak'] = stats['roulette_current_streak']
            stats['roulette_current_streak'] = 0
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=MAIN_MENU_TEXT, reply_markup=create_main_menu_markup())
            return
        if call.data == "show_group_stats":
            send_group_stats(call.message)
            return
        is_game_played, final_text = False, ""
        if call.data == "ask_krasavchik":
            final_text = get_comment("krasavchik", stats['krasavchik'])
            emoji = "😎 Красавчик"
            is_game_played = True
        elif call.data == "ask_loh":
            final_text = get_comment("loh", stats['loh'])
            emoji = "😅 Лох"
            is_game_played = True
        elif call.data == "ask_size":
            final_text = get_comment("size", stats['size'])
            emoji = "🍆 Мой размер"
            is_game_played = True
        elif call.data == "roulette_play_next":
            current_streak = stats['roulette_current_streak']
            current_chance = current_streak + 1
            max_chance = 6
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🌀 Кручу барабан... (Шанс {current_chance}/{max_chance})")
                time.sleep(0.6)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🔫 Приставляю к виску...")
                time.sleep(0.6)
            except Exception: pass
            shot = random.randint(1, max_chance)
            is_dead = (shot <= current_chance)
            if is_dead:
                final_text = f"💥 БАМ! ({current_chance}/{max_chance}). Твоя удача кончилась на {current_chance}-м выстреле!"
                stats['roulette_best_streak'] = max(stats['roulette_best_streak'], current_streak)
                stats['roulette_current_streak'] = 0
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, reply_markup=back_markup)
                user_last_active_chat[user_id] = chat_id
                return
            else:
                stats['roulette_current_streak'] += 1
                new_streak = stats['roulette_current_streak']
                continue_markup = types.InlineKeyboardMarkup(row_width=1)
                if new_streak == max_chance - 1:
                    final_text = f"💨 Щелк! ({current_chance}/{max_chance}). НЕВЕРОЯТНО! Ты выжил... В барабане остался 1 патрон."
                    continue_btn = types.InlineKeyboardButton(f"Сделать выстрел (Шанс 6/6)", callback_data="roulette_play_next")
                else:
                    final_text = f"💨 Щелк! ({current_chance}/{max_chance}). Пронесло... Рискнешь еще?"
                    continue_btn = types.InlineKeyboardButton(f"Играть дальше (Шанс {new_streak + 1}/{max_chance})", callback_data="roulette_play_next")
                stop_btn = types.InlineKeyboardButton(f"🚫 Хватит (сохранить серию: {new_streak})", callback_data="go_back_to_menu")
                continue_markup.add(continue_btn, stop_btn)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, reply_markup=continue_markup)
                user_last_active_chat[user_id] = chat_id
                return
        if final_text:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text, reply_markup=back_markup)
            if is_game_played:
                user_last_active_chat[user_id] = chat_id
    except Exception as e:
        if "message is not modified" in str(e):
            pass
        else:
            logging.error(f"Ошибка в callback: {e}")

app = Flask(__name__)
@app.route('/')
def home(): return "Я жив, бот работает!"
def run():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
def start_server():
    Thread(target=run).start()

logging.info("Starting web server ...")
start_server()
logging.info("Starting Telegram bot ...")
bot.polling(none_stop=True)
