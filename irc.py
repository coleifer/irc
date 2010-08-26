import re
import socket
import time


class IRCConnection(object):
    _sock = None
    _callbacks = None

    chanmsg_re = re.compile(':(?P<nick>.*?)!~\S+\s+?PRIVMSG\s+#(?P<channel>[-\w]+)\s+:(?P<message>[^\n\r]+)')
    privmsg_re = re.compile(':(?P<nick>.*?)!~\S+\s+?PRIVMSG\s+[^#][^:]+:(?P<message>[^\n\r]+)')

    def __init__(self, host, port, nick):
        self.host = host
        self.port = port
        self.nick = nick
        self._callbacks = {
            'PRIVMSG': [],
            'CHANMSG': [],
        }

    def connect(self):
        self._sock = socket.create_connection((self.host, self.port)).makefile()

    def disconnect(self):
        self.send('QUIT')
        self._sock.close()

    def send(self, data):
        self._sock.write('%s\r\n' % data)
        self._sock.flush()

    def authenticate(self):
        self.send('NICK %s' % self.nick)
        self.send('USER %s %s bla :%s' % (self.nick, self.host, self.nick))

    def join(self, channel):
        channel = channel.lstrip('#')
        self.send('JOIN #%s' % channel)

    def part(self, channel):
        channel = channel.lstrip('#')
        self.send('PART #%s' % channel)

    def register_callback(self, event, func):
        self._callbacks[event].append(func)

    def unregister_callback(self, event, func):
        self._callbacks[event].remove(func)

    def enter_event_loop(self):
        while not self._sock.closed:
            line = self._sock.readline()
            line = line.rstrip()
            if line.startswith('PING'):
                self.send('PONG %s' % line.split()[1])
            else:
                chan_match = self.chanmsg_re.match(line)
                if chan_match:
                    for event in self._callbacks['CHANMSG']:
                        event(**chan_match.groupdict())

                priv_match = self.privmsg_re.match(line)
                if priv_match:
                    for event in self._callbacks['PRIVMSG']:
                        event(**priv_match.groupdict())


class Dispatcher(object):    
    rate_limit = (3, .75) # for every three lines, delay .75s
    
    def __init__(self):
        # rate limiter state
        self.num_sent = 0
        self.last_send = 0
    
    def bind(self, conn):
        self.irc = conn

        self.irc.register_callback('CHANMSG', self.on_channel_message)
        self.irc.register_callback('PRIVMSG', self.on_private_message)

    def get_patterns(self):
        """
        A tuple of regex -> callback where the argument signature of callback:

        def some_callback(sender, message, channel, is_ping, reply):
            do some shit
        """
        raise NotImplementedError

    def on_channel_message(self, nick, channel, message):
        is_ping = False
        if re.match('^%s[:,\s]' % self.irc.nick, message):
            message = re.sub('%s[^\s]*?\s' % self.irc.nick, '', message)
            is_ping = True
        for (pattern, callback) in self.get_patterns():
            if re.search(pattern, message):
                def curried_reply(message):
                    return self.send(message, channel=channel, nick=nick)
                result = callback(nick, message, channel, is_ping, curried_reply)
                if result:
                    curried_reply(result)

    def on_private_message(self, nick, message):
        self.on_channel_message(nick, None, message)

    def send(self, message, channel=None, nick=None):
        if self.num_sent == self.rate_limit[0]:
            self.num_sent = 0
            if time.time() - self.last_send <= self.rate_limit[1]:
                time.sleep(self.rate_limit[1] - (time.time() - self.last_send))
            self.last_send = time.time()
        self.num_sent += 1
        if channel:
            self.irc.send('PRIVMSG #%s :%s' % (channel.lstrip('#'), message))
        elif nick:
            self.irc.send('PRIVMSG %s :%s' % (nick, message))


class IRCBot(object):
    def __init__(self, host, port, nick, channels, dispatchers):
        self.conn = IRCConnection(host, port, nick)
        self.conn.connect()
        self.conn.authenticate()

        for channel in channels:
            self.conn.join(channel)

        for dispatcher in dispatchers:
            dispatcher.bind(self.conn)

    def run_forever(self):
        try:
            self.conn.enter_event_loop()
        except KeyboardInterrupt:
            self.conn.disconnect()
