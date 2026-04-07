import os
import eel
import datetime

from engine.features import *
from engine.command import *
from engine.auth import recoganize
def start():
    
    eel.init("www")

    playAssistantSound()
    @eel.expose
    def init():
        subprocess.call([r'device.bat'])
        eel.hideLoader()
        speak("Ready for Face Authentication")
        flag = recoganize.AuthenticateFace()
        if flag == 1:
            eel.hideFaceAuth()
            speak("Face Authentication Successful")
            eel.hideFaceAuthSuccess()
            
            # Time based greeting (Real-time data)
            hour = int(datetime.datetime.now().hour)
            if hour >= 5 and hour < 12:
                greeting = "Good Morning"
            elif hour >= 12 and hour < 16:
                greeting = "Good Midday"
            elif hour >= 16 and hour < 20:
                greeting = "Good Evening"
            else:
                greeting = "Good Night"
                
            speak(f"{greeting} Sushant boss, How can i Help You")
            eel.hideStart()
            playAssistantSound()
        else:
            speak("Face Authentication Fail")
    os.system('start msedge.exe --app="http://localhost:8000/index.html"')

    eel.start('index.html', mode=None, host='localhost', block=True)