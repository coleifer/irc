from irc import IRCBot


class GreeterBot(IRCBot):
    def greet(self, sender, message, channel, is_ping, reply):
        if is_ping or channel is None:
            reply('Hi, %s' % sender)
    
    def get_patterns(self):
        return (
            ('^hello', self.greet),
        )


host = 'irc.freenode.net'
port = 6667
nick = 'greeterbot'

greeter = GreeterBot(host, port, nick, ['#botwars'])
greeter.run_forever()
