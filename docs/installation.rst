.. _installation:

Installation
============

There are a couple of ways to install irckit


Installing with pip
^^^^^^^^^^^^^^^^^^^

::

    pip install irckit
    
    or
    
    pip install -e git+https://github.com/coleifer/irc.git#egg=irc


Installing via git
^^^^^^^^^^^^^^^^^^

::

    git clone https://github.com/coleifer/irc.git
    cd irc
    sudo python setup.py install


Install dependencies
^^^^^^^^^^^^^^^^^^^^

::

    pip install gevent (for botnet)
    pip install boto (for botnet's EC2 launcher)
    pip install httplib2 (for some of the bots)
