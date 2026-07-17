# build_exe.py

import os
import subprocess
import sys

def build():
    print("========================================")
    print("       Building Saarthi Executable      ")
    print("========================================")
    
    # Check for PyInstaller inside the virtual environment first
    venv_pyinstaller = os.path.join(".venv", "Scripts", "pyinstaller.exe")
    if os.path.exists(venv_pyinstaller):
        pyinstaller_bin = venv_pyinstaller
    else:
        pyinstaller_bin = "pyinstaller"

    # Core PyInstaller command options:
    # --noconsole: Hide command-line window
    # --onefile: Pack everything into a single .exe
    # --name: Executable name
    cmd = [
        pyinstaller_bin,
        "--noconsole",
        "--onefile",
        "--name=Saarthi",
        "gui.py"
    ]
    
    print(f"Executing command: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd)
        print("\n[SUCCESS] Build successful!")
        print("Your standalone executable can be found at: dist/Saarthi.exe")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] PyInstaller compilation failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("\n[ERROR] PyInstaller is not installed or not in PATH.")
        print("Please install it in your environment using: pip install pyinstaller")
        sys.exit(1)

if __name__ == "__main__":
    build()
