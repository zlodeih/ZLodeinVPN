#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZLodeinVPN — сборщик и ЧЕСТНЫЙ чекер конфигов (xray-knife).

Этапы:
  1) Скачать источники (поддержка plain и base64), убрать дубли -> all_configs.txt
  2) Реальный тест каждого конфига через xray-knife          -> working.txt
  3) Сложить топ-N + шапку                                  -> cleaned_sub.txt

Запуск: python main.py  (требует бинарь xray-knife в PATH или рядом)
"""

import os
import re
import sys
import time
import base64
import shutil
import subprocess
import urllib.request

# ----------------------------------------------------------------------------
# Источники конфигов
# ----------------------------------------------------------------------------
SOURCES = [
    # --- Под РФ / белые списки ---
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_universal.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-SNI-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/whoahaow/rjsxrd/refs/heads/main/githubmirror/bypass/bypass-all.txt",
    "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/refs/heads/main/kizyakbeta7.txt",
    "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/refs/heads/main/kizyakbeta6.txt",
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/vless.txt",
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/ru-sni/vless_ru.txt",
    # --- Крупные общие (обновляются часто; живые отберёт тест) ---
    # --- Добавлено по запросу ---
    "https://raw.githubusercontent.com/VOID-Anonymity/V.O.I.D-VPN_Bypass/refs/heads/main/url_work.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_SS+All_RUS.txt",
    "https://raw.githubusercontent.com/nikita29a/FreeProxyList/refs/heads/main/mirror/1.txt",
]

ALL_FILE     = "all_configs.txt"
WORKING_FILE = "working.txt"
OUTPUT_FILE  = "cleaned_sub.txt"

XRAY_KNIFE = os.environ.get("XRAY_KNIFE") or shutil.which("xray-knife") or "./xray-knife"
THREADS    = os.environ.get("XK_THREADS", "100")
MAX_OUTPUT = int(os.environ.get("MAX_OUTPUT", "0"))  # 0 = без лимита (все живые)

# ОПЦИОНАЛЬНО: фильтр по конкретным URL (Telegram/Gemini).
# ВКЛЮЧАЕТСЯ только если задан XK_URL_FLAG (точное имя флага вашей версии).
URL_FLAG  = os.environ.get("XK_URL_FLAG", "").strip()
TEST_URLS = [
    u.strip() for u in os.environ.get("XK_TEST_URLS", "").split(",") if u.strip()
]

EXTRA_ARGS = os.environ.get("XK_EXTRA_ARGS", "").split()

PROTO_RE = re.compile(r"(?:vless|vmess|ss|ssr|trojan|tuic|hysteria2?|hy2)://[^\s'\"<>]+")


def extract_from_text(text, seen, out):
    """Извлечь конфиги из текста (построчно), без дублей."""
    cnt = 0
    for m in PROTO_RE.findall(text):
        if m not in seen:
            seen.add(m); out.append(m); cnt += 1
    return cnt


def try_base64(text):
    """Попробовать раскодировать весь блок как base64. Вернёт '' если не вышло."""
    s = "".join(text.split())
    if len(s) < 16:
        return ""
    # добивка padding
    s += "=" * ((4 - len(s) % 4) % 4)
    try:
        return base64.b64decode(s, validate=False).decode("utf-8", "ignore")
    except Exception:
        return ""


def fetch_sources():
    seen, out = set(), []
    for url in SOURCES:
        try:
            print(f"[fetch] {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            text = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
            cnt = extract_from_text(text, seen, out)
            if cnt == 0:
                # возможно подписка в base64
                decoded = try_base64(text)
                if decoded:
                    cnt = extract_from_text(decoded, seen, out)
            print(f"        +{cnt} уникальных")
        except Exception as e:
            print(f"        ! ошибка: {e}")
    with open(ALL_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"[fetch] всего уникальных: {len(out)} -> {ALL_FILE}")
    return len(out)


def ensure_xray_knife():
    if not (os.path.exists(XRAY_KNIFE) or shutil.which(XRAY_KNIFE)):
        print(f"[test] !! xray-knife не найден ({XRAY_KNIFE}).")
        sys.exit(2)


def collect_configs(path):
    if not os.path.exists(path):
        return []
    out, seen = [], set()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            for m in PROTO_RE.findall(line):
                if m not in seen:
                    seen.add(m); out.append(m)
    return out


def test_pass(input_file, out_file, url=None):
    """Один проход xray-knife. url передаётся ТОЛЬКО если задан URL_FLAG."""
    if os.path.exists(out_file):
        os.remove(out_file)
    cmd = [XRAY_KNIFE, "http", "-f", input_file, "-t", str(THREADS), "-o", out_file]
    if url and URL_FLAG:
        cmd += [URL_FLAG, url]
    cmd += EXTRA_ARGS
    print(f"[test] {' '.join(cmd)}")
    subprocess.run(cmd, check=False)
    survivors = collect_configs(out_file)
    print(f"        прошли ({url or 'default'}): {len(survivors)}")
    return survivors


def run_checks():
    print("--- ОСНОВНОЙ тест связи ---")
    survivors = test_pass(ALL_FILE, WORKING_FILE)

    if URL_FLAG and TEST_URLS and survivors:
        print(f"--- ФИЛЬТРЫ по URL (флаг {URL_FLAG}) ---")
        current = WORKING_FILE
        for i, url in enumerate(TEST_URLS):
            out_file = f"working_url_{i}.txt"
            survivors = test_pass(current, out_file, url=url)
            if not survivors:
                print("        живых не осталось, прерываю цепочку")
                break
            current = out_file
    elif TEST_URLS and not URL_FLAG:
        print("[info] XK_TEST_URLS задан, но XK_URL_FLAG пуст — фильтр по URL пропущен.")
        print("       Узнайте флаг командой ./xray-knife http -h и задайте XK_URL_FLAG.")
    return survivors


def write_output(working, total):
    if MAX_OUTPUT > 0:
        working = working[:MAX_OUTPUT]
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    if URL_FLAG and TEST_URLS:
        checks = " + ".join(TEST_URLS)
    else:
        checks = "реальная связь (default)"
    header = [
        "# profile-title: 🌸ZLodeinVPN_CIDR_AUTOMATED🌸",
        "# profile-update-interval: 1",
        f"# Последнее обновление: {ts} UTC",
        f"# Проверено: {total} | Живых: {len(working)} | Тест: {checks}",
    ]
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(header + working) + "\n")
    print(f"[done] записано живых: {len(working)} -> {OUTPUT_FILE}")


def main():
    print("=== ZLodeinVPN: сбор + ЧЕСТНАЯ проверка ===")
    total = fetch_sources()
    if total == 0:
        print("Источники пусты — выходим."); sys.exit(1)
    ensure_xray_knife()
    working = run_checks()
    write_output(working, total)


if __name__ == "__main__":
    main()
