import json
import logging
from pathlib import Path

from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, Dispatcher
from telegram import Update
from telegram.ext import CallbackContext
import re

import config
import controller
import util

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
enabledGroups = list[int]()


def on_message(update: Update, context: CallbackContext):
    if update.message.from_user:
        print(update.message.from_user.full_name + ": " + update.message.text)
    if update.effective_chat.id not in enabledGroups:
        return
    if not update.message.text.__contains__('music.163.com'):
        return

    match_result = re.search(r'(song\?id=)(\d+)?', update.message.text)
    if match_result:
        song_id: str = match_result.group(2)
        controller.download_and_send(update, context, song_id)


def command_ncm(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        update.message.reply_text("NCM Resolver v??\n" \
                                  "/ncm <song_id> -- Resolve and send\n" \
                                  "/ncm enable -- Detects NCM Links in chat and upload it\n" \
                                  "/ncm disable -- Disable NCM Link detection in chat")
        return
    sub_cmd = context.args[0]
    if sub_cmd == "enable":
        if update.effective_chat.id not in enabledGroups:
            enabledGroups.append(update.effective_chat.id)
            update.message.reply_text("NCM Link detection is ENABLED")
        else:
            update.message.reply_text("NCM Link detection is already enabled in this chat")
    elif sub_cmd == "disable":
        if update.effective_chat.id in enabledGroups:
            enabledGroups.remove(update.effective_chat.id)
            update.message.reply_text("NCM Link detection in this chat is DISABLED")
        else:
            update.message.reply_text("NCM Link detection is already disabled in this chat")
    else:
        controller.download_and_send(update, context, context.args[0])


def load_data():
    # load enabled groups...
    enable_group_file: Path = Path("enabled_groups.json")
    if not enable_group_file.exists():
        enable_group_file.write_text(json.dumps(list()))
    with enable_group_file.open('rb') as f:
        global enabledGroups
        enabledGroups = json.loads(f.read())
    print(f'{len(enabledGroups)} groups enabled')
    # load cache
    cache_file: Path = Path("cache.json")
    if not cache_file.exists():
        cache_file.write_text(json.dumps(controller.song2file))
    with cache_file.open('rb') as f:
        controller.song2file = json.load(f)
        print(f'{len(controller.song2file.keys())} songs cached')


def save_data():
    enable_group_file: Path = Path("enabled_groups.json")
    enable_group_file.write_text(json.dumps(enabledGroups))
    cache_file: Path = Path("cache.json")
    cache_file.write_text(json.dumps(controller.song2file))


if __name__ == '__main__':
    REQUEST_KWARGS = {
        # "USERNAME:PASSWORD@" is optional, if you need authentication:
        'proxy_url': 'http://127.0.0.1:8889/',
    }

    # load data.
    load_data()
    updater = Updater(token=config.bot_token, use_context=True)
    dispatcher: Dispatcher = updater.dispatcher
    echo_handler = MessageHandler(Filters.text & (~Filters.command), on_message)
    dispatcher.add_handler(echo_handler)
    dispatcher.add_handler(CommandHandler("ncm", command_ncm))
    updater.start_polling()
    updater.idle()
    save_data()
