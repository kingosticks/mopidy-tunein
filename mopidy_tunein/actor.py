from __future__ import unicode_literals

import logging

import pykka

from mopidy import backend, exceptions
from mopidy.audio import scan
from mopidy.models import Ref, SearchResult

from mopidy_tunein import translator, tunein

logger = logging.getLogger(__name__)


class TuneInBackend(pykka.ThreadingActor, backend.Backend):
    uri_schemes = ['tunein']

    def __init__(self, config, audio):
        super(TuneInBackend, self).__init__()
        self.tunein = tunein.TuneIn(config['tunein']['timeout'])
        self.library = TuneInLibrary(self)
        self.playback = TuneInPlayback(audio=audio,
                                       backend=self,
                                       timeout=config['tunein']['timeout'])


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
    def __init__(self, audio, backend, timeout):
        super(TuneInPlayback, self).__init__(audio, backend)
        self._scanner = scan.Scanner(timeout=timeout)

    def translate_uri(self, uri):
        variant, identifier = translator.parse_uri(uri)
        station = self.backend.tunein.station(identifier)
        if not station:
            return None
        uris = self.backend.tunein.tune(station)
        while uris:
            uri = uris.pop(0)
            logger.debug('Looking up URI: %s.' % uri)
            try:
                # TODO: Somehow update metadata using station.
                return self._scanner.scan(uri).uri
            except exceptions.ScannerError as se:
                try:
                    logger.debug('Mopidy scan failed: %s.' % se)
                    next_uris = self.backend.tunein.parse_stream_url(uri)
                    if next_uris == uri and len(uris) == 0:
                        logger.debug('Attempt to play stream anyway %s.' % uri)
                        return uri
                    uris.extend(next_uris)
                except tunein.PlaylistError as pe:
                    break
        logger.debug('TuneIn lookup failed: %s.' % pe)
        return None
