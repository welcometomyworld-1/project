 

import multiprocessing
import subprocess
import sys
import os

# To run Jarvis
def startJarvis():
        # Code for process 1
        print("Process 1: Jarvis Main UI is starting...")
        from main import start
        start()

# To run hotword
def listenHotword():
        # Code for process 2
        print("Process 2: Listening for Hotword (Jarvis/Alexa)...")
        from engine.features import hotword
        hotword()


    # Start both processes
if __name__ == '__main__':
        # Check if running in virtual environment
        # Only relaunch if we are the main entry point and not in venv
        if not hasattr(sys, 'real_prefix') and not (sys.base_prefix != sys.prefix):
            print("\nWARNING: You are NOT running in a virtual environment!")
            venv_python = os.path.join(os.getcwd(), "venv310", "Scripts", "python.exe")
            if os.path.exists(venv_python):
                print(f"Relaunching using virtual environment: {venv_python}...\n")
                subprocess.run([venv_python] + sys.argv)
                sys.exit()
            else:
                print("Error: Virtual environment 'venv310' not found. Please run: py -3.10 -m venv venv310 and install requirements.\n")
                sys.exit()

        p1 = multiprocessing.Process(target=startJarvis)
        p2 = multiprocessing.Process(target=listenHotword)
        p1.start()
        p2.start()
        p1.join()

        if p2.is_alive():
            p2.terminate()
            p2.join()

        print("system stop")