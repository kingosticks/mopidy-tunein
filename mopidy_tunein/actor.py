from __future__ import unicode_literals

import logging

import pykka

from mopidy import backend, exceptions
from mopidy.audio import scan
from mopidy.models import Ref, Track, SearchResult

from . import tunein, translator

logger = logging.getLogger(__name__)


class TuneinBackend(pykka.ThreadingActor, backend.Backend):
    uri_schemes = ['tunein']

    def __init__(self, config, audio):
        super(TuneinBackend, self).__init__()
        self.tunein = tunein.Tunein(config['tunein']['timeout'])
        self.library = TuneinLibrary(
            backend=self, timeout=config['tunein']['timeout'])
        self.playback = TuneinPlayback(audio=audio, backend=self)


class TuneinLibrary(backend.LibraryProvider):
    root_directory = Ref.directory(uri='tunein:root', name='Tunein')

    def __init__(self, backend, timeout):
        super(TuneinLibrary, self).__init__(backend)
        self._scanner = scan.Scanner(min_duration=None, timeout=timeout)

    def browse(self, uri):
        result = []
        variant, identifier = translator.parse_uri(uri)
        logger.debug('Browsing %s' % uri)
        if variant == 'root':
            for category in self.backend.tunein.categories():
                result.append(translator.category_to_ref(category))
        elif variant == "category" and identifier:
            for section in self.backend.tunein.categories(identifier):
                result.append(translator.section_to_ref(section))
        elif variant == "location" and identifier:
            for location in self.backend.tunein.locations(identifier):
                result.append(translator.section_to_ref(location))
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

        ref = translator.station_to_ref(station)
        return [Track(uri=ref.uri, name=ref.name)]

    def find_exact(self, query=None, uris=None):
        return self.search(query=query, uris=uris)

    def search(self, query=None, uris=None):
        if query is None or not query:
            return
        tunein_query = translator.mopidy_to_tunein_query(query)
        tracks = []
        for station in self.backend.tunein.search(tunein_query):
            ref = translator.station_to_ref(station)
            tracks.append(Track(uri=ref.uri, name=ref.name))
        return SearchResult(uri='tunein:search', tracks=tracks)


class TuneinPlayback(backend.PlaybackProvider):
    def __init__(self, audio, backend):
        super(TuneinPlayback, self).__init__(audio, backend)
        self._scanner = scan.Scanner(min_duration=None, timeout=1000)

    def change_track(self, track):
        variant, identifier = translator.parse_uri(track.uri)
        if variant != 'station':
            return False
        uris = self.backend.tunein.tune(identifier, parse_url=False)
        if not uris:
            return False
        try:
            data = self._scanner.scan(uris[0])
            track = scan.audio_data_to_track(data)
        except exceptions.ScannerError as e:
            logger.debug('Problem looking up %s: %s.', uris[0], e)
            uris = self.backend.tunein.parse_stream_url(uris[0])
            track = track.copy(uri=uris[0])

        return super(TuneinPlayback, self).change_track(track)
