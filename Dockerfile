FROM ubuntu:22.04

ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

ENV DEBIAN_FRONTEND=noninteractive

RUN  apt-get update && apt-get install -y \
    clang \
    curl \
    git \
    vim \
    build-essential \
    libffi-dev \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    software-properties-common \
    vim


RUN add-apt-repository ppa:deadsnakes/ppa -y

RUN apt install python3.9-dev -y

RUN apt install -y python3-pip \
    python3.9-distutils

RUN python3.9 -m pip install --upgrade pip

RUN python3.9 --version

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.9 1
RUN update-alternatives --set python /usr/bin/python3.9



