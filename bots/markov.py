import os
import pickle
import random

from irc import Dispatcher, IRCBot


class MarkovDispatcher(Dispatcher):
    """
    Hacking on a markov chain bot - based on:
    http://code.activestate.com/recipes/194364-the-markov-chain-algorithm/
    """
    max_words = 10
    filename = 'markov.db'
    
    def __init__(self, *args, **kwargs):
        super(MarkovDispatcher, self).__init__(*args, **kwargs)
        self.load_data()
    
    def load_data(self):
        if os.path.exists(self.filename):
            fh = open(self.filename, 'rb')
            self.word_table = pickle.loads(fh.read())
            fh.close()
        else:
            self.word_table = {}
    
    def save_data(self):
        fh = open(self.filename, 'w')
        fh.write(pickle.dumps(self.word_table))
        fh.close()
    
    def split_message(self, message):
        words = message.split()
        for i in range(len(words) - 2):
            yield (words[i], words[i+1], words[i+2])
    
    def generate_message(self, person, size=15):
        person_words = len(self.word_table.get(person, []))
        if person_words < size:
            return
        
        rand_key = random.randint(0, person_words - 1)
        w1, w2 = self.word_table[person].keys()[rand_key]
        
        gen_words = []
        for i in xrange(size):
            gen_words.append(w1)
            try:
                w1, w2 = w2, random.choice(self.word_table[person][(w1, w2)])
                gen_words.append(w2)
            except KeyError:    
                break
        
        return ' '.join(gen_words)

    def imitate(self, sender, message, channel, is_ping, reply):
        if is_ping:
            person = message.replace('imitate ', '').strip()
            return self.generate_message(person)
    
    def log(self, sender, message, channel, is_ping, reply):
        self.word_table.setdefault(sender, {})
        for w1, w2, w3 in self.split_message(message):
            key = (w1, w2)
            if key in self.word_table:
                self.word_table[sender][key].append(w3)
            else:
                self.word_table[sender][key] = [w3]
    
    def get_patterns(self):
        return (
            ('^imitate \S+', self.imitate),
            ('.*', self.log),
        )


host = 'irc.freenode.net'
port = 6667
nick = 'whatyousay'

markov = MarkovDispatcher()
greeter = IRCBot(host, port, nick, ['#lawrence'], [markov])
greeter.run_forever()
markov.save_data()
