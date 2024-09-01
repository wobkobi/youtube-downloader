@echo off
REM Change to the directory where the batch file is located
cd /d "%~dp0"

REM Check if the virtual environment directory exists
IF NOT EXIST "venv" (
    REM Create the virtual environment
    python -m venv venv

    REM Activate the virtual environment
    call venv\Scripts\activate

    REM Upgrade pip
    python -m pip install --upgrade pip

    REM Install dependencies from requirements.txt
    IF EXIST "requirements.txt" (
        pip install -r requirements.txt
    ) ELSE (
        echo No requirements.txt file found.
    )

    REM Deactivate the virtual environment after installing
    deactivate
) ELSE (
    REM Activate the virtual environment if it already exists
    call venv\Scripts\activate
)

REM Run the Python script
python yt.py

REM Deactivate the virtual environment after the script finishes
deactivate

pause
