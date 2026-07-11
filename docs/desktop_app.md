# Laundrex Desktop (PySide6)

This desktop wrapper starts the Django server and loads the UI inside a PySide6 window.

## Install dependencies

```powershell
C:/Users/LENOVO/Desktop/laundrex/.venv/Scripts/python.exe -m pip install -r requirements.txt
```

## Run (development)

```powershell
C:/Users/LENOVO/Desktop/laundrex/.venv/Scripts/python.exe desktop_app/run_desktop.py
```

## Run with external server
Start Django yourself, then:

```powershell
C:/Users/LENOVO/Desktop/laundrex/.venv/Scripts/python.exe desktop_app/run_desktop.py --no-server
```

## Build (Windows)
Install PyInstaller and build a single executable:

```powershell
C:/Users/LENOVO/Desktop/laundrex/.venv/Scripts/python.exe -m pip install pyinstaller
C:/Users/LENOVO/Desktop/laundrex/.venv/Scripts/python.exe -m pyinstaller --noconfirm --windowed --name LaundrexDesktop --icon static/assets/favicon.ico desktop_app/run_desktop.py
```

The output will be in the dist folder.
