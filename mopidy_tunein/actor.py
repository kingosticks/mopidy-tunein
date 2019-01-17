from __future__ import unicode_literals

import logging
import time

from mopidy import backend, exceptions, httpclient
from mopidy.audio import scan
# TODO: Something else, using internal APIs is not cool.
from mopidy.internal import http, playlists
from mopidy.models import Ref, SearchResult

import pykka

import requests

import mopidy_tunein
from mopidy_tunein import translator, tunein

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

        self._session = get_requests_session(
            proxy_config=config['proxy'],
            user_agent='%s/%s' % (
                mopidy_tunein.Extension.dist_name,
                mopidy_tunein.__version__))

        self._timeout = config['tunein']['timeout']
        self._filter = config['tunein']['filter']

        self._scanner = scan.Scanner(
            timeout=config['tunein']['timeout'],
            proxy_config=config['proxy'])
        self.tunein = tunein.TuneIn(
            config['tunein']['timeout'],
            config['tunein']['filter'], self._session)
        self.library = TuneInLibrary(self)
        self.playback = TuneInPlayback(audio=audio, backend=self)


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

    def translate_uri(self, uri):
        variant, identifier = translator.parse_uri(uri)
        station = self.backend.tunein.station(identifier)
        if not station:
            return None
        stream_uris = self.backend.tunein.tune(station)
        while stream_uris:
            uri = stream_uris.pop(0)
            logger.debug('Looking up URI: %s.' % uri)
            new_uri = self.unwrap_stream(uri)
            if new_uri:
                return new_uri
            else:
                logger.debug('Mopidy translate_uri failed.')
                new_uris = self.backend.tunein.parse_stream_url(uri)
                if new_uris == [uri]:
                    logger.debug(
                        'Last attempt, play stream anyway: %s.' % uri)
                    return uri
                stream_uris.extend(new_uris)
        logger.debug('TuneIn lookup failed.')
        return None

    def unwrap_stream(self, uri):
        unwrapped_uri, _ = _unwrap_stream(
            uri, timeout=self.backend._timeout, scanner=self.backend._scanner,
            requests_session=self.backend._session)
        return unwrapped_uri


# Shamelessly taken from mopidy.stream.actor
def _unwrap_stream(uri, timeout, scanner, requests_session):
    """
    Get a stream URI from a playlist URI, ``uri``.

    Unwraps nested playlists until something that's not a playlist is found or
    the ``timeout`` is reached.
    """

    original_uri = uri
    seen_uris = set()
    deadline = time.time() + timeout

    while time.time() < deadline:
        if uri in seen_uris:
            logger.info(
                'Unwrapping stream from URI (%s) failed: '
                'playlist referenced itself', uri)
            return None, None
        else:
            seen_uris.add(uri)

        logger.debug('Unwrapping stream from URI: %s', uri)

        try:
            scan_timeout = deadline - time.time()
            if scan_timeout < 0:
                logger.info(
                    'Unwrapping stream from URI (%s) failed: '
                    'timed out in %sms', uri, timeout)
                return None, None
            scan_result = scanner.scan(uri, timeout=scan_timeout)
        except exceptions.ScannerError as exc:
            logger.debug('GStreamer failed scanning URI (%s): %s', uri, exc)
            scan_result = None

        if scan_result is not None:
            if scan_result.playable or (
                not scan_result.mime.startswith('text/') and
                not scan_result.mime.startswith('application/')
            ):
                logger.debug(
                    'Unwrapped potential %s stream: %s', scan_result.mime, uri)
                return uri, scan_result

        download_timeout = deadline - time.time()
        if download_timeout < 0:
            logger.info(
                'Unwrapping stream from URI (%s) failed: timed out in %sms',
                uri, timeout)
            return None, None
        content = http.download(
            requests_session, uri, timeout=download_timeout / 1000)

        if content is None:
            logger.info(
                'Unwrapping stream from URI (%s) failed: '
                'error downloading URI %s', original_uri, uri)
            return None, None

        uris = playlists.parse(content)
        if not uris:
            logger.debug(
                'Failed parsing URI (%s) as playlist; found potential stream.',
                uri)
            return uri, None

        # TODO Test streams and return first that seems to be playable
        logger.debug(
            'Parsed playlist (%s) and found new URI: %s', uri, uris[0])
        uri = uris[0]
