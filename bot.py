import os
import telebot
import random
import datetime
import time
from flask import Flask
from threading import Thread
from telebot import types
import database
import utils

# Настройка токена бота
BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# Flask сервер (если нужен)
app = Flask(__name__)

def start_server():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

# Инициализация базы данных
database.init_db()

# Обработчик /start
@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.first_name
    today_str = str(datetime.date.today())

    # Обновляем или добавляем статистику
    stats = database.get_or_create_user_stats(user_id, chat_id, username, today_str)

    bot.send_message(chat_id, "Привет! Бот запущен.")

# Обработчик /groupstats
@bot.message_handler(commands=['groupstats'])
def handle_group_stats(message):
    send_group_stats(message.chat.id, message.message_id, False)

def send_group_stats(chat_id, message_id, is_callback):
    today_str = str(datetime.date.today())

    # Удаляем команду /groupstats если не колбэк
    if not is_callback:
        try:
            bot.delete_message(chat_id, message_id)
        except Exception:
            pass

    # Удаление старого отчета (если есть)
    if chat_id in utils.last_stats_message:
        try:
            bot.delete_message(chat_id, utils.last_stats_message[chat_id])
        except Exception:
            pass
        del utils.last_stats_message[chat_id]
    try:
        stats_dict = database.get_chat_statistics(chat_id, today_str)

        if not stats_dict:
            text = f"Статистика за {today_str} в этом чате еще не собрана."
            if is_callback:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
            else:
                bot.send_message(chat_id, text)
            return

        # Формируем отчет
        report = ["📊 Статистика игр за {}:".format(today_str)]
        sorted_stats = sorted(stats_dict.items(), key=lambda x: x[1].get('krasavchik', 0), reverse=True)
        for user_id, data in sorted_stats:
            name_safe = utils.safe_html(data['name'])
            kras = data['krasavchik']
            loh = data['loh']
            size = data['size']
            streak = data.get('roulette_best_streak', 0)
            report.append(f" - {name_safe}: Красавчик {kras}%, Лох {loh}%")
        # Добавляем топов
        king = max(stats_dict.values(), key=lambda d: d.get('krasavchik', 0))
        report.append(f"\n👑 Топ Красавчик: {utils.safe_html(king['name'])}")
        loser = max(stats_dict.values(), key=lambda d: d.get('loh', 0))
        report.append(f"🤦‍♂️ Топ Лох: {utils.safe_html(loser['name'])}")
        final_text = "\n".join(report)

        if is_callback:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text)
        else:
            msg = bot.send_message(chat_id, final_text)
            utils.last_stats_message[chat_id] = msg.message_id
    except Exception as e:
        print(f"Ошибка в send_group_stats: {e}")

# Обработчик /go
@bot.message_handler(commands=['go'])
def handle_create_poll(message):
    chat_id = message.chat.id
    question = message.text[len('/go'):].strip()
    if not question:
        bot.send_message(chat_id, "Задайте вопрос: /go Кто идет?")
        return
    # Создаем опрос
    try:
        database.create_poll_message_id(message.message_id, chat_id, question, message.from_user.id)
        bot.send_message(chat_id, "Опрос создан.")
    except Exception as e:
        print(f"Ошибка при создании опроса: {e}")

# Обработчик калбеков
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        # Реакция на кнопку
        if call.data == "show_group_stats":
            send_group_stats(call.message.chat.id, call.message.message_id, True)
    except Exception as e:
        print(f"Обработка коллбэка вызвала ошибку: {e}")

# Запуск Flask-сервера
Thread(target=start_server).start()

# Запуск бота
print("Запуск бота...")
bot.polling(non_stop=True)
