import html
import random
import time
import telebot
from telebot import types

# --- Константы ---
MAIN_MENU_TEXT = "Докажи, что не терпила!:"

# --- Текстовые "комментарии" ---

def safe_html(text):
    """Экранирует спецсимволы HTML."""
    return html.escape(str(text))

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
    """Возвращает смешной комментарий в зависимости от процента 'лоха'."""
    if percent <= 20:
        return f"Сегодня я лох всего на {percent}%! 🎉 (Ты в безопасности!)"
    elif percent <= 50:
        return f"Сегодня я лох на {percent}%. (Ну, бывает и хуже...)"
    elif percent <= 80:
        return f"Сегодня я лох на {percent}%... 😬 (Осторожнее, есть риски)"
    else: # 81-100
        return f"Сегодня я лох на {percent}%! 🤦‍♂️ (КОМБО! Лучше не рисковать)"

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

# --- Генераторы клавиатур (Markup) ---

def create_main_menu_markup():
    """Создает ГЛАВНОЕ МЕНЮ (4 кнопки)"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("Красавчик 😎", callback_data="ask_krasavchik")
    btn2 = types.InlineKeyboardButton("Лох 😅", callback_data="ask_loh")
    btn5 = types.InlineKeyboardButton("Мой размер 🍆", callback_data="ask_size")
    btn3 = types.InlineKeyboardButton("📊 Статистика", callback_data="show_group_stats")
    btn4 = types.InlineKeyboardButton("🇺🇦 Русская рулетка", callback_data="roulette_play_next")
    markup.add(btn1, btn2, btn5, btn3, btn4)
    return markup

def create_back_to_menu_markup():
    """Создает клавиатуру с ОДНОЙ кнопкой 'Назад'"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data="go_back_to_menu")
    markup.add(back_btn)
    return markup

def create_poll_markup():
    """Создает кнопки для ОПРОСА (/go)"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_go = types.InlineKeyboardButton(f"Я иду! 👍", callback_data="poll_go")
    btn_pass = types.InlineKeyboardButton(f"Я пас 👎", callback_data="poll_pass")
    btn_close = types.InlineKeyboardButton("🔒 Закрыть опрос", callback_data="poll_close")
    markup.add(btn_go, btn_pass, btn_close)
    return markup

# --- Форматирование опроса ---

def format_poll_text(poll_data):
    """Генерирует ТЕКСТ опроса со списками имен."""
    question = safe_html(poll_data['question'])
    votes = poll_data['votes'] # Это словарь {'going': {...}, 'not_going': {...}}
    
    names_going = [safe_html(name) for name in votes['going'].values()]
    names_not_going = [safe_html(name) for name in votes['not_going'].values()]
    
    text_going = " - (пока нет)"
    if names_going:
        text_going = "\n".join([f" - <b>{name}</b>" for name in names_going])
        
    text_not_going = " - (пока нет)"
    if names_not_going:
        text_not_going = "\n".join([f" - {name}" for name in names_not_going])
        
    final_text = f"📣 <b>ОПРОС:</b> {question}\n" \
                 f"--------------------\n" \
                 f"👍 <b>Идут ({len(names_going)}):</b>\n{text_going}\n\n" \
                 f"👎 <b>Пас ({len(names_not_going)}):</b>\n{text_not_going}"
                 
    return final_text

# --- Функция Анимации ---

def show_game_animation(bot_instance, call, animation_prefix, final_text, units="%", min_val=0, max_val=100, emoji="📏"):
    """
    Показывает унифицированную анимацию прокрутки и 
    финальный результат с кнопкой 'Назад'.
    """
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    try:
        # 1. Анимация
        for i in range(6):
            fake_value = random.randint(min_val, max_val)
            current_emoji = "🎰" if i < 5 else emoji
            text = f"{current_emoji} {animation_prefix}: Кручу... {fake_value}{units}"
            
            bot_instance.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
            time.sleep(0.4)
            
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" in str(e): pass
        else: print(f"Ошибка в цикле анимации: {e}")

    # 2. Показываем финальный результат
    bot_instance.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=final_text,
        reply_markup=create_back_to_menu_markup()
    )
