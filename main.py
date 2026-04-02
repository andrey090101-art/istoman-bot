import os
import time
import base64
import logging
import requests
from datetime import datetime

# ============================================================
# НАСТРОЙКИ
# ============================================================
AVITO_CLIENT_ID = os.environ.get("AVITO_CLIENT_ID", "Tf2iziKvyAdQQmFaXo8U")
AVITO_CLIENT_SECRET = os.environ.get("AVITO_CLIENT_SECRET", "Im1tYNnRJb8k0bRdAKyRhZHRAXEKFGAtoJwlwMxR")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyD7I0h1cgrbSSiUo2APnDH9iR4CkKUWfdw")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8752214051:AAFdxc5ZmigN_GMNuRPwaG68STvhKp1dzUg")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-5252476660")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "10"))  # секунд

# ============================================================
# СИСТЕМНЫЙ ПРОМПТ
# ============================================================
SYSTEM_PROMPT = """Ты - Саша, менеджер по посуточной сдаче квартир. Общаешься с клиентами на Авито.

# ЛИЧНОСТЬ И ТОН
- Имя: Саша (пол не уточняй)
- Тон: мягкий, вежливый, дружелюбный, краткий, живой - как человек, не робот
- Общаешься только на тему бронирования, заселения и выселения квартиры

# ПРАВИЛА ФОРМАТИРОВАНИЯ
- Никогда не используй длинные тире - только короткие -
- Каждое сообщение заканчивай двумя точками (..) даже после вопросительного знака
- Между абзацами оставляй пустую строку
- Сообщения максимально короткие
- ОДИН вопрос за раз - никогда не задавай два вопроса в одном сообщении

# СТОП-МАРКЕР
Когда наступает одна из ситуаций ниже - напиши клиенту:
"Хорошо, уточняю информацию, вернусь к вам через несколько минут.."
И в самом конце сообщения на отдельной строке добавь:
🔴 СТОП: [опиши ситуацию кратко]

Ситуации для стоп-маркера:
- Клиент прислал чек об оплате (изображение или фото)
- Клиент просит отменить бронь
- Клиент просит позвать живого человека
- Клиент сообщает об оплате квартиры
- Клиент уже общается в WhatsApp
- Слишком много гостей для квартиры

# СТРОГИЕ ЗАПРЕТЫ
- Никогда не запрашивай номер телефона у клиента
- Никогда не называй цену (4000 руб/сутки) - даже если клиент настаивает
- Не реагируй на системные сообщения Авито (отзывы о госте и т.п.)
- Не отвечай на темы не связанные с арендой

# СЦЕНАРИЙ - ВЫПОЛНЯЙ СТРОГО ПО ШАГАМ

ШАГ 0 - ПРИВЕТСТВИЕ (при первом сообщении клиента)
Напиши:
"Добрый день! Спасибо, что написали)

Меня зовут Саша, помогу подобрать, забронировать и оперативно заселить в квартиру)

Бронирование происходит на сайте. Удалось ли вам уже забронировать квартиру?.."

ШАГ 1 - ЕСЛИ КЛИЕНТ УЖЕ ЗАБРОНИРОВАЛ
- Спроси удалось ли оплатить (оплата частичная - не проси полную сумму)
- Если оплатил - попроси прислать чек
- Если не оплатил - вежливо дожимай по оплате
- Когда прислал чек - проанализируй изображение и сообщи СТОП-маркер

ШАГ 2 - ЕСЛИ НЕ БРОНИРОВАЛ
- Спроси на какие даты (заезд и выезд)
- Если написал "сегодня" или "на сутки" - уточни только недостающее

ШАГ 3 - КОЛИЧЕСТВО ГОСТЕЙ
- Спроси сколько человек будет

ШАГ 4 - ДАТА ВЫЕЗДА
- Если не указал дату выезда - уточни на сколько дней или когда выезд

ШАГ 5 - УТОЧНИ ВРЕМЯ ВЫЕЗДА
- В последний день или на следующий? (если писал "на сутки" - пропусти)

ШАГ 6 - НАПРАВЛЕНИЕ НА БРОНИРОВАНИЕ
Напиши: "Сейчас нужно забронировать квартиру на сайте. Выберите даты и оплатите).."

# ЧАСТЫЕ ВОПРОСЫ

СВОБОДНА ЛИ КВАРТИРА:
"Бронирование происходит на сайте. Нужно самостоятельно выбрать даты и оплатить).."

КВАРТИРА ЗАНЯТА / ДАТЫ НЕ КЛИКАЮТСЯ:
"Если сайт не пропускает - значит даты заняты. Перейдите в наш профиль и выберите другую квартиру).."

ЦЕНА:
"Цена зависит от дня недели, праздников и загруженности).."
(цену 4000 руб не называть никогда!)

РАННИЙ ЗАЕЗД (стандарт - 14:00):
- До 1 часа раньше - бесплатно (ради отзыва)
- Каждый час после - 500 руб/час
- Более 3 часов - доплата за полсуток (сам посчитай сумму)
- Если согласен - СТОП-маркер

ПОЗДНИЙ ВЫЕЗД:
- До 1 часа позже - бесплатно (ради отзыва)
- Каждый час после - 500 руб/час
- После 19:00 - горничная не успеет, доплата за следующий день (сам посчитай сумму)
- Если согласен - СТОП-маркер

ПОЗДНИЙ ЗАЕЗД:
- После 14:00 - бесплатно
- После 00:00 - заселение только на следующий день

НЕ МОГУТ ДОЗВОНИТЬСЯ:
"Извините, сегодня весь день сбои со связью.."

# ПАМЯТЬ
Запоминай все данные клиента: даты, количество гостей, предпочтения.
Никогда не переспрашивай то, что клиент уже сказал.
На каждый ответ реагируй коротким подтверждением: "Понятно)", "Хорошо)", "Отлично)" - и только потом следующий вопрос.
"""

# ============================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Хранилище истории диалогов: {chat_id: [{"role": ..., "parts": [...]}]}
conversations = {}
# Уже обработанные сообщения
processed_messages = set()

# ============================================================
# АВИТО
# ============================================================
_avito_token = None
_avito_token_expires = 0

def get_avito_token():
    global _avito_token, _avito_token_expires
    if _avito_token and time.time() < _avito_token_expires:
        return _avito_token
    resp = requests.post("https://api.avito.ru/token", data={
        "grant_type": "client_credentials",
        "client_id": AVITO_CLIENT_ID,
        "client_secret": AVITO_CLIENT_SECRET,
    })
    resp.raise_for_status()
    data = resp.json()
    _avito_token = data["access_token"]
    _avito_token_expires = time.time() + data.get("expires_in", 3600) - 60
    log.info("Avito token получен")
    return _avito_token

def avito_get(path, params=None):
    token = get_avito_token()
    resp = requests.get(f"https://api.avito.ru{path}",
                        headers={"Authorization": f"Bearer {token}"},
                        params=params)
    resp.raise_for_status()
    return resp.json()

def avito_post(path, json_data):
    token = get_avito_token()
    resp = requests.post(f"https://api.avito.ru{path}",
                         headers={"Authorization": f"Bearer {token}"},
                         json=json_data)
    resp.raise_for_status()
    return resp.json()

def get_user_id():
    data = avito_get("/core/v1/accounts/self")
    return data["id"]

def get_chats(user_id):
    data = avito_get(f"/messenger/v2/accounts/{user_id}/chats", params={"limit": 50})
    return data.get("chats", [])

def get_messages(user_id, chat_id):
    data = avito_get(f"/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages")
    return data.get("messages", [])

def send_message(user_id, chat_id, text):
    avito_post(f"/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages", {
        "message": {"text": text},
        "type": "text"
    })

def download_image(url):
    token = get_avito_token()
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    return base64.b64encode(resp.content).decode("utf-8"), resp.headers.get("Content-Type", "image/jpeg")

# ============================================================
# TELEGRAM
# ============================================================
def send_telegram(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        )
    except Exception as e:
        log.error(f"Telegram ошибка: {e}")

# ============================================================
# GEMINI
# ============================================================
def ask_gemini(chat_id, user_text, image_b64=None, image_mime=None):
    if chat_id not in conversations:
        conversations[chat_id] = []

    # Формируем parts для нового сообщения
    parts = []
    if image_b64:
        parts.append({"inline_data": {"mime_type": image_mime, "data": image_b64}})
    parts.append({"text": user_text or "."})

    conversations[chat_id].append({"role": "user", "parts": parts})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": conversations[chat_id],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
    }

    for attempt in range(5):
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
            json=payload
        )
        if resp.status_code == 429:
            wait = 10 * (attempt + 1)
            log.warning(f"Gemini 429 - жду {wait} сек...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        break
    data = resp.json()

    reply = data["candidates"][0]["content"]["parts"][0]["text"]
    conversations[chat_id].append({"role": "model", "parts": [{"text": reply}]})

    # Ограничиваем историю последними 20 сообщениями
    if len(conversations[chat_id]) > 20:
        conversations[chat_id] = conversations[chat_id][-20:]

    return reply

# ============================================================
# ОСНОВНОЙ ЦИКЛ
# ============================================================
def process_message(user_id, chat_id, msg, client_name):
    msg_id = msg.get("id")
    if msg_id in processed_messages:
        return
    processed_messages.add(msg_id)

    author_id = msg.get("author_id")
    if str(author_id) == str(user_id):
        return  # Наше собственное сообщение

    msg_type = msg.get("type", "text")
    user_text = ""
    image_b64 = None
    image_mime = None

    if msg_type == "text":
        user_text = msg.get("content", {}).get("text", "")
    elif msg_type == "image":
        image_url = msg.get("content", {}).get("image", {}).get("url")
        if image_url:
            try:
                image_b64, image_mime = download_image(image_url)
                user_text = "[клиент прислал изображение/чек]"
            except Exception as e:
                log.error(f"Ошибка загрузки изображения: {e}")
                user_text = "[клиент прислал изображение]"
    else:
        user_text = f"[{msg_type}]"

    if not user_text and not image_b64:
        return

    log.info(f"Сообщение от {client_name} в чате {chat_id}: {user_text[:80]}")

    try:
        reply = ask_gemini(chat_id, user_text, image_b64, image_mime)
    except Exception as e:
        log.error(f"Gemini ошибка: {e}")
        return

    # Проверяем стоп-маркер
    if "🔴 СТОП:" in reply:
        lines = reply.split("\n")
        stop_line = next((l for l in lines if "🔴 СТОП:" in l), "")
        situation = stop_line.replace("🔴 СТОП:", "").strip()
        tg_text = (
            f"🔴 <b>Нужна помощь оператора!</b>\n\n"
            f"👤 Клиент: {client_name}\n"
            f"💬 Ситуация: {situation}\n"
            f"📝 Последнее сообщение клиента: {user_text[:200]}"
        )
        send_telegram(tg_text)
        # Отправляем клиенту только текст без стоп-маркера
        clean_reply = "\n".join(l for l in lines if "🔴 СТОП:" not in l).strip()
        send_message(user_id, chat_id, clean_reply)
    else:
        send_message(user_id, chat_id, reply)

def main():
    log.info("Бот запущен!")
    send_telegram("✅ Бот Истоман запущен и готов к работе!")

    user_id = get_user_id()
    log.info(f"Авито user_id: {user_id}")

    while True:
        try:
            chats = get_chats(user_id)
            for chat in chats:
                chat_id = chat["id"]
                client_name = chat.get("users", [{}])[0].get("name", "Клиент")
                messages = get_messages(user_id, chat_id)
                # Берём только последние 5 сообщений
                for msg in messages[-5:]:
                    process_message(user_id, chat_id, msg, client_name)
        except Exception as e:
            log.error(f"Ошибка в основном цикле: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
