import speech_recognition as sr
import pyaudio

def test_microphones():
    print("\n--- Microphone Diagnostic ---\n")
    
    # 1. Check PyAudio Devices
    p = pyaudio.PyAudio()
    print("Available Audio Devices (PyAudio):")
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            print(f"Index {i}: {p.get_device_info_by_host_api_device_index(0, i).get('name')}")
    
    print("\n--- Testing Speech Recognition ---")
    
    # 2. Test SpeechRecognition
    r = sr.Recognizer()
    print("Microphones detected by SpeechRecognition:")
    mics = sr.Microphone.list_microphone_names()
    for index, name in enumerate(mics):
        print(f"Index {index}: {name}")

    print("\nAttempting to listen from default microphone for 3 seconds...")
    try:
        with sr.Microphone() as source:
            print("Listening... (Speak now!)")
            r.adjust_for_ambient_noise(source, duration=1)
            audio = r.listen(source, timeout=5, phrase_time_limit=5)
            print("Recognizing...")
            query = r.recognize_google(audio, language='en-in')
            print(f"Success! I heard: '{query}'")
    except sr.WaitTimeoutError:
        print("Error: Listening timed out. No speech detected.")
    except sr.UnknownValueError:
        print("Error: Could not understand the audio.")
    except sr.RequestError as e:
        print(f"Error: Could not request results from Google; {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    p.terminate()

if __name__ == "__main__":
    test_microphones()
