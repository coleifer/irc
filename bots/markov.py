import random

from irc import Dispatcher, IRCBot
    

class MarkovDispatcher(Dispatcher):
    """
    Hacking on a markov chain bot - based on:
    http://code.activestate.com/recipes/194364-the-markov-chain-algorithm/
    """
    max_words = 10
    
    def __init__(self, *args, **kwargs):
        super(MarkovDispatcher, self).__init__(*args, **kwargs)
        self.word_table = {} # use memory! :D
    
    def imitate(self, sender, message, channel, is_ping, reply):
        if is_ping:
            person = message.replace('imitate ', '').strip()
            if person in self.word_table:
                w1 = ' '
                w2 = ' '
                phrase = []
                for i in xrange(self.max_words):
                    try:
                        new_word = random.choice(self.word_table[person][(w1, w2)])
                    except KeyError:
                        break
                    phrase.append(new_word)
                    w1, w2 = w2, new_word
                reply(' '.join(phrase))
    
    def log(self, sender, message, channel, is_ping, reply):
        self.word_table.setdefault(sender, {})
        w1 = ' '
        w2 = ' '
        for word in message.split():
            self.word_table[sender].setdefault((w1, w2), []).append(word)
            w1, w2 = w2, word
    
    def get_patterns(self):
        return (
            ('^imitate \S+', self.imitate),
            ('.*', self.log),
        )


host = 'irc.freenode.net'
port = 6667
nick = 'whatyousay'

greeter = IRCBot(host, port, nick, ['#lawrence-botwars'], [MarkovDispatcher()])
greeter.run_forever()
