import httplib2
import json
import re
import urllib

from irc import IRCBot, run_bot


class YahooAnswersBot(IRCBot):
    def get_json(self, url):
        sock = httplib2.Http(timeout=4)
        headers, response = sock.request(url)
        if headers['status'] in (200, '200'):
            return json.loads(response)
    
    def fetch_answer(self, query):
        question_search = self.get_json(
            'http://answers.yahooapis.com/AnswersService/V1/questionSearch?appid=YahooDemo&query=%s&output=json' % \
            urllib.quote(query)
        )
        if len(question_search['all']['questions']):
            question_id = question_search['all']['questions'][0]['Id']
            answer_data = self.get_json(
                'http://answers.yahooapis.com/AnswersService/V1/getQuestion?appid=YahooDemo&question_id=%s&output=json' % \
                urllib.quote(question_id)
            )
            chosen = answer_data['all']['question'][0]['ChosenAnswer']
            return chosen.encode('utf-8', 'replace')
    
    def answer(self, sender, message, channel):
        result = self.fetch_answer(message)
        if result:
            return re.sub('[\r\n ]+', ' ', result).strip()
    
    def command_patterns(self):
        return (
            self.ping('^\S+', self.answer),
        )


host = 'irc.freenode.net'
port = 6667
nick = 'answer_bot'
run_bot(YahooAnswersBot, host, port, nick, ['#botwars'])
