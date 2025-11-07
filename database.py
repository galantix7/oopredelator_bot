import os
import psycopg2
import psycopg2.extras # Нам нужен RealDictCursor
import datetime
import random
import json

# Получаем URL из переменных окружения Render
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """Создает и возвращает соединение с БД."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"!!! ОШИБКА ПОДКЛЮЧЕНИЯ К БД: {e}")
        return None

def init_db():
    """Инициализирует базу данных и создает таблицы, если их нет."""
    # PostgreSQL синтаксис немного отличается
    create_stats_table = """
    CREATE TABLE IF NOT EXISTS user_stats (
        user_id BIGINT,
        chat_id BIGINT,
        date TEXT,
        name TEXT,
        krasavchik INTEGER,
        loh INTEGER,
        size INTEGER,
        roulette_best_streak INTEGER,
        roulette_current_streak INTEGER,
        PRIMARY KEY (user_id, chat_id, date)
    );
    """
    
    create_activity_table = """
    CREATE TABLE IF NOT EXISTS user_activity (
        user_id BIGINT PRIMARY KEY,
        last_chat_id BIGINT
    );
    """
    
    create_polls_table = """
    CREATE TABLE IF NOT EXISTS polls (
        message_id BIGINT PRIMARY KEY,
        chat_id BIGINT,
        question TEXT,
        creator_id BIGINT,
        votes JSONB 
    );
    """
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(create_stats_table)
                cursor.execute(create_activity_table)
                cursor.execute(create_polls_table)
            conn.commit()
        print("База данных PostgreSQL инициализирована.")
    except Exception as e:
        print(f"!!! ОШИБКА init_db: {e}")

# --- Функции для Игровой Статистики ---
# (Запросы заменены с '?' на '%s')

def get_or_create_user_stats(user_id, chat_id, user_name, today_str):
    """
    Получает статистику пользователя за сегодня. 
    Если ее нет - создает, записывает в БД и возвращает.
    """
    sql_select = "SELECT * FROM user_stats WHERE user_id = %s AND chat_id = %s AND date = %s"
    
    with get_db_connection() as conn:
        # RealDictCursor возвращает строки в виде словарей, как мы и привыкли
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            
            cursor.execute(sql_select, (user_id, chat_id, today_str))
            stats = cursor.fetchone()
            
            if stats:
                return dict(stats)
            else:
                new_stats = {
                    'user_id': user_id,
                    'chat_id': chat_id,
                    'date': today_str,
                    'name': user_name,
                    'krasavchik': random.randint(0, 100),
                    'loh': random.randint(0, 100),
                    'size': random.randint(1, 30),
                    'roulette_best_streak': 0,
                    'roulette_current_streak': 0
                }
                
                sql_insert = """
                INSERT INTO user_stats (user_id, chat_id, date, name, krasavchik, loh, size, roulette_best_streak, roulette_current_streak)
                VALUES (%(user_id)s, %(chat_id)s, %(date)s, %(name)s, %(krasavchik)s, %(loh)s, %(size)s, %(roulette_best_streak)s, %(roulette_current_streak)s)
                """
                cursor.execute(sql_insert, new_stats)
                conn.commit()
                
                update_last_active_chat(user_id, chat_id)
                return new_stats

def update_user_stats(user_id, chat_id, today_str, key, value):
    """Безопасно обновляет одно поле в статистике."""
    
    allowed_keys = ['roulette_best_streak', 'roulette_current_streak', 'name']
    if key not in allowed_keys:
        print(f"Попытка обновить запрещенное поле: {key}")
        return 
        
    # f-строка для имени колонки безопасна, т.к. мы ее проверили
    sql_update = f"UPDATE user_stats SET {key} = %s WHERE user_id = %s AND chat_id = %s AND date = %s"
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql_update, (value, user_id, chat_id, today_str))
            conn.commit()

def get_chat_statistics(chat_id, today_str):
    """Получает ВСЮ статистику по чату за сегодня."""
    sql_select = "SELECT * FROM user_stats WHERE chat_id = %s AND date = %s"
    
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(sql_select, (chat_id, today_str))
            rows = cursor.fetchall()
            # Превращаем список [dict, dict] в словарь {user_id: dict, ...}
            stats_dict = {row['user_id']: dict(row) for row in rows}
            return stats_dict

# --- Функции для Инлайн-Режима ---

def update_last_active_chat(user_id, chat_id):
    """Обновляет или вставляет (UPSERT) последний активный чат."""
    # Синтаксис UPSERT в PostgreSQL
    sql_upsert = """
    INSERT INTO user_activity (user_id, last_chat_id) VALUES (%s, %s)
    ON CONFLICT (user_id) DO UPDATE SET last_chat_id = EXCLUDED.last_chat_id
    """
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql_upsert, (user_id, chat_id))
            conn.commit()

def get_last_active_chat(user_id):
    """Получает ID последнего чата, где играл юзер."""
    sql_select = "SELECT last_chat_id FROM user_activity WHERE user_id = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql_select, (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None

def get_user_stats_for_inline(user_id, chat_id, today_str):
    """Получает статистику ОДНОГО юзера для инлайн-режима."""
    if not chat_id:
        return None
        
    sql_select = "SELECT * FROM user_stats WHERE user_id = %s AND chat_id = %s AND date = %s"
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(sql_select, (user_id, chat_id, today_str))
            stats = cursor.fetchone()
            return dict(stats) if stats else None

# --- Функции для Опросов (/go) ---

def create_poll(message_id, chat_id, question, creator_id):
    """Создает новый опрос в БД."""
    empty_votes = {'going': {}, 'not_going': {}}
    # psycopg2 сам преобразует dict в JSONB
    
    sql_insert = """
    INSERT INTO polls (message_id, chat_id, question, creator_id, votes)
    VALUES (%s, %s, %s, %s, %s)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql_insert, (message_id, chat_id, question, creator_id, json.dumps(empty_votes)))
            conn.commit()

def get_poll_data(message_id):
    """Получает данные опроса по ID сообщения."""
    sql_select = "SELECT * FROM polls WHERE message_id = %s"
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(sql_select, (message_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # `votes` уже будет словарем, т.к. это JSONB и RealDictCursor
            return dict(row) 

def update_poll_vote(message_id, user_id, user_name, vote_type):
    """Обновляет голос в опросе."""
    poll_data = get_poll_data(message_id)
    if not poll_data:
        return None 

    votes = poll_data['votes'] # Это уже словарь
    
    # ID юзеров должны быть строками для ключей JSON
    user_id_str = str(user_id) 
    
    if vote_type == 'go':
        votes['going'][user_id_str] = user_name
        votes['not_going'].pop(user_id_str, None)
    elif vote_type == 'pass':
        votes['not_going'][user_id_str] = user_name
        votes['going'].pop(user_id_str, None)

    sql_update = "UPDATE polls SET votes = %s WHERE message_id = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql_update, (json.dumps(votes), message_id))
            conn.commit()
        
    return poll_data 

def delete_poll(message_id):
    """Удаляет опрос из БД (когда он закрыт)."""
    sql_delete = "DELETE FROM polls WHERE message_id = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql_delete, (message_id,))
            conn.commit()
