import json
import os
import threading

PROGRESS_FILE = os.path.join(os.path.dirname(__file__), "progress.json")
_lock = threading.Lock()


def load_all():
    if not os.path.exists(PROGRESS_FILE):
        return {}
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_all(data):
    with _lock:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def get_progress(chat_id):
    data = load_all()
    return data.get(str(chat_id), {"current_lesson": 0, "completed": [], "best_scores": {}})


def set_progress(chat_id, progress):
    data = load_all()
    data[str(chat_id)] = progress
    save_all(data)
