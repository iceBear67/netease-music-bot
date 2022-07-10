# -*- coding: utf-8 -*-

import os
import re
import sys
import tempfile

import requests

from ncm import config
from ncm.api import CloudApi
from ncm.file_util import add_metadata_to_song
from ncm.file_util import resize_img
from telegram import Message


def get_song_info_by_id(song_id):
    api = CloudApi()
    song = api.get_song(song_id)
    return song


def download_song_by_id(song_id):
    # get song info
    song = get_song_info_by_id(song_id)
    return download_song_by_song(song)


def download_song_by_song(song, message: Message):
    # get song info
    api = CloudApi()
    song_id = song['id']
    song_name = format_string(song['name'])
    artist_name = format_string(song['artists'][0]['name'])
    album_name = format_string(song['album']['name'])

    # update song file name by config
    song_file_name = '{}.mp3'.format(song_name)
    switcher_song = {
        1: song_file_name,
        2: '{} - {}.mp3'.format(artist_name, song_name),
        3: '{} - {}.mp3'.format(song_name, artist_name)
    }
    song_file_name = switcher_song.get(config.SONG_NAME_TYPE, song_file_name)

    # update song folder name by config, if support sub folder
    song_download_folder = tempfile.gettempdir()
    # download song
    song_url = api.get_song_url(song_id)
    if song_url is None:
        message.edit_text('Song <<{}>> is not available due to copyright issue!'.format(song_name))
        return
    is_already_download = download_file(song_url, song_file_name, song_download_folder, message)
    song_file_path = os.path.join(song_download_folder, song_file_name)
    if is_already_download:
        print('Mp3 file already download:', song_file_name)
        message.edit_text('Mp3 file already download: {}'.format(song_file_name))
        return song_file_path

    # download cover
    cover_url = song['album']['blurPicUrl']
    if cover_url is None:
        cover_url = song['album']['picUrl']
    cover_file_name = 'cover_{}.jpg'.format(song_id)
    download_file(cover_url, cover_file_name, song_download_folder, message)

    # resize cover
    resize_img(os.path.join(song_download_folder, cover_file_name))

    # add metadata for song
    cover_file_path = os.path.join(song_download_folder, cover_file_name)
    add_metadata_to_song(song_file_path, cover_file_path, song)

    # delete cover file
    os.remove(cover_file_path)
    return song_file_path


def download_file(file_url, file_name, folder, message: Message):
    if not os.path.exists(folder):
        os.makedirs(folder)
    file_path = os.path.join(folder, file_name)

    response = requests.get(file_url, stream=True)
    length = int(response.headers.get('Content-Length'))

    # TODO need to improve whether the file exists
    if os.path.exists(file_path) and os.path.getsize(file_path) > length:
        return True

    progress = ProgressBar(file_name, length, message)

    with open(file_path, 'wb') as file:
        for buffer in response.iter_content(chunk_size=1024):
            if buffer:
                file.write(buffer)
                progress.refresh(len(buffer))
    return False


class ProgressBar(object):

    def __init__(self, file_name, total, message: Message):
        super().__init__()
        self.file_name = file_name
        self.count = 0
        self.prev_count = 0
        self.message = message
        self.total = total
        self.end_str = '\r'

    def __get_info(self):
        return 'Progress: {:6.2f}%, {:8.2f}KB, [{:.30}]' \
            .format(self.count / self.total * 100, self.total / 1024, self.file_name)

    def refresh(self, count):
        self.count += count
        # Update progress if down size > 100k
        if self.count - self.prev_count > 102400:
            self.prev_count = self.count
            self.message.edit_text(self.__get_info())
            # print(self.__get_info(), end=self.end_str)
        # Finish downloading
        if self.count >= self.total:
            self.end_str = '\n'
            self.message.edit_text(self.__get_info())
            print(self.__get_info(), end=self.end_str)


def format_string(string):
    """
    Replace illegal character with ' '
    """
    return re.sub(r'[\\/:*?"<>|\t]', ' ', string)
