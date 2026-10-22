import os
import time
import requests
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHANNEL_ID = os.environ.get("TG_CHANNEL_ID", "-1004329382085")

PROMO_CODE = "Soleilqqe"
MODEL = "gemini-3.8-flash"


def get_uzbek_market_news():
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        api_url = "https://openinfo.uz/api/v2/disclosure/facts/?format=json&page_size=5"
        resp = requests.get(api_url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            news_list = []
            for item in data.get("results", []):
                org = item.get("organization_name", "Компания")
                title = item.get("fact_title", "Существенный факт")
                date = item.get("pub_date", "")
                news_list.append(f"Эмитент: {org} | Событие: {title} | Дата: {date}")
            if news_list:
                return "\n".join(news_list)
    except Exception as e:
        print(f"Лог парсера: {e}")

    return "Инфоповод дня: разбор главных дивидендных акций РФБ Тошкент (Узтелеком, АГМК, Узбекинвест) и стратегия регулярных покупок."


def generate_text(client, prompt, attempts=4):
    for i in range(1, attempts + 1):
        try:
            response = client.models.generate_content(model=MODEL, contents=prompt)
            if response and response.text:
                return response.text
            print(f"Попытка {i}: пустой ответ")
        except Exception as e:
            print(f"Попытка {i}: ошибка Gemini: {e}")
        if i < attempts:
            time.sleep(10 * i)
    raise Exception("Gemini не ответил после нескольких попыток.")


def run_agent():
    if not GEMINI_API_KEY or not TG_BOT_TOKEN:
        raise Exception("Не заданы секреты GEMINI_API_KEY или TG_BOT_TOKEN в GitHub Secrets.")

    print("1. Скаут проверяет openinfo.uz...")
    raw_news = get_uzbek_market_news()

    print("2. Аналитик Gemini пишет посты...")
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
    Ты четкий финансовый аналитик фондового рынка Узбекистана (РФБ Тошкент) с хорошим чувством юмора и легкой самоиронией.
    На основе этих данных напиши ДВА готовых поста:

    1) Пост для Telegram-канала (структурно, по фактам, с легким юмором про узбекский рынок).
    2) Короткий дерзкий вброс для Threads (до 350 символов), чтобы забайтить людей на комментарии.

    Строгие правила:
    * Вообще не используй символ тире в тексте (заменяй двоеточием или запятыми).
    * В конце поста для Telegram нативно и с юмором напиши, что сам берешь акции через приложение Jett, и предложи ввести промокод {PROMO_CODE} при регистрации (честно обыграй, что новичку он ничего не даст, зато автору капнет 5000 сум на кофе и оплату серверов для этого ИИ-агента, а за скрин ввода кода ты скинешь полезный бонус по рынку).

    Данные для анализа:
    {raw_news}
    """

    text = generate_text(client, prompt)

    print("3. Публикатор отправляет пост в закрытый ТГ-канал...")
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    res = requests.post(url, json={
        "chat_id": TG_CHANNEL_ID,
        "text": text[:4096],
    }, timeout=30)
    print("Ответ Телеграма:", res.json())

    if not res.ok:
        raise Exception(f"Telegram вернул ошибку: {res.text}")


if __name__ == "__main__":
    run_agent()
