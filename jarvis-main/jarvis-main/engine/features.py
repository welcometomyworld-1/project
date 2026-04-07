import json
import os
try:
    from shlex import quote
except ImportError:
    from pipes import quote
import re
import sqlite3
import struct
import subprocess
import time
import webbrowser
from playsound import playsound
import eel
import pyaudio
import pyautogui
from engine.command import speak
from engine.config import ASSISTANT_NAME, LLM_KEY
# Playing assiatnt sound function
import pywhatkit as kit
import pvporcupine

from engine.helper import extract_yt_term, markdown_to_text, remove_words
from hugchat import hugchat

con = sqlite3.connect("jarvis.db")
cursor = con.cursor()

@eel.expose
def playAssistantSound():
    music_dir = "www\\assets\\audio\\start_sound.mp3"
    playsound(music_dir)

    
def openCommand(query):
    query = query.replace(ASSISTANT_NAME, "")
    query = query.replace("open", "")
    query = query.lower().strip()

    if query != "":
        try:
            # 1. Try DB for system commands
            cursor.execute('SELECT path FROM sys_command WHERE LOWER(name) = ?', (query,))
            results = cursor.fetchall()

            if results:
                speak(f"Opening {query}")
                os.startfile(results[0][0])
                return

            # 2. Try DB for web commands
            cursor.execute('SELECT url FROM web_command WHERE LOWER(name) = ?', (query,))
            results = cursor.fetchall()
            
            if results:
                speak(f"Opening {query}")
                webbrowser.open(results[0][0])
                return

            # 3. Direct logic for common apps if not in DB
            if "chrome" in query:
                speak("Opening Google Chrome")
                os.system("start chrome")
                return
            elif "edge" in query:
                speak("Opening Microsoft Edge")
                os.system("start msedge")
                return
            elif "notepad" in query:
                speak("Opening Notepad")
                os.system("start notepad")
                return
            elif "calculator" in query:
                speak("Opening Calculator")
                os.system("start calc")
                return

            # 4. Final attempt: start command
            speak(f"Opening {query}")
            os.system(f'start {query}')
            
        except Exception as e:
            print(f"Error in openCommand: {e}")
            speak(f"I couldn't find {query} on your laptop.")

def PlayYoutube(query):
    search_term = extract_yt_term(query)
    speak("Playing "+search_term+" on YouTube")
    kit.playonyt(search_term)

def hotword():
    porcupine=None
    paud=None
    audio_stream=None
    try:
        porcupine=pvporcupine.create(keywords=["jarvis","alexa"]) 
        paud=pyaudio.PyAudio()
        audio_stream=paud.open(rate=porcupine.sample_rate,channels=1,format=pyaudio.paInt16,input=True,frames_per_buffer=porcupine.frame_length)
        print("Jarvis is listening for hotword...")
        while True:
            try:
                keyword=audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
                keyword=struct.unpack_from("h"*porcupine.frame_length,keyword)
                keyword_index=porcupine.process(keyword)
                if keyword_index>=0:
                    print("Hotword detected!")
                    import pyautogui as autogui
                    autogui.keyDown("win")
                    autogui.press("j")
                    time.sleep(1)
                    autogui.keyUp("win")
            except IOError:
                continue
    except Exception as e:
        print(f"Hotword Error: {e}")
    finally:
        if porcupine: porcupine.delete()
        if audio_stream: audio_stream.close()
        if paud: paud.terminate()

def findContact(query):
    words_to_remove = [ASSISTANT_NAME, 'make', 'a', 'to', 'phone', 'call', 'send', 'message', 'wahtsapp', 'video']
    query = remove_words(query, words_to_remove)
    try:
        query = query.strip().lower()
        cursor.execute("SELECT mobile_no FROM contacts WHERE LOWER(name) LIKE ? OR LOWER(name) LIKE ?", ('%' + query + '%', query + '%'))
        results = cursor.fetchall()
        mobile_number_str = str(results[0][0])
        if not mobile_number_str.startswith('+91'):
            mobile_number_str = '+91' + mobile_number_str
        return mobile_number_str, query
    except:
        speak('not exist in contacts')
        return 0, 0

def whatsApp(mobile_no, message, flag, name):
    if flag == 'message':
        target_tab = 12
        jarvis_message = "message send successfully to "+name
    elif flag == 'call':
        target_tab = 7
        message = ''
        jarvis_message = "calling to "+name
    else:
        target_tab = 6
        message = ''
        jarvis_message = "staring video call with "+name
    encoded_message = quote(message)
    whatsapp_url = f"whatsapp://send?phone={mobile_no}&text={encoded_message}"
    full_command = f'start "" "{whatsapp_url}"'
    subprocess.run(full_command, shell=True)
    time.sleep(5)
    subprocess.run(full_command, shell=True)
    pyautogui.hotkey('ctrl', 'f')
    for i in range(1, target_tab):
        pyautogui.hotkey('tab')
    pyautogui.hotkey('enter')
    speak(jarvis_message)

def chatBot(query):
    user_input = query.lower()
    chatbot = hugchat.ChatBot(cookie_path=r"engine\cookies.json")
    id = chatbot.new_conversation()
    chatbot.change_conversation(id)
    response =  chatbot.chat(user_input)
    speak(response)
    return response

def makeCall(name, mobileNo):
    mobileNo =mobileNo.replace(" ", "")
    speak("Calling "+name)
    command = 'adb shell am start -a android.intent.action.CALL -d tel:'+mobileNo
    os.system(command)

def sendMessage(message, mobileNo, name):
    from engine.helper import replace_spaces_with_percent_s, goback, keyEvent, tapEvents, adbInput
    message = replace_spaces_with_percent_s(message)
    mobileNo = replace_spaces_with_percent_s(mobileNo)
    speak("sending message")
    goback(4)
    time.sleep(1)
    keyEvent(3)
    tapEvents(136, 2220)
    tapEvents(819, 2192)
    adbInput(mobileNo)
    tapEvents(601, 574)
    tapEvents(390, 2270)
    adbInput(message)
    tapEvents(957, 1397)
    speak("message send successfully to "+name)

import google.generativeai as genai
import datetime
import psutil

@eel.expose
def get_time():
    time_now = datetime.datetime.now().strftime("%I:%M %p")
    speak(f"Sushant Boss, the time is {time_now}", voice_type="female")
    return time_now

@eel.expose
def get_date():
    date_now = datetime.datetime.now().strftime("%A, %d %B %Y")
    speak(f"Sushant Boss, today is {date_now}", voice_type="female")
    return date_now

@eel.expose
def get_battery():
    battery = psutil.sensors_battery()
    if battery:
        percentage = battery.percent
        msg = f"Sushant Boss, the system is at {percentage} percent battery"
        if battery.power_plugged:
            msg += " and it is currently charging"
        else:
            msg += " and it is not charging"
        speak(msg, voice_type="female")
        return percentage
    else:
        speak("Sushant Boss, I couldn't detect the battery status", voice_type="female")
        return None

@eel.expose
def google_search(query):
    query = query.replace(ASSISTANT_NAME, "")
    query = query.replace("search on google", "")
    query = query.replace("google search", "")
    query = query.replace("search", "")
    search_query = query.strip()
    if search_query:
        speak(f"Sushant Boss, searching for {search_query} on Google", voice_type="female")
        webbrowser.open(f"https://www.google.com/search?q={search_query}")
    else:
        speak("Sushant Boss, what do you want to search for?", voice_type="female")

@eel.expose
def take_screenshot():
    speak("Sushant Boss, taking screenshot", voice_type="female")
    path = os.path.join(os.environ['USERPROFILE'], 'Pictures', f'screenshot_{int(time.time())}.png')
    pyautogui.screenshot(path)
    speak(f"Sushant Boss, screenshot saved to your Pictures folder", voice_type="female")

# --- VOLUME CONTROL ---
@eel.expose
def volume_up():
    pyautogui.press("volumeup")
    speak("Sushant Boss, volume increased", voice_type="female")

@eel.expose
def volume_down():
    pyautogui.press("volumedown")
    speak("Sushant Boss, volume decreased", voice_type="female")

@eel.expose
def volume_mute():
    pyautogui.press("volumemute")
    speak("Sushant Boss, volume toggled", voice_type="female")

@eel.expose
def tell_joke():
    import requests
    try:
        res = requests.get("https://official-joke-api.appspot.com/random_joke").json()
        joke = f"{res['setup']} ... {res['punchline']}"
        speak(f"Sushant Boss, here is a joke for you: {joke}", voice_type="female")
    except:
        speak("Sushant Boss, why did the computer go to the doctor? Because it had a virus!", voice_type="female")

@eel.expose
def weather_info(city="mumbai"):
    speak(f"Sushant Boss, I don't have a weather API key yet, but it looks like a great day in {city}!", voice_type="female")

@eel.expose
def laptop_brightness(query):
    import screen_brightness_control as sbc
    try:
        current_brightness = sbc.get_brightness()[0]
        if "increase" in query or "up" in query:
            new_brightness = min(100, current_brightness + 20)
            sbc.set_brightness(new_brightness)
            speak(f"Sushant Boss, brightness increased to {new_brightness} percent", voice_type="female")
        elif "decrease" in query or "down" in query:
            new_brightness = max(0, current_brightness - 20)
            sbc.set_brightness(new_brightness)
            speak(f"Sushant Boss, brightness decreased to {new_brightness} percent", voice_type="female")
        else:
            import re
            numbers = re.findall(r'\d+', query)
            if numbers:
                level = int(numbers[0])
                sbc.set_brightness(level)
                speak(f"Sushant Boss, brightness set to {level} percent", voice_type="female")
            else:
                speak("Sushant Boss, how much brightness should I set?", voice_type="female")
    except Exception as e:
        print(f"Brightness Error: {e}")
        speak("Sushant Boss, I'm sorry, I couldn't control the brightness on this device.", voice_type="female")

@eel.expose
def minimize_windows():
    speak("Sushant Boss, minimizing all windows", voice_type="female")
    pyautogui.hotkey('win', 'd')

@eel.expose
def close_window():
    speak("Sushant Boss, closing the current window", voice_type="female")
    pyautogui.hotkey('alt', 'f4')

@eel.expose
def open_app(app_name):
    apps = {
        "chrome": "start chrome",
        "edge": "start msedge",
        "firefox": "start firefox",
        "notepad": "notepad",
        "word": "start winword",
        "excel": "start excel",
        "powerpoint": "start powerpnt",
        "vscode": "code",
        "cmd": "start cmd",
        "powershell": "start powershell",
        "task manager": "taskmgr",
        "control panel": "control",
        "settings": "start ms-settings:",
    }
    app_name = app_name.lower().strip()
    if app_name in apps:
        speak(f"Sushant Boss, opening {app_name}", voice_type="female")
        os.system(apps[app_name])
    else:
        openCommand(app_name)

@eel.expose
def open_website(site_name):
    sites = {
        "google": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "github": "https://github.com",
        "linkedin": "https://linkedin.com",
        "gmail": "https://mail.google.com",
    }
    site_name = site_name.lower().strip()
    if site_name in sites:
        speak(f"Sushant Boss, opening {site_name}", voice_type="female")
        webbrowser.open(sites[site_name])
    else:
        speak(f"Sushant Boss, searching for {site_name} on Google", voice_type="female")
        webbrowser.open(f"https://www.google.com/search?q={site_name}")

@eel.expose
def jarvis_system_info():
    import platform
    battery = psutil.sensors_battery().percent if psutil.sensors_battery() else "Unknown"
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    info = f"Sushant Boss, your system is running on {platform.system()}. Battery is at {battery} percent. CPU usage is {cpu} percent, and RAM usage is {ram} percent."
    speak(info, voice_type="female")

@eel.expose
def send_whatsapp(number, message):
    import pywhatkit
    speak(f"Sushant Boss, sending WhatsApp message to {number}", voice_type="female")
    pywhatkit.sendwhatmsg_instantly(f"+91{number}", message)

@eel.expose
def system_control(command):
    if "shutdown" in command:
        speak("Sushant Boss, shutting down the system in 5 seconds", voice_type="female")
        os.system("shutdown /s /t 5")
    elif "restart" in command:
        speak("Sushant Boss, restarting the system in 5 seconds", voice_type="female")
        os.system("shutdown /r /t 5")
    elif "log off" in command:
        speak("Sushant Boss, logging off", voice_type="female")
        os.system("shutdown /l")
    elif "lock" in command:
        speak("Sushant Boss, locking the workstation", voice_type="female")
        os.system("rundll32.exe user32.dll,LockWorkStation")
    elif "sleep" in command:
        speak("Sushant Boss, putting the system to sleep", voice_type="female")
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    elif "hibernate" in command:
        speak("Sushant Boss, hibernating the system", voice_type="female")
        os.system("shutdown /h")

@eel.expose
def open_folder(folder_name):
    folders = {
        "downloads": "explorer shell:Downloads",
        "documents": "explorer shell:Documents",
        "desktop": "explorer shell:Desktop",
        "pictures": "explorer shell:Pictures",
        "videos": "explorer shell:Videos",
        "music": "explorer shell:Music",
        "this pc": "explorer shell:MyComputerFolder",
    }
    folder_name = folder_name.lower().strip()
    if folder_name in folders:
        speak(f"Sushant Boss, opening {folder_name}", voice_type="female")
        os.system(folders[folder_name])

@eel.expose
def media_control(action):
    if "play" in action or "pause" in action:
        pyautogui.press("playpause")
    elif "next" in action:
        pyautogui.press("nexttrack")
    elif "previous" in action:
        pyautogui.press("prevtrack")

@eel.expose
def type_text(text):
    pyautogui.write(text)

@eel.expose
def press_enter():
    pyautogui.press("enter")

@eel.expose
def close_app(app_name):
    app_map = {
        "chrome": "chrome.exe",
        "vscode": "Code.exe",
        "notepad": "notepad.exe",
    }
    app_name = app_name.lower().strip()
    if app_name in app_map:
        speak(f"Sushant Boss, closing {app_name}", voice_type="female")
        os.system(f"taskkill /f /im {app_map[app_name]}")

@eel.expose
def open_camera():
    import cv2
    speak("Sushant Boss, opening camera", voice_type="female")
    cap = cv2.VideoCapture(0)
    while True:
        ret, img = cap.read()
        cv2.imshow('Jarvis Camera', img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()

def geminai(query):
    try:
        query = query.replace(ASSISTANT_NAME, "")
        query = query.replace("search", "")
        genai.configure(api_key=LLM_KEY)
        model = genai.GenerativeModel(
            model_name="gemini-flash-latest",
            system_instruction="You are Jarvis, a highly advanced AI assistant developed by Digambar. "
                               "Your user is Sushant Boss. ALWAYS start your responses "
                               "by addressing him as 'Sushant Boss'. "
                               "You understand both Hindi and English. If the user speaks in Hindi, "
                               "respond in Hindi. If in English, respond in English. "
                               "If in Hinglish, respond in Hinglish. "
                               "You can perform system tasks like opening apps, searching Google/YouTube, "
                               "taking screenshots, controlling volume, and telling time/date. "
                               "Always keep responses helpful, polite, and very concise."
        )
        response = model.generate_content(query)
        if response.text:
            filter_text = markdown_to_text(response.text)
            # AI uses male voice
            speak(filter_text, voice_type="male")
        else:
            speak("Sushant Boss, I'm sorry, I couldn't generate a response.", voice_type="female")
    except Exception as e:
        print("Error in Gemini:", e)
        speak("Sushant Boss, there was an error with the AI engine.", voice_type="female")

@eel.expose
def assistantName():
    return ASSISTANT_NAME

@eel.expose
def personalInfo():
    try:
        cursor.execute("SELECT * FROM info")
        results = cursor.fetchall()
        jsonArr = json.dumps(results[0])
        eel.getData(jsonArr)
        return 1    
    except:
        print("no data")

@eel.expose
def updatePersonalInfo(name, designation, mobileno, email, city):
    cursor.execute("SELECT COUNT(*) FROM info")
    count = cursor.fetchone()[0]
    if count > 0:
        cursor.execute('''UPDATE info SET name=?, designation=?, mobileno=?, email=?, city=?''', (name, designation, mobileno, email, city))
    else:
        cursor.execute('''INSERT INTO info (name, designation, mobileno, email, city) VALUES (?, ?, ?, ?, ?)''', (name, designation, mobileno, email, city))
    con.commit()
    personalInfo()
    return 1

@eel.expose
def displaySysCommand():
    cursor.execute("SELECT * FROM sys_command")
    results = cursor.fetchall()
    jsonArr = json.dumps(results)
    eel.displaySysCommand(jsonArr)
    return 1

@eel.expose
def deleteSysCommand(id):
    cursor.execute("DELETE FROM sys_command WHERE id = ?", (id,))
    con.commit()

@eel.expose
def addSysCommand(key, value):
    cursor.execute('''INSERT INTO sys_command VALUES (?, ?, ?)''', (None,key, value))
    con.commit()

@eel.expose
def displayWebCommand():
    cursor.execute("SELECT * FROM web_command")
    results = cursor.fetchall()
    jsonArr = json.dumps(results)
    eel.displayWebCommand(jsonArr)
    return 1

@eel.expose
def addWebCommand(key, value):
    cursor.execute('''INSERT INTO web_command VALUES (?, ?, ?)''', (None, key, value))
    con.commit()

@eel.expose
def deleteWebCommand(id):
    cursor.execute("DELETE FROM web_command WHERE Id = ?", (id,))
    con.commit()

@eel.expose
def displayPhoneBookCommand():
    cursor.execute("SELECT * FROM contacts")
    results = cursor.fetchall()
    jsonArr = json.dumps(results)
    eel.displayPhoneBookCommand(jsonArr)
    return 1

@eel.expose
def deletePhoneBookCommand(id):
    cursor.execute("DELETE FROM contacts WHERE Id = ?", (id,))
    con.commit()

@eel.expose
def InsertContacts(Name, MobileNo, Email, City):
    cursor.execute('''INSERT INTO contacts VALUES (?, ?, ?, ?, ?)''', (None,Name, MobileNo, Email, City))
    con.commit()
