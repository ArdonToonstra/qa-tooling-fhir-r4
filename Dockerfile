# 20.04 is the last usable LTS release, as Firely Terminal currently requires a .Net Core version which is not
# supported on Ubuntu 22.04
FROM ubuntu:20.04
RUN apt-get update && apt-get -y upgrade
RUN apt-get -y install wget
RUN apt-get -y install openjdk-11-jre-headless
RUN apt-get -y install git
RUN apt-get -y install python3 python3-yaml python3-requests python3-aiohttp

# Needed for setting tzdata, which is a dependency down the line
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections
RUN apt-get -y install tzdata

RUN apt-get -y install mitmproxy

RUN wget https://packages.microsoft.com/config/ubuntu/20.04/packages-microsoft-prod.deb && dpkg -i packages-microsoft-prod.deb && rm packages-microsoft-prod.deb
RUN apt-get update && apt-get -y install apt-transport-https && apt-get -y install dotnet-sdk-3.1 

RUN mkdir /tools
RUN mkdir /input

RUN mkdir tools/validator
RUN wget -nv https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar -O /tools/validator/validator.jar
RUN java -jar /tools/validator/validator.jar -version 4.0 -ig nictiz.fhir.nl.r4.profilingguidelines -tx 'n/a' | cat

RUN dotnet tool install -g --version 2.0.0 firely.terminal
RUN ~/.dotnet/tools/fhir install hl7.fhir.r4.core 4.0.1
RUN ~/.dotnet/tools/fhir install nictiz.fhir.nl.r4.profilingguidelines

RUN git clone -b v0.17 --depth 1 https://github.com/pieter-edelman-nictiz/hl7-fhir-validator-action /tools/hl7-fhir-validator-action

COPY entrypoint.py /entrypoint.py
COPY CombinedTX /tools/CombinedTX
COPY server /server
ENTRYPOINT ["python3", "entrypoint.py"]
