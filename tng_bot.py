"""
tng_bot.py uses premade markov chains to parrot ST:TNG characters into slack

"""
__author__ = "Andrew Herrington <me@aherrington.com>"
__license__ = "Apache V2"
__version__ = ".1"
__maintainer__ = "Andrew Herrington"
__email__ = "<me@aherrington.com>"
__status__ = "Development"

import os
import re
import pickle
import requests
import click
from requests.packages.urllib3.exceptions import InsecureRequestWarning, SNIMissingWarning
from slackclient import SlackClient
import time

requests.packages.urllib3.disable_warnings()
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(SNIMissingWarning)

CHARACTER_LIST=['picard',
                'riker',
                'troi',
                'data',
                'crusher',
                'wesley',
                'laforge',
                'yar',
                'pulaski']

@click.command()
@click.option('--corpus_path', type=click.Path(), help='directory that contains the corpuses')
@click.option('--slack_token', envvar='SLACK_TOKEN', type=unicode)
@click.option('--bot_name', envvar='BOT_NAME', default='tng_bot', type=unicode)
def main(corpus_path, slack_token, bot_name):

    character_chains = {}
    for character_name in CHARACTER_LIST:
        character_chains[character_name.lower()] = load_corpus(corpus_path, character_name)

    # Create the slackclient instance
    sc = SlackClient(slack_token)

    # Connect to slack
    if not sc.rtm_connect():
        raise Exception("Couldn't connect to slack.")

    # Where the magic happens

    while True:
        # Examine latest events
        for slack_event in sc.rtm_read():

            # Disregard events that are not messages
            if not slack_event.get('type') == "message":
                continue

            message = slack_event.get("text")
            user = slack_event.get("user")
            channel = slack_event.get("channel")

            if not message or not user:
                continue

            ######
            # Commands we're listening for.
            ######
            reply = None
            # help message
            if message.startswith('./{} help'.format(bot_name)):
                reply = "I'm a silly bot written by @andrewherrington to emulate Star Trek TNG Characters \n" \
                          "Commands:\n" \
                          "./{bot_name} list - lists all the characters I know\n" \
                          "./{bot_name} <Character> - will return a generated line as if I was that character\n" \
                          "./{bot_name} help - Will print this text".format(bot_name=bot_name)


            # list message
            elif message.startswith('./{} list'.format(bot_name)):
                reply = "I know the below characters: \n{}".format('\n'.join(CHARACTER_LIST))

            # ping message
            elif message.startswith('./{} ping'.format(bot_name)):
                reply = 'Make it So'

            # any othe message, looks for a character name
            elif message.startswith('./{}'.format(bot_name)):
                text = message.split(' ')
                character = text[1].lower()
                if character not in CHARACTER_LIST:
                    reply = 'I do not know who {} is.'.format(character)

                else:
                    reply = character_chains[character.lower()].make_sentence()
                    reply = '{}: {}'.format(character,format_message(reply))

            if reply is not None:
                sc.rtm_send_message(channel, reply)
        # Sleep for half a second
        time.sleep(0.1)


def load_corpus(path, character_name):
    with open(os.path.join(path, '{}.txt'.format(character_name.lower()))) as file_handler:
        return pickle.load(file_handler)

def format_message(original):
    """
    Do any formatting necessary to markov chains before relaying to Slack.
    """
    if original is None:
        return

    # Clear <> from urls
    cleaned_message = re.sub(r'<(htt.*)>', '\1', original)

    return cleaned_message

if __name__ == '__main__':
    main()