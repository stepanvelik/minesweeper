@echo off
rem Сборка Сапёра в Saper.exe с иконкой (запускать на Windows)
py -m pip install --upgrade pygame pyinstaller
py -m PyInstaller --noconfirm --onefile --windowed --icon assets\icon.ico --name Saper minesweeper.py
echo.
echo Done: dist\Saper.exe  (положи рядом папку assets, чтобы была иконка окна)
pause
