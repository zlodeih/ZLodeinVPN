#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZLodeinVPN — сборщик и ЧЕСТНЫЙ чекер конфигов (xray-knife).

Этапы:
  1) Скачать источники (plain и base64), убрать дубли       -> all_configs.txt
  2) Реальный тест + СОРТИРОВКА по скорости (xray-knife --sort) -> working.txt
  3) GeoIP-флаги, метка 🆕, имена 🇩🇪ZloyVPN №1♨          -> cleaned_sub.txt
     + отдельный RU-тариф                                -> cleaned_ru.txt

Состояние (для метки 🆕 «новый») хранится в seen.json.
"""

import os
import re
import sys
import json
import time
import base64
import socket
import shutil
import subprocess
import urllib.request
from urllib.parse import urlsplit, quote, unquote

# ----------------------------------------------------------------------------
# Источники: (url, is_ru)  — is_ru=True → заточено под РФ/белые списки
# ----------------------------------------------------------------------------
SOURCES = [
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_universal.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-SNI-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/refs/heads/main/kizyakbeta7.txt",
    "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/refs/heads/main/kizyakbeta6.txt",
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/vless.txt",
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/ru-sni/vless_ru.txt",
    "https://raw.githubusercontent.com/VOID-Anonymity/V.O.I.D-VPN_Bypass/refs/heads/main/url_work.txt",
]

ALL_FILE     = "all_configs.txt"
WORKING_FILE = "working.txt"
OUTPUT_FILE  = "cleaned_sub.txt"
RU_FILE      = "cleaned_ru.txt"
SEEN_FILE    = "seen.json"

XRAY_KNIFE = os.environ.get("XRAY_KNIFE") or shutil.which("xray-knife") or "./xray-knife"
THREADS    = os.environ.get("XK_THREADS", "100")
MAX_OUTPUT = int(os.environ.get("MAX_OUTPUT", "0"))   # 0 = без лимита
VPN_NAME   = os.environ.get("XK_VPN_NAME", "ZloyVPN")
USE_GEOIP  = os.environ.get("XK_GEOIP", "1") != "0"
NEW_WINDOW = int(os.environ.get("XK_NEW_WINDOW", "3600"))  # сек: «новый» 🆕
NO_SORT    = os.environ.get("XK_NO_SORT", "0") == "1"

# ОПЦИОНАЛЬНО: фильтр по конкретным URL (Telegram/Gemini).
URL_FLAG  = os.environ.get("XK_URL_FLAG", "").strip()
TEST_URLS = [u.strip() for u in os.environ.get("XK_TEST_URLS", "").split(",") if u.strip()]
EXTRA_ARGS = os.environ.get("XK_EXTRA_ARGS", "").split()

PROTO_RE = re.compile(r"(?:vless|vmess|ss|ssr|trojan|tuic|hysteria2?|hy2)://[^\s'\"<>]+")
FLAG_RE  = re.compile("[\U0001F1E6-\U0001F1FF]{2}")

socket.setdefaulttimeout(6)


# ============================================================================
# СБОР ИСТОЧНИКОВ
# ============================================================================
def extract_all(text):
    return PROTO_RE.findall(text)


def try_base64(text):
    s = "".join(text.split())
    if len(s) < 16:
        return ""
    s += "=" * ((4 - len(s) % 4) % 4)
    try:
        return base64.b64decode(s, validate=False).decode("utf-8", "ignore")
    except Exception:
        return ""


def fetch_sources():
    """Возвращает (configs, ru_set)."""
    seen, out, ru_set = set(), [], set()
    for url, is_ru in SOURCES:
        try:
            print(f"[fetch] {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            text = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
            found = extract_all(text)
            if not found:
                decoded = try_base64(text)
                if decoded:
                    found = extract_all(decoded)
            cnt = 0
            for m in found:
                if m not in seen:
                    seen.add(m); out.append(m); cnt += 1
                if is_ru:
                    ru_set.add(m)
            print(f"        +{cnt} уникальных (ru={is_ru})")
        except Exception as e:
            print(f"        ! ошибка: {e}")
    with open(ALL_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"[fetch] всего уникальных: {len(out)} -> {ALL_FILE}")
    return out, ru_set


# ============================================================================
# ТЕСТ ЧЕРЕЗ XRAY-KNIFE (+ сортировка по скорости)
# ============================================================================
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
    if os.path.exists(out_file):
        os.remove(out_file)
    cmd = [XRAY_KNIFE, "http", "-f", input_file, "-t", str(THREADS), "-o", out_file]
    if not NO_SORT:
        cmd += ["--sort"]          # быстрые сверху
    if url and URL_FLAG:
        cmd += [URL_FLAG, url]
    cmd += EXTRA_ARGS
    print(f"[test] {' '.join(cmd)}")
    subprocess.run(cmd, check=False)
    survivors = collect_configs(out_file)
    print(f"        прошли ({url or 'default'}): {len(survivors)}")
    return survivors


def run_checks():
    print("--- ОСНОВНОЙ тест связи (+сортировка) ---")
    survivors = test_pass(ALL_FILE, WORKING_FILE)
    if URL_FLAG and TEST_URLS and survivors:
        print(f"--- ФИЛЬТРЫ по URL (флаг {URL_FLAG}) ---")
        current = WORKING_FILE
        for i, url in enumerate(TEST_URLS):
            out_file = f"working_url_{i}.txt"
            survivors = test_pass(current, out_file, url=url)
            if not survivors:
                print("        живых не осталось, прерываю")
                break
            current = out_file
    return survivors


# ============================================================================
# СОСТОЯНИЕ для метки 🆕
# ============================================================================
def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_seen(seen):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(seen, f)
    except Exception as e:
        print(f"[seen] не сохранён: {e}")


# ============================================================================
# GeoIP + имена
# ============================================================================
def cc_to_flag(cc):
    cc = (cc or "").upper()
    if len(cc) != 2 or not cc.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in cc)


def get_host(cfg):
    if cfg.startswith("vmess://"):
        b64 = cfg[8:].split("#", 1)[0]
        b64 += "=" * ((4 - len(b64) % 4) % 4)
        try:
            obj = json.loads(base64.b64decode(b64).decode("utf-8", "ignore"))
            return obj.get("add") or ""
        except Exception:
            return ""
    try:
        h = urlsplit(cfg).hostname
        if h:
            return h
    except Exception:
        pass
    m = re.search(r"@([^:/?#]+):\d+", cfg)
    return m.group(1) if m else ""


def extract_existing_flag(cfg):
    m = FLAG_RE.search(unquote(cfg))
    return m.group(0) if m else ""


def resolve_ip(host):
    if not host:
        return None
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
        return host
    try:
        return socket.gethostbyname(host)
    except Exception:
        return None


def geoip_lookup(hosts):
    cc_by_host = {h: "" for h in hosts}
    if not USE_GEOIP:
        return cc_by_host
    ip_by_host = {h: resolve_ip(h) for h in hosts}
    ips = list({ip for ip in ip_by_host.values() if ip})
    cc_by_ip = {}
    for i in range(0, len(ips), 100):
        chunk = ips[i:i + 100]
        try:
            payload = json.dumps(
                [{"query": ip, "fields": "countryCode,query"} for ip in chunk]
            ).encode()
            req = urllib.request.Request(
                "http://ip-api.com/batch", data=payload,
                headers={"Content-Type": "application/json"},
            )
            arr = json.loads(urllib.request.urlopen(req, timeout=25).read().decode())
            for item in arr:
                cc_by_ip[item.get("query")] = item.get("countryCode", "") or ""
        except Exception as e:
            print(f"[geoip] ошибка: {e}")
        time.sleep(1)
    for h, ip in ip_by_host.items():
        cc_by_host[h] = cc_by_ip.get(ip, "")
    return cc_by_host


def set_name(cfg, name):
    if cfg.startswith("vmess://"):
        b64 = cfg[8:].split("#", 1)[0]
        b64 += "=" * ((4 - len(b64) % 4) % 4)
        try:
            obj = json.loads(base64.b64decode(b64).decode("utf-8", "ignore"))
            obj["ps"] = name
            nb = base64.b64encode(json.dumps(obj, ensure_ascii=False).encode("utf-8")).decode()
            return "vmess://" + nb
        except Exception:
            return cfg
    base = cfg.split("#", 1)[0]
    return base + "#" + quote(name, safe="")


def build_named(configs, cc_by_host, new_set, start=1):
    """Проставляет имена [🆕]<флаг>ZloyVPN №N♨ (нумерация по порядку = скорость)."""
    out = []
    i = start
    for cfg in configs:
        host = get_host(cfg)
        flag = cc_to_flag(cc_by_host.get(host, "")) or extract_existing_flag(cfg) or "\U0001F3F4"
        tag = "\U0001F195" if cfg in new_set else ""   # 🆕
        name = f"{tag}{flag}{VPN_NAME} \u2116{i}\u2668"
        out.append(set_name(cfg, name))
        i += 1
    return out


# ============================================================================
# ЗАПИСЬ
# ============================================================================
def header(total, alive, checks, title_extra=""):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    return [
        f"# profile-title: \U0001F338ZLodeinVPN{title_extra}\U0001F338",
        "# profile-update-interval: 1",
        f"# Последнее обновление: {ts} UTC",
        f"# Проверено: {total} | Живых: {alive} | Тест: {checks}",
    ]


def write_file(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    print("=== ZLodeinVPN: сбор + ЧЕСТНАЯ проверка ===")
    configs, ru_set = fetch_sources()
    total = len(configs)
    if total == 0:
        print("Источники пусты — выходим."); sys.exit(1)
    ensure_xray_knife()

    working = run_checks()                 # уже отсортировано по скорости
    if MAX_OUTPUT > 0:
        working = working[:MAX_OUTPUT]

    # --- метка 🆕 ---
    now = int(time.time())
    seen = load_seen()
    new_set = set()
    for cfg in working:
        first = seen.get(cfg)
        if first is None:
            seen[cfg] = now
            first = now
        if now - int(first) <= NEW_WINDOW:
            new_set.add(cfg)
    # чистим состояние от старых (>30 дней и не в текущих)
    cur = set(working)
    seen = {k: v for k, v in seen.items() if k in cur or now - int(v) < 2592000}
    save_seen(seen)

    # --- GeoIP для всех живых ---
    hosts = list(dict.fromkeys(h for h in (get_host(c) for c in working) if h))
    print(f"[geoip] определяю страны для {len(hosts)} хостов...")
    cc_by_host = geoip_lookup(hosts)

    checks = " + ".join(TEST_URLS) if (URL_FLAG and TEST_URLS) else "реальная связь (default)"

    # --- основной файл (все живые) ---
    named_all = build_named(working, cc_by_host, new_set)
    write_file(OUTPUT_FILE, header(total, len(named_all), checks) + named_all)
    print(f"[done] {OUTPUT_FILE}: {len(named_all)} живых")

    # --- RU-тариф ---
    ru_working = [c for c in working if c in ru_set]
    named_ru = build_named(ru_working, cc_by_host, new_set)
    write_file(RU_FILE, header(total, len(named_ru), checks, title_extra="\u00B7RU") + named_ru)
    print(f"[done] {RU_FILE}: {len(named_ru)} живых (под РФ)")


if __name__ == "__main__":
    main()
