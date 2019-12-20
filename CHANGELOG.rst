*********
Changelog
*********


v1.0.0a1 (UNRELEASED)
=====================

Alpha release.

- Require Mopidy >= 3.0.0a5. (PR: #36)

- Require Python >= 3.7. (PR: #36)

- Update project setup. (PR: #36)

- Support filtering search results by station or program. (PR: #34)


v0.4.1 (2016-06-14)
===================

- Port timeout fix for Mopidy's internal stream unwrapping code from mopidy/mopidy#1522 (Fixes: #31)


v0.4.0 (2016-02-16)
===================

- Borrow Mopidy's internal stream unwrapping to avoid incompatibilities with Mopidy v2.0.0 (PR: #28)

- Improved handling of malformed pls playlists.


v0.3.0 (2016-02-06)
===================

- Requires Mopidy v1.1

- Respect user's Mopidy proxy configuration and set user-agent.

- Utilise Mopidy's nested playlist handling (Fixes: #23 PR: #22)


v0.2.2 (2015-04-24)
===================

- Fix infinite loop when adding some stations, again (my bad).


v0.2.1 (2015-04-24)
===================

- Fix infinite loop when adding some stations. (PR: #17)


v0.2 (2015-03-26)
=================

- Fix utf-8 encoding for searches. (PR: #15)

- Fixed inaccessible stream URIs identified as recursive playlist and not using the remaining stream URIs.

- Update to work with new playback API in Mopidy 1.0.

- Update to work with new backend search API in Mopidy 1.0.

- Requires Mopidy v1.0.


v0.1.3 (2014-01-22)
===================

- Don't submit a search (and receive an error) when the query is empty.

- Improved nested playlist support.

- Support for 'protocol rollover' style ASX playlists.

- ASF HTTP streams in ASX playlists are converted to MMS steams.

- Ignore nested subtypes in content-type header field to fix #5.

- Added support for a station's logo.

- Include currently playing info.

- Unplayable streams now correctly recognised by Mopidy and playback fails rather than continuing to play the previous track.


v0.1.2 (2014-04-13)
===================

- Improved stream selection for stations using PLS format playlists.

- Added suggested additional gstreamer plugin packages. 


v0.1.1 (2014-02-24)
===================

- Fixed package description typo and capitalisation inconsistency in name!


v0.1.0 (2014-02-23)
===================

- Initial release.
