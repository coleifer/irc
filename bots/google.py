import httplib2
import json
import urllib

from irc import IRCBot, run_bot


class GoogleBot(IRCBot):
    def fetch_result(self, query):
        sock = httplib2.Http(timeout=1)
        headers, response = sock.request(
            'http://ajax.googleapis.com/ajax/services/search/web?v=2.0&q=%s' % \
            urllib.quote(query)
        )
        if headers['status'] in (200, '200'):
            response = json.loads(response)
            return response['responseData']['results'][0]['unescapedUrl']
    
    def find_me(self, nick, message, channel, query):
        result = self.fetch_result(query)
        if result:
            return result
    
    def command_patterns(self):
        return (
            self.ping('^find me (?P<query>\S+)', self.find_me),
        )


host = 'irc.freenode.net'
port = 6667
nick = 'googlebot1337'

run_bot(GoogleBot, host, port, nick, ['#botwars'])
