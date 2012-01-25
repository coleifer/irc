#!/usr/bin/python
import random
import re
import redis

from irc import IRCBot, run_bot


class MarkovBot(IRCBot):
    """
    http://code.activestate.com/recipes/194364-the-markov-chain-algorithm/
    http://github.com/ericflo/yourmomdotcom
    """
    chain_length = 2
    chattiness = .01
    max_words = 30
    messages_to_generate = 5
    prefix = 'irc'
    separator = '\x01'
    stop_word = '\x02'
    
    def __init__(self, *args, **kwargs):
        super(MarkovBot, self).__init__(*args, **kwargs)
        
        self.redis_conn = redis.Redis()
    
    def make_key(self, k):
        return '-'.join((self.prefix, k))
    
    def sanitize_message(self, message):
        return re.sub('[\"\']', '', message.lower())

    def split_message(self, message):
        # split the incoming message into words, i.e. ['what', 'up', 'bro']
        words = message.split()
        
        # if the message is any shorter, it won't lead anywhere
        if len(words) > self.chain_length:
            
            # add some stop words onto the message
            # ['what', 'up', 'bro', '\x02']
            words.append(self.stop_word)
            
            # len(words) == 4, so range(4-2) == range(2) == 0, 1, meaning
            # we return the following slices: [0:3], [1:4]
            # or ['what', 'up', 'bro'], ['up', 'bro', '\x02']
            for i in range(len(words) - self.chain_length):
                yield words[i:i + self.chain_length + 1]
    
    def generate_message(self, seed):
        key = seed
        
        # keep a list of words we've seen
        gen_words = []
        
        # only follow the chain so far, up to <max words>
        for i in xrange(self.max_words):
        
            # split the key on the separator to extract the words -- the key
            # might look like "this\x01is" and split out into ['this', 'is']
            words = key.split(self.separator)
            
            # add the word to the list of words in our generated message
            gen_words.append(words[0])
            
            # get a new word that lives at this key -- if none are present we've
            # reached the end of the chain and can bail
            next_word = self.redis_conn.srandmember(self.make_key(key))
            if not next_word:
                break
            
            # create a new key combining the end of the old one and the next_word
            key = self.separator.join(words[1:] + [next_word])

        return ' '.join(gen_words)

    def log(self, sender, message, channel):
        # speak only when spoken to, or when the spirit moves me
        say_something = self.is_ping(message) or (
            sender != self.conn.nick and random.random() < self.chattiness
        )
        
        messages = []
        
        # use a convenience method to strip out the "ping" portion of a message
        if self.is_ping(message):
            message = self.fix_ping(message)
        
        if message.startswith('/'):
            return

        # split up the incoming message into chunks that are 1 word longer than
        # the size of the chain, e.g. ['what', 'up', 'bro'], ['up', 'bro', '\x02']
        for words in self.split_message(self.sanitize_message(message)):
            # grab everything but the last word
            key = self.separator.join(words[:-1])
            
            # add the last word to the set
            self.redis_conn.sadd(self.make_key(key), words[-1])
            
            # if we should say something, generate some messages based on what
            # was just said and select the longest, then add it to the list
            if say_something:
                best_message = ''
                for i in range(self.messages_to_generate):
                    generated = self.generate_message(seed=key)
                    if len(generated) > len(best_message):
                        best_message = generated
                
                if best_message:
                    messages.append(best_message)
        
        if len(messages):
            return random.choice(messages)

    def command_patterns(self):
        return (
            ('.*', self.log),
        )


host = 'irc.freenode.net'
port = 6667
nick = 'whatyousay'

run_bot(MarkovBot, host, port, nick, ['#lawrence-botwars'])
