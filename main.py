# -*- coding: utf-8 -*-
# import config
import sys

import requests
import telebot
import subprocess
import tempfile
import os
import xml.etree.ElementTree as XmlElementTree
import httplib2
import uuid
from telebot import types
import logging

logger = telebot.logger
telebot.logger.setLevel(logging.DEBUG)  # Outputs debug messages to console.

words = ['по жанру', 'по языку', 'по исполнителю', 'по названию']
us_com = dict()

YANDEX_API_KEY = "a1747d0f-0e79-408e-8ba4-b53eb5c56970"
YANDEX_ASR_HOST = 'asr.yandex.net'
YANDEX_ASR_PATH = '/asr_xml'
CHUNK_SIZE = 1024 ** 2

token = '472543405:AAHecv83IiQYVHcMe9xRIk_g4zSMgLdOFig'
bot = telebot.TeleBot('472543405:AAHecv83IiQYVHcMe9xRIk_g4zSMgLdOFig')

nameDB = 'telegram'
nameTable = 'info'
port = 3306
music_path = 'music'

ffmpeg_exec = 'ffmpeg'  # for linux
if sys.platform.startswith("win"):
    # for windows
    ffmpeg_exec = r'bin\ffmpeg.exe'


# Создание своего исключения
class SpeechException(Exception):
    pass


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
            ffmpeg_exec,  # путь до ffmpeg.exe
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


def read_chunks(chunk_size, b):
    while True:
        chunk = b[:chunk_size]
        b = b[chunk_size:]

        yield chunk

        if not b:
            break


def get_xml(chunks, url):
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
    return connection.getresponse()


def xml_parse(xml: XmlElementTree):
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
            raise SpeechException('No text found.\n\nResponse:')
    else:
        raise SpeechException('No text found.\n\nResponse:')


def speech_to_text(filename=None, inbytes=None, request_id=uuid.uuid4().hex, topic='queries',
                   key=YANDEX_API_KEY, mat=False, need_lang=False):
    # Если передан файл
    if filename:
        with open(filename, 'br') as file:
            inbytes = file.read()
    if not inbytes:
        raise Exception('Neither file name nor bytes provided.')

    # Конвертирование в нужный формат
    inbytes = convert_to_pcm16b16000r(in_bytes=inbytes)

    lang = '&biometry=language'

    # Формирование тела запроса к Yandex API
    url = YANDEX_ASR_PATH + '?uuid=%s&key=%s&topic=%s&disableAntimat=%s%s' % (
        request_id,
        key,
        topic,
        "true" if mat else "false",
        lang if need_lang else ""
    )

    # Считывание блока байтов
    chunks = read_chunks(CHUNK_SIZE, inbytes)

    response = get_xml(chunks, url)
    # Обработка ответа сервера
    if response.code == 200:
        response_text = response.read()
        xml = XmlElementTree.fromstring(response_text)
        try:
            return xml_parse(xml)
        except SpeechException:
            print(response_text)
            raise SpeechException
    else:
        raise SpeechException('Unknown error.\nCode: %s\n\n%s' % (response.code, response.read()))


@bot.message_handler(commands=["start"])
def start(m):
    global us_com
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in words])
    # Задаём параметр по умолчанию
    if us_com.get(m.chat.id) is None:
        us_com[m.chat.id] = words[0]
    cur = us_com[m.chat.id]

    bot.send_message(m.chat.id, "Выберите критерий, текущий: " + cur, reply_markup=keyboard)


def key_handler(message):
    global us_com
    text = message.text
    if message.content_type == "voice":
        try:
            text = voice_processing(message)
        except SpeechException:
            text = ""

    if message.content_type != "voice" and message.content_type != "text" or text == "":
        bot.send_message(message.chat.id, "Не понимаю")
        return

    if text in words:
        us_com[message.chat.id] = text
        bot.send_message(message.chat.id, "Текущий критерий: " + text)
    else:
        do_request(text, message)


def do_request(text, message):
    bot.send_message(message.chat.id, text + " Reply")


# функция получения сообщения
@bot.message_handler(content_types=['voice', 'text'])
def repeat_voice(message):
    print("Get", message.content_type)
    key_handler(message)


def voice_processing(message):
    file_info = bot.get_file(message.voice.file_id)
    file = requests.get(
        'https://api.telegram.org/file/bot{0}/{1}'.format(token, file_info.file_path))
    try:
        return speech_to_text(inbytes=file.content, topic="notes", mat=False)
    except SpeechException:
        raise SpeechException


if __name__ == '__main__':
    bot.polling(none_stop=True)
