#!/usr/bin/python
import os
import pickle
import random
import re
import sys

from irc import Dispatcher, IRCBot


class MarkovDispatcher(Dispatcher):
    """
    Hacking on a markov chain bot - based on:
    http://code.activestate.com/recipes/194364-the-markov-chain-algorithm/
    http://github.com/ericflo/yourmomdotcom
    """
    max_words = 15
    chain_length = 2
    stop_word = '\n'
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
        if len(words) > self.chain_length:
            words.extend([self.stop_word] * self.chain_length)
            for i in range(len(words) - self.chain_length):
                yield (words[i:i + self.chain_length + 1])

    def generate_message(self, person, size=15):
        person_words = len(self.word_table.get(person, []))
        if person_words < size:
            return

        rand_key = random.randint(0, person_words - 1)
        words = self.word_table[person].keys()[rand_key]

        gen_words = []
        for i in xrange(size):
            if words[0] == self.stop_word:
                break

            gen_words.append(words[0])
            try:
                words = words[1:] + (random.choice(self.word_table[person][words]),)
            except KeyError:
                break
        
        return ' '.join(gen_words)

    def imitate(self, sender, message, channel, is_ping, reply):
        if is_ping:
            person = message.replace('imitate ', '').strip()[:10]
            return self.generate_message(person)
    
    def sanitize_message(self, message):
        """Convert to lower-case and strip out all quotation marks"""
        return re.sub('[\"\']', '', message.lower())

    def log(self, sender, message, channel, is_ping, reply):
        sender = sender[:10]
        self.word_table.setdefault(sender, {})
        for words in self.split_message(self.sanitize_message(message)):
            key = tuple(words[:-1])
            if key in self.word_table:
                self.word_table[sender][key].append(words[-1])
            else:
                self.word_table[sender][key] = [words[-1]]

    def load_log_file(self, filename):
        fh = open(filename, 'r')
        logline_re = re.compile('<\s*(\w+)>[^\]]+\]\s([^\r\n]+)[\r\n]')
        for line in fh.readlines():
            match = logline_re.search(line)
            if match:
                sender, message = match.groups()
                self.log(sender, message, '', False, None)
    
    def get_patterns(self):
        return (
            ('^imitate \S+', self.imitate),
            ('.*', self.log),
        )


host = 'irc.freenode.net'
port = 6667
nick = 'whatyousay'

markov = MarkovDispatcher()

if len(sys.argv) == 3 and sys.argv[1] == '-log':
    markov.load_log_file(sys.argv[2])
    markov.save_data()
else:   
    greeter = IRCBot(host, port, nick, ['#lawrence'], [markov])
    greeter.run_forever()
    markov.save_data()
