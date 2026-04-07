import pyttsx3
import speech_recognition as sr
import eel
import time
import os
from gtts import gTTS
from playsound import playsound
from langdetect import detect

def speak(text, voice_type="male"):
    text = str(text)
    print(f"Jarvis: {text}")
    eel.DisplayMessage(text)
    eel.receiverText(text)

    try:
        # Detect language
        try:
            lang = detect(text)
        except:
            lang = 'en'
        
        # Use gTTS for realistic voice if online, else fallback to pyttsx3
        if lang == 'hi' or voice_type == "female":
            tts = gTTS(text=text, lang=lang)
            temp_file = "temp_voice.mp3"
            tts.save(temp_file)
            playsound(temp_file)
            os.remove(temp_file)
        else:
            engine = pyttsx3.init('sapi5')
            voices = engine.getProperty('voices')
            # 0 for male, 1 for female (if available)
            voice_index = 0 if voice_type == "male" else 1
            if voice_index < len(voices):
                engine.setProperty('voice', voices[voice_index].id)
            engine.setProperty('rate', 174)
            engine.say(text)
            engine.runAndWait()
    except Exception as e:
        print(f"Speak Error: {e}")
        # Final fallback to basic pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()

def takecommand():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print('Listening....')
        eel.DisplayMessage('Listening....')
        r.pause_threshold = 1
        r.non_speaking_duration = 0.5
        r.energy_threshold = 300 
        
        try:
            r.adjust_for_ambient_noise(source, duration=1)
            audio = r.listen(source, timeout=10, phrase_time_limit=6)
        except sr.WaitTimeoutError:
            return ""
        except Exception as e:
            print(f"Error while listening: {e}")
            return ""

    try:
        print('Recognizing...')
        eel.DisplayMessage('Recognizing....')
        # Support for Hindi + English (Hinglish)
        query = r.recognize_google(audio, language='hi-IN')
        print(f"User said: {query}")
        eel.DisplayMessage(query)
        time.sleep(1)
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        print(f"Request Error: {e}")
        return ""
    except Exception as e:
        return ""
    
    return query.lower()

@eel.expose
def allCommands(message=1):

    if message == 1:
        query = takecommand()
        print(query)
        eel.senderText(query)
    else:
        query = message
        eel.senderText(query)
    try:
        if "open" in query:
            from engine.features import open_app, open_folder, open_website
            if "downloads" in query or "documents" in query or "desktop" in query or "pictures" in query or "videos" in query or "music" in query or "this pc" in query:
                folder = query.replace("open", "").strip()
                open_folder(folder)
            elif "google" in query or "youtube" in query or "github" in query or "linkedin" in query or "gmail" in query:
                site = query.replace("open", "").strip()
                open_website(site)
            else:
                app = query.replace("open", "").strip()
                open_app(app)
        elif "on youtube" in query:
            from engine.features import PlayYoutube
            PlayYoutube(query)
        elif "time" in query:
            from engine.features import get_time
            get_time()
        elif "date" in query:
            from engine.features import get_date
            get_date()
        elif "battery" in query or "cpu" in query or "ram" in query or "system info" in query:
            from engine.features import jarvis_system_info
            jarvis_system_info()
        elif "google" in query:
            from engine.features import google_search
            google_search(query)
        elif "screenshot" in query:
            from engine.features import take_screenshot
            take_screenshot()
        elif "volume up" in query:
            from engine.features import volume_up
            volume_up()
        elif "volume down" in query:
            from engine.features import volume_down
            volume_down()
        elif "mute" in query:
            from engine.features import volume_mute
            volume_mute()
        elif "joke" in query:
            from engine.features import tell_joke
            tell_joke()
        elif "shutdown" in query or "restart" in query or "log off" in query or "lock" in query or "sleep" in query or "hibernate" in query:
            from engine.features import system_control
            system_control(query)
        elif "weather" in query:
            from engine.features import weather_info
            weather_info()
        elif "brightness" in query:
            from engine.features import laptop_brightness
            laptop_brightness(query)
        elif "minimize" in query:
            from engine.features import minimize_windows
            minimize_windows()
        elif "close" in query:
            if "window" in query:
                from engine.features import close_window
                close_window()
            else:
                from engine.features import close_app
                app = query.replace("close", "").strip()
                close_app(app)
        elif "play" in query or "pause" in query or "next" in query or "previous" in query:
            from engine.features import media_control
            media_control(query)
        elif "type" in query:
            from engine.features import type_text
            text = query.replace("type", "").strip()
            type_text(text)
        elif "press enter" in query:
            from engine.features import press_enter
            press_enter()
        elif "camera" in query:
            from engine.features import open_camera
            open_camera()
        elif "whatsapp" in query:
            from engine.features import send_whatsapp
            speak("Sushant Boss, please tell the phone number")
            num = takecommand()
            speak("What is the message?")
            msg = takecommand()
            send_whatsapp(num, msg)
        elif "send message" in query or "phone call" in query or "video call" in query:
            from engine.features import findContact, whatsApp, makeCall, sendMessage
            contact_no, name = findContact(query)
            if(contact_no != 0):
                speak("Which mode you want to use whatsapp or mobile")
                preferance = takecommand()
                print(preferance)

                if "mobile" in preferance:
                    if "send message" in query or "send sms" in query: 
                        speak("what message to send")
                        message = takecommand()
                        sendMessage(message, contact_no, name)
                    elif "phone call" in query:
                        makeCall(name, contact_no)
                    else:
                        speak("please try again")
                elif "whatsapp" in preferance:
                    message = ""
                    if "send message" in query:
                        message = 'message'
                        speak("what message to send")
                        query = takecommand()
                                        
                    elif "phone call" in query:
                        message = 'call'
                    else:
                        message = 'video call'
                                        
                    whatsApp(contact_no, query, message, name)

        else:
            from engine.features import geminai
            geminai(query)
    except:
        print("error")
    
    eel.ShowHood()