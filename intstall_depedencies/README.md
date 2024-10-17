# Install dependencies example scripts

This folder contains example scripts that needs to be executed before the docker is runned so the validator gets all the depedencies.

## Contents

- `qa.bat`: Batch script for Windows to install dependencies and run the QA process.
- `qa.sh`: Shell script for Unix-based systems (Linux, macOS) to install dependencies and run the QA process.
- `config.txt`: Configuration file for storing sensitive information such as Simplifier credentials.

## Prerequisites

- .NET SDK installed on your machine.
- Access to a Simplifier account with credentials that allow for the installation of private packages.

## Installation

1. Copy the contents of this folder to your repo.
2. Create a config.txt file in the same directory as `qa.bat` and `qa.sh`.
3. Manually include private packages in the scripts based on a [package name]@[version] notation