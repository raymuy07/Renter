import requests

BOT_TOKEN = "8415624082:AAFecrpgFvg2v5OOiroHWL4j4VGl6suIEKk"
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

response = requests.get(url)
print(response.json())
