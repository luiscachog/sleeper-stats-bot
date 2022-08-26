# -*- coding: utf-8 -*-
from constants import GITHUB_REPOSITORY


class BotInterface:
    def __init__(self, bot_id):
        self.bot_id = bot_id

    def send_message(self, message):
        """
        Will be implemented in each derived class differently.
        Sends a message to the chat. NotImplemented error
        if the method is not implemented in a subclass.
        :param message: The message to send
        :return: None
        """
        raise NotImplementedError(
            "A send message method has not been implemented"
        )

    def send_photo(self, photo, caption):
        raise NotImplementedError(
            "A send message method has not been implemented"
        )

    def send(self, callback, *args):
        """

        :param callback: The callback function to call
        :param args: The arguments to the callback function
        :return: None
        """
        try:
            if type(args[0]) is str:
                message = callback(*args)
                self.send_message(message)

            else:
                self.send_photo(args[0])

        except Exception as err:
            message = (
                "There was an error that occurred with the bot: {}\n\n".format(
                    err
                )
            )
            message += "Please report it at " + GITHUB_REPOSITORY + "/issues"
