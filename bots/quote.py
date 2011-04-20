import httplib2
import random
import re
import urllib

from BeautifulSoup import BeautifulSoup

from irc import IRCBot, run_bot


class QuoteBot(IRCBot):
    last_message = ''
    
    def fetch_result(self, phrase):
        sock = httplib2.Http(timeout=1)
        
        headers, response = sock.request(
            'http://www.esvapi.org/v2/rest/passageQuery?key=TEST&q=%s&include-headings=false' % (
            urllib.quote(phrase)
        ))
        if headers['status'] in (200, '200'):
            return self.random_from(response)
    
    def random_from(self, response):
        soup = BeautifulSoup(response)
        results = soup.findAll('p', {'class': 'search-result'})
        if not len(results):
            return
        
        quote = results[random.randint(0, len(results) - 1)]
        chap = quote.find('a').string
        ghetto_parsed = re.search('<br />(.*)</p>', str(quote)).groups()[0]
        no_html = re.sub('<[^\>]+>', '', ghetto_parsed)
        no_charrefs = re.sub('&[^\;]+;', '', no_html)
        return chap, no_charrefs
    
    def display(self, sender, message, channel):
        if self.is_ping(message):
            query = self.fix_ping(message)
            result = self.fetch_result(query)
            if result:
                return '%s: %s' % (result[0], result[1])
        else:
            self.last_message = message
    
    def contextualize(self, sender, message, channel):
        result = self.fetch_result(self.last_message)
        if result:
            return '%s: %s' % (result[0], result[1])
    
    def command_patterns(self):
        return (
            ('^contextualize', self.contextualize),
            ('', self.display),
        )


host = 'irc.freenode.net'
port = 6667
nick = 'quote_bot'

run_bot(QuoteBot, host, port, nick, ['#botwars'])
