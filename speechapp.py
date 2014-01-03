__author__ = 'jrc'
import time
import threading
import math
from collections import deque
import logging
import audioop
import alsaaudio
import RPi.GPIO as GPIO
import config
from speech import AccessToken, SpeechToText, TextToSpeech
from utils import get_content_type
import sys

#audio constants
SAMPLE_RATE = 16000
SAMPLE_BITS = 16
CHANNELS = 1
SAMPLE_BYTES = SAMPLE_BITS / 8
CAPTURE_AUDIO_TYPE = 'audio/raw;coding=linear;rate=16000;byteorder=LE'
FRAME_SIZE = CHANNELS * SAMPLE_BYTES
PERIOD_SIZE = 320
SLEEP_TIME = (SAMPLE_RATE / PERIOD_SIZE / 1000.0)
LOW_THRESHOLD = 2000
HIGH_THRESHOLD = 32000
low_threshold_log = math.log(LOW_THRESHOLD)
high_threshold_log = math.log(HIGH_THRESHOLD)
#audio output devices
HDMI_AUDIO = False
YETI_MIC = False
#led control constants
LED_NORM = .5
LED_BLINK_ON_TIME = .1
LED_FREQUENCY_DEFAULT = 0.5
LED_FREQUENCY_MAX = 8.0
LED_FREQUENCY_MIN = 0.5
LED_FREQUENCY_INCREMENT = 1.0

USE_DAEMON = False

#logging
LOGGING_LEVEL = logging.DEBUG
PRINT_AUDIO_LEVELS = False
logger = logging.getLogger('speechapp')
logger.setLevel(LOGGING_LEVEL)
fh = logging.FileHandler('speechapp')
fh.setLevel(LOGGING_LEVEL)
ch = logging.StreamHandler()
ch.setLevel(LOGGING_LEVEL)
formatter = logging.Formatter('%(asctime)s - %(levelname)s:%(name)s: %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
logger.addHandler(ch)
logger.addHandler(fh)

def audio_env():
    """Display the cards and mixers in the audio subsystem."""
    list_of_cards = alsaaudio.cards()
    num_cards = len(list_of_cards)

    logger.debug('audio_env %s %s %s', num_cards, ' cards found: ', list_of_cards)
    logger.debug('audio_env %s %s', 'mixers =', alsaaudio.mixers() )

    for index in range(num_cards):
        logger.debug('audio_env %s %s %s %s', 'card =', list_of_cards[index], 'mixer =', alsaaudio
        .mixers(
            index))

def audio_output():
    """Configure and provide an audio output for playback."""
    #this is hardware dependent
    if HDMI_AUDIO:
        card = 'ALSA'
    else:
        card = 'Device'
    output = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK, card=card)
    output.setchannels(CHANNELS)
    output.setrate(SAMPLE_RATE)
    output.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    #period size controls the internal number of frames per period.
    output.setperiodsize(PERIOD_SIZE)
    return output

def audio_play(audio_output, audio_data):
    """Play audio on the specified audio output device."""
    #audio_play(audio_output(), audio_dat
    audio_output.write(audio_data)

def audio_input():
    """Provide an audio input - microphone capture"""

    if YETI_MIC:
        card = 'Microphone'
    else:
        card = 'Device'

    #get the microphone input device
    input = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NONBLOCK, card)

    #get the microphone mixer
    mixer = alsaaudio.Mixer(control='Mic', id=0, cardindex=1)

    mixer_config = {}

    #name of the sound card used by this Mixer object
    mixer_config['card_name'] = mixer.cardname()

    #name of the specific mixer controlled by this object
    mixer_config['name'] = mixer.mixer()

    #ID of the ALSA mixer controlled by this object.
    mixer_config['id'] = mixer.mixerid()

    #list of the switches which are defined by this specific mixer
    mixer_config['switch_cap'] = mixer.switchcap()

    #list of the volume control capabilities of this mixer.
    mixer_config['volume_cap'] = mixer.volumecap()

    #For enumerated controls, return the currently selected item and the list of items available
    mixer_config['controls'] = mixer.getenum()

    #list indicating the current mute setting for each channel.
    #0 means not muted, 1 means muted.
    mixer_config['mute_settings'] = mixer.getmute()

    #volume range of the ALSA mixer controlled by this object.
    mixer_config['volume_range_capture'] = mixer.getrange('capture')
    mixer_config['volume_range_playback'] = mixer.getrange('playback')

    #list indicating the current record mute setting for each channel.
    #0 means not recording, 1 means recording
    mixer_config['record_mute_settings'] = mixer.getrec()

    #list with the current volume settings for each channel.
    #The list elements are integer percentages.
    mixer_config['volume_capture'] = mixer.getvolume('capture')
    mixer_config['volume_playback'] = mixer.getvolume('playback')

    #tuple of (file descriptor, eventmask) that can be used to
    #wait for changes on the mixer with select.poll.
    mixer_config['polldescriptors'] = mixer.polldescriptors()

    #TODO audio settings are from env not explicitly set
    #Change the current volume settings for this mixer.
    #The volume argument controls the new volume setting as an integer percentage
    #set each ch to 70%
    #_mixer.setvolume(70, 0, 'capture')
    #_mixer.setvolume(70, 1, 'capture')
    #Sets the mute flag to a new value. The mute argument is either 0 for not muted, or 1 for muted.
    #un-mute ch's 0 and 1
    #_mixer.setmute(0, 0)
    #_mixer.setmute(0, 1)
    #_mixer.setmute(0)
    ##Sets the capture mute flag to a new value. The capture argument is either
    ##0 for no capture, or 1 for capture.
    ##_mixer.setrec(1, 0)
    ##_mixer.setrec(1, 1)
    #_mixer.setrec(1)
    #logger.debug('%s', mixer_config)

    input.setchannels(CHANNELS)
    input.setrate(SAMPLE_RATE)
    input.setformat(alsaaudio.PCM_FORMAT_S16_LE)

    # The period size controls the internal number of frames per period.
    # The significance of this parameter is documented in the ALSA api.
    # For our purposes, it is suficcient to know that reads from the device
    # will return this many frames. Each frame being 2 bytes long.
    # This means that the reads below will return either 320 bytes of data
    # or 0 bytes of data. The latter is possible because we are in nonblocking
    # mode.
    #    PCM.read()
    #In PCM_NORMAL mode, this function blocks until a full period is available,
    # and then returns a tuple (length,data) where length is the number of frames of captured data,
    # and data is the captured sound frames as a string.
    # The length of the returned data will be periodsize*framesize bytes.
    #
    #In PCM_NONBLOCK mode, the call will not block, but will return (0,'')
    # if no new period has become available since the last call to read.
    #inp.setperiodsize(160)
    input.setperiodsize(PERIOD_SIZE)

    return input

class AudioCapture(threading.Thread):
    """Capture audio from a stream (deque) or file."""

    def __init__(self, audio_stream):
        """The audio source can be a thread safe fifo (deque) or a file path"""
        threading.Thread.__init__(self, name="AudioCapture")
        self.finished = threading.Event()
        self.chunk_counter = 0
        self.volume = 0.0
        self.volume_threshold = 1.0
        #self.silence_chunk_threshold = 8
        self.silence_chunk_threshold = 10
        self.silence_chunk_counter = 0
        self.silence_detected = False
        self.input = None
        self.is_file_input = False

        if type(audio_stream) is deque:
            #a deque is used as a thread safe fifo between capture and streaming api
            self.audio_stream = audio_stream
            logger.debug('%s creating thread with a deque', self.name)
        elif type(audio_stream) is str:
            logger.debug('%s creating thread with a file path %s', self.name, audio_stream)

            try:
                f = open(audio_stream, 'rb')
                self.audio_stream =f.read()
                f.close()
                self.is_file_input = True

                if LOGGING_LEVEL == logging.DEBUG:
                    #copy the audio to a local file for debug
                    fp = open(config.AUDIO_FILE_CAPTURE, 'wb')
                    fp.write(self.audio_stream)
                    fp.close()

                logger.debug('%s audio_stream path= %s len of file= %s', self.name, audio_stream,
                             len(self.audio_stream))
            except IOError as e:
                logger.error('%s File does not exist at %s \n%s', self.name, audio_stream,
                             e.message)
                self.audio_stream = None
        else:
            logger.debug('%s error unexpected type= %s', self.name, type(audio_stream))
            self.audio_stream = None

    def run(self):
        """The audio_stream may be raw bytes from a file or a fifo (deque)"""
        logger.debug('%s %s', self.name, 'audio capture thread started')

        if self.is_file_input:
            #type(self.audio_stream) is str:
            #non-streaming: file data has been read into audio_stream
            logger.debug('%s %s', self.name, 'thread was created with an audio file')
            pass
        else:
            #streaming: captures audio data into fifo until silence is detected
            logger.debug('%s %s', self.name, 'thread was created with a deque')
            #an audio_stream deque has been provided for microphone audio capture
            if PRINT_AUDIO_LEVELS:
                #prints a table of audio volume in sample
                print 'peak_volume_in_sample,volume_unit,current_volume'

            fp = None
            if LOGGING_LEVEL == logging.DEBUG:
                #copy the audio_stream to a local file for debug
                fp = open(config.AUDIO_FILE_CAPTURE, 'wb')

            self.input = audio_input()

            silence_bytes = 0
            #add audio frames to the audio_stream until capture has completed
            while not self.finished.isSet():
                #each frame is 2 bytes so 2 * 16000/sec = 32K bytes per sec
                #ALSA returns 'n' bytes based on driver interrupt cycle
                #e.g. chunk sizes of 341  would be 682 bytes in each fetch
                number_of_frames, audio_data = self.input.read()
                audio_data_length = len(audio_data)
                if number_of_frames:
                    peak_volume_in_sample = audioop.max(audio_data, 2)
                    volume_unit = (math.log(
                        float(max(peak_volume_in_sample, 1))) - low_threshold_log) / (
                                  high_threshold_log - low_threshold_log)
                    current_volume = min(max((volume_unit * 10), 0), 10)

                    if PRINT_AUDIO_LEVELS:
                        print str(peak_volume_in_sample) + ',' + str(volume_unit) + ',' + str(
                            current_volume)

                    if self.chunk_counter == 0:
                        #haven't processed any chunks yet
                        if current_volume < self.volume_threshold:
                            #capture just started and no audio detected
                            if current_volume != 0:
                                #there is some audio but it's below threshold
                                logger.debug('%s %s %s %s', self.name, 'audio below threshold',
                                             current_volume, self.volume_threshold)
                                #get another chunk from audio subsystem
                            continue
                    else:
                        #we have already acquired at least one period size worth of data
                        if self.chunk_counter > 0 and self.volume == 0:
                            #last period was silence - inc the silence count
                            self.silence_chunk_counter += 1
                            silence_bytes += audio_data_length
                        else:
                            #last period was not silent - reset the silence count
                            self.silence_chunk_counter = 0
                            silence_bytes = 0

                    if self.silence_chunk_counter >= self.silence_chunk_threshold:
                        #silence has been detected
                        logger.debug('%s %s', self.name, 'silence detected - capture done')
                        try:
                            #remove the silence chunks that we had detected
                            for i in range(1, self.silence_chunk_threshold):
                                #remove silence chunks deque
                                self.silence_detected = True
                                #pop removes newest data popleft removes oldest
                                #logger.debug('%s silence bytes= %s', self.name, silence_bytes)
                                #todo remove silence from end
                                #for index in range(silence_bytes):
                                #    self.audio_stream.pop()
                        except IndexError:
                            pass
                            #silence was detected so we have completed the audio capture
                        break
                        #actively capturing audio - capture current volume for next sample
                    self.volume = float(current_volume)
                    #count the number of chunks we have read
                    self.chunk_counter += 1

                    #need to add bytes to audio_stream not chunks
                    if fp is not None:
                        #debug mode only: copy the bytes we write to the fifo to a file
                        fp.write(audio_data)

                    for index in range(audio_data_length):
                        self.audio_stream.append(audio_data[index])

                time.sleep(.001)
            if fp is not None:
                fp.close()

    def stop(self):
        """Stop the thread gracefully."""
        self.finished.set()
        self.join()

class SpeechToTextThread(threading.Thread):
    """Execute speech to text call in a thread."""
    def __init__(self, audio_stream, access_token, audio_type, producer):
        threading.Thread.__init__(self, name="SpeechToTextThread")
        self.finished = threading.Event()
        self.access_token = access_token
        self.audio_type = audio_type
        self.producer = producer
        self.api = None
        self.audio_stream = audio_stream
        self.chunk_counter = 0

    def run(self):
        logger.debug('%s SpeechToTextThread started with %s', self.name, type(self.audio_stream))

        self.api = SpeechToText(audio_data=self.audio_stream, content_type=self.audio_type,
                                    access_token=self.access_token, headers=None,
                                    url=config.URL_SPEECH, producer=self.producer)
        self.api.post()

    def stop (self):
        self.finished.set()
        self.join()

class LEDThread(threading.Thread):
    """Control the PI onboard OK LED."""
    def __init__(self):
        threading.Thread.__init__(self, name="LEDThread")
        self.pause = False
        self.finished = threading.Event()

        self.frequency = LED_FREQUENCY_DEFAULT
        self.blink_on_time = float(LED_BLINK_ON_TIME)
        self.period = 1 / float(self.frequency)
        self.blink_off_time = float(self.period - self.blink_on_time)
        self.mode = 'blink'

        # Needs to be BCM. GPIO.BOARD lets you address GPIO ports by periperal
        # connector pin number, and the LED GPIO isn't on the connector
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        # set up GPIO output channel
        GPIO.setup(16, GPIO.OUT)
        # On
        GPIO.output(16, GPIO.LOW)
        # Off
        GPIO.output(16, GPIO.HIGH)

    def run(self):

        while not self.finished.isSet():
            if self.mode == 'blink':
                self.period = 1 / float(self.frequency)
                self.blink_off_time = self.period - self.blink_on_time
                if self.blink_off_time < 0:
                    logger.debug('off time < 0 - mode %s off_time %s on time is %s period is '
                                 '%s', self.mode,
                                 self.blink_off_time, self.blink_on_time, self.period)
                    self.blink_off_time = 0.0

                # On
                GPIO.output(16, GPIO.LOW)
                time.sleep(self.blink_on_time)
                # Off
                GPIO.output(16, GPIO.HIGH)
                time.sleep(self.blink_off_time)

            elif self.mode == 'on':
                # On
                GPIO.output(16, GPIO.LOW)
                #adding a sleep here toggles the led
                #time.sleep(.5)
            elif self.mode == 'off':
                # Off
                GPIO.output(16, GPIO.HIGH)
                time.sleep(.5)

        GPIO.cleanup()

    def stop(self):
        self.finished.set()
        self.join()
        GPIO.cleanup()

    def blink(self):
        self.mode = 'blink'

    def on(self):
        self.mode = 'on'

    def off(self):
        self.mode = 'off'

    def set_frequency(self, freq):
        self.frequency = float(freq)

        if self.frequency > LED_FREQUENCY_MAX:
            self.frequency = LED_FREQUENCY_MAX

        if self.frequency < LED_FREQUENCY_MIN:
            self.frequency = LED_FREQUENCY_MIN

        self.period = 1 / self.frequency

        logger.debug('frequency= %s, period= %s, mode= %s, on time=%s, off time= %s',
                     self.frequency, self.period, self.mode, self.blink_on_time,
                     self.blink_off_time)

    def set_on_time(self, t):
        if t < 0:
            self.blink_on_time = 0.0
        elif t >= self.period:
            self.blink_on_time = self.period

    def faster(self):
        self.set_frequency(self.frequency + LED_FREQUENCY_INCREMENT)

    def slower(self):
        self.set_frequency(self.frequency - LED_FREQUENCY_INCREMENT)

    def fastest(self):
        self.set_frequency(LED_FREQUENCY_MAX)

    def slowest(self):
        self.set_frequency(LED_FREQUENCY_MIN)

    def normal(self):
        self.set_frequency(LED_FREQUENCY_DEFAULT)

def transcription_processor(transcription, target):
    """Analyze the transcription and take action."""
    command_string = str(transcription)
    led = target
    result = ''
    if command_string.find('turn on') != -1:
        led.on()
        result = 'thank you for turning me on'
    elif command_string.find('turn off') != -1:
        led.off()
        result = 'i am sorry you are turning me off'
    elif command_string.find('flash') != -1:
        led.blink()
        result = 'i will blink now'
    elif command_string.find('faster') != -1:
        led.faster()
        result = 'speeding up'
    elif command_string.find('slower')!= -1:
        led.slower()
        result = 'slowing down'
    elif command_string.find('stop') != -1:
        led.stop()
        result = 'good bye'
    elif command_string.find('maximum') != -1:
        led.fastest()
        result = 'this is as fast as i can go'
    elif command_string.find('minimum') != -1:
        led.slowest()
        result = 'going as slow as i can'
    elif command_string.find('frequency') != -1:
        #next word should be frequency selection
        result = 'setting frequency'
    else:
        result = None
    return result

def main():
    """Demo: Get access_token, capture audio, convert to text, act on text, play response."""
    try:
        logger.info('\n')
        #for demo we will control an on board PI led - visible feedback
        led = LEDThread()
        led.start()
        logger.info('LED control thread has started')

        oauth = AccessToken(url=config.URL_OAUTH, app_key=config.APP_KEY,
                                    app_secret=config.APP_SECRET, scopes=config.APP_SCOPES,
                                    grant_type=config.APP_GRANT_TYPE, new=False)

        access_token = oauth.access_token

        #simple loop on keyboard entry - replace with command line args, external stimuli, etc.
        while True:
            c = raw_input('--> enter any key to start audio capture (q to quit): ')
            logger.info('--> %s', c)
            if c == 'q':
                led.stop()
                exit()
            audio_stream = deque()
            audio_capture = None
            audio_type = CAPTURE_AUDIO_TYPE

            file_provided = False
            if len(sys.argv) == 2:
                #a file was provided on the command line
                file_provided = True
                #for illustration purpose using our capture thread with a file
                logger.info('audio_stream is a file')
                #audio_stream = 'static' + os.sep + 'homeBy6.wav'
                audio_stream = sys.argv[1]
                audio_type = get_content_type(audio_stream)

                audio_capture = AudioCapture(audio_stream)
                audio_capture.daemon = USE_DAEMON
                audio_capture.start()
                audio_capture.join()
                audio_stream = audio_capture.audio_stream
            else:
                logger.info('audio stream is audio input')
                #setup and start audio capture thread
                audio_capture = AudioCapture(audio_stream)
                audio_capture.daemon = USE_DAEMON
                audio_capture.start()
                logger.info('\n\nJ------------------------ > SPEAK NOW <-------------------')


            speechToText_thread = SpeechToTextThread(audio_stream=audio_stream,
                                                     access_token=access_token,
                                                     audio_type=audio_type, producer=audio_capture)
            speechToText_thread.daemon = USE_DAEMON
            speechToText_thread.start()

            #wait for speechToText_thread to complete
            speechToText_thread.join(timeout=240)

            transcription = speechToText_thread.api.transcription
            logger.info('transcription=  %s', transcription)

            interactive = transcription_processor(str(transcription), led)

            if interactive is None:
                logger.info('command unknown or silence')
                interactive = 'I do not understand the command'
            else:
                logger.info('command is known: %s', interactive)

            #convert command response text to speech and play it
            tts = TextToSpeech(interactive, 'audio/x-wav', 'text/plain', access_token, None,
                               config.URL_TTS)
            #tts.headers['X-Arg: VoiceName'] = 'Mike'
            #tts.headers['X-Arg: Tempo'] = 0
            audio_data = tts.post()
            audio_play(audio_output(), audio_data)
            if file_provided:
                raise Exception


    except Exception:
        if audio_capture.isAlive():
            audio_capture.stop()

        if speechToText_thread.isAlive():
            speechToText_thread.stop()

        if led.isAlive():
            led.stop()

if __name__ == "__main__":
    main()
    exit(0)




