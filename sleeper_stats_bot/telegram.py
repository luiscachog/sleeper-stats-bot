# -*- coding: utf-8 -*-
import os

import requests
from bot_interface import BotInterface

telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]


class Telegram(BotInterface):
    def __init__(self, webhook):
        self.webhook = webhook

    def send_photo(self, photo):
        url = (
            "https://api.telegram.org/bot"
            + telegram_bot_token
            + "/sendPhoto?chat_id="
            + telegram_chat_id
        )
        files = {"photo": photo}
        requests.post(url, files=files)

    def send_message(self, message):

        url = (
            "https://api.telegram.org/bot"
            + telegram_bot_token
            + "/sendMessage?chat_id="
            + telegram_chat_id
            + "&text="
            + message
            + "&parse_mode=HTML"
            + "&disable_notification=true"
        )

        requests.post(url)
