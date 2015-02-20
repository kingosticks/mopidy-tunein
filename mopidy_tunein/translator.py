from __future__ import unicode_literals

import logging
import re
import urllib

from mopidy.models import Album, Artist, Ref, Track

logger = logging.getLogger(__name__)

TUNEIN_API_ENCODING = 'utf-8'

TUNEIN_ID_PROGRAM = 'program'
TUNEIN_ID_STATION = 'station'
TUNEIN_ID_GROUP = 'group'
TUNEIN_ID_TOPIC = 'topic'
TUNEIN_ID_CATEGORY = 'category'
TUNEIN_ID_REGION = 'region'
TUNEIN_ID_PODCAST = 'podcast_category'
TUNEIN_ID_AFFILIATE = 'affiliate'
TUNEIN_ID_STREAM = 'stream'
TUNEIN_ID_UNKNOWN = 'unknown'


def unparse_uri(variant, identifier):
    return b'tunein:%s:%s' % (variant, identifier)


def parse_uri(uri):
    result = re.findall(r'^tunein:([a-z]+)(?::(\w+))?$', uri)
    if result:
        return result[0]
    return None, None


def station_to_ref(station):
    if station['type'] != 'audio':
        logger.debug('Expecting station but got %s' % station['type'])
    guide_id = station.get('guide_id', '??')
    uri = unparse_uri('station', guide_id)
    name = station.get('text', station['URL'])
    # TODO: Should the name include 'now playing' for all stations?
    if get_id_type(guide_id) == TUNEIN_ID_TOPIC:
        name = name + ' [%s]' % station.get('subtext', '??')
    return Ref.track(uri=uri, name=name)


def station_to_track(station):
    ref = station_to_ref(station)
    return Track(uri=ref.uri,
                 name=ref.name,
                 album=Album(name=ref.name,
                             uri=ref.uri,
                             images=[station.get('image')]),
                 artists=[Artist(name=station.get('subtext', ''))])


def show_to_ref(show):
    if show['item'] != 'show':
        logger.debug('Expecting show but got %s' % show['item'])
    uri = unparse_uri('episodes', show.get('guide_id', '??'))
    name = show.get('text', show['URL'])
    return Ref.directory(uri=uri, name=name)


def category_to_ref(category):
    uri = unparse_uri('category', category['key'])
    return Ref.directory(uri=uri, name=category['text'])


def section_to_ref(section, identifier=''):
    if section.get('type', 'link') == 'audio':
        return station_to_ref(section)
    guide_id = section.get('guide_id', '??')
    if get_id_type(guide_id) == TUNEIN_ID_REGION or identifier == 'local':
        uri = unparse_uri('location', guide_id)
    else:
        uri = unparse_uri('section', guide_id)
    return Ref.directory(uri=uri, name=section['text'])


def get_id_type(guide_id):
    return {'p': TUNEIN_ID_PROGRAM,
            's': TUNEIN_ID_STATION,
            'g': TUNEIN_ID_GROUP,
            't': TUNEIN_ID_TOPIC,
            'c': TUNEIN_ID_CATEGORY,
            'r': TUNEIN_ID_REGION,
            'f': TUNEIN_ID_PODCAST,
            'a': TUNEIN_ID_AFFILIATE,
            'e': TUNEIN_ID_STREAM}.get(guide_id[0], TUNEIN_ID_UNKNOWN)


def mopidy_to_tunein_query(mopidy_query):
    tunein_query = []
    for (field, values) in mopidy_query.iteritems():
        if not hasattr(values, '__iter__'):
            values = [values]
        for value in values:
            if field == 'any':
                tunein_query.append(value)
    query = ' '.join(tunein_query).encode(TUNEIN_API_ENCODING)
    return urllib.pathname2url(query)
