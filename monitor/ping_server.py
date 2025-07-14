import asyncio
import os
import time

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile
from dotenv import load_dotenv
import shutil

load_dotenv()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HOST = os.getenv("SERVER_HOST")

HTTP = f"http://{HOST}:3000"
CHECK_URLS = [
    (f"{HTTP}/projects/1/", {}),
]
AUTH_URL = f"{HTTP}/login"
LOG_URLS = [f"{HTTP}/debug/log/error"]

LOG_DIR = "./logs"
CRITICAL_LOG = os.path.join(LOG_DIR, "critical.log")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)
session = requests.Session()

last_check_message_id = None
last_critical_size = 0


def auth():
    resp = session.post(AUTH_URL, json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    return resp.status_code == 200


def check_urls():
    for url, data in CHECK_URLS:
        resp = session.post(url, json=data)
        if resp.status_code == 401:
            if not auth():
                return False, f"Авторизация не удалась для {url}"
            resp = session.post(url, json=data)
        if resp.status_code != 200:
            return False, f"Ошибка {resp.status_code} для {url}"
    return True, None


def get_log_files():
    filenames = []
    for i, log_url in enumerate(LOG_URLS, start=1):
        resp = session.get(log_url, stream=True)
        if resp.status_code == 200:
            filename = f"server_error_log_{i}.txt"
            with open(filename, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            filenames.append(filename)
    return filenames


async def send_check_status(text, file_paths=None):
    global last_check_message_id

    if last_check_message_id:
        try:
            await bot.edit_message_text(
                chat_id=TELEGRAM_CHAT_ID,
                message_id=last_check_message_id,
                text=text
            )
        except Exception:
            msg = await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
            last_check_message_id = msg.message_id
    else:
        msg = await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
        last_check_message_id = msg.message_id

    if file_paths:
        for file_path in file_paths:
            input_file = InputFile(file_path)
            await bot.send_document(chat_id=TELEGRAM_CHAT_ID, document=input_file)


async def monitor_critical_log():
    global last_critical_size
    while True:
        try:
            size = os.path.getsize(CRITICAL_LOG)
            if size > last_critical_size:
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="⚠️ Обновление critical.log")
                await bot.send_document(chat_id=TELEGRAM_CHAT_ID, document=InputFile(CRITICAL_LOG))
                last_critical_size = size
        except FileNotFoundError:
            pass
        await asyncio.sleep(10)


@dp.message_handler(commands=["error"])
async def send_error_log(message: types.Message):
    path = os.path.join(LOG_DIR, "error.log")
    await message.answer_document(InputFile(path))


@dp.message_handler(commands=["warning"])
async def send_warning_log(message: types.Message):
    path = os.path.join(LOG_DIR, "warning.log")
    await message.answer_document(InputFile(path))


@dp.message_handler(commands=["fastapi"])
async def send_fastapi_log(message: types.Message):
    path = os.path.join(LOG_DIR, "fastapi.log")
    await message.answer_document(InputFile(path))


@dp.message_handler(commands=["info"])
async def send_info_log(message: types.Message):
    path = os.path.join(LOG_DIR, "info.log")
    await message.answer_document(InputFile(path))


@dp.message_handler(commands=["logs"])
async def send_logs_archive(message: types.Message):
    archive_path = "./logs.rar"
    shutil.make_archive("logs", "zip", LOG_DIR)
    os.rename("logs.zip", archive_path)
    await message.answer_document(InputFile(archive_path))


async def main_loop():
    while True:
        ok, error = check_urls()
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        if ok:
            await send_check_status(f"✅ САПР жив!. Проверка в {now}")
        else:
            await send_check_status(f"❗ Проблема с сервером в {now}: {error}")
            log_files = get_log_files()
            for file_path in log_files:
                await bot.send_document(chat_id=TELEGRAM_CHAT_ID, document=InputFile(file_path))

        await asyncio.sleep(60)


async def main():
    await asyncio.gather(
        main_loop(),
        monitor_critical_log(),
        dp.start_polling()
    )


if __name__ == "__main__":
    asyncio.run(main())
