import httplib2
import random
import time
import urllib

from irc import IRCBot, run_bot


class AsciiArtBot(IRCBot):
    groupings = ['ab', 'c', 'def', 'ghi', 'jkl', 'mno', 'pqr', 's', 't', 'uvw', 'xyz']
    
    def get_grouping(self, word):
        first_char = word.lower()[0]
        for grouping in self.groupings:
            if first_char in grouping:
                return grouping
    
    def fetch_result(self, query):
        sock = httplib2.Http(timeout=1)
        
        query = query.strip()
        potentials = [query]
        if query.endswith('s'):
            potentials.append(query[:-1])
        
        grouping = self.get_grouping(query)
        
        for potential in potentials:
            headers, response = sock.request(
                'http://www.ascii-art.de/ascii/%s/%s.txt' % (
                grouping, urllib.quote(potential)
            ))
            if headers['status'] in (200, '200'):
                return self.random_from(response)
    
    def random_from(self, ascii_art):
        guesses = ascii_art.split('\n\n\n')
        while len(guesses):
            img = random.randint(0, len(guesses) - 1)
            if self.is_quality(guesses[img]):
                return guesses[img]
            else:
                guesses = guesses[:img] + guesses[img + 1:]
    
    def is_quality(self, img):
        non_empty_lines = 0
        for line in img.splitlines():
            if line.strip():
                non_empty_lines += 1
        
        return non_empty_lines > 3
    
    def display(self, nick, message, channel):
        result = self.fetch_result(message)
        if result:
            for line in result.splitlines()[:45]:
                self.respond(line, channel=channel)
                time.sleep(.2)
    
    def command_patterns(self):
        return (
            self.ping('^\S+', self.display),
        )


host = 'irc.freenode.net'
port = 6667
nick = 'picasso_bot'

run_bot(AsciiArtBot, host, port, nick, ['#botwars'])
