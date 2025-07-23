import requests

BOT_TOKEN = "7889379066:AAEflJTAFqwTDLXoYClOddzUoSXHR2Yxw1U"
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

response = requests.get(url)
print(response.json())
