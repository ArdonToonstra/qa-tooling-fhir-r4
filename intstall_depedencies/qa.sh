#!/bin/bash

# 0.1 Load credentials from the config file
CONFIG_FILE="config.txt"

# 0.2 Check if the config file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# 0.3 Read the config file
# Source the config file to load variables
source "$CONFIG_FILE"

# 1. Check if .NET is installed
if ! command -v dotnet &> /dev/null; then
    echo ".NET could not be found. Please install the .NET SDK before running this script."
    exit 1
fi

# 2. Check .NET SDK version
DOTNET_VERSION=$(dotnet --version)
echo "Using .NET SDK version: $DOTNET_VERSION"

# 3. Install Firely.Terminal if not installed
if ! command -v fhir &> /dev/null; then
    echo "Firely Terminal is not installed. Installing now..."
    dotnet tool install --global Firely.Terminal --version 3.2.0
else
    echo "Firely Terminal is already installed."
fi

# 4. Check Firely Terminal version
FIRELY_TERMINAL_VERSION=$(fhir -v)
echo "Firely Terminal version: $FIRELY_TERMINAL_VERSION"

# 5. Simplifier login using environment variables
if [[ -z "$SIMPLIFIER_USERNAME" ]]; then
    echo "Simplifier username is not set. Please set SIMPLIFIER_USERNAME in config.txt or GitHub environment settings."
    exit 1
elif [[ -z "$SIMPLIFIER_PASSWORD" ]]; then
    echo "Simplifier password is not set. Please set SIMPLIFIER_PASSWORD in config.txt or GitHub environment settings."
    exit 1
else
    echo "Logging into Simplifier with Firely Terminal..."
    fhir login email="$SIMPLIFIER_USERNAME" password="$SIMPLIFIER_PASSWORD"
    if [[ $? -ne 0 ]]; then
        echo "Simplifier login failed. Please check credentials."
        exit 1
    else
        echo "Simplifier login successful."
    fi
fi

# Fill in the correct package name here!! 
echo "Installing the private dependency [package name]..."
fhir install example.package@1.0.0 --here --private
if [[ $? -ne 0 ]]; then
    echo "Failed to install [package name]. Please check the command or your access rights."
    exit 1
else
    echo "Successfully installed [package name]."
fi

# Start Docker Compose
docker-compose -f qa/docker-compose.yml up "$@"

# Optional: Add a pause equivalent for a shell script (if needed)
read -p "Press [Enter] key to continue..."
