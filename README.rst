irc
===

tinkering with a made-from-scratch irc library in python

`documentation <http://irckit.readthedocs.org>`_ hosted on readthedocs.org


installing
----------

install from github (recommended)::

    pip install -e git+git://github.com/coleifer/irc.git#egg=irckit

install using pypi::

    pip install irckit

install dependencies::

    pip install gevent (for botnet)
    pip install boto (for botnet's EC2 launcher)
    pip install httplib2 (for some of the bots)
