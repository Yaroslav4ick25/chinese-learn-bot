# -*- coding: utf-8 -*-
"""Генерирует audio/lesson_<id>.mp3 (слова урока) и audio/dialog_<n>.mp3 (диалоги)
голосом zh-CN-XiaoxiaoNeural (Microsoft Edge TTS, бесплатно)."""
import asyncio
import os

import edge_tts

from lessons import LESSONS, DIALOGUES

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

VOICE = "zh-CN-XiaoxiaoNeural"


def build_lesson_text(lesson):
    return "。".join(w["hanzi"] for w in lesson["words"]) + "。"


def build_dialogue_text(dialogue):
    return "".join(hanzi for _, hanzi, _, _ in dialogue)


async def synth(text, out_path):
    communicate = edge_tts.Communicate(text, VOICE, rate="-5%")
    await communicate.save(out_path)


async def synth_with_retry(text, out_path, label):
    for attempt in range(3):
        try:
            await synth(text, out_path)
            size = os.path.getsize(out_path)
            if size < 500:
                raise RuntimeError(f"suspiciously small file ({size} bytes)")
            print(f"OK  {label}: {out_path} ({size} bytes)")
            return True
        except Exception as e:
            print(f"RETRY {label} attempt {attempt + 1}: {e}")
            await asyncio.sleep(2)
    print(f"FAIL {label}")
    return False


async def main():
    done, failed = 0, 0

    for i, dialogue in enumerate(DIALOGUES):
        out_path = os.path.join(AUDIO_DIR, f"dialog_{i}.mp3")
        if os.path.exists(out_path):
            continue
        ok = await synth_with_retry(build_dialogue_text(dialogue), out_path, f"dialog {i}")
        done += ok
        failed += not ok

    for lesson in LESSONS:
        lid = lesson["id"]
        out_path = os.path.join(AUDIO_DIR, f"lesson_{lid}.mp3")
        if os.path.exists(out_path):
            continue
        ok = await synth_with_retry(build_lesson_text(lesson), out_path, f"lesson {lid}")
        done += ok
        failed += not ok

    print(f"\nDone: {done}, failed: {failed}")


if __name__ == "__main__":
    asyncio.run(main())
