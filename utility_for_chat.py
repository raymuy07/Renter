import os

import requests


def main() -> None:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN environment variable is required")

    response = requests.get(f"https://api.telegram.org/bot{bot_token}/getUpdates", timeout=30)
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()
