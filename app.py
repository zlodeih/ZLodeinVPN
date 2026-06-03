from flask import Flask, Response
import subprocess
import json
import time
import os

app = Flask(__name__)

CONFIG_FILE = "cleaned_sub.txt"
UPDATE_SCRIPT = "main.py"

def get_latest_config():
    if not os.path.exists(CONFIG_FILE) or (time.time() - os.path.getmtime(CONFIG_FILE) > 300): # Обновляем каждые 5 минут
        print("Обновляю конфигурации...")
        try:
            subprocess.run(["python", UPDATE_SCRIPT], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Ошибка при обновлении конфигураций: {e}")
            return None
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Пропускаем первые 4 строки с метаданными
            configs = [line.strip() for line in lines[4:] if line.strip()]
            return configs
    except Exception as e:
        print(f"Ошибка при чтении конфигураций: {e}")
        return None

@app.route("/subscribe")
def subscribe():
    configs = get_latest_config()
    if configs:
        # Возвращаем все конфигурации как есть, клиент сам выберет лучшую
        # Или можно реализовать логику выбора лучшей на сервере, если клиент не умеет
        response_content = "\n".join(configs)
        return Response(response_content, mimetype="text/plain")
    else:
        return Response("No configurations available", status=500, mimetype="text/plain")

if __name__ == "__main__":
    # Убедимся, что начальная конфигурация существует
    get_latest_config()
    app.run(host="0.0.0.0", port=8080)