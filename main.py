import urllib.request
import socket
import re
import time
import traceback
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

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

def check_port_and_ping(ip, port):
    try:
        start_time = time.perf_counter()
        sock = socket.create_connection((ip, int(port)), timeout=2)
        sock.close()
        return time.perf_counter() - start_time
    except:
        return None

def process_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if "://" not in line:
        return None
    
    try:
        clean = line.split('#')[0]
        netloc = urlparse(clean).netloc.split("@")[-1]
        if ":" in netloc:
            host, port = netloc.split(":")[:2]
            port = re.split(r'[/?]', port)[0]
            
            # Замеряем пинг
            latency = check_port_and_ping(host, port)
            if latency is not None:
                return (latency, line)
    except:
        pass
    return None

def main():
    print("=== ЗАПУСК СУПЕР-БЫСТРОГО ЧЕКЕРА ===")
    checked_servers = []
    seen_configs = set()
    all_lines = []

    # 1. Скачиваем все базы
    for url in SOURCES:
        try:
            print(f"Скачиваю базу: {url}")
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            text = urllib.request.urlopen(req, timeout=15).read().decode('utf-8')
            for line in text.splitlines():
                line = line.strip()
                if line and "://" in line and not line.startswith("#"):
                    if line not in seen_configs:
                        seen_configs.add(line)
                        all_lines.append(line)
        except Exception as e:
            print(f"Ошибка при скачивании {url}: {e}")

    print(f"Уникальных серверов найдено: {len(all_lines)}. Запускаю 100 потоков проверки...")

    # 2. Проверяем в 100 потоков одновременно
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(process_line, line) for line in all_lines]
        for future in as_completed(futures):
            res = future.result()
            if res is not None:
                checked_servers.append(res)

    print(f"Проверка завершена! Найдено живых серверов: {len(checked_servers)}")

    # 3. Сортируем от быстрых к медленным
    checked_servers.sort(key=lambda x: x[0])

    # Отбираем ровно 300 лучших
    top_fast_servers = checked_servers[:300]
    working_servers = [line for latency, line in top_fast_servers]

    # 4. Формируем красивый заголовок для Cloudflare и Happ VPN
    final_lines = [
        "# profile-title: 🌸ZLodeinVPN🌸",
        "# profile-update-interval: 1",
        f"# Всего живых: {len(checked_servers)} | Отобрано топ-300 лучших по пингу"
    ]
    final_lines.extend(working_servers)

    # Записываем результат
    with open("cleaned_sub.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(final_lines))
    
    print("Результат успешно сохранен в cleaned_sub.txt! Топ-300 готовы.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("!!! КРИТИЧЕСКАЯ ОШИБКА В СИСТЕМЕ !!!")
        traceback.print_exc()
        exit(1)
