import configparser
import io
import logging
import re
import time
import xml.etree.ElementTree as elementtree  # noqa: N813
from collections import OrderedDict
from contextlib import closing
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


class PlaylistError(Exception):
    pass


class cache:  # noqa N801
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
                if self._call_count > self.ctl or age > self.ttl:
                    self._call_count = 0
                    raise AttributeError
                if self.ctl:
                    self._call_count += 1
                return value

            except (KeyError, AttributeError):
                value = func(*args)
                if value:
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
    for line in data.splitlines():
        if not line.strip() or line.startswith(b"#"):
            continue

        try:
            line = line.decode()
        except UnicodeDecodeError:
            continue

        yield line.strip()


def parse_pls(data):
    # Copied from mopidy.audio.playlists
    try:
        cp = configparser.RawConfigParser(strict=False)
        cp.read_string(data.decode())
    except configparser.Error:
        return

    for section in cp.sections():
        if section.lower() != "playlist":
            continue
        for i in range(cp.getint(section, "numberofentries")):
            try:
                # TODO: Remove this horrible hack to avoid adverts
                if cp.has_option(section, f"length{i + 1}"):
                    if cp.get(section, f"length{i + 1}") == "-1":
                        yield cp.get(section, f"file{i + 1}").strip("\"'")
                else:
                    yield cp.get(section, f"file{i + 1}").strip("\"'")
            except configparser.NoOptionError:
                return


def fix_asf_uri(uri):
    return re.sub(r"http://(.+\?mswmext=\.asf)", r"mms://\1", uri, flags=re.I)


def parse_old_asx(data):
    try:
        cp = configparser.RawConfigParser()
        cp.read_string(data.decode())
    except configparser.Error:
        return

    for section in cp.sections():
        if section.lower() != "reference":
            continue
        for option in cp.options(section):
            if option.lower().startswith("ref"):
                uri = cp.get(section, option).lower()
                yield fix_asf_uri(uri.strip())


def parse_new_asx(data):
    # Copied from mopidy.audio.playlists
    try:
        # Last element will be root.
        for _event, element in elementtree.iterparse(io.BytesIO(data)):
            element.tag = element.tag.lower()  # normalize
    except elementtree.ParseError:
        return

    for ref in element.findall("entry/ref[@href]"):
        yield fix_asf_uri(ref.get("href", "").strip())

    for entry in element.findall("entry[@href]"):
        yield fix_asf_uri(entry.get("href", "").strip())


def parse_asx(data):
    if b"asx" in data[0:50].lower():
        return parse_new_asx(data)
    else:
        return parse_old_asx(data)


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
    extension_map = {
        ".asx": parse_asx,
        ".wax": parse_asx,
        ".m3u": parse_m3u,
        ".pls": parse_pls,
    }
    content_type_map = {
        "video/x-ms-asf": parse_asx,
        "application/x-mpegurl": parse_m3u,
        "audio/x-scpls": parse_pls,
    }

    parser = extension_map.get(extension, None)
    if not parser and content_type:
        # Annoying case where the url gave us no hints so try and work it out
        # from the header's content-type instead.
        # This might turn out to be server-specific...
        parser = content_type_map.get(content_type.lower(), None)
    return parser


class TuneIn:
    """Wrapper for the TuneIn API."""

    ID_PROGRAM = "program"
    ID_STATION = "station"
    ID_GROUP = "group"
    ID_TOPIC = "topic"
    ID_CATEGORY = "category"
    ID_REGION = "region"
    ID_PODCAST = "podcast_category"
    ID_AFFILIATE = "affiliate"
    ID_STREAM = "stream"
    ID_UNKNOWN = "unknown"

    def __init__(self, timeout, filter_=None, session=None):
        self._base_uri = "https://opml.radiotime.com/%s"
        self._session = session or requests.Session()
        self._timeout = timeout / 1000.0
        if filter_ in [TuneIn.ID_PROGRAM, TuneIn.ID_STATION]:
            self._filter = f"&filter={filter_[0]}"
        else:
            self._filter = ""
        self._stations = {}

    def reload(self):
        self._stations.clear()
        self._tunein.clear()
        self._get_playlist.clear()

    def _flatten(self, data):
        results = []
        for item in data:
            if "children" in item:
                results.extend(item["children"])
            else:
                results.append(item)
        return results

    def _filter_results(self, data, section_name=None, map_func=None):
        results = []

        def grab_item(item):
            if "guide_id" not in item:
                return
            if map_func:
                station = map_func(item)
            elif item.get("type", "link") == "link":
                results.append(item)
                return
            else:
                station = item
            self._stations[station["guide_id"]] = station
            results.append(station)

        for item in data:
            if section_name is not None:
                section_key = item.get("key", "").lower()
                if section_key.startswith(section_name.lower()):
                    for child in item["children"]:
                        grab_item(child)
            else:
                grab_item(item)
        return results

    def categories(self, category=""):
        if category == "location":
            args = "&id=r0"  # Annoying special case
        elif category == "language":
            args = "&c=lang"
            return []  # TuneIn's API is a mess here, cba
        else:
            args = "&c=" + category

        # Take a copy so we don't modify the cached data
        results = list(self._tunein("Browse.ashx", args))
        if category in ("podcast", "local"):
            # Flatten the results!
            results = self._filter_results(self._flatten(results))
        elif category == "":
            trending = {
                "text": "Trending",
                "key": "trending",
                "type": "link",
                "URL": self._base_uri % "Browse.ashx?c=trending",
            }
            # Filter out the language root category for now
            results = [x for x in results if x["key"] != "language"]
            results.append(trending)
        else:
            results = self._filter_results(results)
        return results

    def locations(self, location):
        args = "&id=" + location
        results = self._tunein("Browse.ashx", args)
        # TODO: Support filters here
        return [x for x in results if x.get("type", "") == "link"]

    def _browse(self, section_name, guide_id):
        args = "&id=" + guide_id
        results = self._tunein("Browse.ashx", args)
        return self._filter_results(results, section_name)

    def featured(self, guide_id):
        return self._browse("Featured", guide_id)

    def local(self, guide_id):
        return self._browse("Local", guide_id)

    def stations(self, guide_id):
        return self._browse("Station", guide_id)

    def related(self, guide_id):
        return self._browse("Related", guide_id)

    def shows(self, guide_id):
        return self._browse("Show", guide_id)

    def episodes(self, guide_id):
        args = f"&c=pbrowse&id={guide_id}"
        results = self._tunein("Tune.ashx", args)
        return self._filter_results(results, "Topic")

    def _map_listing(self, listing):
        # We've already checked 'guide_id' exists
        url_args = f'Tune.ashx?id={listing["guide_id"]}'
        return {
            "text": listing.get("name", "???"),
            "guide_id": listing["guide_id"],
            "type": "audio",
            "image": listing.get("logo", ""),
            "subtext": listing.get("slogan", ""),
            "URL": self._base_uri % url_args,
        }

    def _station_info(self, station_id):
        logger.debug(f"Fetching info for station {station_id}")
        args = f"&c=composite&detail=listing&id={station_id}"
        results = self._tunein("Describe.ashx", args)
        listings = self._filter_results(results, "Listing", self._map_listing)
        if listings:
            return listings[0]

    def parse_stream_url(self, url):
        logger.debug(f"Extracting URIs from {url!r}")
        extension = urlparse(url).path[-4:]
        if extension in [".mp3", ".wma"]:
            return [url]  # Catch these easy ones
        results = []
        playlist_data, content_type = self._get_playlist(url)
        if playlist_data:
            parser = find_playlist_parser(extension, content_type)
            if parser:
                try:
                    results = [
                        u for u in parser(playlist_data) if u and u != url
                    ]
                except Exception as e:
                    logger.error(f"TuneIn playlist parsing failed {e}")
                if not results:
                    playlist_str = playlist_data.decode(errors="ignore")
                    logger.debug(
                        f"Parsing failure, malformed playlist: {playlist_str}"
                    )
        elif content_type:
            results = [url]
        logger.debug(f"Got {results}")
        return list(OrderedDict.fromkeys(results))

    def tune(self, station):
        logger.debug(f'Tuning station id {station["guide_id"]}')
        args = f'&id={station["guide_id"]}'
        stream_uris = []
        for stream in self._tunein("Tune.ashx", args):
            if "url" in stream:
                stream_uris.append(stream["url"])
        if not stream_uris:
            logger.error(f'Failed to tune station id {station["guide_id"]}')
        return list(OrderedDict.fromkeys(stream_uris))

    def station(self, station_id):
        if station_id in self._stations:
            station = self._stations[station_id]
        else:
            station = self._station_info(station_id)
            self._stations["station_id"] = station
        return station

    def search(self, query):
        # "Search.ashx?query=" + query + filterVal
        if not query:
            logger.debug("Empty search query")
            return []
        logger.debug(f"Searching TuneIn for '{query}'")
        args = f"&query={query}{self._filter}"
        search_results = self._tunein("Search.ashx", args)
        results = []
        for item in self._flatten(search_results):
            if item.get("type", "") == "audio":
                # Only return stations
                self._stations[item["guide_id"]] = item
                results.append(item)

        return results

    @cache()
    def _tunein(self, variant, args):
        uri = (self._base_uri % variant) + f"?render=json{args}"
        logger.debug(f"TuneIn request: {uri!r}")
        try:
            with closing(self._session.get(uri, timeout=self._timeout)) as r:
                r.raise_for_status()
                return r.json()["body"]
        except Exception as e:
            logger.info(f"TuneIn API request for {variant} failed: {e}")
        return {}

    @cache()
    def _get_playlist(self, uri):
        data, content_type = None, None
        try:
            # Defer downloading the body until know it's not a stream
            with closing(
                self._session.get(uri, timeout=self._timeout, stream=True)
            ) as r:
                r.raise_for_status()
                content_type = r.headers.get("content-type", "audio/mpeg")
                logger.debug(f"{uri} has content-type: {content_type}")
                if content_type != "audio/mpeg":
                    data = r.content
        except Exception as e:
            logger.info(f"TuneIn playlist request for {uri} failed: {e}")
        return (data, content_type)
