import urllib.request
import socket
import re
import time
from urllib.parse import urlparse

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
        # Засекаем точное время начала проверки
        start_time = time.perf_counter()
        
        # Пытаемся подключиться. Если сервер мертв, через 2 секунды он отвалится
        sock = socket.create_connection((ip, int(port)), timeout=2)
        sock.close()
        
        # Возвращаем время ответа (чем меньше, тем быстрее сервер)
        return time.perf_counter() - start_time
    except:
        return None

# Список для хранения кортежей вида: (время_ответа, строка_конфига)
checked_servers = []
seen_configs = set()

for url in SOURCES:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        text = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("#") and "profile-" in line.lower():
                continue
            if not line.startswith("#") and "://" in line:
                if line not in seen_configs:
                    seen_configs.add(line)
                    
                    clean = line.split('#')[0]
                    netloc = urlparse(clean).netloc.split("@")[-1]
                    if ":" in netloc:
                        host, port = netloc.split(":")[:2]
                        port = re.split(r'[/?]', port)[0]
                        
                        # Замеряем пинг
                        latency = check_port_and_ping(host, port)
                        if latency is not None:
                            checked_servers.append((latency, line))
    except:
        pass

# Сортируем весь список по времени ответа — от самых быстрых к самым медленным
checked_servers.sort(key=lambda x: x[0])

# Забираем ровно 300 самых первых (самых быстрых) серверов
top_fast_servers = checked_servers[:300]

# Вытаскиваем обратно чистые конфигурации без циферок пинга
working_servers = [line for latency, line in top_fast_servers]

# Формируем заголовок файла
final_lines = [
    "# profile-title: 🌸ZLodeinVPN🌸",
    "# profile-update-interval: 1",
    f"# Всего живых: {len(checked_servers)} | Отобрано топ-300 лучших по пингу"
]
final_lines.extend(working_servers)

# Перезаписываем наш cleaned_sub.txt
with open("cleaned_sub.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(final_lines))
