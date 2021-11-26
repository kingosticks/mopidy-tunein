*************
Mopidy-TuneIn
*************

.. image:: https://img.shields.io/pypi/v/Mopidy-TuneIn
    :target: https://pypi.org/project/Mopidy-TuneIn/
    :alt: Latest PyPI version

.. image:: https://img.shields.io/github/workflow/status/kingosticks/mopidy-tunein/CI
    :target: https://github.com/kingosticks/mopidy-tunein/actions
    :alt: CI build status

.. image:: https://img.shields.io/codecov/c/gh/kingosticks/mopidy-tunein
    :target: https://codecov.io/gh/kingosticks/mopidy-tunein
    :alt: Test coverage

`Mopidy <https://mopidy.com/>`_ extension for playing music from
`TuneIn <https://tunein.com>`_. Listen to the world’s radio with 70,000 stations of music,
sports and news streaming from every continent.

Acknowledgement and thanks to Marius Wyss for his original version of this extension and Brian Hornsby's 
`XBMC plugin <https://github.com/brianhornsby/plugin.audio.tuneinradio>`_ that was based on. 

This product uses TuneIn but is not endorsed, certified or otherwise approved in any way by TuneIn. 
TuneIn is the registered trade mark of TuneIn Inc.


Installation
============

Install by running::

    python3 -m pip install Mopidy-TuneIn

Or, if available, install the Debian/Ubuntu package from
`apt.mopidy.com <https://apt.mopidy.com/>`_.

Some radio streams may require additional audio plugins. These can be found in the gstreamer plugin packages for your system. For Mopidy v3.0.0 and later, these might include:
 * `gstreamer1.0-plugins-ugly`
 * `gstreamer1.0-plugins-bad`
 * `gstreamer1.0-libav`


Known issues
============

The following functionality is not yet implemented:
 * Playback of podcasts/shows.
 * User login and access to saved stations.


Configuration
=============

You can add configuration for
Mopidy-TuneIn to your Mopidy configuration file but it's not required::

    [tunein]
    timeout = 5000

The following configuration values are available:

- ``tunein/enabled``: If the TuneIn extension should be enabled or not. Defaults to true.
- ``tunein/filter``:  Limit the search results. ``station``, ``program`` or leave blank to disable filtering. Defaults to blank.
- ``tunein/timeout``: Milliseconds before giving up waiting for results. Defaults to ``5000``.
- ``tunein/formats``: List of formats supported by local Mopidy installation. Streams that are aren't available in any compatible
  format are not returned by search. Defaults to ``*`` (all formats).


Project resources
=================

- `Source code <https://github.com/kingosticks/mopidy-tunein>`_
- `Issue tracker <https://github.com/kingosticks/mopidy-tunein/issues>`_
- `Changelog <https://github.com/kingosticks/mopidy-tunein/releases>`_


Credits
=======

- Original author: `Nick Steel <https://github.com/kingosticks>`__
- Current maintainer: `Nick Steel <https://github.com/kingosticks>`__
- `Contributors <https://github.com/kingosticks/mopidy-tunein/graphs/contributors>`_
