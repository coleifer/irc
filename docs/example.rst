.. _example:

example bot
===========

::

    from irc import IRCBot, run_bot


    class GreeterBot(IRCBot):
        def greet(self, nick, message, channel):
            return 'Hi, %s' % nick
        
        def command_patterns(self):
            return (
                self.ping('^hello', self.greet),
            )


    host = 'irc.freenode.net'
    port = 6667
    nick = 'greeterbot'

    run_bot(GreeterBot, host, port, nick, ['#botwars'])
