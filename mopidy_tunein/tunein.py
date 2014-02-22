from __future__ import unicode_literals

import ConfigParser as configparser
import logging
import requests
import StringIO
import time
import urlparse

try:
    import xml.etree.cElementTree as elementtree
except ImportError:
    import xml.etree.ElementTree as elementtree

logger = logging.getLogger(__name__)


class cache(object):
    # TODO: merge this to util library (copied from mopidy-spotify)

    def __init__(self, ctl=0, ttl=3600):
        self.cache = {}
        self.ctl = ctl
        self.ttl = ttl
        self._call_count = 0

    def __call__(self, func):
        def _memoized(*args):
            now = time.time()
            try:
                value, last_update = self.cache[args]
                age = now - last_update
                if (self._call_count > self.ctl or age > self.ttl):
                    self._call_count = 0
                    raise AttributeError
                if self.ctl:
                    self._call_count += 1
                return value

            except (KeyError, AttributeError):
                value = func(*args)
                self.cache[args] = (value, now)
                return value

            except TypeError:
                return func(*args)

        def clear():
            self.cache.clear()

        _memoized.clear = clear
        return _memoized


def parse_m3u(data):
    # Copied from mopidy.audio.playlists
    # Mopidy version expects a header but it's not always present
    for line in data.readlines():
        if not line.startswith('#') and line.strip():
            yield line.strip()


def parse_pls(data):
    # Copied from mopidy.audio.playlists
    try:
        cp = configparser.RawConfigParser()
        cp.readfp(data)
    except configparser.Error:
        return

    for section in cp.sections():
        if section.lower() != 'playlist':
            continue
        for i in xrange(cp.getint(section, 'numberofentries')):
            yield cp.get(section, 'file%d' % (i+1))


def parse_asx(data):
    # Copied from mopidy.audio.playlists
    # Mopidy doesn't support asx: mopidy/mopidy#687
    try:
        for event, element in elementtree.iterparse(data):
            element.tag = element.tag.lower()  # normalize
    except elementtree.ParseError:
        return

    for ref in element.findall('entry/ref'):
        yield ref.get('href', '').strip()

# This is all broken: mopidy/mopidy#225
# from gi.repository import TotemPlParser
# def totem_plparser(uri):
#     results = []
#     def entry_parsed(parser, uri, metadata):
#         results.append(uri)

#     parser = TotemPlParser.Parser.new()
#     someid = parser.connect('entry-parsed', entry_parsed)
#     res = parser.parse(uri, False)
#     parser.disconnect(someid)
#     if res != TotemPlParser.ParserResult.SUCCESS:
#         logger.debug('Failed to parse playlist')
#     return results


def find_playlist_parser(extension, content_type):
    extension_map = {'.asx': parse_asx,
                     '.m3u': parse_m3u,
                     '.pls': parse_pls}
    content_type_map = {'video/x-ms-asf': parse_asx,
                        'application/x-mpegurl': parse_m3u,
                        'audio/x-scpls': parse_pls}

    parser = extension_map.get(extension, None)
    if not parser and content_type:
        # Annoying case where the url gave us no hints so try and work it out
        # from the header's content-type instead.
        # This might turn out to be server-specific...
        parser = content_type_map.get(content_type.lower(), None)
    return parser


class Tunein(object):
    """Wrapper for the Tunein API."""

    def __init__(self, timeout):
        self._base_uri = 'http://opml.radiotime.com/%s'
        self._timeout = timeout / 1000.0
        self._stations = {}

    def reload(self):
        self._stations.clear()
        self._tunein.clear()
        self._get_playlist.clear()

    def _filter_results(self, data, section_name=None, map_func=None):
        results = []

        def grab_item(item):
            if 'guide_id' not in item:
                return
            if item.get('type', 'link') == 'link':
                results.append(item)
                return
            if map_func:
                station = map_func(item)
            else:
                station = item
            self._stations[station['guide_id']] = station
            results.append(station)

        for item in data:
            if section_name is not None:
                section_key = item.get('key', '').lower()
                if section_key.startswith(section_name.lower()):
                    for child in item['children']:
                        grab_item(child)
            else:
                grab_item(item)
        return results

    def categories(self, category=''):
        if category == 'location':
            args = '&id=r0'  # Annoying special case
        elif category == 'language':
            args = '&c=lang'
            return []  # Tunein's API is a mess here, cba
        else:
            args = '&c=' + category

        # Take a copy so we don't modify the cached data
        results = list(self._tunein('Browse.ashx', args))
        if category in ('podcast', 'local'):
            results = self._filter_results(results, '')  # Flatten the results!
        elif category == '':
            trending = {'text': 'Trending',
                        'key': 'trending',
                        'type': 'link',
                        'URL': self._base_uri % 'Browse.ashx?c=trending'}
            # Filter out the language root category for now
            results = [x for x in results if x['key'] != 'language']
            results.append(trending)
        else:
            results = self._filter_results(results)
        return results

    def locations(self, location):
        args = '&id=' + location
        results = self._tunein('Browse.ashx', args)
        # TODO: Support filters here
        return [x for x in results if x.get('type', '') == 'link']

    def _browse(self, section_name, guide_id):
        args = '&id=' + guide_id
        results = self._tunein('Browse.ashx', args)
        return self._filter_results(results, section_name)

    def featured(self, guide_id):
        return self._browse('Featured', guide_id)

    def local(self, guide_id):
        return self._browse('Local', guide_id)

    def stations(self, guide_id):
        return self._browse('Station', guide_id)

    def related(self, guide_id):
        return self._browse('Related', guide_id)

    def shows(self, guide_id):
        return self._browse('Show', guide_id)

    def episodes(self, guide_id):
        args = '&c=pbrowse&id=' + guide_id
        results = self._tunein('Tune.ashx', args)
        return self._filter_results(results, 'Topic')

    def _map_listing(self, listing):
        # We've already checked 'guide_id' exists
        return {'text': listing.get('name', '???'),
                'guide_id': listing['guide_id'],
                'type': 'audio',
                'subtext': listing.get('slogan', '')}

    def _station_info(self, station_id):
        args = '&c=composite&detail=listing&id=' + station_id
        results = self._tunein('Describe.ashx', args)
        listings = self._filter_results(results, 'Listing', self._map_listing)
        if listings:
            return listings[0]

    def parse_stream_url(self, url):
        logger.debug('Using tunein stream url parsing')
        extension = urlparse.urlparse(url).path[-4:]
        if extension in ['.mp3', '.wma']:
            return [url]  # Catch these easy ones
        results = []
        playlist, content_type = self._get_playlist(url)
        if playlist:
            parser = find_playlist_parser(extension, content_type)
            if parser:
                playlist_data = StringIO.StringIO(playlist)
                results = [u for u in parser(playlist_data) if u is not None]

        if not results:
            results = [url]
        return results

    def tune(self, station_id, parse_url=True):
        logger.debug('Tuning station id %s' % station_id)
        args = '&id=' + station_id
        for stream in self._tunein('Tune.ashx', args):
            if 'url' in stream:
                # TODO Cache these playable stream urls?
                if parse_url:
                    return self.parse_stream_url(stream['url'])
                else:
                    return [stream['url']]

        logger.error('Failed to tune station id %s' % station_id)
        return []

    def station(self, station_id):
        if station_id in self._stations:
            station = self._stations[station_id]
        else:
            station = self._station_info(station_id)
            self._stations['station_id'] = station
        return station

    def search(self, query):
        # "Search.ashx?query=" + query + filterVal
        args = '&query=' + query
        results = []
        for item in self._tunein('Search.ashx', args):
            if item.get('type', '') == 'audio':
                # Only return stations
                self._stations[item['guide_id']] = item
                results.append(item)

        return results

    @cache()
    def _tunein(self, variant, args):
        uri = (self._base_uri % variant) + '?render=json' + args
        logger.debug('Tunein request: %s', uri)
        try:
            response = requests.get(uri, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
            if (data['head']['status'] != '200'):
                raise requests.exceptions.HTTPError(data['head']['status'],
                                                    data['head']['fault'])
            return data['body']
        except Exception as e:
            logger.error('Tunein request failed: %s', e)
        return {}

    @cache()
    def _get_playlist(self, uri):
        logger.debug('Playlist request: %s', uri)
        try:
            # Defer downloading the body until know it's not a stream
            response = requests.get(uri, timeout=self._timeout, stream=True)
            response.raise_for_status()
            content_type = response.headers.get('content-type', 'audio/mpeg')
            if content_type == 'audio/mpeg':
                logger.debug('Found streaming audio at %s' % uri)
                data = None
            else:
                data = response.text
            response.close()
            return (data, content_type)
        except Exception as e:
            logger.error('Playlist request failed: %s', e)
        return (None, None)
