@echo off

REM 0.1 Load credentials from the config file
setlocal enabledelayedexpansion
set CONFIG_FILE=config.txt

REM 0.2 Check if the config file exists
if not exist "%CONFIG_FILE%" (
    echo "Configuration file not found: %CONFIG_FILE%"
    exit /b 1
)

REM 0.3 Read the config file
for /f "tokens=1,2 delims==" %%a in (%CONFIG_FILE%) do (
    set %%a=%%b
)

REM 1. Check if .NET is installed
where dotnet >nul 2>nul
if %errorlevel% neq 0 (
    echo ".NET could not be found. Please install the .NET SDK before running this script."
    exit /b 1
)

REM 2. Check .NET SDK version
for /f "delims=" %%i in ('dotnet --version') do set DOTNET_VERSION=%%i
echo Using .NET SDK version: %DOTNET_VERSION%

REM 3. Install Firely.Terminal if not installed
where fhir >nul 2>nul
if %errorlevel% neq 0 (
    echo "Firely Terminal is not installed. Installing now..."
    dotnet tool install --global Firely.Terminal --version 3.2.0
) else (
    echo "Firely Terminal is already installed."
)

REM 4. Check Firely Terminal version
for /f "delims=" %%i in ('fhir -v') do set FIRELY_TERMINAL_VERSION=%%i
echo Firely Terminal version: %FIRELY_TERMINAL_VERSION%

REM 5. Simplifier login using environment variables
if "%SIMPLIFIER_USERNAME%"=="" (
    echo "Simplifier username is not set. Please set SIMPLIFIER_USERNAME in config.txt or GitHub environment settings."
    exit /b 1
) else if "%SIMPLIFIER_PASSWORD%"=="" (
    echo "Simplifier password is not set. Please set SIMPLIFIER_PASSWORD in config.txt or GitHub environment settings.."
    exit /b 1
) else (
    echo Logging into Simplifier with Firely Terminal...
    fhir login email=%SIMPLIFIER_USERNAME% password=%SIMPLIFIER_PASSWORD%
    if %errorlevel% neq 0 (
        echo "Simplifier login failed. Please check credentials."
        exit /b 1
    ) else (
        echo "Simplifier login successful."
    )
)

echo Installing the private dependency [package name]...
fhir install example.package@1.0.0 --here --private
if %errorlevel% neq 0 (
    echo "Failed to install [package name]. Please check the command or your access rights."
    exit /b 1
) else (
    echo "Successfully installed [package name]."
)

docker-compose -f qa/docker-compose.yml up %*

pause

