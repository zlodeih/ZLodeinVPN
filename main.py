import urllib.request
import socket
import re
import time
import traceback
import random
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import ipaddress

SOURCES = [
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_universal.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-SNI-RU-all.txt",
    "https://raw.githubusercontent.com/whoahaow/rjsxrd/refs/heads/main/githubmirror/bypass/bypass-all.txt",
    "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/refs/heads/main/kizyakbeta7.txt",
    "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/refs/heads/main/kizyakbeta6.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt"
]

# Списки CIDR, которые часто используются для белых списков в РФ (например, Cloudflare, хостинги и т.д.)
# Или мы можем динамически проверять, входит ли IP сервера в разрешенные подсети.
def is_ip_in_allowed_cidr(ip_str):
    # Если это домен, то резолвим его сначала
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        try:
            ip_str = socket.gethostbyname(ip_str)
            ip = ipaddress.ip_address(ip_str)
        except:
            return False

    # Пример некоторых распространенных подсетей Cloudflare и популярных CDN, которые часто в белых списках
    allowed_subnets = [
        "104.16.0.0/12",
        "172.64.0.0/13",
        "188.114.96.0/20",
        "162.159.0.0/16",
        "108.162.192.0/18",
        "190.93.240.0/20",
        "141.101.64.0/18",
        "197.234.240.0/22",
        "198.41.128.0/17",
        "66.249.64.0/19", # Googlebot (часто в белых списках)
        "17.0.0.0/8"      # Apple (тоже часто не блокируют полностью)
    ]

    for subnet in allowed_subnets:
        if ip in ipaddress.ip_network(subnet):
            return True
    return False

def check_port_and_ping(ip, port):
    try:
        start_time = time.perf_counter()
        sock = socket.create_connection((ip, int(port)), timeout=3.5)
        sock.close()
        return time.perf_counter() - start_time
    except:
        return None

def get_real_ip(hostname):
    try:
        return socket.gethostbyname(hostname)
    except:
        return None

def check_vless_url(vless_url):
    try:
        parsed_url = urlparse(vless_url)
        host = parsed_url.hostname
        port = parsed_url.port or 443

        # Проверяем доступность хоста и порта
        latency = check_port_and_ping(host, port)
        if latency is None:
            return None

        query_params = parse_qs(parsed_url.query)
        sni = query_params.get("sni", [host])[0]

        # Важная проверка для обхода блокировок:
        # Проверяем, находится ли IP сервера или его SNI в разрешенных CIDR / белых списках
        is_allowed_route = is_ip_in_allowed_cidr(host) or is_ip_in_allowed_cidr(sni)

        # Если это TLS/Reality, проверяем SNI
        if parsed_url.scheme == "vless" and ("security=tls" in vless_url or "security=reality" in vless_url):
            if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", sni):
                real_sni_ip = get_real_ip(sni)
                if real_sni_ip is None:
                    return None
            
            try:
                # Имитируем запрос к SNI
                response = requests.get(f"https://{host}:{port}", timeout=5, verify=False, headers={'Host': sni})
                if response.status_code in [200, 400, 404]:
                    # Приоритет серверам, которые используют разрешенные CIDR/белые домены
                    score = latency if is_allowed_route else latency + 1.0 # Искусственно увеличиваем пинг для не-CIDR серверов, чтобы продвинуть лучшие вперед
                    return (score, vless_url)
            except requests.exceptions.RequestException:
                pass
        else:
            if is_allowed_route:
                return (latency, vless_url)
            return (latency + 0.5, vless_url)

    except Exception as e:
        pass
    return None

def process_line(line):
    line = line.strip()
    if not line or line.startswith("#") or "://" not in line:
        return None
    try:
        if line.startswith("vless://") or line.startswith("trojan://") or line.startswith("ss://"):
            return check_vless_url(line)
        else:
            clean = line.split("#")[0]
            netloc = urlparse(clean).netloc.split("@")[-1]
            if ":" in netloc:
                host, port = netloc.split(":")[:2]
                port = re.split(r"[/?]", port)[0]
                
                latency = check_port_and_ping(host, port)
                if latency is not None:
                    return (latency, line)
    except:
        pass
    return None

def main():
    print("=== ЗАПУСК ЧЕКЕРА С ПОДДЕРЖКОЙ CIDR И БЕЛЫХ СПИСКОВ ===")
    checked_servers = []
    seen_configs = set()
    all_lines = []

    for url in SOURCES:
        try:
            print(f"Скачиваю базу: {url}")
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}) 
            text = urllib.request.urlopen(req, timeout=15).read().decode('utf-8')
            count = 0
            for line in text.splitlines():
                line = line.strip()
                if line and "://" in line and not line.startswith("#"):
                    if line not in seen_configs:
                        seen_configs.add(line)
                        all_lines.append(line)
                        count += 1
            print(f"-> Успешно загружено уникальных строк: {count}")
        except Exception as e:
            print(f" Ошибка при скачивании {url}: {e}")

    total_found = len(all_lines)
    print(f" Всего уникальных серверов в базах: {total_found}")

    if total_found > 5000:
        print(" Серверов очень много! Берем случайные 5000 для проверки...")
        random.shuffle(all_lines)
        all_lines = all_lines[:5000]

    print(f"Запускаю 150 параллельных потоков...")

    with ThreadPoolExecutor(max_workers=150) as executor:
        futures = [executor.submit(process_line, line) for line in all_lines]
        for i, future in enumerate(as_completed(futures)):
            res = future.result()
            if res is not None:
                checked_servers.append(res)
            if i > 0 and i % 500 == 0:
                print(f" Проверено: {i} / {len(all_lines)}...")

    print(f"Проверка завершена! Найдено живых серверов: {len(checked_servers)}")

    # Сортируем по качеству (с учетом задержки и приоритета CIDR)
    checked_servers.sort(key=lambda x: x[0])
    top_fast_servers = checked_servers[:250]
    working_servers = [line for score, line in top_fast_servers]

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    final_lines = [
        "# profile-title: 🌸ZLodeinVPN_CIDR_AUTOMATED🌸",
        "# profile-update-interval: 1",
        f"# Последнее обновление: {timestamp} UTC",
        f"# Всего проверено: {len(all_lines)} | Живых: {len(checked_servers)} | Отобрано топ-{len(working_servers)} лучших"
    ]
    final_lines.extend(working_servers)

    with open("cleaned_sub.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(final_lines))
    
    print(f" Результат успешно сохранен в cleaned_sub.txt!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("!!! КРИТИЧЕСКИЙ СБОЙ !!!")
        traceback.print_exc()
        exit(1)
