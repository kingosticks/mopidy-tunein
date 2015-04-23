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
`TuneIn <http://www.tunein.com>`_. Listen to the world’s radio with 70,000 stations of music, 
sports and news streaming from every continent.

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

Some radio streams may require additional audio plugins. These can be found in the following packages:
 * `gstreamer0.10-plugins-ugly`
 * `gstreamer0.10-plugins-bad`
 * `gstreamer0.10-ffmpeg`


Known issues
============

The following functionality is not yet implemented:
 * Playback of podcasts/shows.
 * User login and access to saved stations.


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

v0.2.1 (2015-04-24)
-------------------

- Fix infinite loop when adding some stations. (PR: #17)

v0.2 (2015-03-26)
-------------------

- Fix utf-8 encoding for searches. (PR: #15)
- Fixed inaccessible stream URIs identified as recursive playlist and not using the remaining stream URIs.
- Update to work with new playback API in Mopidy 1.0.
- Update to work with new backend search API in Mopidy 1.0.
- Requires Mopidy v1.0.

v0.1.3 (2014-01-22)
-------------------

- Don't submit a search (and receive an error) when the query is empty.
- Improved nested playlist support.
- Support for 'protocol rollover' style ASX playlists.
- ASF HTTP streams in ASX playlists are converted to MMS steams.
- Ignore nested subtypes in content-type header field to fix #5.
- Added support for a station's logo.
- Include currently playing info.
- Unplayable streams now correctly recognised by Mopidy and playback fails rather than continuing to play the previous track.

v0.1.2 (2014-04-13)
-------------------

- Improved stream selection for stations using PLS format playlists.
- Added suggested additional gstreamer plugin packages. 

v0.1.1 (2014-02-24)
-------------------

- Fixed package description typo and capitalisation inconsistency in name!

v0.1.0 (2014-02-23)
-------------------

- Initial release.
