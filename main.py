import urllib.request
import socket
import re
from urllib.parse import urlparse

# Сюда можно добавлять любые ссылки на txt файлы с серверами
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

def check_port(ip, port):
    try:
        # Пытаемся подключиться к порту. Даем 2 секунды на ответ.
        socket.create_connection((ip, int(port)), timeout=2)
        return True
    except:
        return False

working_servers = []

for url in SOURCES:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        text = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        
        for line in text.splitlines():
            line = line.strip()
            # Пропускаем комментарии и берем только ссылки
            if not line.startswith("#") and "://" in line:
                if line not in working_servers:
                    # Вытаскиваем IP и порт для проверки
                    clean = line.split('#')[0]
                    netloc = urlparse(clean).netloc.split("@")[-1]
                    if ":" in netloc:
                        host, port = netloc.split(":")[:2]
                        port = re.split(r'[/?]', port)[0]
                        
                        # Если сервер отвечает, добавляем в белый список
                        if check_port(host, port):
                            working_servers.append(line)
    except:
        pass

# Сохраняем все рабочие сервера в новый файл
with open("cleaned_sub.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(working_servers))
