#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZLodeinVPN — сборщик и ЧЕСТНЫЙ чекер конфигов.
​
Этапы:
  1) Скачать источники, убрать дубли                       -> all_configs.txt
  2) BASELINE: проверить, какие конфиги вообще живые
     (обычный generate_204) — это диагностика.
  3) ФИЛЬТРЫ: по очереди прогнать выживших через каждый
     тест-URL (Telegram, Gemini). В итоге остаются только те,
     что тянут ВСЕ URL.
  4) Сложить топ-N + шапку                         -> cleaned_sub.txt
​
Запуск: python main.py  (требует бинарь xray-knife в PATH или рядом)
"""
​
import os
import re
import sys
import time
import shutil
import subprocess
import urllib.request
​
# ----------------------------------------------------------------------------
# Настройки (можно переопределить через env)
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
​
ALL_FILE    = "all_configs.txt"
OUTPUT_FILE = "cleaned_sub.txt"
​
XRAY_KNIFE = os.environ.get("XRAY_KNIFE") or shutil.which("xray-knife") or "./xray-knife"
THREADS    = os.environ.get("XK_THREADS", "100")
MAX_OUTPUT = int(os.environ.get("MAX_OUTPUT", "300"))
​
# Базовый URL "живости" (диагностика). Пусто — пропустить.
BASELINE_URL = os.environ.get("XK_BASELINE_URL", "https://www.gstatic.com/generate_204").strip()
​
# Тест-URLы: конфиг должен открыть КАЖДЫЙ. Дефолт: Telegram + Gemini.
# Важно: берём страницы, которые отдают 200 напрямую (без редиректа).
TEST_URLS = [
    u.strip() for u in os.environ.get(
        "XK_TEST_URLS",
        "https://web.telegram.org/k/,https://gemini.google.com/",
    ).split(",") if u.strip()
]
​
URL_FLAG   = os.environ.get("XK_URL_FLAG", "-d")          # флаг тест-URL (исторически -d/--destURL)
EXTRA_ARGS = os.environ.get("XK_EXTRA_ARGS", "").split()  # любые доп. флаги
​
PROTO_RE = re.compile(r"(?:vless|vmess|ss|ssr|trojan|tuic|hysteria2?|hy2)://[^\s'\"<>]+")
​
​
def fetch_sources():
    seen, out = set(), []
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
                    seen.add(line); out.append(line); cnt += 1
            print(f"        +{cnt} уникальных")
        except Exception as e:
            print(f"        ! ошибка: {e}")
    with open(ALL_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"[fetch] всего уникальных: {len(out)} -> {ALL_FILE}")
    return len(out)
​
​
def ensure_xray_knife():
    if not (os.path.exists(XRAY_KNIFE) or shutil.which(XRAY_KNIFE)):
        print(f"[test] !! xray-knife не найден ({XRAY_KNIFE}).")
        sys.exit(2)
​
​
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
​
​
def test_pass(input_file, url, out_file):
    if os.path.exists(out_file):
        os.remove(out_file)
    cmd = [XRAY_KNIFE, "http", "-f", input_file, "-t", str(THREADS), "-o", out_file]
    if url:
        cmd += [URL_FLAG, url]
    cmd += EXTRA_ARGS
    print(f"[test] {' '.join(cmd)}")
    subprocess.run(cmd, check=False)
    survivors = collect_configs(out_file)
    print(f"        прошли ({url or 'default'}): {len(survivors)}")
    return survivors
​
​
def run_checks():
    # Диагностика: сколько вообще живых (не режет итог, только показывает)
    if BASELINE_URL:
        print("--- BASELINE: проверка базовой живости ---")
        alive = test_pass(ALL_FILE, BASELINE_URL, "working_baseline.txt")
        if not alive:
            print("!! BASELINE = 0: ни один конфиг не прошёл даже базовый тест.")
            print("   Значит проблема не в URL, а в ядре/флагах/конфигах.")
        start_input, start_file = ALL_FILE, None
        if alive:
            start_file = "working_baseline.txt"
            start_input = start_file
    else:
        start_input = ALL_FILE
​
    # Фильтры по тест-URLам (Telegram, Gemini, ...)
    current_input = start_input
    survivors = collect_configs(start_input) if start_input != ALL_FILE else []
    print("--- ФИЛЬТРЫ по тест-URLам ---")
    for i, url in enumerate(TEST_URLS):
        out_file = f"working_{i}.txt"
        survivors = test_pass(current_input, url, out_file)
        if not survivors:
            print("        живых не осталось, прерываю цепочку")
            break
        current_input = out_file
    return survivors
​
​
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
​
​
def main():
    print("=== ZLodeinVPN: сбор + ЧЕСТНАЯ проверка ===")
    total = fetch_sources()
    if total == 0:
        print("Источники пусты — выходим."); sys.exit(1)
    ensure_xray_knife()
    working = run_checks()
    write_output(working, total)
​
​
if __name__ == "__main__":
    main()
​
