from irc import Dispatcher, IRCBot


class GreetingDispatcher(Dispatcher):
    def greet(self, sender, message, channel, is_ping):
        if is_ping or channel is None:
            self.send('Hi, %s' % sender, channel=channel, nick=sender)
    
    def get_patterns(self):
        return (
            ('^hello', self.greet),
        )


host = 'irc.freenode.net'
port = 6667
nick = 'greeterbot'

greeter = IRCBot(host, port, nick, ['#lawrence-botwars'], [GreetingDispatcher])
greeter.run_forever()
