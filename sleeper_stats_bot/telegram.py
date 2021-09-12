# -*- coding: utf-8 -*-
import os

import requests
from bot_interface import BotInterface

telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]


class Telegram(BotInterface):
    def __init__(self, webhook):
        self.webhook = webhook

    def send_message(self, message):
        requests.post(
            "https://api.telegram.org/bot"
            + telegram_bot_token
            + "/sendMessage",
            json={
                "text": message,
                "disable_notification": "true",
                "chat_id": telegram_chat_id,
                "parse_mode": "HTML",
            },
        )
