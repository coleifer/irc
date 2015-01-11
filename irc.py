import logging
import os
import random
import re
import sys
import time

try:
    from gevent import socket
except ImportError:
    import socket

from logging.handlers import RotatingFileHandler
from optparse import OptionParser


class IRCConnection(object):
    """\
    Connection class for connecting to IRC servers
    """
    # a couple handy regexes for reading text
    nick_re = re.compile('.*?Nickname is already in use')
    nick_change_re = re.compile(':(?P<old_nick>.*?)!\S+\s+?NICK\s+:\s*(?P<new_nick>[-\w]+)')
    ping_re = re.compile('^PING (?P<payload>.*)')
    chanmsg_re = re.compile(':(?P<nick>.*?)!\S+\s+?PRIVMSG\s+(?P<channel>#+[-\w]+)\s+:(?P<message>[^\n\r]+)')
    privmsg_re = re.compile(':(?P<nick>.*?)!~\S+\s+?PRIVMSG\s+[^#][^:]+:(?P<message>[^\n\r]+)')
    part_re = re.compile(':(?P<nick>.*?)!\S+\s+?PART\s+(?P<channel>#+[-\w]+)')
    join_re = re.compile(':(?P<nick>.*?)!\S+\s+?JOIN\s+.*?(?P<channel>#+[-\w]+)')
    quit_re = re.compile(':(?P<nick>.*?)!\S+\s+?QUIT\s+.*')
    registered_re = re.compile(':(?P<server>.*?)\s+(?:376|422)')

    # mapping for logging verbosity
    verbosity_map = {
        0: logging.ERROR,
        1: logging.INFO,
        2: logging.DEBUG,
    }

    def __init__(self, server, port, nick, password=None, logfile=None, verbosity=1, needs_registration=True):
        self.server = server
        self.port = port
        self.nick = self.base_nick = nick
        self.password = password

        self.logfile = logfile
        self.verbosity = verbosity

        self._registered = not needs_registration
        self._out_buffer = []
        self._callbacks = []
        self.logger = self.get_logger('ircconnection.logger', self.logfile)

    def get_logger(self, logger_name, filename):
        log = logging.getLogger(logger_name)
        log.setLevel(self.verbosity_map.get(self.verbosity, logging.INFO))

        if self.logfile:
            handler = RotatingFileHandler(filename, maxBytes=1024*1024, backupCount=2)
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            log.addHandler(handler)

        if self.verbosity == 2 or not self.logfile:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            log.addHandler(stream_handler)

        return log

    def send(self, data, force=False):
        """\
        Send raw data over the wire if connection is registered. Otherewise,
        save the data to an output buffer for transmission later on.
        If the force flag is true, always send data, regardless of
        registration status.
        """
        if self._registered or force:
            self._sock_file.write('%s\r\n' % data)
            self._sock_file.flush()
        else:
            self._out_buffer.append(data)

    def connect(self):
        """\
        Connect to the IRC server using the nickname
        """
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._sock.connect((self.server, self.port))
        except socket.error:
            self.logger.error('Unable to connect to %s on port %d' % (self.server, self.port), exc_info=1)
            return False

        self._sock_file = self._sock.makefile()
        if self.password:
            self.set_password()
        self.register_nick()
        self.register()
        return True

    def close(self):
        self._sock.close()

    def set_password(self):
        self.logger.info('Setting password')
        self.send('PASS %s' % self.password, True)

    def register_nick(self):
        self.logger.info('Registering nick %s' % self.nick)
        self.send('NICK %s' % self.nick, True)

    def register(self):
        self.logger.info('Authing as %s' % self.nick)
        self.send('USER %s %s bla :%s' % (self.nick, self.server, self.nick), True)

    def join(self, channel):
        if not channel.startswith('#'):
            channel = '#%s' % channel
        self.send('JOIN %s' % channel)
        self.logger.debug('joining %s' % channel)

    def part(self, channel):
        if not channel.startswith('#'):
            channel = '#%s' % channel
        self.send('PART %s' % channel)
        self.logger.debug('leaving %s' % channel)

    def respond(self, message, channel=None, nick=None):
        """\
        Multipurpose method for sending responses to channel or via message to
        a single user
        """
        if channel:
            if not channel.startswith('#'):
                channel = '#%s' % channel
            self.send('PRIVMSG %s :%s' % (channel, message))
        elif nick:
            self.send('PRIVMSG %s :%s' % (nick, message))

    def dispatch_patterns(self):
        """\
        Low-level dispatching of socket data based on regex matching, in general
        handles

        * In event a nickname is taken, registers under a different one
        * Responds to periodic PING messages from server
        * Dispatches to registered callbacks when
            - any user leaves or enters a room currently connected to
            - a channel message is observed
            - a private message is received
        """
        return (
            (self.nick_re, self.new_nick),
            (self.nick_change_re, self.handle_nick_change),
            (self.ping_re, self.handle_ping),
            (self.part_re, self.handle_part),
            (self.join_re, self.handle_join),
            (self.quit_re, self.handle_quit),
            (self.chanmsg_re, self.handle_channel_message),
            (self.privmsg_re, self.handle_private_message),
            (self.registered_re, self.handle_registered),
        )

    def register_callbacks(self, callbacks):
        """\
        Hook for registering custom callbacks for dispatch patterns
        """
        self._callbacks.extend(callbacks)

    def new_nick(self):
        """\
        Generates a new nickname based on original nickname followed by a
        random number
        """
        old = self.nick
        self.nick = '%s_%s' % (self.base_nick, random.randint(1, 1000))
        self.logger.warn('Nick %s already taken, trying %s' % (old, self.nick))
        self.register_nick()
        self.handle_nick_change(old, self.nick)

    def handle_nick_change(self, old_nick, new_nick):
        for pattern, callback in self._callbacks:
            if pattern.match('/nick'):
                callback(old_nick, '/nick', new_nick)

    def handle_ping(self, payload):
        """\
        Respond to periodic PING messages from server
        """
        self.logger.info('server ping: %s' % payload)
        self.send('PONG %s' % payload, True)

    def handle_registered(self, server):
        """\
        When the connection to the server is registered, send all pending
        data.
        """
        if not self._registered:
            self.logger.info('Registered')
            self._registered = True
            for data in self._out_buffer:
                self.send(data)
            self._out_buffer = []

    def handle_part(self, nick, channel):
        for pattern, callback in self._callbacks:
            if pattern.match('/part'):
                callback(nick, '/part', channel)

    def handle_join(self, nick, channel):
        for pattern, callback in self._callbacks:
            if pattern.match('/join'):
                callback(nick, '/join', channel)

    def handle_quit(self, nick):
        for pattern, callback in self._callbacks:
            if pattern.match('/quit'):
                callback(nick, '/quit', None)

    def _process_command(self, nick, message, channel):
        results = []

        for pattern, callback in self._callbacks:
            match = pattern.match(message) or pattern.match('/privmsg')
            if match:
                results.append(callback(nick, message, channel, **match.groupdict()))

        return results

    def handle_channel_message(self, nick, channel, message):
        for result in self._process_command(nick, message, channel):
            if result:
                self.respond(result, channel=channel)

    def handle_private_message(self, nick, message):
        for result in self._process_command(nick, message, None):
            if result:
                self.respond(result, nick=nick)

    def enter_event_loop(self):
        """\
        Main loop of the IRCConnection - reads from the socket and dispatches
        based on regex matching
        """
        patterns = self.dispatch_patterns()
        self.logger.debug('entering receive loop')

        while 1:
            try:
                data = self._sock_file.readline()
            except socket.error:
                data = None

            if not data:
                self.logger.info('server closed connection')
                self.close()
                return True

            data = data.rstrip()

            for pattern, callback in patterns:
                match = pattern.match(data)
                if match:
                    callback(**match.groupdict())


class IRCBot(object):
    """\
    A class that interacts with the IRCConnection class to provide a simple way
    of registering callbacks and scripting IRC interactions
    """
    def __init__(self, conn):
        self.conn = conn

        # register callbacks with the connection
        self.register_callbacks()

    def register_callbacks(self):
        """\
        Hook for registering callbacks with connection -- handled by __init__()
        """
        self.conn.register_callbacks((
            (re.compile(pattern), callback) \
                for pattern, callback in self.command_patterns()
        ))

    def _ping_decorator(self, func):
        def inner(nick, message, channel, **kwargs):
            message = re.sub('^%s[:,\s]\s*' % self.conn.nick, '', message)
            return func(nick, message, channel, **kwargs)
        return inner

    def is_ping(self, message):
        return re.match('^%s[:,\s]' % self.conn.nick, message) is not None

    def fix_ping(self, message):
        return re.sub('^%s[:,\s]\s*' % self.conn.nick, '', message)

    def ping(self, pattern, callback):
        return (
            '^%s[:,\s]\s*%s' % (self.conn.nick, pattern.lstrip('^')),
            self._ping_decorator(callback),
        )

    def command_patterns(self):
        """\
        Hook for defining callbacks, stored as a tuple of 2-tuples:

        return (
            ('/join', self.room_greeter),
            ('!find (^\s+)', self.handle_find),
        )
        """
        raise NotImplementedError

    def respond(self, message, channel=None, nick=None):
        """\
        Wraps the connection object's respond() method
        """
        self.conn.respond(message, channel, nick)


def run_bot(bot_class, host, port, nick, channels=None):
    """\
    Convenience function to start a bot on the given network, optionally joining
    some channels
    """
    conn = IRCConnection(host, port, nick)
    bot_instance = bot_class(conn)

    while 1:
        if not conn.connect():
            break

        channels = channels or []

        for channel in channels:
            conn.join(channel)

        conn.enter_event_loop()


class SimpleSerialize(object):
    """\
    Allow simple serialization of data in IRC messages with minimum of space.

    * Only supports dictionaries *
    """
    def serialize(self, dictionary):
        return '|'.join(('%s:%s' % (k, v) for k, v in dictionary.iteritems()))

    def deserialize(self, string):
        return dict((piece.split(':', 1) for piece in string.split('|')))
