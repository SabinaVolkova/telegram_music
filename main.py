# -*- coding: utf-8 -*-
# import config
import random

import requests
import telebot

token = '472543405:AAHecv83IiQYVHcMe9xRIk_g4zSMgLdOFig'
bot = telebot.TeleBot('472543405:AAHecv83IiQYVHcMe9xRIk_g4zSMgLdOFig')


@bot.message_handler(content_types=["text"])
def repeat_all_messages(message):  # Название функции не играет никакой роли, в принципе
    bot.send_message(message.chat.id, message.text)


@bot.message_handler(content_types=['voice'])
def voice_processing(message):
    file_info = bot.get_file(message.voice.file_id)
    file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(bot, file_info.file_path))
    audio = open("sound.ogg", mode="w")
    print(file, file=audio)
    audio.close()


# функция получения голосовго сообщения
@bot.message_handler(content_types=['voice'])
def voice_processing(message):
    file_info = bot.get_file(message.voice.file_id)
    file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(token, file_info.file_path))
    print("lol")


if __name__ == '__main__':
    bot.polling(none_stop=True)
