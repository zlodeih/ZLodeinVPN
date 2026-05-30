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
        # Таймаут 2.0 секунды, чтобы не отсекать рабочие сервера с высоким пингом
        sock = socket.create_connection((ip, int(port)), timeout=2.0)
        sock.close()
        return time.perf_counter() - start_time
    except:
        return None

def process_line(line):
    line = line.strip()
    if not line or line.startswith("#") or "://" not in line:
        return None
    try:
        clean = line.split('#')[0]
        netloc = urlparse(clean).netloc.split("@")[-1]
        
        # Обработка IPv6 и стандартных IPv4
        if "]" in netloc:
             host_port = netloc.split("]:")
             if len(host_port) == 2:
                 host = host_port[0].replace("[", "")
                 port = re.split(r'[/?]', host_port[1])[0]
             else:
                 return None
        elif ":" in netloc:
            # IPv4
            host, port = netloc.split(":")[:2]
            port = re.split(r'[/?]', port)[0]
        else:
            return None
            
        latency = check_port_and_ping(host, port)
        if latency is not None:
            return (latency, line)
    except:
        pass
    return None

def main():
    print("=== ЗАПУСК СКОРОСТНОГО ЧЕКЕРА ===\n")
    checked_servers = []
    seen_configs = set()
    all_lines = []

    # 1. Скачиваем ВСЕ базы
    for url in SOURCES:
        try:
            print(f"Скачиваю: {url}")
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            text = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
            count = 0
            for line in text.splitlines():
                line = line.strip()
                if line and "://" in line and not line.startswith("#"):
                    if line not in seen_configs:
                        seen_configs.add(line)
                        all_lines.append(line)
                        count += 1
            print(f" -> Добавлено: {count} шт.")
        except Exception as e:
            print(f" Ошибка : {e}")

    total_found = len(all_lines)
    print(f"\nВсего собрано уникальных серверов: {total_found}")
    print(f"Запускаю 200 параллельных потоков (GitHub Actions мощный, это займет мало времени)...\n")

    # 2. Массовая проверка ВСЕХ серверов в 200 потоков
    with ThreadPoolExecutor(max_workers=200) as executor:
        futures = [executor.submit(process_line, line) for line in all_lines]
        for i, future in enumerate(as_completed(futures)):
            res = future.result()
            if res is not None:
                checked_servers.append(res)
            
            # Лог прогресса каждые 500 штук
            if i > 0 and i % 500 == 0:
                print(f" Проверено: {i} / {total_found} | Найдено живых на тест: {len(checked_servers)}")

    print(f"\nПроверка завершена! На порт откликнулись: {len(checked_servers)} серверов.")

    # 3. Сортируем по скорости (от самого быстрого к медленному)
    checked_servers.sort(key=lambda x: x[0])
    
    # Отбираем РОВНО ТОП-100 самых быстрых
    top_limit = 100
    top_fast_servers = checked_servers[:top_limit]
    working_servers = [line for latency, line in top_fast_servers]

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    # 4. Формируем файл
    final_lines = [
        "# profile-title: 🌸ZLodeinVPN🌸",
        "# profile-update-interval: 1",
        f"# Последнее обновление: {timestamp} UTC",
        f"# Успешных коннектов: {len(checked_servers)} | Отобрано топ-{len(working_servers)} самых быстрых"
    ]
    final_lines.extend(working_servers)

    with open("cleaned_sub.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(final_lines))
    
    print(f"Результат ({len(working_servers)} серверов) сохранен в cleaned_sub.txt!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("!!! КРИТИЧЕСКИЙ СБОЙ СКРИПТА !!!")
        traceback.print_exc()
        exit(1)
