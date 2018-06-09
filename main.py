# -*- coding: utf-8 -*-
# import config
import random

import requests
import telebot
import subprocess
import tempfile
import os
import xml.etree.ElementTree as XmlElementTree
import httplib2
import uuid
from telebot import types

YANDEX_API_KEY = "a1747d0f-0e79-408e-8ba4-b53eb5c56970"

YANDEX_ASR_HOST = 'asr.yandex.net'
YANDEX_ASR_PATH = '/asr_xml'
CHUNK_SIZE = 1024 ** 2

token = '472543405:AAHecv83IiQYVHcMe9xRIk_g4zSMgLdOFig'
bot = telebot.TeleBot('472543405:AAHecv83IiQYVHcMe9xRIk_g4zSMgLdOFig')


@bot.message_handler(commands=["actions"])
def actions(message):
    # Эти параметры для клавиатуры необязательны, просто для удобства
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    button_genre = types.KeyboardButton(text="По жанру", genre=True)
    button_lang = types.KeyboardButton(text="По языку", languahe=True)
    button_art = types.KeyboardButton(text="По исполнителю", artist=True)
    button_name = types.KeyboardButton(text="По названию", name=True)
    bot.keyboard.add(bot.button_genre, bot.button_lang, bot.button_art, bot.button_name)
    bot.send_message(bot.send_message.chat.id, "По каким параметрам подобрать музыку?", reply_markup=bot.keyboard)


def convert_to_pcm16b16000r(in_filename=None, in_bytes=None):
    with tempfile.TemporaryFile() as temp_out_file:
        temp_in_file = None
        if in_bytes:
            temp_in_file = tempfile.NamedTemporaryFile(delete=False)
            temp_in_file.write(in_bytes)
            in_filename = temp_in_file.name
            temp_in_file.close()
        if not in_filename:
            raise Exception('Neither input file name nor input bytes is specified.')

        # Запрос в командную строку для обращения к FFmpeg
        command = [
            r'bin\ffmpeg.exe',  # путь до ffmpeg.exe
            '-i', in_filename,
            '-f', 's16le',
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-'
        ]

        proc = subprocess.Popen(command, stdout=temp_out_file, stderr=subprocess.DEVNULL)
        proc.wait()

        if temp_in_file:
            os.remove(in_filename)

        temp_out_file.seek(0)
        return temp_out_file.read()


def read_chunks(chunk_size, bytes):
    while True:
        chunk = bytes[:chunk_size]
        bytes = bytes[chunk_size:]

        yield chunk

        if not bytes:
            break


def speech_to_text(filename=None, bytes=None, request_id=uuid.uuid4().hex, topic='notes', lang='ru-RU',
                   key=YANDEX_API_KEY):
    # Если передан файл
    if filename:
        with open(filename, 'br') as file:
            bytes = file.read()
    if not bytes:
        raise Exception('Neither file name nor bytes provided.')

    # Конвертирование в нужный формат
    bytes = convert_to_pcm16b16000r(in_bytes=bytes)

    # Формирование тела запроса к Yandex API
    url = YANDEX_ASR_PATH + '?uuid=%s&key=%s&topic=%s&disableAntimat=true' % (
        request_id,
        key,
        topic
    )

    # Считывание блока байтов
    chunks = read_chunks(CHUNK_SIZE, bytes)

    # Установление соединения и формирование запроса
    connection = httplib2.HTTPConnectionWithTimeout(YANDEX_ASR_HOST)

    connection.connect()
    connection.putrequest('POST', url)
    connection.putheader('Transfer-Encoding', 'chunked')
    connection.putheader('Content-Type', 'audio/x-pcm;bit=16;rate=16000')
    connection.endheaders()

    # Отправка байтов блоками
    for chunk in chunks:
        connection.send(('%s\r\n' % hex(len(chunk))[2:]).encode())
        connection.send(chunk)
        connection.send('\r\n'.encode())

    connection.send('0\r\n\r\n'.encode())
    response = connection.getresponse()

    # Обработка ответа сервера
    if response.code == 200:
        response_text = response.read()
        xml = XmlElementTree.fromstring(response_text)
        print(response_text)

        if int(xml.attrib['success']) == 1:
            max_confidence = - float("inf")
            text = ''

            for child in xml:
                if float(child.attrib['confidence']) > max_confidence:
                    text = child.text
                    max_confidence = float(child.attrib['confidence'])

            if max_confidence != - float("inf"):
                return text
            else:
                # Создавать собственные исключения для обработки бизнес-логики - правило хорошего тона
                raise SpeechException('No text found.\n\nResponse:\n%s' % (response_text))
        else:
            raise SpeechException('No text found.\n\nResponse:\n%s' % (response_text))
    else:
        raise SpeechException('Unknown error.\nCode: %s\n\n%s' % (response.code, response.read()))


class SpeechException(Exception):
    pass


# Создание своего исключения


@bot.message_handler(content_types=["text"])
def repeat_all_messages(message):  # Название функции не играет никакой роли, в принципе
    bot.send_message(message.chat.id, message.text)


# функция получения голосовго сообщения
@bot.message_handler(content_types=['voice'])
def voice_processing(message):
    file_info = bot.get_file(message.voice.file_id)
    file = requests.get(
        'https://api.telegram.org/file/bot{0}/{1}'.format(token, file_info.file_path))

    try:
        # обращение к нашему новому модулю
        text = speech_to_text(bytes=file.content)
        print(text)
    except SpeechException:
        # Обработка случая, когда распознавание не удалось
        print("Cannot detect")
    else:
        print("Else?")


# Бизнес-логика


if __name__ == '__main__':
    bot.polling(none_stop=True)
