import urllib.request
import json
import time
import os

from lessons import LESSONS
from progress import get_progress, set_progress

TOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN_HERE")
API = f"https://api.telegram.org/bot{TOKEN}"

# session[chat_id] = {"lesson": int, "stage": "words"|"grammar"|"quiz", "q": int, "score": int}
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


def edit_markup(chat_id, msg_id, keyboard=None):
    params = {"chat_id": chat_id, "message_id": msg_id}
    params["reply_markup"] = keyboard if keyboard else {"inline_keyboard": []}
    api("editMessageReplyMarkup", **params)


def answer_callback(callback_id, text=""):
    api("answerCallbackQuery", callback_query_id=callback_id, text=text)


def menu_keyboard(chat_id):
    progress = get_progress(chat_id)
    buttons = []
    next_lesson = progress["current_lesson"]
    if next_lesson < len(LESSONS):
        label = "▶️ Продолжить обучение" if progress["completed"] else "🚀 Начать урок 1"
        buttons.append([{"text": label, "callback_data": f"start:{next_lesson}"}])
    buttons.append([{"text": "📋 Все уроки", "callback_data": "list"}])
    return {"inline_keyboard": buttons}


def lessons_list_keyboard(chat_id):
    progress = get_progress(chat_id)
    buttons = []
    for i, lesson in enumerate(LESSONS):
        mark = "✅ " if i in progress["completed"] else ""
        buttons.append([{"text": f"{mark}{lesson['title']}", "callback_data": f"start:{i}"}])
    return {"inline_keyboard": buttons}


def quiz_keyboard(options, q_index):
    buttons = [[{"text": f"{k}) {v}", "callback_data": f"ans:{q_index}:{k}"}]
               for k, v in options.items()]
    return {"inline_keyboard": buttons}


def handle_start(chat_id):
    send(chat_id,
         "👋 <b>Добро пожаловать!</b>\n\n"
         "Этот бот поможет выучить китайский язык по урокам: "
         "новые слова, короткая грамматика и мини-тест на закрепление.\n\n"
         "Выберите, с чего начать:",
         keyboard=menu_keyboard(chat_id))


def handle_list(chat_id, msg_id):
    edit_markup(chat_id, msg_id)
    send(chat_id, "📋 <b>Список уроков</b>", keyboard=lessons_list_keyboard(chat_id))


def send_words(chat_id, lesson_index):
    lesson = LESSONS[lesson_index]
    lines = [f"📚 <b>{lesson['title']}</b>\n", "Новые слова:\n"]
    for w in lesson["words"]:
        lines.append(f"<b>{w['hanzi']}</b> ({w['pinyin']}) — {w['translation']}")
    send(chat_id, "\n".join(lines),
         keyboard={"inline_keyboard": [[{"text": "Далее ➡️", "callback_data": f"grammar:{lesson_index}"}]]})


def send_grammar(chat_id, lesson_index):
    lesson = LESSONS[lesson_index]
    send(chat_id, lesson["grammar"],
         keyboard={"inline_keyboard": [[{"text": "Начать тест ✏️", "callback_data": f"quiz:{lesson_index}:0"}]]})


def send_quiz_question(chat_id, lesson_index, q_index):
    quiz = LESSONS[lesson_index]["quiz"]
    q = quiz[q_index]
    text = f"{q_index + 1}/{len(quiz)}\n\n{q['text']}"
    send(chat_id, text, keyboard=quiz_keyboard(q["options"], q_index))


def handle_start_lesson(chat_id, msg_id, lesson_index):
    edit_markup(chat_id, msg_id)
    session[chat_id] = {"lesson": lesson_index, "score": 0}
    send_words(chat_id, lesson_index)


def handle_grammar(chat_id, msg_id, lesson_index):
    edit_markup(chat_id, msg_id)
    send_grammar(chat_id, lesson_index)


def handle_quiz_start(chat_id, msg_id, lesson_index):
    edit_markup(chat_id, msg_id)
    session[chat_id] = {"lesson": lesson_index, "score": 0}
    send_quiz_question(chat_id, lesson_index, 0)


def handle_answer(chat_id, msg_id, q_index, chosen, callback_id):
    state = session.get(chat_id)
    if not state:
        answer_callback(callback_id, "Начните урок через /start")
        return

    lesson_index = state["lesson"]
    quiz = LESSONS[lesson_index]["quiz"]
    q = quiz[q_index]
    correct = q["answer"]
    is_correct = chosen == correct

    if is_correct:
        state["score"] += 1

    answer_callback(callback_id)
    edit_markup(chat_id, msg_id)

    if is_correct:
        send(chat_id, "✅ <b>Правильно!</b>")
    else:
        send(chat_id, f"❌ Неправильно. Верный ответ: <b>{correct}) {q['options'][correct]}</b>")

    next_q = q_index + 1
    if next_q < len(quiz):
        send_quiz_question(chat_id, lesson_index, next_q)
    else:
        finish_lesson(chat_id, lesson_index, state["score"], len(quiz))


def finish_lesson(chat_id, lesson_index, score, total):
    progress = get_progress(chat_id)
    if lesson_index not in progress["completed"]:
        progress["completed"].append(lesson_index)
    progress["best_scores"][str(lesson_index)] = max(
        progress["best_scores"].get(str(lesson_index), 0), score
    )
    if lesson_index + 1 > progress["current_lesson"]:
        progress["current_lesson"] = lesson_index + 1
    set_progress(chat_id, progress)
    session.pop(chat_id, None)

    lesson_title = LESSONS[lesson_index]["title"]
    text = (
        f"🏁 <b>Урок завершён!</b>\n\n"
        f"{lesson_title}\n"
        f"✅ Результат теста: <b>{score}/{total}</b>\n\n"
    )
    buttons = []
    if lesson_index + 1 < len(LESSONS):
        buttons.append([{"text": "➡️ Следующий урок", "callback_data": f"start:{lesson_index + 1}"}])
    buttons.append([{"text": "📋 Все уроки", "callback_data": "list"}])
    send(chat_id, text, keyboard={"inline_keyboard": buttons})


def process_update(upd):
    if "callback_query" in upd:
        cb = upd["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        msg_id = cb["message"]["message_id"]
        data = cb["data"]
        cb_id = cb["id"]

        if data == "list":
            handle_list(chat_id, msg_id)
        elif data.startswith("start:"):
            handle_start_lesson(chat_id, msg_id, int(data.split(":")[1]))
        elif data.startswith("grammar:"):
            handle_grammar(chat_id, msg_id, int(data.split(":")[1]))
        elif data.startswith("quiz:"):
            _, lesson_str, _ = data.split(":")
            handle_quiz_start(chat_id, msg_id, int(lesson_str))
        elif data.startswith("ans:"):
            _, q_str, chosen = data.split(":")
            handle_answer(chat_id, msg_id, int(q_str), chosen, cb_id)
        return

    msg = upd.get("message", {})
    if not msg:
        return
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if text.startswith("/start"):
        handle_start(chat_id)
    elif session.get(chat_id):
        send(chat_id, "Выбирайте ответ кнопками выше ⬆️")
    else:
        send(chat_id, "Напишите /start, чтобы начать обучение.")


def main():
    print("Бот запущен! Изучение китайского")
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
