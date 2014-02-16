from __future__ import unicode_literals

import ConfigParser as configparser
import json
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
    """Decorator that caches a function's return value each time it is called 
    within a TTL.
    """

    def __init__(self, ttl=3600):
        self.cache = {}
        self.ttl = ttl

    def __call__(self, func):
        def wrapped(*args):
            now = time.time()
            try:
                value, last_update = self.cache[args]
                if (now - last_update > self.ttl):
                    raise AttributeError
                # logger.info('Cache hit! ' + repr(value))
                return value
            except (KeyError, AttributeError):
                value = func(*args)
                self.cache[args] = (value, now)
                # logger.info('Cache save! ' + repr(value))
                return value
            except TypeError:
                return func(*args) # uncachable
        
        def clear():
            self.cache.clear()

        wrapped.clear = clear
        return wrapped

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
    try:
        for event, element in elementtree.iterparse(data):
            element.tag = element.tag.lower()  # normalize
    except elementtree.ParseError:
        return

    for ref in element.findall('entry/ref'):
        yield ref.get('href', '').strip()

def find_playlist_parser(extension, content_type):
    extension_map = {'.asx' : parse_asx,
                     '.m3u' : parse_m3u,
                     '.pls' : parse_pls}
    content_type_map = {'video/x-ms-asf'        : parse_asx,
                        'application/x-mpegurl' : parse_m3u,
                        'audio/x-scpls'         : parse_pls}

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
        self._stations = {}
        #categories.clear()
        #section.clear()

    def _filter_results(self, data, section_name='', map_func=None):
        for section in data:
            section_key = section.get('key', '').lower()
            if section_key.startswith(section_name.lower()):
                results = []
                for item in section['children']:
                    if 'guide_id' in item:
                        if map_func:
                            station = map_func(item)
                        else:
                            station = item
                        self._stations[station['guide_id']] = station
                        results.append(station)
                return results
        return []

    def categories(self, category=''):
        if category == 'location':
            args = '&id=r0' # Annoying special case
        elif category == 'language':
            args = '&c=lang'
            return [] # Tunein's API is a mess here, cba
        else:
            args = '&c=' + category
        results = self._tunein('Browse.ashx', args)
        if (category == 'podcast'):
            results = self._filter_results(results) # More API fun please!
        return results

    def locations(self, location):
        args = '&id=' + location
        results = self._tunein('Browse.ashx', args)
        # TODO: Support filters here 
        return [x for x in results if 'guide_id' in x]

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
        return self._browse('Show', guide_id)#

    def episodes(self, guide_id):
        args = '&c=pbrowse&id=' + guide_id
        results = self._tunein('Tune.ashx', args)
        return self._filter_results(results, 'Topic')

    def _map_listing(self, listing):
        # We've already checked 'guide_id' exists
        #url = 'http://opml.radiotime.com/Tune.ashx?id=%s' % listing['guide_id']
        return {'text'     : listing.get('name', '???'),
                'guide_id' : listing['guide_id'],
                'type'     : 'audio',
                #'URL'      : url, # TODO needed?
                'subtext'  : listing.get('slogan', '')}

    def _station_info(self, station_id):
        args = '&c=composite&detail=listing&id=' + station_id
        results = self._tunein('Describe.ashx', args)
        listings = self._filter_results(results, 'Listing', self._map_listing)
        if listings:
            return listings[0]

    def _extract_stream_urls(self, url):
        extension = urlparse.urlparse(url).path[-4:]
        if extension in ['.mp3', '.wma']:
            return [url]
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

    def tune(self, station_id):
        logger.debug('Tuning station id %s' % station_id)
        args = '&id=' + station_id
        for stream in self._tunein('Tune.ashx', args):
            if 'url' in stream:
                # TODO Cache these playable stream urls?
                return self._extract_stream_urls(stream['url'])
        
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
            r = requests.get(uri, timeout=self._timeout)
            r.raise_for_status()
            resp = r.json()
            if (resp['head']['status'] != '200'):
                raise requests.exceptions.HTTPError(resp['head']['status'],
                    resp['head']['fault'])
            return resp['body']
        except Exception as e:
            logger.error('Tunein request failed: %s', e)
        return {}

    @cache()
    def _get_playlist(self, uri):
        logger.debug('Playlist request: %s', uri)
        try:
            # Defer downloading the content until know it's not a stream 
            r = requests.get(uri, timeout=self._timeout, stream=True)
            r.raise_for_status()
            content_type = r.headers.get('content-type', 'audio/mpeg')
            if content_type == 'audio/mpeg':
                logger.debug('Found streaming audio at %s' % uri)
                content = None
            else:
                content = r.text
            r.close()
            return (content, content_type)
        except Exception as e:
            logger.error('Playlist request failed: %s', e)
        return (None, None)
