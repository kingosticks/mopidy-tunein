from __future__ import unicode_literals

import logging

from mopidy import backend, exceptions, httpclient
from mopidy.audio import scan
from mopidy.models import Ref, SearchResult
from mopidy.internal import http, playlists

import pykka

import requests

import mopidy_tunein
from mopidy_tunein import translator, tunein, Extension

logger = logging.getLogger(__name__)


def get_requests_session(proxy_config, user_agent):
    proxy = httpclient.format_proxy(proxy_config)
    full_user_agent = httpclient.format_user_agent(user_agent)

    session = requests.Session()
    session.proxies.update({'http': proxy, 'https': proxy})
    session.headers.update({'user-agent': full_user_agent})

    return session


class TuneInBackend(pykka.ThreadingActor, backend.Backend):
    uri_schemes = ['tunein']

    def __init__(self, config, audio):
        super(TuneInBackend, self).__init__()

        session = get_requests_session(
            proxy_config=config['proxy'],
            user_agent='%s/%s' % (
                mopidy_tunein.Extension.dist_name,
                mopidy_tunein.__version__))

        self.tunein = tunein.TuneIn(config['tunein']['timeout'], session)
        self.library = TuneInLibrary(self)
        self.playback = TuneInPlayback(audio=audio,
                                       backend=self,
                                       config=config)


class TuneInLibrary(backend.LibraryProvider):
    root_directory = Ref.directory(uri='tunein:root', name='TuneIn')

    def __init__(self, backend):
        super(TuneInLibrary, self).__init__(backend)

    def browse(self, uri):
        result = []
        variant, identifier = translator.parse_uri(uri)
        logger.debug('Browsing %s' % uri)
        if variant == 'root':
            for category in self.backend.tunein.categories():
                result.append(translator.category_to_ref(category))
        elif variant == "category" and identifier:
            for section in self.backend.tunein.categories(identifier):
                result.append(translator.section_to_ref(section, identifier))
        elif variant == "location" and identifier:
            for location in self.backend.tunein.locations(identifier):
                result.append(translator.section_to_ref(location, 'local'))
            for station in self.backend.tunein.stations(identifier):
                result.append(translator.station_to_ref(station))
        elif variant == "section" and identifier:
            if (self.backend.tunein.related(identifier)):
                result.append(Ref.directory(
                    uri='tunein:related:%s' % identifier, name='Related'))
            if (self.backend.tunein.shows(identifier)):
                result.append(Ref.directory(
                    uri='tunein:shows:%s' % identifier, name='Shows'))
            for station in self.backend.tunein.featured(identifier):
                result.append(translator.section_to_ref(station))
            for station in self.backend.tunein.local(identifier):
                result.append(translator.station_to_ref(station))
            for station in self.backend.tunein.stations(identifier):
                result.append(translator.station_to_ref(station))
        elif variant == "related" and identifier:
            for section in self.backend.tunein.related(identifier):
                result.append(translator.section_to_ref(section))
        elif variant == "shows" and identifier:
            for show in self.backend.tunein.shows(identifier):
                result.append(translator.show_to_ref(show))
        elif variant == "episodes" and identifier:
            for episode in self.backend.tunein.episodes(identifier):
                result.append(translator.station_to_ref(episode))
        else:
            logger.debug('Unknown URI: %s', uri)

        return result

    def refresh(self, uri=None):
        self.backend.tunein.reload()

    def lookup(self, uri):
        variant, identifier = translator.parse_uri(uri)
        if variant != 'station':
            return []
        station = self.backend.tunein.station(identifier)
        if not station:
            return []

        track = translator.station_to_track(station)
        return [track]

    def search(self, query=None, uris=None, exact=False):
        if query is None or not query:
            return
        tunein_query = translator.mopidy_to_tunein_query(query)
        tracks = []
        for station in self.backend.tunein.search(tunein_query):
            track = translator.station_to_track(station)
            tracks.append(track)
        return SearchResult(uri='tunein:search', tracks=tracks)


class TuneInPlayback(backend.PlaybackProvider):
    def __init__(self, audio, backend, config):
        super(TuneInPlayback, self).__init__(audio, backend)
        self._scanner = scan.Scanner(timeout=config['tunein']['timeout'])
        self._config = config
        self._session = http.get_requests_session(
            proxy_config=config['proxy'],
            user_agent='%s/%s' % (
                Extension.dist_name, Extension.version))

    def translate_uri(self, uri):
        variant, identifier = translator.parse_uri(uri)
        station = self.backend.tunein.station(identifier)
        if not station:
            return None
        stream_uris = self.backend.tunein.tune(station)
        while stream_uris:
            uri = stream_uris.pop(0)
            logger.debug('Looking up URI: %s.' % uri)
            try:
            new_uri = _unwrap_stream(
                uri,
                scanner=self._scanner,
                requests_session=self._session,
                recursion_level=10
            )
            if new_uri:
                # TODO: Somehow update metadata using station.
                return new_uri
#                   return self._scanner.scan(uri).uri
#                except exceptions.ScannerError as se:
            else:
                logger.debug('Mopidy scan failed: %s.' % se)
                new_uris = self.backend.tunein.parse_stream_url(uri)
                if new_uris == [uri]:
                    logger.debug(
                        'Last attempt, play stream anyway: %s.' % uri)
                    return uri
                stream_uris.extend(new_uris)
        logger.debug('TuneIn lookup failed.')
        return None

def _unwrap_stream(uri, scanner, requests_session, recursion_level):
    """
    Get a stream URI from a playlist URI, ``uri``.

    Unwraps nested playlists until something that's not a playlist is found or
    the ``timeout`` is reached.
    """

    original_uri = uri
    seen_uris = set()

#    while time.time() < deadline:
    while True:
        if uri in seen_uris:
            logger.info(
                'Unwrapping stream from URI (%s) failed: '
                'playlist referenced itself', uri)
            return None
        else:
            seen_uris.add(uri)

        logger.debug('Unwrapping stream from URI: %s', uri)

        try:
            scan_result = scanner.scan(uri)
        except exceptions.ScannerError as exc:
            logger.debug('GStreamer failed scanning URI (%s): %s', uri, exc)
            scan_result = None

        if scan_result is not None and not (
                scan_result.mime.startswith('text/') or
                scan_result.mime.startswith('application/')):
            logger.debug(
                'Unwrapped potential %s stream: %s', scan_result.mime, uri)
            return uri

        content = http.download(
            requests_session, uri)

        if content is None:
            logger.info(
                'Unwrapping stream from URI (%s) failed: '
                'error downloading URI %s', original_uri, uri)
            return None

        uris = playlists.parse(content)
        if not uris:
            logger.debug(
                'Failed parsing URI (%s) as playlist; found potential stream.',
                uri)
            return uri

        # TODO Test streams and return first that seems to be playable
        logger.debug(
            'Parsed playlist (%s) and found new URI: %s', uri, uris[0])
	if recursion_level:
	    uri = _unwrap_stream(uris[0], scanner, requests_session, recursion_level-1)
	else:	
            logger.info(
                'Unwrapping stream from URI (%s) failed: '
                'error downloading URI %s', original_uri, uri)
            return None

