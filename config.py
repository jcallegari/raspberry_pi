__author__ = 'jrc'
import os

#Application Detail - Put Your App Info Here
APP_SCOPES = 'SPEECH,STTC,TTS'
APP_KEY = 'xiprzvi7s0kg5lhb0kqybkm92cqy805q'
APP_SECRET = 'migubmxi0gk9ebgiodkuo46a6xvsquis'
#APP_KEY = 'your app key here'
#APP_SECRET = 'your app secret here'
APP_GRANT_TYPE = 'client_credentials'

#API URLs
URL_OAUTH = 'https://api.att.com/oauth/token'
URL_SPEECH = 'https://api.att.com/speech/v3/speechToText'
URL_STTC = 'https://api.att.com/speech/v4/speechToTextCustom'
URL_TTS = 'https://api.att.com/speech/v3/textToSpeech'

#Default API Headers
HEADERS_OAUTH = {'Content-type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}
HEADERS_SPEECH = {'Authorization': 'Bearer ', 'Accept': 'application/json',
                  'X-SpeechContext': 'Generic'}
HEADERS_TTS = {'Authorization': 'Bearer ', 'Content-Type': 'text/plain', 'Accept': 'audio/x-wav',
               'Content-Language': 'en-US', 'X-Arg': 'VoiceName=crystal, Volume=250, Tempo--1'}
SPEECH_CONTEXTS = ['BusinessSearch', 'Gaming', 'Generic', 'QuestionAndAnswer', 'SMS', 'SocialMedia',
                   'TV', 'VoiceMail', 'WebSearch']
LANGUAGE_SUPPORT = {'en-US': ['BusinessSearch', 'Gaming', 'Generic', 'QuestionAndAnswer', 'SMS',
                              'SocialMedia', 'TV', 'VoiceMail', 'WebSearch'],
                    'es-US': ['BusinessSearch', 'Gaming', 'Generic', 'QuestionAndAnswer', 'SMS',
                              'SocialMedia', 'TV', 'VoiceMail', 'WebSearch'],
                    'en-US_es-US': ['VoiceMail', 'VoiceMailAuto']}

#Streaming Chunk Size
MAX_CHUNK_SIZE = 512

#Default audio files
AUDIO_FILE_DEFAULT = 'static' + os.sep + 'updateStatus.wav'
#generated debug files
AUDIO_FILE_DEBUG_COPY = 'static' + os.sep + 'speechToText.wav'
AUDIO_FILE_TTS = 'static' + os.sep + 'textToSpeech.wav'
#copy of captured audio data
AUDIO_FILE_CAPTURE = 'static' + os.sep + 'capture_debug.wav'

def main():
    pass

if __name__ == "__main__":
    main()
