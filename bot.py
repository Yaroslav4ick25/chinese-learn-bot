import urllib.request
import json
import time
import os
import uuid
import mimetypes

from lessons import LESSONS, DIALOGUES
from progress import get_progress, set_progress

TOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN_HERE")
API = f"https://api.telegram.org/bot{TOKEN}"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LEVELS = ["HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6"]
LESSONS_BY_ID = {l["id"]: l for l in LESSONS}
LESSONS_BY_LEVEL = {lvl: [l["id"] for l in LESSONS if l["level"] == lvl] for lvl in LEVELS}
PAGE_SIZE = 10

# session[chat_id] = {"lesson": int, "step": "words"|"grammar"|"dialogue"|"quiz",
#                      "quiz_q": int, "quiz_score": int}
session = {}


def api(method, **params):
    data = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{API}/{method}",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"API error {method}: {e}")
        return {}


def send(chat_id, text, keyboard=None, parse_mode="HTML"):
    params = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if keyboard:
        params["reply_markup"] = keyboard
    return api("sendMessage", **params)


def send_audio(chat_id, rel_path, caption=None, keyboard=None):
    file_path = os.path.join(BASE_DIR, rel_path)
    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
    except OSError as e:
        print(f"Audio file error: {e}")
        return {}

    filename = os.path.basename(file_path)
    mime_type = mimetypes.guess_type(filename)[0] or "audio/mpeg"
    boundary = uuid.uuid4().hex

    def field(name, value):
        return (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode()

    parts = [field("chat_id", chat_id)]
    if caption:
        parts.append(field("caption", caption))
        parts.append(field("parse_mode", "HTML"))
    if keyboard:
        parts.append(field("reply_markup", json.dumps(keyboard)))
    parts.append(
        (f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; filename="{filename}"\r\n'
         f'Content-Type: {mime_type}\r\n\r\n').encode() + file_data + b'\r\n'
    )
    parts.append(f'--{boundary}--\r\n'.encode())
    body = b"".join(parts)

    req = urllib.request.Request(
        f"{API}/sendAudio",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"API error sendAudio: {e}")
        return {}


def edit_markup(chat_id, msg_id, keyboard=None):
    params = {"chat_id": chat_id, "message_id": msg_id,
              "reply_markup": keyboard or {"inline_keyboard": []}}
    api("editMessageReplyMarkup", **params)


def answer_callback(callback_id, text=""):
    api("answerCallbackQuery", callback_query_id=callback_id, text=text)


def main_menu_keyboard(chat_id):
    progress = get_progress(chat_id)
    buttons = []
    next_id = progress.get("current_lesson", 0) + 1
    if next_id in LESSONS_BY_ID:
        label = "▶️ Продолжить обучение" if progress.get("completed") else "🚀 Начать урок 1"
        buttons.append([{"text": label, "callback_data": f"lesson:{next_id}:words"}])
    buttons.append([{"text": "📚 Выбрать уровень HSK", "callback_data": "nav:levels"}])
    return {"inline_keyboard": buttons}


def levels_keyboard():
    buttons = [[{"text": f"Уровень {lvl}", "callback_data": f"nav:level:{lvl}:0"}] for lvl in LEVELS]
    buttons.append([{"text": "🏠 Главное меню", "callback_data": "nav:home"}])
    return {"inline_keyboard": buttons}


def lessons_page_keyboard(chat_id, level, page):
    progress = get_progress(chat_id)
    completed = set(progress.get("completed", []))
    ids = LESSONS_BY_LEVEL[level]
    start = page * PAGE_SIZE
    chunk = ids[start:start + PAGE_SIZE]
    buttons = []
    for lid in chunk:
        mark = "✅ " if lid in completed else ""
        buttons.append([{"text": f"{mark}{LESSONS_BY_ID[lid]['title']}", "callback_data": f"lesson:{lid}:words"}])
    nav_row = []
    if start > 0:
        nav_row.append({"text": "« Назад", "callback_data": f"nav:level:{level}:{page - 1}"})
    if start + PAGE_SIZE < len(ids):
        nav_row.append({"text": "Вперёд »", "callback_data": f"nav:level:{level}:{page + 1}"})
    if nav_row:
        buttons.append(nav_row)
    buttons.append([{"text": "📚 Все уровни", "callback_data": "nav:levels"}])
    return {"inline_keyboard": buttons}


def next_keyboard(lesson_id, target):
    return {"inline_keyboard": [[{"text": "Дальше ▶️", "callback_data": f"lesson:{lesson_id}:{target}"}]]}


def quiz_keyboard(lesson_id, q_index, options):
    buttons = [[{"text": f"{k}) {v}", "callback_data": f"quizans:{lesson_id}:{q_index}:{k}"}]
               for k, v in options.items()]
    return {"inline_keyboard": buttons}


def after_quiz_keyboard(lesson_id):
    buttons = []
    if lesson_id + 1 in LESSONS_BY_ID:
        buttons.append([{"text": "➡️ Следующий урок", "callback_data": f"lesson:{lesson_id + 1}:words"}])
    buttons.append([{"text": "📚 Все уровни", "callback_data": "nav:levels"}])
    return {"inline_keyboard": buttons}


def handle_start(chat_id):
    send(chat_id,
         "👋 <b>Добро пожаловать!</b>\n\n"
         "Полный курс китайского языка по программе <b>HSK 1–6</b> (5000 слов, 501 урок): "
         "новые слова с произношением, грамматика, диалог для аудирования и мини-тест.\n\n"
         "Выберите, с чего начать:",
         keyboard=main_menu_keyboard(chat_id))


def send_words(chat_id, lesson_id):
    l = LESSONS_BY_ID[lesson_id]
    session[chat_id] = {"lesson": lesson_id, "quiz_q": 0, "quiz_score": 0}
    lines = [f"📚 <b>Урок {lesson_id}/{len(LESSONS)} [{l['level']}]: {l['title']}</b>\n", "Новые слова:\n"]
    for w in l["words"]:
        lines.append(f"<b>{w['hanzi']}</b> ({w['pinyin']}) — {w['translation']}")
    text = "\n".join(lines)

    audio_path = f"audio/lesson_{lesson_id}.mp3"
    if os.path.exists(os.path.join(BASE_DIR, audio_path)):
        send(chat_id, text)
        send_audio(chat_id, audio_path, caption="🔊 Произношение новых слов",
                   keyboard=next_keyboard(lesson_id, "grammar"))
    else:
        send(chat_id, text, keyboard=next_keyboard(lesson_id, "grammar"))


def send_grammar(chat_id, lesson_id):
    l = LESSONS_BY_ID[lesson_id]
    send(chat_id, f"📖 <b>Грамматика</b>\n\n{l['grammar']}",
         keyboard=next_keyboard(lesson_id, "dialogue"))


def send_dialogue(chat_id, lesson_id):
    l = LESSONS_BY_ID[lesson_id]
    dlg = DIALOGUES[l["dialogue"]]
    lines = "\n".join(f"<b>{speaker}:</b> {hanzi} ({pinyin})\n<i>{translation}</i>"
                       for speaker, hanzi, pinyin, translation in dlg)
    text = f"💬 <b>Диалог для аудирования</b>\n\n{lines}"

    audio_path = f"audio/dialog_{l['dialogue']}.mp3"
    if os.path.exists(os.path.join(BASE_DIR, audio_path)):
        send(chat_id, text)
        send_audio(chat_id, audio_path, caption="🔊 Озвучка диалога",
                   keyboard=next_keyboard(lesson_id, "quiz"))
    else:
        send(chat_id, text, keyboard=next_keyboard(lesson_id, "quiz"))


def send_quiz_question(chat_id, lesson_id, q_index):
    l = LESSONS_BY_ID[lesson_id]
    q = l["quiz"][q_index]
    text = f"❓ <b>Мини-тест {q_index + 1}/{len(l['quiz'])}</b>\n\n{q['text']}"
    send(chat_id, text, keyboard=quiz_keyboard(lesson_id, q_index, q["options"]))


def handle_lesson_nav(chat_id, lesson_id, target):
    if lesson_id not in LESSONS_BY_ID:
        send(chat_id, "Урок не найден.")
        return
    if target == "words":
        send_words(chat_id, lesson_id)
    elif target == "grammar":
        send_grammar(chat_id, lesson_id)
    elif target == "dialogue":
        send_dialogue(chat_id, lesson_id)
    elif target == "quiz":
        session[chat_id] = {"lesson": lesson_id, "quiz_q": 0, "quiz_score": 0}
        send_quiz_question(chat_id, lesson_id, 0)


def finish_lesson(chat_id, lesson_id, score, total):
    progress = get_progress(chat_id)
    if lesson_id not in progress["completed"]:
        progress["completed"].append(lesson_id)
    progress["best_scores"][str(lesson_id)] = max(progress["best_scores"].get(str(lesson_id), 0), score)
    if lesson_id > progress["current_lesson"]:
        progress["current_lesson"] = lesson_id
    set_progress(chat_id, progress)
    session.pop(chat_id, None)

    l = LESSONS_BY_ID[lesson_id]
    send(chat_id,
         f"🏁 <b>Урок {lesson_id} завершён!</b>\n\n"
         f"{l['title']}\n"
         f"✅ Результат теста: <b>{score}/{total}</b>\n\n"
         f"Продолжайте в том же духе! 💪",
         keyboard=after_quiz_keyboard(lesson_id))


def handle_quiz_answer(chat_id, msg_id, lesson_id, q_index, chosen, callback_id):
    state = session.get(chat_id)
    if not state or state.get("lesson") != lesson_id:
        answer_callback(callback_id, "Начните урок через /start")
        return
    if state["quiz_q"] != q_index:
        answer_callback(callback_id, "Вы уже ответили!")
        return

    l = LESSONS_BY_ID[lesson_id]
    q = l["quiz"][q_index]
    correct = q["answer"]
    is_correct = chosen == correct

    if is_correct:
        state["quiz_score"] += 1
    state["quiz_q"] += 1

    answer_callback(callback_id)
    edit_markup(chat_id, msg_id)

    if is_correct:
        send(chat_id, "✅ <b>Правильно!</b>")
    else:
        send(chat_id, f"❌ Неправильно. Верный ответ: <b>{correct}) {q['options'][correct]}</b>")

    total = len(l["quiz"])
    if state["quiz_q"] < total:
        send_quiz_question(chat_id, lesson_id, state["quiz_q"])
    else:
        finish_lesson(chat_id, lesson_id, state["quiz_score"], total)


def process_update(upd):
    if "callback_query" in upd:
        cb = upd["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        msg_id = cb["message"]["message_id"]
        data = cb["data"]
        cb_id = cb["id"]

        if data == "nav:home":
            answer_callback(cb_id)
            edit_markup(chat_id, msg_id)
            handle_start(chat_id)
        elif data == "nav:levels":
            answer_callback(cb_id)
            edit_markup(chat_id, msg_id)
            send(chat_id, "📚 <b>Выберите уровень HSK:</b>", keyboard=levels_keyboard())
        elif data.startswith("nav:level:"):
            _, _, level, page = data.split(":")
            answer_callback(cb_id)
            edit_markup(chat_id, msg_id)
            send(chat_id, f"📚 <b>Уровень {level}</b>\nВыберите урок:",
                 keyboard=lessons_page_keyboard(chat_id, level, int(page)))
        elif data.startswith("lesson:"):
            _, lid_str, target = data.split(":")
            answer_callback(cb_id)
            edit_markup(chat_id, msg_id)
            handle_lesson_nav(chat_id, int(lid_str), target)
        elif data.startswith("quizans:"):
            _, lid_str, q_str, chosen = data.split(":")
            handle_quiz_answer(chat_id, msg_id, int(lid_str), int(q_str), chosen, cb_id)
        return

    msg = upd.get("message", {})
    if not msg:
        return
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if text.startswith("/start"):
        handle_start(chat_id)
    elif text.startswith("/menu"):
        send(chat_id, "📚 <b>Выберите уровень HSK:</b>", keyboard=levels_keyboard())
    elif session.get(chat_id):
        send(chat_id, "Выбирайте ответ кнопками выше ⬆️")
    else:
        send(chat_id, "Напишите /start, чтобы начать обучение.")


def main():
    print("Бот запущен! Изучение китайского (HSK 1-6)")
    offset = 0
    while True:
        try:
            resp = api("getUpdates", offset=offset, timeout=30)
            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1
                process_update(upd)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
