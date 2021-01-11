import logging
import time

import pykka
import requests
from mopidy import backend, exceptions, httpclient
from mopidy.audio import scan
from mopidy.internal import http, playlists
from mopidy.models import Ref, SearchResult

from mopidy_tunein import Extension, translator, tunein

logger = logging.getLogger(__name__)


def get_requests_session(proxy_config):
    user_agent = f"{Extension.dist_name}/{Extension.version}"
    proxy = httpclient.format_proxy(proxy_config)
    full_user_agent = httpclient.format_user_agent(user_agent)

    session = requests.Session()
    session.proxies.update({"http": proxy, "https": proxy})
    session.headers.update({"user-agent": full_user_agent})

    return session


class TuneInBackend(pykka.ThreadingActor, backend.Backend):
    uri_schemes = ["tunein"]

    def __init__(self, config, audio):
        super().__init__()

        self._session = get_requests_session(config["proxy"])
        self._timeout = config["tunein"]["timeout"]
        self._filter = config["tunein"]["filter"]

        self._scanner = scan.Scanner(
            timeout=config["tunein"]["timeout"], proxy_config=config["proxy"]
        )
        self.tunein = tunein.TuneIn(
            config["tunein"]["timeout"],
            config["tunein"]["filter"],
            self._session,
        )
        self.library = TuneInLibrary(self)
        self.playback = TuneInPlayback(audio=audio, backend=self)


class TuneInLibrary(backend.LibraryProvider):
    root_directory = Ref.directory(uri="tunein:root", name="TuneIn")

    def __init__(self, backend):
        super().__init__(backend)

    def browse(self, uri):
        result = []
        variant, identifier = translator.parse_uri(uri)
        logger.debug(f"Browsing {uri!r}")
        if variant == "root":
            for category in self.backend.tunein.categories():
                result.append(translator.category_to_ref(category))
        elif variant == "category" and identifier:
            for section in self.backend.tunein.categories(identifier):
                result.append(translator.section_to_ref(section, identifier))
        elif variant == "location" and identifier:
            for location in self.backend.tunein.locations(identifier):
                result.append(translator.section_to_ref(location, "local"))
            for station in self.backend.tunein.stations(identifier):
                result.append(translator.station_to_ref(station))
        elif variant == "section" and identifier:
            if self.backend.tunein.related(identifier):
                result.append(
                    Ref.directory(
                        uri=f"tunein:related:{identifier}", name="Related"
                    )
                )
            if self.backend.tunein.shows(identifier):
                result.append(
                    Ref.directory(
                        uri=f"tunein:shows:{identifier}", name="Shows"
                    )
                )
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
            logger.debug(f"Unknown URI: {uri!r}")

        return result

    def refresh(self, uri=None):
        self.backend.tunein.reload()

    def lookup(self, uri):
        variant, identifier = translator.parse_uri(uri)
        if variant != "station":
            return []
        station = self.backend.tunein.station(identifier)
        if not station:
            return []

        track = translator.station_to_track(station)
        return [track]

    def get_images(self, uris):
        results = {}
        for uri in uris:
            variant, identifier = translator.parse_uri(uri)
            if variant != "station":
                continue
            station = self.backend.tunein.station(identifier)
            image = translator.station_to_image(station)
            if image is not None:
                results[uri] = [image]
        return results

    def search(self, query=None, uris=None, exact=False):
        if query is None or not query:
            return
        tunein_query = translator.mopidy_to_tunein_query(query)
        tracks = []
        for station in self.backend.tunein.search(tunein_query):
            track = translator.station_to_track(station)
            tracks.append(track)
        return SearchResult(uri="tunein:search", tracks=tracks)


class TuneInPlayback(backend.PlaybackProvider):
    def __init__(self, audio, backend):
        super().__init__(audio, backend)
        self._stream_info = None

    def translate_uri(self, uri):
        variant, identifier = translator.parse_uri(uri)
        station = self.backend.tunein.station(identifier)
        if not station:
            return None
        stream_uris = self.backend.tunein.tune(station)
        while stream_uris:
            uri = stream_uris.pop(0)
            logger.debug(f"Looking up URI: {uri!r}")
            new_uri = self.unwrap_stream(uri)
            if new_uri:
                return new_uri
            else:
                logger.debug("Mopidy translate_uri failed.")
                new_uris = self.backend.tunein.parse_stream_url(uri)
                if new_uris == [uri]:
                    logger.debug(f"Last attempt, play stream anyway: {uri!r}")
                    return uri
                stream_uris.extend(new_uris)
        logger.debug("TuneIn lookup failed.")
        return None

    def unwrap_stream(self, uri):
        unwrapped_uri, self._stream_info = _unwrap_stream(
            uri,
            timeout=self.backend._timeout,
            scanner=self.backend._scanner,
            requests_session=self.backend._session,
        )
        return unwrapped_uri

    def is_live(self, uri):
        return (
            self._stream_info is not None
            and self._stream_info.uri == uri
            and self._stream_info.playable
            and not self._stream_info.seekable
        )


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
                f"Unwrapping stream from URI ({uri!r}) failed: "
                "playlist referenced itself",
            )
            return None, None
        else:
            seen_uris.add(uri)

        logger.debug(f"Unwrapping stream from URI: {uri!r}")

        try:
            scan_timeout = deadline - time.time()
            if scan_timeout < 0:
                logger.info(
                    f"Unwrapping stream from URI ({uri!r}) failed: "
                    f"timed out in {timeout}ms",
                )
                return None, None
            scan_result = scanner.scan(uri, timeout=scan_timeout)
        except exceptions.ScannerError as exc:
            logger.debug(f"GStreamer failed scanning URI ({uri!r}): {exc}")
            scan_result = None

        if scan_result is not None:
            if scan_result.playable or (
                not scan_result.mime.startswith("text/")
                and not scan_result.mime.startswith("application/")
            ):
                logger.debug(
                    f"Unwrapped potential {scan_result.mime} stream: {uri!r}"
                )
                return uri, scan_result

        download_timeout = deadline - time.time()
        if download_timeout < 0:
            logger.info(
                f"Unwrapping stream from URI ({uri!r}) failed: timed out in {timeout}ms"
            )
            return None, None
        content = http.download(
            requests_session, uri, timeout=download_timeout / 1000
        )

        if content is None:
            logger.info(
                f"Unwrapping stream from URI ({original_uri!r}) failed: "
                f"error downloading URI {uri!r}",
            )
            return None, None

        uris = playlists.parse(content)
        if not uris:
            logger.debug(
                f"Failed parsing URI ({uri!r}) as playlist; "
                "found potential stream.",
            )
            return uri, None

        # TODO Test streams and return first that seems to be playable
        logger.debug(
            f"Parsed playlist ({uri!r}) and found new URI: {uris[0]!r}"
        )
        uri = uris[0]
