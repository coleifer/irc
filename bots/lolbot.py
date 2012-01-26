#!/usr/bin/python
import random
import re
import redis

from irc import IRCBot, run_bot


class LolBot(IRCBot):
    key = 'lolbot'
    url_pattern = re.compile('(https?://[-A-Za-z0-9+&@#/%?=~_()|!:,.;]*[-A-Za-z0-9+&@#/%=~_|])')
    phrases = 'lol|haha|:\)|nice|wat\?|wtf'
    influencer_patterns = [
        ('^%(sender)s[:,\s]\s(%(phrases)s)', 3),
        ('^(%(phrases)s)', 1),
    ]

    lifetime = 5
    repeat_score = 5
    
    def __init__(self, *args, **kwargs):
        super(LolBot, self).__init__(*args, **kwargs)
        
        self.message_count = 0
        self.last_urls = {}
        self.redis_conn = redis.Redis()

    def store_url(self, sender, url):
        score = self.redis_conn.zscore(self.key, url)
        if score is None:
            self.redis_conn.zadd(self.key, url, 1)
        else:
            self.redis_conn.zincrby(self.key, url, self.repeat_score)

    def search_urls(self, sender, message, channel):
        if not self.url_pattern.search(message):
            return

        self.message_count = self.lifetime

        for url in self.url_pattern.findall(message):
            self.store_url(sender, url)
            self.last_urls[channel] = {
                'sender': sender,
                'url': url,
            }

    def check_lulz(self, sender, message, channel):
        if channel in self.last_urls and self.message_count > 0:
            vals = {
                'sender': self.last_urls[channel]['sender'],
                'phrases': self.phrases,
            }
            for pattern, score in self.influencer_patterns:
                if re.match(pattern % vals, message):
                    self.redis_conn.zincrby(self.last_urls[channel]['url'], score)

    def log(self, sender, message, channel):
        if self.message_count > 0:
            self.message_count -= 1

        self.check_lulz(sender, message, channel)
        self.search_urls(sender, message, channel)

    def command_patterns(self):
        return (
            ('.*', self.log),
        )


host = 'irc.freenode.net'
port = 6667
nick = 'walrus-whisker'

run_bot(LolBot, host, port, nick, ['#lawrence-botwars'])
