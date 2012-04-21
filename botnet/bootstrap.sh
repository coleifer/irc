#!/bin/bash
apt-get update
apt-get install -y git-core libevent-dev python-dev python-setuptools
easy_install pip
pip install gevent
git clone https://github.com/coleifer/irc.git /root/irc
cd /root/irc/
python setup.py install
cd /root/irc/botnet/
python worker.py %(worker_options)s
