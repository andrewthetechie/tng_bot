"""
Script_processor.py extracts lines from ST: TNG scripts for a specific character and outputs them to a json file

This script downloads scripts from http://www.chakoteya.net/
"""
__author__ = "Andrew Herrington <me@aherrington.com>"
__license__ = "Apache V2"
__version__ = ".1"
__maintainer__ = "Andrew Herrington"
__email__ = "<me@aherrington.com>"
__status__ = "Development"

import os
import sys
import errno
import shutil
import json
import glob
import re
import pickle
import requests
import click
import markovify
from tqdm import tqdm
from bs4 import BeautifulSoup
from cerberus import Validator
from pprint import pprint

BASE_URL = 'http://www.chakoteya.net'
SERIES_INFO = {
    'TOS': {'url_base': '/StarTrek/', 'bgcolor': '#eeeeee'},
    'TNG': {'url_base': '/NextGen/', 'bgcolor': '#eeeeee'},
    'DS9': {'url_base': '/DS9/', 'bgcolor': '#eeeeee'},
    'VOY': {'url_base': '/Voyager/', 'bgcolor': '#ffffff'},
    'ENT': {'url_base': '/Enterprise/', 'bgcolor': '#eeeeee'},
}


@click.command()
@click.option('--script_directory', type=click.Path(), help='Path to store scripts.',
              default=click.Path('/tmp/tng_bot'))
@click.option('--series', type=click.Choice(['TOS', 'TNG', 'DS9', 'VOY', 'ENT']),
              help='Series to pull the character from')
@click.option('--character_name',  help='Name of the character to parse for. Ex. Picard, Data, Riker')
@click.option('--output_file', type=click.File('w'), help='File to output to')
def main(script_directory, series, character_name, output_file):
    series = series.upper()
    if not _check_script_cache(os.path.join(script_directory, series)):
        _get_scripts(series, script_directory)


    _write_corpus(os.path.join(script_directory, series), character_name, output_file)
    sys.exit(0)

def _write_corpus(script_directory, character_name, output_file_handler):
    character_name=character_name.upper()
    lines = []
    for script in tqdm(glob.glob(os.path.join(script_directory, '*.html'))):
        with open(script, 'r') as script_file_handler:
            soup_parser = BeautifulSoup(script_file_handler, 'html.parser')
            texts = soup_parser.findAll(text=True)
            for text in texts:
                text = re.sub(r"\n", " ", text).lstrip()
                try:
                    if text.startswith(character_name):
                        try:
                            lines.append(re.sub("[\(\[].*?[\)\]]", "", text.split(':')[1].lstrip().rstrip()))
                        except IndexError:
                            lines.append(re.sub("[\(\[].*?[\)\]]", "", text.split(character_name)[1].lstrip().rstrip()))
                except UnicodeEncodeError:
                    pass
    chain = markovify.Text(" ".join(lines), state_size=2)
    pickle.dump(chain, output_file_handler)

def _check_script_cache(path):
    if not os.path.exists(path):
        return False
    try:
        with open(os.path.join(path, 'meta'), 'r') as meta_file_handler:
            meta_data = json.load(meta_file_handler)
    except IOError:
        return False

    schema = {
        'total_scripts': {'type': 'integer', 'required': True}
    }
    validator = Validator(schema)

    if not validator.validate(meta_data):
        return False

    file_count = _get_file_count(path, 'html')

    if file_count != meta_data['total_scripts']:
        return False

    return True


def _get_file_count(path, extension):
    (_, _, my_files) = os.walk(path).next()
    return len([f for f in my_files if f.endswith('.{}'.format(extension))])


def _get_scripts(series, script_directory):
    series = series.upper() # upper case just in case we got here somehow weird
    series_path = os.path.join(script_directory, series)
    _make_sure_path_exists(series_path)
    try:
        episode_listing_url = BASE_URL + SERIES_INFO[series]['url_base'] + 'episodes.htm'
    except KeyError:
        click.echo('Series is invalid: {}'.format(series))
        sys.exit(1)

    script_urls = _get_script_urls(episode_listing_url, SERIES_INFO[series]['bgcolor'])
    click.echo('Downloading {count} scripts for {series} to {path}'.format(
        count=len(script_urls),
        series=series,
        path=series_path
    ))
    counter = 1
    for url in tqdm(script_urls):
        this_url = BASE_URL + SERIES_INFO[series]['url_base'] + url
        response = requests.get(this_url, stream=True)
        if response.status_code != 200:
            tqdm.write('Unable to download Script. URL: {}'.format(this_url))
        else:
            with open(os.path.join(series_path, '{}.html'.format(counter)), 'wb') as f:
                response.raw.decode_content = True
                shutil.copyfileobj(response.raw, f)
        counter += 1

    with open(os.path.join(series_path, 'meta'), 'w') as meta_file_handler:
        meta_data = {'total_scripts': len(script_urls)}
        meta_file_handler.write(json.dumps(meta_data))


def _get_script_urls(listing_url, bgcolor):
    response = requests.get(listing_url)
    if response.status_code != 200:
        click.echo('Error when accessing {url}\nStatus Code: {status}'.format(url=listing_url,
                                                                              status=response.status_code))
        sys.exit(2)

    soup_parser = BeautifulSoup(response.text, "html.parser")
    links = soup_parser.findAll("td", attrs={"bgcolor": bgcolor})
    script_links = []

    for link in links:

        try:
            script_links.append(link.font.a['href'])
        except TypeError:
            pass
        except AttributeError:
            pass
    return script_links


def _make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            click.echo('Unable to create directory {path} \n Error: {exception}'.format(path=path, exception=exception))
            sys.exit(1)