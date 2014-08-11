from __future__ import unicode_literals

import io
import unittest

from mopidy_tunein import tunein

ASX = b"""<ASX version="3.0">
  <TITLE>Example</TITLE>
  <ENTRY>
    <TITLE>Sample Title</TITLE>
    <REF href="file:///tmp/foo" />
  </ENTRY>
  <ENTRY>
    <TITLE>Example title</TITLE>
    <REF href="file:///tmp/bar" />
  </ENTRY>
  <ENTRY>
    <TITLE>Other title</TITLE>
    <REF href="file:///tmp/baz" />
  </ENTRY>
</ASX>
"""

SIMPLE_ASX = b"""<ASX version="3.0">
  <ENTRY href="file:///tmp/foo" />
  <ENTRY href="file:///tmp/bar" />
  <ENTRY href="file:///tmp/baz" />
</ASX>
"""

OLD_ASX = b"""[Reference]
Ref1=file:///tmp/foo
Ref2=file:///tmp/bar
Ref3=file:///tmp/baz
"""

ASF_ASX = b"""[Reference]
Ref1=http://tmp.com/foo-mbr?MSWMExt=.asf
Ref2=mms://tmp.com:80/bar-mbr?mswmext=.asf
Ref3=http://tmp.com/baz
"""


class BaseAsxPlaylistTest(object):
    valid = None
    parse = staticmethod(tunein.parse_asx)

    def test_parse_valid_playlist(self):
        uris = list(self.parse(io.BytesIO(self.valid)))
        expected = [b'file:///tmp/foo', b'file:///tmp/bar', b'file:///tmp/baz']
        self.assertEqual(uris, expected)


class AsxPlaylistTest(BaseAsxPlaylistTest, unittest.TestCase):
    valid = ASX


class AsxSimplePlaylistTest(BaseAsxPlaylistTest, unittest.TestCase):
    valid = SIMPLE_ASX


class AsxOldPlaylistTest(BaseAsxPlaylistTest, unittest.TestCase):
    valid = OLD_ASX


class PlaylistTest(unittest.TestCase):
    parse = staticmethod(tunein.parse_asx)

    def test_parse_asf_playlist(self):
        uris = list(self.parse(io.BytesIO(ASF_ASX)))
        expected = [b'mms://tmp.com/foo-mbr?mswmext=.asf',
                    b'mms://tmp.com:80/bar-mbr?mswmext=.asf',
                    b'http://tmp.com/baz']
        self.assertEqual(uris, expected)
