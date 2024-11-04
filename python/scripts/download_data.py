import requests
import datetime
import gzip
import os

def to_filename(pair, date: datetime):
    return f'{pair}_{date:%Y%m%d}.gz'

def download_file(url, filename, over_write=False):
    if os.path.exists(filename) and not over_write:
        print(f'Existing {filename} found, skipping download...')
        return

    with open(filename, "wb") as file:
        response = requests.get(url)
        file.write(response.content)

def preview_file(filename: str):
    with gzip.open(filename, 'r') as f:
        for i in range(5):
            line = f.readline()
            print(line)
