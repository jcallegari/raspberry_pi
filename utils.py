__author__ = 'jrc'
import mimetypes
import json
import logging
import sys

logger = logging.getLogger('utils')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('utils')
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s:%(name)s: %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
logger.addHandler(ch)
logger.addHandler(fh)

def get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

def convert_json(json_str):
    j = {}
    try:
        j = json.loads(json_str)
        j['json'] = True
    except ValueError, e:
        logger.error('ValueError: parsing json string: %s\n%s', json_str, e)
        j['json'] = False
        j['error'] = e
    return j

def printf(format, *args):
    sys.stdout.write(format % args)

def reverse_string(strs):
    return ''.join([strs[i] for i in xrange(len(strs)-1, -1, -1)])

def reverse_words(txt):
    words = []
    word = []

    for char in txt:
        if char == ' ':
            words.append(''.join(word))
            word = []
        else:
            word.append(char)
    words.append(''.join(word))

    return ' '.join(reversed(words))
