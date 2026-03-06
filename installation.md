# Installation Guide for AH Control

Official setup instructions for AH Control.

Last updated: 2026-03-06

## Requirements
- Python 3.14 or higher (currently tested on 3.14)
- `pip`
- `git`
- Operating system: macOS, Linux, or Windows

## 1. Clone the Repository
```bash
git clone https://github.com/Project-for-Accessible-Radio-Telescopes/ah-control.git
cd ah-control
```

## 2. Create and Activate a Virtual Environment
Using a virtual environment is strongly recommended.

macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

Windows PowerShell:
```powershell
py -m venv venv
venv\Scripts\Activate.ps1
```

Windows CMD:
```cmd
py -m venv venv
venv\Scripts\activate.bat
```

## 3. Install Python Dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

All required packages are listed in the [requirements.txt](requirements.txt) file.

## 4. SDR Driver/Library Setup (RTL-SDR)
AH Control can run without live SDR capture features, but core recording features (to operate the telescope) require associated libraries. If you want to operate the telescope with AH Control, you will need to follow the steps below.

### Windows
- Install an RTL-SDR USB driver (commonly with Zadig/WinUSB).
- If needed, use precompiled binaries from the pyrtlsdr release page:
  - https://github.com/roger-/pyrtlsdr/releases
- Ensure `rtlsdr.dll` is available on your `PATH` or in the same directory as the Python executable.

### macOS
Install the native RTL-SDR library first:
```bash
brew install librtlsdr
```

If Homebrew is not installed, install it first, then run the command above.

### Linux (Debian/Ubuntu)
```bash
sudo apt update
sudo apt install -y rtl-sdr librtlsdr-dev
```

You may also need udev permission rules for non-root SDR access depending on your distro. To verify the library import works, run: 
```
python -c "from rtlsdr import RtlSdr; print('pyrtlsdr import OK')"
```

## 5. Run the Application
From the project root:
```bash
python main.py
```

## 6. Quick Verification
If startup is successful, a GUI window should appear and logs should include the exact lines: 
```
Application started successfully
Login time: [date] [time]
AH version: [version]
User: [username]
OS: [os name and version]
Python: [python version]
Working directory: /path/to/ah-control
Welcome to the AH Control v[version]!
```

## Troubleshooting
- `ModuleNotFoundError`: ensure the virtual environment is activated and rerun `pip install -r requirements.txt`.
- SDR import/runtime errors: verify native RTL-SDR libraries are installed for your OS.
- On macOS/Linux, make sure you run with `python` from the active venv.
- For any issues not mentioned here, feel free to ask a question on the discussion or open an issue on GitHub. You can also contact the PART team directly at [inquiries.part@gmail.com.](mailto:inquiries.part@gmail.com).

## Updating
To pull latest changes and refresh dependencies:
```bash
git pull
pip install -r requirements.txt
```