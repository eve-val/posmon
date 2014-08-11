#!/usr/bin/env python

from evelink.account import Account
from evelink.api import API, APIError
from evelink.cache.shelf import ShelveCache
from evelink.corp import Corp
from evelink.map import Map
from sde import SDE, TowerSet
from datetime import datetime

import ConfigParser
import logging
import sys


def process(api_key):
    corp = Corp(api_key)
    sde = SDE()

    my_character = Account(api_key).key_info().result['characters'].values()[0]
    my_alliance = my_character['alliance']['id'] if 'alliance' in my_character else None
    print 'Towers for "%s" corporation' % my_character['corp']['name']

    sov = Map(api_key).sov_by_system().result[0]

    towerset = TowerSet(sde)
    towerset.add_all(corp.starbases().result)
    def details_cb(item_id):
        try:
            return corp.starbase_details(starbase_id=item_id).result
        except APIError as e:
            if e.code == '114':
                return None
            raise
    towerset.enrich(details_cb,
                    lambda solar_id: solar_id in sov and sov[solar_id]['alliance_id'] == my_alliance,
                    my_alliance)

    modules = []
    towers = []
    assets = {}

    assets_api = corp.assets()
    assets_result = assets_api.result
    assets_timestamp = datetime.utcfromtimestamp(assets_api.timestamp)
    print 'Values cached as of %s (%0.2f hours ago)\n\n' % (
        assets_timestamp,
        (datetime.utcnow() - assets_timestamp).total_seconds() / 3600.)

    for location in assets_result:
        if sde.location(location).type != 'system':
            continue
        for item in assets_result[location]['contents']:
            item_id = item['id']
            if item['item_type_id'] in sde.towers:
                assets[item_id] = item
                towers.append(item_id)
            elif item['item_type_id'] in sde.tower_mods:
                assets[item_id] = item
                modules.append(item_id)

    def add_all_mods(locations):
        for location in locations:
            try:
                r = corp.locations(location_list=[location]).result
                towerset.add_mods(r, assets)
            except APIError as e:
                if e.code == '135':
                    print "strange location: %r" % location
                    continue
                raise
    add_all_mods(towers)
    add_all_mods(modules)

    print towerset.eval_moongoo()

    warnings = towerset.find_warnings()
    if warnings:
        print '!!! WARNINGS !!!'
        for tower in warnings:
            print '%s "%s"' % (towerset._towers[tower].loc, towerset._towers[tower]._name)
            for warning in warnings[tower]:
                print '* %s' % warning

    print '=============================================='

def keys_from_args(args):
    return [(int(args[i]), args[i+1]) for i in range(1, len(args)-1, 2)]

def keys_from_config(filename):
    config = ConfigParser.RawConfigParser()
    config.read(filename)
    return [(config.getint(section, 'keyID'), config.get(section, 'vCode'))
            for section in config.sections() if section.startswith('key:')]

if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

    if len(sys.argv) > 1:
        keys = keys_from_args(sys.argv)
    else:
        keys = keys_from_config('posmon.ini')
    for key_id, vcode in keys:
        api_key = API(api_key=(key_id, vcode),
                      cache=ShelveCache('/tmp/eveapi'))
        process(api_key)
