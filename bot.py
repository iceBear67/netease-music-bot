import asyncio
import logging
import os
from concurrent import futures
from pathlib import Path
from threading import Lock

from telegram.ext import Updater, MessageHandler, Filters, DictPersistence, CommandHandler, Dispatcher, \
    PicklePersistence
from telegram import Update, InputFile, Message, Document
from telegram.ext import CallbackContext
from ncm.api import CloudApi
import re

import util

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
api = CloudApi()
executor = futures.ThreadPoolExecutor(max_workers=5)
dictLock = Lock()

songLock = Lock()
downloadingSongs = dict()


def on_message(update: Update, context: CallbackContext):
    print(update.message.from_user.full_name + ": " + update.message.text)
    context.chat_data.setdefault(str(update.message.chat_id), dict())
    if "enable" not in context.chat_data[str(update.message.chat_id)]:
        return
    if not update.message.text.__contains__('music.163.com'):
        return

    match_result = re.search(r'(song\?id=)(\d+)?', update.message.text)
    if match_result:
        song_id = match_result.group(2)
        with dictLock:
            cache: Document = context.bot_data[str(context.bot.id)][str(song_id)]
        if cache:
            context.bot.send_document(chat_id=update.effective_chat.id, document=cache)
        else:
            with songLock:
                started = song_id in downloadingSongs
                if started:
                    if update.effective_chat.id in downloadingSongs:
                        update.message.reply_text(text='Already downloading...')
                    return
                else:
                    executor.submit(resolv_and_upload, update, context, song_id)


def resolv_and_upload(update: Update, context: CallbackContext, song_id: int):
    print(f'Found Song ID: {song_id}')
    update.message.reply_text(text=f'Resolving...')
    song_info = util.get_song_info_by_id(song_id)
    if song_info:
        message = update.message.reply_text(text=f'Downloading...')
        result: os.path = util.download_song_by_song(song_info, message)
        # message.edit_text(text=f'Downloaded! Uploading now...')
        io = Path(result).open('rb')
        try:
            audio: Message = context.bot.send_audio(chat_id=update.effective_chat.id, audio=InputFile(io)
                                                    , title=song_info['name']
                                                    , performer=song_info['artists'][0]['name']
                                                    ,
                                                    filename=f"{song_info['artists'][0]['name']} ~ {song_info['name']}")
            message.delete()
            # broadcast
            with dictLock:
                context.bot_data[str(context.bot.id)][str(song_id)] = audio.document
            with songLock:
                for chat_id in downloadingSongs[song_id]:
                    if chat_id == str(update.effective_chat.id):
                        continue
                    else:
                        context.bot.send_document(chat_id=chat_id, document=audio.document)
        except Exception as e:
            io.close()
            message.edit_text(f'Download failed. Error: {e}')


def enable_detection(update: Update, context: CallbackContext):
    context.chat_data.setdefault(str(update.message.chat_id), dict())
    print(type(context.chat_data[str(update.message.chat_id)]))
    print(context.chat_data[str(update.message.chat_id)])
    context.chat_data[str(update.message.chat_id)]["enable"] = True

    update.message.reply_text("NCM Link Detection is ENABLED")


def disable_detection(update: Update, context: CallbackContext):
    context.chat_data.setdefault(str(update.message.chat_id), dict())
    dict_: dict = context.chat_data[str(update.message.chat_id)]
    if "enable" in dict_:
        dict_.__delitem__("enable")
        update.message.reply_text("NCM Link Detection is DISABLED")
    else:
        update.message.reply_text("Not enabled.")


if __name__ == '__main__':
    REQUEST_KWARGS = {
        # "USERNAME:PASSWORD@" is optional, if you need authentication:
        'proxy_url': 'http://127.0.0.1:8889/',
    }
    updater = Updater(token='5593989289:AAFOLjzoRLweCVOSXf3Subx1cZHfKkH6tro', use_context=True,
                      request_kwargs=REQUEST_KWARGS)
    dispatcher: Dispatcher = updater.dispatcher
    echo_handler = MessageHandler(Filters.text & (~Filters.command), on_message)
    command_enable_handler = CommandHandler("ncmenable", enable_detection)
    command_disable_handler = CommandHandler("ncmdisable", disable_detection)
    dispatcher.add_handler(echo_handler)
    dispatcher.add_handler(command_disable_handler)
    dispatcher.add_handler(command_enable_handler)
    updater.start_polling()
    updater.idle()
