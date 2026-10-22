import os
import json
import time
import hashlib
import requests
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHANNEL_ID = os.environ.get("TG_CHANNEL_ID", "-1004329382085")

PROMO_CODE = "Soleilqqe"
MODEL = "gemini-3.8-flash"
SEEN_FILE = "seen.json"


def load_seen():
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return None  # файла нет: первый запуск


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen)[-500:], f)


def fetch_facts():
    headers = {"User-Agent": "Mozilla/5.0"}
    api_url = "https://openinfo.uz/api/v2/disclosure/facts/?format=json&page_size=10"
    resp = requests.get(api_url, headers=headers, timeout=15)
    resp.raise_for_status()
    facts = []
    for item in resp.json().get("results", []):
        org = item.get("organization_name", "Компания")
        title = item.get("fact_title", "Существенный факт")
        date = item.get("pub_date", "")
        uid = str(item.get("id") or hashlib.md5(f"{org}{title}{date}".encode()).hexdigest())
        facts.append((uid, f"Эмитент: {org} | Событие: {title} | Дата: {date}"))
    return facts


def generate_text(client, prompt, attempts=4):
    for i in range(1, attempts + 1):
        try:
            r = client.models.generate_content(model=MODEL, contents=prompt)
            if r and r.text:
                return r.text
        except Exception as e:
            print(f"Попытка {i}: ошибка Gemini: {e}")
        if i < attempts:
            time.sleep(10 * i)
    raise Exception("Gemini не ответил после нескольких попыток.")


def run_agent():
    if not GEMINI_API_KEY or not TG_BOT_TOKEN:
        raise Exception("Не заданы GEMINI_API_KEY или TG_BOT_TOKEN в Secrets.")

    print("1. Скаут проверяет openinfo.uz...")
    facts = fetch_facts()
    seen = load_seen()

    if seen is None:
        save_seen({uid for uid, _ in facts})
        print("Первый запуск: текущие новости запомнил, публиковать начну со следующих.")
        return

    new = [(uid, line) for uid, line in facts if uid not in seen]
    if not new:
        print("Новых фактов нет.")
        return

    print(f"Новых фактов: {len(new)}")
    raw_news = "\n".join(line for _, line in new)

    print("2. Аналитик Gemini пишет посты...")
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
    Ты четкий финансовый аналитик фондового рынка Узбекистана (РФБ Тошкент) с хорошим чувством юмора и легкой самоиронией.
    Напиши ДВА поста, разделённых отдельной строкой ===THREADS===

    1) Пост для Telegram-канала (структурно, по фактам, с легким юмором про узбекский рынок).
    2) Короткий дерзкий вброс для Threads (до 350 символов), чтобы забайтить людей на комментарии.

    Строгие правила:
    * Вообще не используй символ тире в тексте (заменяй двоеточием или запятыми).
    * Шути над рынком в целом, не намекай на нарушения конкретных компаний и не приписывай им мотивов.
    * В конце поста для Telegram нативно и с юмором напиши, что сам берешь акции через приложение Jett, и предложи ввести промокод {PROMO_CODE} при регистрации (честно обыграй, что новичку он ничего не даст, зато автору капнет 5000 сум на кофе и оплату серверов для этого ИИ-агента, а за скрин ввода кода ты скинешь полезный бонус по рынку).

    Данные для анализа:
    {raw_news}
    """

    text = generate_text(client, prompt)
    parts = text.split("===THREADS===")
    tg_post = parts[0].strip()
    threads_post = parts[1].strip() if len(parts) > 1 else ""

    print("3. Публикатор отправляет пост в ТГ-канал...")
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    res = requests.post(url, json={"chat_id": TG_CHANNEL_ID, "text": tg_post[:4096]}, timeout=30)
    print("Ответ Телеграма:", res.json())
    if not res.ok:
        raise Exception(f"Telegram вернул ошибку: {res.text}")

    save_seen(seen | {uid for uid, _ in new})
    print("Threads-пост (скопируй вручную):\n", threads_post)


if __name__ == "__main__":
    run_agent()
