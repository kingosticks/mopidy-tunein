import logging
import re
from urllib import request

from mopidy.models import Album, Artist, Image, Ref, Track

from mopidy_tunein.tunein import TuneIn

logger = logging.getLogger(__name__)


def unparse_uri(variant, identifier):
    return f"tunein:{variant}:{identifier}"


def parse_uri(uri):
    result = re.findall(r"^tunein:([a-z]+)(?::(\w+))?$", uri)
    if result:
        return result[0]
    return None, None


def station_to_ref(station):
    if station["type"] != "audio":
        logger.debug(f'Expecting station but got {station["type"]}')
    guide_id = station.get("guide_id", "??")
    uri = unparse_uri("station", guide_id)
    name = station.get("text", station["URL"])
    # TODO: Should the name include 'now playing' for all stations?
    if get_id_type(guide_id) == TuneIn.ID_TOPIC:
        name = f'{name} [{station.get("subtext", "??")}]'
    return Ref.track(uri=uri, name=name)


def station_to_track(station):
    ref = station_to_ref(station)
    return Track(
        uri=ref.uri,
        name=station.get("subtext", ref.name),
        album=Album(name=ref.name, uri=ref.uri),
        artists=[Artist(name=ref.name, uri=ref.uri)],
    )


def station_to_image(station):
    if station is not None and "image" in station:
        return Image(uri=station["image"])


def show_to_ref(show):
    if show["item"] != "show":
        logger.debug(f'Expecting show but got {show["item"]}')
    uri = unparse_uri("episodes", show.get("guide_id", "??"))
    name = show.get("text", show["URL"])
    return Ref.directory(uri=uri, name=name)


def category_to_ref(category):
    uri = unparse_uri("category", category["key"])
    return Ref.directory(uri=uri, name=category["text"])


def section_to_ref(section, identifier=""):
    if section.get("type", "link") == "audio":
        return station_to_ref(section)
    guide_id = section.get("guide_id", "??")
    if get_id_type(guide_id) == TuneIn.ID_REGION or identifier == "local":
        uri = unparse_uri("location", guide_id)
    else:
        uri = unparse_uri("section", guide_id)
    return Ref.directory(uri=uri, name=section["text"])


def get_id_type(guide_id):
    return {
        "p": TuneIn.ID_PROGRAM,
        "s": TuneIn.ID_STATION,
        "g": TuneIn.ID_GROUP,
        "t": TuneIn.ID_TOPIC,
        "c": TuneIn.ID_CATEGORY,
        "r": TuneIn.ID_REGION,
        "f": TuneIn.ID_PODCAST,
        "a": TuneIn.ID_AFFILIATE,
        "e": TuneIn.ID_STREAM,
    }.get(guide_id[0], TuneIn.ID_UNKNOWN)


def mopidy_to_tunein_query(mopidy_query):
    tunein_query = []
    for (field, values) in mopidy_query.items():
        for value in values:
            if field == "any":
                tunein_query.append(value)
    query = " ".join(tunein_query)
    return request.pathname2url(query)
