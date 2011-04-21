#!/usr/bin/python
import os
import pickle
import random
import re
import sys

from irc import IRCBot, IRCConnection


class MarkovBot(IRCBot):
    """
    Hacking on a markov chain bot - based on:
    http://code.activestate.com/recipes/194364-the-markov-chain-algorithm/
    http://github.com/ericflo/yourmomdotcom
    """
    messages_to_generate = 5
    chattiness = .01
    max_words = 15
    chain_length = 2
    stop_word = '\n'
    filename = 'markov.db'
    last = None 
    
    def __init__(self, *args, **kwargs):
        super(MarkovBot, self).__init__(*args, **kwargs)
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

    def generate_message(self, person, size=15, seed_key=None):
        person_words = len(self.word_table.get(person, {}))
        if person_words < size:
            return

        if not seed_key:
            seed_key = random.choice(self.word_table[person].keys())

        message = []
        for i in xrange(self.messages_to_generate):
            words = seed_key
            gen_words = []
            for i in xrange(size):
                if words[0] == self.stop_word:
                    break

                gen_words.append(words[0])
                try:
                    words = words[1:] + (random.choice(self.word_table[person][words]),)
                except KeyError:
                    break

            if len(gen_words) > len(message):
                message = list(gen_words)
        
        return ' '.join(message)

    def imitate(self, sender, message, channel):
        person = message.replace('imitate ', '').strip()[:10]
        if person != self.conn.nick:
            return self.generate_message(person)

    def cite(self, sender, message, channel):
        if self.last:
            return self.last
    
    def sanitize_message(self, message):
        """Convert to lower-case and strip out all quotation marks"""
        return re.sub('[\"\']', '', message.lower())

    def log(self, sender, message, channel):
        sender = sender[:10]
        self.word_table.setdefault(sender, {})
        
        if message.startswith('/'):
            return

        try:
            say_something = self.is_ping(message) or sender != self.conn.nick and random.random() < self.chattiness
        except AttributeError:
            say_something = False
        messages = []
        seed_key = None
        
        if self.is_ping(message):
            message = self.fix_ping(message)

        for words in self.split_message(self.sanitize_message(message)):
            key = tuple(words[:-1])
            if key in self.word_table:
                self.word_table[sender][key].append(words[-1])
            else:
                self.word_table[sender][key] = [words[-1]]

            if self.stop_word not in key and say_something:
                for person in self.word_table:
                    if person == sender:
                        continue
                    if key in self.word_table[person]:
                        generated = self.generate_message(person, seed_key=key)
                        if generated:
                            messages.append((person, generated))
        
        if len(messages):
            self.last, message = random.choice(messages)
            return message


    def load_log_file(self, filename):
        fh = open(filename, 'r')
        logline_re = re.compile('<\s*(\w+)>[^\]]+\]\s([^\r\n]+)[\r\n]')
        for line in fh.readlines():
            match = logline_re.search(line)
            if match:
                sender, message = match.groups()
                self.log(sender, message, '', False, None)

    def load_text_file(self, filename, sender):
        fh = open(filename, 'r')
        for line in fh.readlines():
            self.log(sender, line, '', False, None)
    
    def command_patterns(self):
        return (
            self.ping('^imitate \S+', self.imitate),
            self.ping('^cite', self.cite),
            ('.*', self.log),
        )


host = 'irc.freenode.net'
port = 6667
nick = 'whatyousay'

conn = IRCConnection(host, port, nick)
markov_bot = MarkovBot(conn)

if len(sys.argv) > 1 and sys.argv[1] == '-log':
    if len(sys.argv) == 3:
        markov_bot.load_log_file(sys.argv[2])
    elif len(sys.argv):
        markov_bot.load_text_file(sys.argv[2], sys.argv[3])
else:
    conn.connect()
    conn.join('#botwars')
    try:
        conn.enter_event_loop()
    except:
        pass

markov_bot.save_data()
