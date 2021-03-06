import os
from concurrent import futures
from pathlib import Path
from threading import Lock

from ncm.api import CloudApi
from telegram import Update, Document, Message, InputFile, Audio
from telegram.ext import CallbackContext

import util

api = CloudApi()
executor = futures.ThreadPoolExecutor(max_workers=5)
cacheLock = Lock()

songLock = Lock()
downloadingSongs = dict[str, list[int]]()

song2file = dict[str, dict]()


def download_and_send(update: Update, context: CallbackContext, song_id: str, is_program: bool):
    with cacheLock:
        if song_id in song2file.keys():
            dct = song2file[song_id]
            context.bot.send_audio(chat_id=update.effective_chat.id, audio=Audio(
                file_id=dct["id"],
                file_unique_id=dct["unique_id"],
                duration=dct["duration"]
            ))
            return
    with songLock:
        started = song_id in downloadingSongs.keys()
        if started:
            if update.effective_chat.id in downloadingSongs[song_id]:
                update.message.reply_text(text='已经在下载了...')
                return
            else:
                downloadingSongs[song_id].append(update.effective_chat.id)
        else:
            downloadingSongs[song_id] = list()
            downloadingSongs[song_id].append(update.effective_chat.id)
            executor.submit(resolv_and_upload, update, context, song_id, is_program)


def resolv_and_upload(update: Update, context: CallbackContext, song_id: int, is_program: bool):
    if song_id not in downloadingSongs.keys():
        print("Possibly downloaded song, skip this request.")
        return
    print(f'Found Song ID: {song_id}')
    message = update.message.reply_text(text=f'解析中...')
    try:
        if is_program:
            song_info = api.get_program(song_id)
        else:
            song_info = util.get_song_info_by_id(song_id)
    except Exception as e:
        message.edit_text(f"无法获取歌曲信息！{e}")
        del downloadingSongs[song_id]
        return
    if song_info:
        message.edit_text(text=f'下载中...')
        result: os.path = util.download_song_by_song(song_info, message, is_program)
        # message.edit_text(text=f'Downloaded! Uploading now...')
        io = Path(result).open('rb')
        try:
            if is_program:
                audio: Message = context.bot.send_audio(chat_id=update.effective_chat.id, audio=InputFile(io)
                                                        , title=song_info['name']
                                                        , performer=song_info['dj']['nickname']
                                                        ,
                                                        filename=f"{song_info['dj']['nickname']} ~ {song_info['name']}")
            else:
                audio: Message = context.bot.send_audio(chat_id=update.effective_chat.id, audio=InputFile(io)
                                                        , title=song_info['name']
                                                        , performer=song_info['artists'][0]['name'],
                                                        filename=f"{song_info['artists'][0]['name']} ~ {song_info['name']}")
            message.delete()
            # broadcast
            with cacheLock:
                song2file[str(song_id)] = {
                    "id": audio.audio.file_id,
                    "unique_id": audio.audio.file_unique_id,
                    "duration": audio.audio.duration
                }
                # print(repr(song2file))
                # print(audio.audio.file_id)
                # print(audio.audio.file_unique_id)
            with songLock:
                for chat_id in downloadingSongs[str(song_id)]:
                    if chat_id == update.effective_chat.id:
                        continue
                    else:
                        context.bot.send_audio(chat_id=chat_id, audio=audio.audio)
                del downloadingSongs[str(song_id)]
        except Exception as e:
            io.close()
            message.edit_text(f'下载失败. Error: {e}')
            del downloadingSongs[str(song_id)]
        cache_file: Path = Path(result)
        os.remove(cache_file)
    else:
        message.edit_text(text=f'未找到曲目.')
        del downloadingSongs[str(song_id)]
