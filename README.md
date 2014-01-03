raspberry_pi
============

Sample code and apps for the Raspberry Pi


Demonstration of AT&T's Speech APIs on the Raspberry Pi


API Platform
    You can access AT&T APIs by navigating to http://developer.att.com. Use a trial account or
    full membership to create an 'app' and get the app details you will need to use the APIs. You
     need app key and app secret (config.py). <!--

Demo Design:
    This code is offered without warranty and is provided for educational purposes. The Raspberry
    Pi is and interesting target that has garnered considerable interest and the goal that
    The Linux ALSA audio system (alsaaudio) captures data in chunks. The size of the chunks is
    determined by ALSA. AT&T's speech to text API in streaming mode expects chunks of data
    no greater than 512 bytes. An alsaaudio input is configured. A queue is configured. An audio
    capture thread is started which puts that data into the queue. A speechToText API thread is
    started that pulls data from the queue and streams to the API.
    The transcription is processed, action is taken, and text is converted to synthesized speech
    with the textToSpeech API and then played.
    Audio files (as opposed to microphone) may also be converted.
        speech.py provides API methods
        speechapp.py provides the demo app

Files Provided:
    config.py: default configuration of APIs and a few demo app constants.
    speech.py: python methods to call oauth and speech APIs
    speechapp.py: demo app that captures audio and uses oauth, speechToText, and textToSpeech
    utils.py: a few methods used by the other modules.
    media files: several sample wav files are provided.

How To Use The Demo Code:
    speech.py contains five classes and one method:
        AccessToken: Gets a new access token or restore a saved one.
        SpeechToText: Convert speech into text.
        TextToSpeech: Converts text into synthesized speech.
        APIException: Handles API exceptions.
        API: Base class for APIs.
        main(): Method that demonstrates:
            get access token
            play speech file
            convert that speech file into text
            convert that text into synthesized speech
            play the synthesized speech
        Command Line:
            python speech.py
                Using a default audio speech file, play it, convert to text,
                convert that text into synthesized speech and play that speech.
            python speech.py {audio file path}
                Provide an audio file, convert it to text, that text into synthesized
                speech and play that speech.
    speechapp.py Uses the API classes in speech.py to implement a simple demonstration app.
        contains three classes and six methods:
        audio_env(): Display the cards and mixers in the audio subsystem.
        audio_output(): Configure and provide an audio output for playback.
        audio_play() : Play audio on the specified audio output device.
        audio_input(): Provides an audio input - microphone capture.
        AudioCapture: Capture audio from a stream (deque) or file.
        SpeechToTextThread: Execute speech to text call in a thread.
        LEDThread: Control the PI onboard OK LED.
        transcription_processor(): Analyze the transcription and take action.
        Speechapp does not explicity set audio mixers/controls; it uses whatever settings are
        made in the environment. This is a good future optimization target.
        Command Line:
            python speechapp.py
                must run as root (GPIO control)
                get access token
                capture real time audio from microphone and stream to speechToText API
                get the transcription and act on it - example: control the LED
                based on the transcription get a speech response using textToSpeech API and play it
            python speechapp.py {your file}
                The above but source is file not microphone.
    config.py: API and program settings.
    utils.py: A few common methods.
    demo media files:
        static/updateStatus.wav
    generated files:
        static/speechToText.wav
        static/textToSpeech.wav
        static/capture_debug.wav

The PI:
    This demo code has been tested on a Raspberry Pi Model B Board w/NOOBS on a 8GB SD.
    Wi-Fi: WI-PI Setup:
        vi /etc/network/interfaces
            auto wlan0
            iface wlan0 inet dhcp
            wpa-ssid <name of your WiFi network> wpa-psk <password of your WiFi network>
        sudo /etc/init.d/networking restart
        ifconfig
    LED Control:
        The demo app uses one of the on board LEDs to provide visual feedback of "control".
        This article tells you how to control the green OK LED:
            http://www.raspberrypi.org/phpBB3/viewtopic.php?p=136266
    PI Specific Code:
        Hardware Specific:  Controlling the LEDs
        Removing the above and modifying audio system configuration should enable the code to run
         on most linux systems.

Packages you might need:
    Use apt-get or pip to install any needed packages.
    You may need to install:
        alsaaudio: a Python package for working with Linux ALSA audio subsystem.
            apt-get install python-alsaaudio
        RPi.GPIO: work with I/O - in this application the LEDs
        httplib2: used to make API requests
            pip install httplib2
        pycurl: used to make API requests
            apt-get python-pycurl

Useful Debugging Tools/Commands:
    Audio commands:
        interactive set up of audio subsystem: alsamixer
        store alsamixer with: alsactl store 1
        list card contents: amixer --card 1 contents
        list your capture devices: arecord -l
        reset the alsa system with: alsactl init
        play a wav file: aplay ./static/updateStatus.wav
        what sound cards do you have:
            cat /proc/asound/cards
    USB audio pi issue - read this!:
        ...
    pip: If you don't have pip then:
        apt-get install python-pip
    PI information:
        cat /proc/cpuinfo
        cat /proc/meminfo
        cat /proc/sys/kernel/hostname
        cat /proc/sys/kernel/ostype
        cat /proc/sys/kernel/osrelease
        cat /proc/sys/kernel/pid_max
        cat /proc/sys/kernel/poweroff_cmd
    Display USB devices:
        lsusb -t
        lsusb --verbose | less
    Find where your default packages are stored:
        python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())"

    Running Your App at Startup:
        Add a command line to /etc/rc.local for example 'python speechapp.py'















