import httplib2
import json
import urllib

from irc import IRCBot


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
    
    def find_me(self, sender, message, channel, is_ping, reply):
        if is_ping:
            result = self.fetch_result(message.replace('find me ', ''))
            if result:
                reply(result)
    
    def get_patterns(self):
        return (
            ('^find me \S+', self.find_me),
        )


host = 'irc.freenode.net'
port = 6667
nick = 'googlebot1337'

greeter = GoogleBot(host, port, nick, ['#botwars'])
greeter.run_forever()
