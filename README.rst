irc
===

tinkering with a made-from-scratch irc library in python


example bot
-----------

::

    from irc import IRCBot, run_bot


    class GreeterBot(IRCBot):
        def greet(self, nick, message, channel):
            return 'Hi, %s' % nick
        
        def command_patterns(self):
            return (
                self.ping('^hello', self.greet),
            )


    host = 'irc.freenode.net'
    port = 6667
    nick = 'greeterbot'

    run_bot(GreeterBot, host, port, nick, ['#botwars'])


running the botnet
------------------

the botnet consists of a "boss" command program which interfaces with any
number of "workers".  to run it from the command-line::

    python boss.py -c secretbotz -n daboss1

this will start the command program using "#secretbotz" as the command channel.
the boss will be identified by the nickname "daboss1".  the default host is
irc.freenode.net but can be configured using the "-h" option.

next, start up any number of workers.  the workers will need to know the nick
of the command bot so they can register themselves and start accepting tasks::

    python worker.py -b daboss1

now you should be able to join #secretbotz using your IRC client and see
"daboss1" just chilling out::

    <cleifer> !auth password
    <daboss1> Success
    <cleifer> !status
    <daboss1> 1 workers available
    <daboss1> 0 tasks have been scheduled

let's execute a program on the worker machine::

    <cleifer> !execute run vmstat
    <daboss1> Scheduled task: "run vmstat" with id 1 [1 workers]
    <daboss1> Task 1 completed by 1 workers

what was the output of the command?

::

    cleifer> !print
    <daboss1> [w0rk3r:{alpha}] - run vmstat
    <daboss1> procs -----------memory---------- ---swap-- -----io---- -system-- ----cpu----
    <daboss1> r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa
    <daboss1> 0  0      0 977784 504004 910144    0    0    46    29  103  443  3  1 96  0
