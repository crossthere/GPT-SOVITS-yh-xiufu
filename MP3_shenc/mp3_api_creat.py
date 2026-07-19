#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any
import wave

import requests


API_BASE = "http://127.0.0.1:9880"

SENTENCE_ENDINGS = {"\u3002", "\uff1f", "\uff01", "?", "!", "\u2026"}
CLOSING_MARKS = {
    "\u201d",
    "\u2019",
    "\u300d",
    "\u300f",
    "\uff09",
    ")",
    "\u300b",
    "\u3011",
    "]",
}
PUNCTUATION_ONLY_CHARS = SENTENCE_ENDINGS | CLOSING_MARKS | set(
    "\uff0c,\u3001\uff1b;\uff1a:\u201c\u2018\uff08(\u300a\u3010[\u2014-\u3000 "
)


def has_text_content(text: str) -> bool:
    return any(char not in PUNCTUATION_ONLY_CHARS and not char.isspace() for char in text)


def sentence_newline_text(text: str) -> str:
    """Return text as one sentence per line before sending it to GPT-SoVITS."""
    sentence_lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        buffer: list[str] = []
        index = 0
        while index < len(raw_line):
            char = raw_line[index]
            buffer.append(char)

            if char in SENTENCE_ENDINGS:
                next_index = index + 1
                if char == "\u2026":
                    while next_index < len(raw_line) and raw_line[next_index] == "\u2026":
                        buffer.append(raw_line[next_index])
                        next_index += 1
                while next_index < len(raw_line) and raw_line[next_index] in CLOSING_MARKS:
                    buffer.append(raw_line[next_index])
                    next_index += 1

                sentence = "".join(buffer).strip()
                if sentence and has_text_content(sentence):
                    sentence_lines.append(sentence)
                buffer = []
                index = next_index
                continue

            index += 1

        tail = "".join(buffer).strip()
        if tail and has_text_content(tail):
            sentence_lines.append(tail)

    return "\n".join(sentence_lines)


def build_tts_payload(
    text: str,
    voice_config: dict[str, Any],
    split_method: str = "cut1",
    *,
    sentence_newline: bool = True,
    extra_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tts_text = sentence_newline_text(text) if sentence_newline else text
    payload: dict[str, Any] = {
        "text": tts_text,
        "text_lang": "zh",
        "ref_audio_path": voice_config["ref_audio"],
        "prompt_text": voice_config["ref_text"],
        "prompt_lang": "zh",
        "text_split_method": split_method,
        "temperature": 1,
        "batch_size": 8,
    }
    if extra_params:
        payload.update(extra_params)
    return payload


def synthesize_tts_to_file(
    text: str,
    voice_config: dict[str, Any],
    split_method: str,
    output_path: str | Path,
    *,
    api_base: str = API_BASE,
    timeout: int = 600,
    sentence_newline: bool = True,
    error_label: str = "TTS synthesis failed",
) -> None:
    payload = build_tts_payload(
        text,
        voice_config,
        split_method,
        sentence_newline=sentence_newline,
    )
    response = requests.post(f"{api_base}/tts", json=payload, timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(f"{error_label}: {response.text}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(response.content)


def fetch_tts_meta(
    *,
    api_base: str = API_BASE,
    timeout: int = 10,
    error_label: str = "Fetch TTS metadata failed",
) -> dict[str, Any]:
    response = requests.get(f"{api_base}/tts_meta", timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(f"{error_label}: {response.text}")
    return response.json()


def fetch_tts_segments(
    *,
    api_base: str = API_BASE,
    timeout: int = 10,
    error_label: str = "Fetch TTS segments failed",
) -> list[dict[str, Any]]:
    return fetch_tts_meta(api_base=api_base, timeout=timeout, error_label=error_label).get("segments", [])


def get_wav_duration(wav_path: str | Path) -> float:
    with wave.open(str(wav_path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        return frames / float(rate)
