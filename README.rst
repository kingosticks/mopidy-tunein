****************************
Mopidy-TuneIn
****************************

.. image:: https://pypip.in/v/Mopidy-TuneIn/badge.png
    :target: https://pypi.python.org/pypi/Mopidy-TuneIn/
    :alt: Latest PyPI version

.. image:: https://pypip.in/d/Mopidy-TuneIn/badge.png
    :target: https://pypi.python.org/pypi/Mopidy-TuneIn/
    :alt: Number of PyPI downloads

.. image:: https://travis-ci.org/kingosticks/mopidy-tunein.png?branch=master
    :target: https://travis-ci.org/kingosticks/mopidy-tunein
    :alt: Travis CI build status

.. image:: https://coveralls.io/repos/kingosticks/mopidy-tunein/badge.png?branch=master
   :target: https://coveralls.io/r/kingosticks/mopidy-tunein?branch=master
   :alt: Test coverage

`Mopidy <http://www.mopidy.com/>`_ extension for playing music from
`TuneIn <http://www.tunein.com>`_.

Acknowledgement and thanks to Marius Wyss for his original version of this extension and Brian Hornsby's 
`XBMC plugin <https://github.com/brianhornsby/plugin.audio.tuneinradio>`_ that was based on. 

This product uses TuneIn but is not endorsed, certified or otherwise approved in any way by TuneIn. 
TuneIn is the registered trade mark of TuneIn Inc.


Installation
============

Install by running::

    pip install Mopidy-TuneIn

.. Or, if available, install the Debian/Ubuntu package from `apt.mopidy.com
.. <http://apt.mopidy.com/>`_.

Some radio streams may require additional audio plugins, installing the following will help:
 * `gstreamer0.10-plugins-ugly`
 * `gstreamer0.10-plugins-bad`
 * `gstreamer0.10-ffmpeg'


Configuration
=============

Before starting Mopidy, you must add configuration for
Mopidy-TuneIn to your Mopidy configuration file::

    [tunein]
    timeout = 5000


Project resources
=================

- `Source code <https://github.com/kingosticks/mopidy-tunein>`_
- `Issue tracker <https://github.com/kingosticks/mopidy-tunein/issues>`_
- `Download development snapshot <https://github.com/kingosticks/mopidy-tunein/tarball/master#egg=Mopidy-TuneIn-dev>`_


Changelog
=========

v0.1.1 (2014-02-24)
----------------------------------------

- Fixed package description typo and capitalisation inconsistency in name!

v0.1.0 (2014-02-23)
----------------------------------------

- Initial release.
