#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZLodeinVPN — сборщик и ЧЕСТНЫЙ чекер конфигов (xray-knife).

Этапы:
  1) Скачать источники (plain и base64), убрать дубли       -> all_configs.txt
  2) Реальный тест каждого конфига через xray-knife          -> working.txt
  3) Переименовать (флаг страны + ZloyVPN №N♨) + шапка -> cleaned_sub.txt

Запуск: python main.py  (требует бинарь xray-knife в PATH или рядом)

ID-название сервера: 🇩🇪ZloyVPN №1♨ (флаг = страна по GeoIP сервера).
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
# Источники конфигов
# ----------------------------------------------------------------------------
SOURCES = [
    # --- Под РФ / белые списки ---
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_universal.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-SNI-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/refs/heads/main/kizyakbeta7.txt",
    "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/refs/heads/main/kizyakbeta6.txt",
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/vless.txt",
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/ru-sni/vless_ru.txt",
    "https://raw.githubusercontent.com/VOID-Anonymity/V.O.I.D-VPN_Bypass/refs/heads/main/url_work.txt",
    # --- Крупные общие (живые отберёт тест) ---

]

ALL_FILE     = "all_configs.txt"
WORKING_FILE = "working.txt"
OUTPUT_FILE  = "cleaned_sub.txt"

XRAY_KNIFE = os.environ.get("XRAY_KNIFE") or shutil.which("xray-knife") or "./xray-knife"
THREADS    = os.environ.get("XK_THREADS", "100")
MAX_OUTPUT = int(os.environ.get("MAX_OUTPUT", "0"))   # 0 = без лимита (все живые)
VPN_NAME   = os.environ.get("XK_VPN_NAME", "ZloyVPN")
USE_GEOIP  = os.environ.get("XK_GEOIP", "1") != "0"  # определять страну по IP сервера

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
def extract_from_text(text, seen, out):
    cnt = 0
    for m in PROTO_RE.findall(text):
        if m not in seen:
            seen.add(m); out.append(m); cnt += 1
    return cnt


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
    seen, out = set(), []
    for url in SOURCES:
        try:
            print(f"[fetch] {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            text = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
            cnt = extract_from_text(text, seen, out)
            if cnt == 0:
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


# ============================================================================
# ТЕСТ ЧЕРЕЗ XRAY-KNIFE
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
    return survivors


# ============================================================================
# ПЕРЕИМЕНОВАНИЕ + GeoIP
# ============================================================================
def cc_to_flag(cc):
    cc = (cc or "").upper()
    if len(cc) != 2 or not cc.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in cc)


def get_host(cfg):
    """Извлечь host сервера из конфига."""
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
    # fallback для ss:// с base64 в userinfo
    m = re.search(r"@([^:/?#]+):\d+", cfg)
    return m.group(1) if m else ""


def extract_existing_flag(cfg):
    m = FLAG_RE.search(unquote(cfg))
    return m.group(0) if m else ""


def resolve_ip(host):
    if not host:
        return None
    # уже IP?
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
        return host
    try:
        return socket.gethostbyname(host)
    except Exception:
        return None


def geoip_lookup(hosts):
    """host -> ISO-код страны через ip-api.com (batch)."""
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
        time.sleep(1)  # бережём лимит ip-api (≤100 batch / мин)
    for h, ip in ip_by_host.items():
        cc_by_host[h] = cc_by_ip.get(ip, "")
    return cc_by_host


def set_name(cfg, name):
    """Поставить новое имя конфигу (fragment или ps для vmess)."""
    if cfg.startswith("vmess://"):
        b64 = cfg[8:].split("#", 1)[0]
        b64 += "=" * ((4 - len(b64) % 4) % 4)
        try:
            obj = json.loads(base64.b64decode(b64).decode("utf-8", "ignore"))
            obj["ps"] = name
            nb = base64.b64encode(
                json.dumps(obj, ensure_ascii=False).encode("utf-8")
            ).decode()
            return "vmess://" + nb
        except Exception:
            return cfg
    base = cfg.split("#", 1)[0]
    return base + "#" + quote(name, safe="")


def rename_configs(configs):
    hosts = [get_host(c) for c in configs]
    uniq = list(dict.fromkeys(h for h in hosts if h))
    print(f"[geoip] определяю страны для {len(uniq)} хостов...")
    cc_by_host = geoip_lookup(uniq)
    out = []
    for i, (cfg, host) in enumerate(zip(configs, hosts), 1):
        flag = cc_to_flag(cc_by_host.get(host, "")) or extract_existing_flag(cfg) or "\U0001F3F4"
        name = f"{flag}{VPN_NAME} \u2116{i}\u2668"
        out.append(set_name(cfg, name))
    return out


# ============================================================================
# ЗАПИСЬ
# ============================================================================
def write_output(working, total):
    if MAX_OUTPUT > 0:
        working = working[:MAX_OUTPUT]
    working = rename_configs(working)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    checks = " + ".join(TEST_URLS) if (URL_FLAG and TEST_URLS) else "реальная связь (default)"
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
