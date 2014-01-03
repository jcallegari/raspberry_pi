__author__ = 'jrc'
import urllib
import httplib2
import pycurl
import os
import sys
import config
import pickle
import copy
import cStringIO
from utils import convert_json, get_content_type
from collections import deque
import logging
import time
#log to file and console
LOGGING_LEVEL = logging.DEBUG
logger = logging.getLogger('speech')
logger.setLevel(LOGGING_LEVEL)
fh = logging.FileHandler('speech')
fh.setLevel(LOGGING_LEVEL)
ch = logging.StreamHandler()
ch.setLevel(LOGGING_LEVEL)
formatter = logging.Formatter('%(asctime)s - %(levelname)s:%(name)s: %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
logger.addHandler(ch)
logger.addHandler(fh)

http = httplib2.Http(disable_ssl_certificate_validation=True)
#disable/enable HTTP exceptions
http.force_exception_to_status_code = True

class APIException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return 'APIException\n\t' + self.value

class API:
    def __init__(self):
        self.name = str(self.__class__)[str(self.__class__).find('.') + 1:]
        #all APIs are set up with a persist path that can be used for pickling
        #pickle objects are stored in local dir e.g. data/AccessToken.p
        self.persist_path = 'data' + os.sep + self.name + '.p'
        self.url = None
        self.headers = None
        self.body = None
        self.status_code = None
        self.response = None
        self.content = None

    def __str__(self):
        return self.name

    def __repr__(self):
        return self

    def post(self):
        """HTTP POST verb."""
        pass

    def get(self):
        """HTTP GET verb."""
        pass

    def put(self):
        """HTTP PUT verb."""
        pass

    def delete(self):
        """HTTP DELETE verb."""
        pass

    def __eq__(self, other):
        #testing equality between api transactions
        if self.status_code != other.status_code:
            return False
        for header in self.headers:
            if header != 'Authorization':
                if self.headers[header] != other.headers[header]:
                    return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

class AccessToken(API):
    """Get a new or saved access token."""
    def __init__(self, url, app_key, app_secret, scopes, grant_type, new):
        API.__init__(self)
        #complete API URL
        self.url = url
        #info from developer portal app page
        self.app_key = app_key
        self.app_secret = app_secret
        self.scopes = scopes
        #grant_type for all  speech APIs is client credentials
        self.grant_type = grant_type
        #use a saved token or force retrieval of a new token
        self.new = new
        self.headers = config.HEADERS_OAUTH
        self.body = {'client_id': self.app_key, 'client_secret': self.app_secret,
                     'grant_type': self.grant_type, 'scope': self.scopes}

        if self.new == True:
            #ignore any saved token and simple get a new one
            self.post()
            logger.debug('%s %s %s %s', self.name, 'getting a new access_token',
                        self.persist_path, self.access_token)
        else:
            #get a saved access token if one exists
            try:
                #persist_path is set by the API super class
                self.access_token = pickle.load(open(self.persist_path, "rb"))
                logger.debug('%s %s %s %s', self.name, 'using a saved access_token',
                            self.persist_path,
                            self.access_token)
            except IOError:
                #otherwise get a new one - implicit save
                self.post()
                logger.debug('%s %s %s %s', self.name, 'no saved_access token, getting a new one',
                            self.persist_path, self.access_token)

    def __str__(self):
        return self.access_token

    def __repr__(self):
        return self

    def post(self):
        """Get an access_token - make an oAuth API request."""
        #a direct call to post will always fetch a new access_token
        self.response, self.content = http.request(self.url, 'POST', headers=self.headers,
                                                   body=urllib.urlencode(self.body))
        #using httplib2, force_exception_to_status_code True we don't get exceptions'
        self.status_code = int(self.response['status'])
        try:
            _content_dict = convert_json(self.content)

            if self.status_code == 200:
                self.access_token = _content_dict['access_token']
                #save the token
                pickle.dump(copy.deepcopy(self.access_token), open(self.persist_path, "wb"))
            else:
                logger.error('%s %s %s %s %s', self.name, 'status_code', self.status_code,
                             'content', self.content)
                self.access_token = None
        except ValueError, e:
            logger.error('%s %s %s %s %s %s %s', self.name, 'Error parsing JSON response',
                         'status_code', self.status_code, 'content', self.content, e)
            self.access_token = None
        return self.access_token

class SpeechToText(API):
    """Convert speech into text from a file or audio stream."""
    def __init__(self, audio_data, content_type, access_token, headers, url, producer):
        API.__init__(self)
        self.body = audio_data
        self.content_type = content_type
        self.access_token = access_token
        self.headers = headers
        self.url = url
        #worker thread producing bytes for this method to consume
        self.producer = producer
        self.response = None
        self.content = None
        self.recognition = None
        self.transcription = []
        self.number_of_transcriptions = 0
        self.bytes_transfer = 0
        self.audio_file = None
        self.headers = headers

        if LOGGING_LEVEL == logging.DEBUG:
            #for debug copy audio data to a local file for review
            self.audio_file = open(config.AUDIO_FILE_DEBUG_COPY, 'wb')

        if self.access_token is None:
            raise APIException('No access_token provided')

    def __str__(self):
        # Return a list of 1 or more transcriptions (or None)
        return str(self.transcription)

    def chunker(self, sz):
        #provide 512 byte or less chunks to the pycurl request with each call
        #pycurl calls this with sz but sz is os derived
        #producer is the thread feeding the queue
        chunk = None
        #cStringIO gives us a file write/read buffer
        chunk = cStringIO.StringIO()
        index = 0
        while True:
            try:
                val = self.body.popleft()
                chunk.write(val)
                self.bytes_transfer += 1
                index += 1
                if self.audio_file is not None:
                    #debug mode - capture data to file
                    self.audio_file.write(val)

                if index == config.MAX_CHUNK_SIZE:
                    time.sleep(.0001)
                    return chunk.getvalue()

            except IndexError:
                if self.producer.is_alive():
                    #capture is in progress, we may or may not have a bytes in a chunk
                    if chunk.getvalue() == '':
                        #chunk is empty, capture in progress, stream empty
                        #logger.debug('%s %s', self.name, 'chunk is empty, capture in progress, stream empty')
                        #time.sleep(.1)
                        continue
                    else:
                        #chunk has contents, capture in progress, stream empty
                        logger.debug('%s %s', self.name, 'chunk has contents, capture in progress, stream empty')
                        #time.sleep(.1)
                        continue
                else:
                    #capture thread has completed or stopped
                    if chunk.getvalue() == '':
                        #chunk is empty, capture has stopped, stream empty
                        logger.debug('%s %s', self.name, 'chunk is empty, capture has stopped, stream empty')
                        return ''
                    else:
                        #chunk has content, capture has stopped, stream empty
                        #logger.debug('%s %s -> %s', self.name, 'returning a chunk',
                        #             len(self.body))
                        time.sleep(.0001)
                        return chunk.getvalue()

    def post(self):
        """convert audio data to text"""
        #Watson Recognition object - JSON
        self.recognition = None
        #List of transcriptions
        self.transcription = []
        self.number_of_transcriptions = 0

        response = cStringIO.StringIO()
        response_headers = cStringIO.StringIO()

        #configure the API request using pycurl
        _curl = pycurl.Curl()
        _curl.setopt(_curl.POST, 1)
        _curl.setopt(_curl.URL, self.url)
        _curl.setopt(_curl.HEADERFUNCTION, response_headers.write)
        _curl.setopt(_curl.WRITEFUNCTION, response.write)
        #_curl.setopt(_curl.VERBOSE, 1)
        #_curl.setopt(_curl.TIMEOUT, 120)

        if type(self.body) is str:
            logger.debug('%s converting with a file', self.name)
            #non-streaming: instance was created with raw bytes
            if self.headers is None:
                self.headers = ['Authorization: Bearer ' + str(self.access_token),
                                'Content-Type: ' + self.content_type, 'Accept: application/json',
                                'Content-Language: en-US', 'X-SpeechContext: Generic',
                                'Content-Length: ' + str(len(self.body))]

            _curl.setopt(_curl.POSTFIELDS,  self.body)
            _curl.setopt(_curl.POSTFIELDSIZE, len(self.body))

            logger.debug('%s non-streaming _curl self.body len= %s', self.name, len(self.body))
        elif type(self.body) is deque:
            logger.debug('%s converting with a stream', self.name)
            #streaming: instance was created with a deque (fifo) - chunk max size = 512
            if self.headers is None:
                self.headers = ['Authorization: Bearer ' + str(self.access_token),
                                'Content-Type: ' + self.content_type, 'Accept: application/json',
                                'Content-Language: en-US', 'X-SpeechContext: Generic',
                                'Transfer-Encoding: chunked', 'Cache-Control: no-cache',
                                'Connection: Keep-Alive']
            _curl.setopt(_curl.READFUNCTION, self.chunker)
        else:
            s = str(self.name) + ' unknown body type ' + str(type(self.body))
            raise APIException(s)
        #best result or all results
        self.headers.append('X-Arg: HasMultipleNBest=false')

        logger.debug('%s Request headers= \n%s type of headers= %s', self.name, self.headers,
                     type(self.headers))

        _curl.setopt(_curl.HTTPHEADER, self.headers)

        _curl.perform()
        self.status_code = _curl.getinfo(_curl.HTTP_CODE)
        _curl.close()

        #this is raw curl response - format
        self.response_headers = response_headers
        self.response = response

        try:
            logger.debug('%s raw response value= \n%s', self.name, response.getvalue())
            logger.debug('%s raw header value = \n%s', self.name, response_headers.getvalue())

            self.content = convert_json(response.getvalue())

            if self.status_code == 200:
                self.recognition_status = self.content['Recognition']['Status']

                logger.debug('%s Recognition status = %s', self.name, self.recognition_status)

                #HTTP 200 OK is the only success response we expect
                self.recognition = self.content

                if self.recognition_status == 'OK':
                    self.number_of_transcriptions = len(
                        self.recognition['Recognition']['NBest'])

                    #construct a list of transcriptions
                    logger.info('%s Speech was recognized.', self.name)
                    for index in range(self.number_of_transcriptions):
                        self.transcription.append(
                            self.recognition['Recognition']['NBest'][index][
                                'ResultText'])
                else:
                    #speech is not recognized
                    logger.info('%s Speech was not recognized, please try again.', self.name)

            elif self.status_code == 400:
                #bad request
                logger.error('%s Bad Request: %s', self.status_code, self.content)
            elif self.status_code == 401:
                #Unauthorized
                logger.error('%s Unauthorized: %s', self.status_code, self.content)
            elif self.status_code == 403:
                #Forbidden
                logger.error('%s Forbidden: %s', self.status_code, self.content)
            elif self.status_code == 404:
                #Not found
                logger.error('%s Not found: %s', self.status_code, self.content)
            elif self.status_code == 405:
                #Method not supported
                logger.error('%s Method not supported: %s', self.status_code, self.content)
            elif self.status_code == 500:
                #Internal server error
                logger.error('%s Internal server error: %s', self.status_code, self.content)
            elif self.status_code == 503:
                #Service unavailable
                logger.error('%s Service unavailable: %s', self.status_code, self.content)
            else:
                logger.error('%s Error: %s', self.status_code, self.content)
                s = 'SpeechToText API: unknown HTTP status code'
                raise APIException(s)

        except ValueError, e:
            logger.error('%s %s %s %s %s %s', self.name, 'error parsing json', 'status_code',
                         self.status_code, self.response, e)
        except APIException, e:
            logger.error('APIException is %s %s', e, e.value)

        if self.audio_file is not None:
            self.audio_file.close()
        # Return a list of 0 or more transcriptions
        return self.transcription

class TextToSpeech(API):
    """Convert text into synthesized speech."""
    def __init__(self, text, accept, content_type, access_token, headers, url):
        """Convert text into speech."""
        API.__init__(self)

        self.body = text

        #do some error checking
        if not self.body:
            raise APIException('no text provided')

        #accept can be audio/amr, audio/amr-wb, audio/x-wav
        self.accept = accept
        accept_values = ['audio/amr', 'audio/amr-wb', 'audio/x-wav']
        if self.accept:
            if self.accept not in accept_values:
                s = 'accept header value: ' + self.accept + ' is not valid.'
                raise APIException(s)
        else:
            raise APIException('accept header not provided')

        self.content_type = content_type
        content_type_values = ['text/plain', 'application/ssml+xml']
        if self.content_type:
            if self.content_type not in content_type_values:
                raise APIException('content_type header value ' + str(self.content_type) + 'is not valid')
        else:
            raise APIException('accept header not provided')

        self.access_token = access_token
        if self.access_token is None:
            raise APIException('No access_token provided - None')

        self.url = url
        if self.url is None:
            raise APIException('No api URL provided')

        self.headers = headers

        if self.headers is None:
            #setup some default headers
            self.headers = config.HEADERS_TTS

            self.headers['Authorization'] = 'Bearer ' + str(self.access_token)
            self.headers['Content-Type'] = self.content_type
            self.headers['Accept'] = self.accept
        else:
            #explicitly set headers
            self.headers = headers

        self.response = None
        self.content = None

    def __str__(self):
        # Return a list of 1 or more transcriptions (or None)
        return str(self.body)

    def __repr__(self):
        API.__repr__()

    def __eq__(self, other):
        """Test the equality of two textToSpeech transactions."""
        _status = False

        if API.__eq__(self, other):
            #status_code and headers (except Authorization) match
            logger.debug('%s %s %s %s', self.name, 'self', 'content len', len(self.content))
            logger.debug('%s %s %s %s', self.name, 'other', 'content len', len(other.content))
            if len(self.content) == len(other.content):
                #content could be None for a negative case or some length if success
                _status = True

        return _status

    def __ne__(self, other):
        return not self.__eq__(other)

    def post(self):
        self.response, self.content = http.request(self.url, 'POST', headers=self.headers,
                                                   body=self.body)

        #we have disabled HTTP exceptions so we'll get all status codes in response here
        self.status_code = int(self.response['status'])
        if self.status_code == 200:
            # Return the binary response data
            return self.content
        else:
            #display the error response
            logger.error('%s status_code = %s content= %s', self.name, self.status_code,
                         self.content)
            return None

    def dumps(self):
        s = str(self.status_code) + str(self.headers) + str(self.body)
        return s

def main():
    """Get access token, play speech file, convert to text then text to synthesized speech"""
    logger.info('getting an access_token')
    oauth = AccessToken(url=config.URL_OAUTH, app_key=config.APP_KEY,
                        app_secret=config.APP_SECRET, scopes=config.APP_SCOPES,
                        grant_type=config.APP_GRANT_TYPE, new=False)
    #access_token = oauth.post()
    access_token = oauth.access_token

    logger.info('access_token= %s', access_token)

    if len(sys.argv) == 2:
        #file path in command line argument
        audio_file = sys.argv[1]
        audio_type = get_content_type(audio_file)
    else:
        #no arg so use a default audio file
        audio_file = config.AUDIO_FILE_DEFAULT
        audio_type = get_content_type(audio_file)

    #invoke a system command to play the source audio file
    os.system('aplay ' + audio_file)
    logger.info('speechToText with audio file= %s audio_type= %s', audio_file, audio_type)

    f = open(audio_file, 'rb')
    audio_data = f.read()
    f.close()

    stt = SpeechToText(audio_data=audio_data, content_type=audio_type, access_token=access_token,
                       headers=None, url=config.URL_SPEECH, producer=None)
    stt.post()

    logger.info('number of transcriptions= %s', stt.number_of_transcriptions)
    for index in range(stt.number_of_transcriptions):
        logger.info('transcription %s: %s', index, stt.transcription[index])

    #use the transcription as text input for textToSpeech API request
    say_this_text = 'You said. ' + stt.transcription[0]
    logger.info('say_this_text= %s', say_this_text)

    tts = TextToSpeech(text=say_this_text, accept='audio/x-wav', content_type='text/plain',
                       access_token=access_token, headers=None,
                       url=config.URL_TTS)

    audio_data = tts.post()
    tts_file = config.AUDIO_FILE_TTS
    f = open(tts_file, 'wb')
    f.write(audio_data)

    #invoke a system command to play the tts audio file
    os.system('aplay ' + tts_file)

if __name__ == "__main__":
    main()


