#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZLodeinVPN — сборщик и ЧЕСТНЫЙ чекер конфигов.

Логика:
  1) Скачать все источники, убрать дубликаты                 -> all_configs.txt
  2) Реально проверить каждый конфиг через xray-knife по очереди
     на каждый тест-URL (Telegram, затем Gemini). Каждый проход
     тестирует только выживших предыдущего -> в итоге остаются
     только конфиги, которые тянут ВСЕ указанные URL.
  3) Сложить топ-N живых + шапку профиля                 -> cleaned_sub.txt

Запуск: python main.py
Требует в PATH (или рядом) бинарь xray-knife. В GitHub Actions он скачивается
шагом workflow до запуска этого скрипта.
"""

import os
import re
import sys
import time
import shutil
import subprocess
import urllib.request

# ----------------------------------------------------------------------------
# Настройки (можно переопределить через переменные окружения)
# ----------------------------------------------------------------------------
SOURCES = [
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_universal.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-SNI-RU-all.txt",
    "https://raw.githubusercontent.com/whoahaow/rjsxrd/refs/heads/main/githubmirror/bypass/bypass-all.txt",
    "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/refs/heads/main/kizyakbeta7.txt",
    "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/refs/heads/main/kizyakbeta6.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
]

ALL_FILE     = "all_configs.txt"
OUTPUT_FILE  = "cleaned_sub.txt"

# Путь к бинарю xray-knife: env XRAY_KNIFE -> в PATH -> ./xray-knife
XRAY_KNIFE = os.environ.get("XRAY_KNIFE") or shutil.which("xray-knife") or "./xray-knife"
THREADS    = os.environ.get("XK_THREADS", "100")

# Сколько конфигов оставлять в итоговом файле (0 = всех живых)
MAX_OUTPUT = int(os.environ.get("MAX_OUTPUT", "300"))

# Тест-URLы: конфиг должен реально открыть КАЖДЫЙ из них.
# По умолчанию: Telegram + Gemini. Переопределяется через XK_TEST_URLS (через запятую).
TEST_URLS = [
    u.strip() for u in os.environ.get(
        "XK_TEST_URLS",
        "https://web.telegram.org,https://gemini.google.com",
    ).split(",") if u.strip()
]

# Флаг тест-URL у xray-knife (исторически -d / --destURL). При желании поменяй через env.
URL_FLAG = os.environ.get("XK_URL_FLAG", "-d")
# Любые доп. аргументы для xray-knife (напр. отсечка по задержке)
EXTRA_ARGS = os.environ.get("XK_EXTRA_ARGS", "").split()

PROTO_RE = re.compile(r"(?:vless|vmess|ss|ssr|trojan|tuic|hysteria2?|hy2)://[^\s'\"<>]+")


def fetch_sources():
    """Скачать все источники, оставить уникальные строки-конфиги."""
    seen = set()
    out = []
    for url in SOURCES:
        try:
            print(f"[fetch] {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            text = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
            cnt = 0
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "://" not in line:
                    continue
                if line not in seen:
                    seen.add(line)
                    out.append(line)
                    cnt += 1
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
        print("        Укажи путь через переменную XRAY_KNIFE или положи бинарь рядом.")
        sys.exit(2)


def collect_configs(path):
    """Достать конфиги из файла результата xray-knife (plain или CSV — без разницы)."""
    if not os.path.exists(path):
        return []
    out, seen = [], set()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            for m in PROTO_RE.findall(line):
                if m not in seen:
                    seen.add(m)
                    out.append(m)
    return out


def test_pass(input_file, url, out_file):
    """Один проход проверки через xray-knife против одного URL."""
    if os.path.exists(out_file):
        os.remove(out_file)
    cmd = [XRAY_KNIFE, "http", "-f", input_file, "-t", str(THREADS),
           "-o", out_file, URL_FLAG, url] + EXTRA_ARGS
    print(f"[test] {' '.join(cmd)}")
    subprocess.run(cmd, check=False)
    survivors = collect_configs(out_file)
    print(f"        прошли ({url}): {len(survivors)}")
    return survivors


def run_checks():
    """Последовательные проходы: каждый режет выживших по следующему URL."""
    if not TEST_URLS:
        print("[test] нет тест-URL — проверяю с дефолтным URL xray-knife")
        if os.path.exists("working_0.txt"):
            os.remove("working_0.txt")
        cmd = [XRAY_KNIFE, "http", "-f", ALL_FILE, "-t", str(THREADS),
               "-o", "working_0.txt"] + EXTRA_ARGS
        print(f"[test] {' '.join(cmd)}")
        subprocess.run(cmd, check=False)
        return collect_configs("working_0.txt")

    current_input = ALL_FILE
    survivors = []
    for i, url in enumerate(TEST_URLS):
        out_file = f"working_{i}.txt"
        survivors = test_pass(current_input, url, out_file)
        if not survivors:
            print("        живых не осталось, прерываю цепочку")
            break
        current_input = out_file
    return survivors


def write_output(working, total):
    if MAX_OUTPUT > 0:
        working = working[:MAX_OUTPUT]
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    checks = " + ".join(TEST_URLS) if TEST_URLS else "default"
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
    print("=== ZLodeinVPN: сбор + ЧЕСТНАЯ проверка (Telegram + Gemini) ===")
    total = fetch_sources()
    if total == 0:
        print("Источники пусты — выходим.")
        sys.exit(1)
    ensure_xray_knife()
    working = run_checks()
    write_output(working, total)


if __name__ == "__main__":
    main()
