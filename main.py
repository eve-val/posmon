#!/usr/bin/env python

from evelink.account import Account
from evelink.api import API
from evelink.cache.shelf import ShelveCache
from evelink.corp import Corp
from evelink.map import Map
from sde import SDE, TowerSet
from datetime import datetime

import logging
import sys

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


def process(key, vcode):
    api_key = API(api_key=(key, vcode),
                  cache=ShelveCache('/tmp/eveapi'))
    corp = Corp(api_key)
    sde = SDE()

    my_character = Account(api_key).key_info().result['characters'].values()[0]
    my_alliance = my_character['alliance']['id'] if 'alliance' in my_character else None
    print 'Towers for "%s" corporation' % my_character['corp']['name']

    sov = Map(api_key).sov_by_system().result[0]

    towerset = TowerSet(sde)
    towerset.add_all(corp.starbases().result)
    towerset.enrich(lambda item_id: corp.starbase_details(starbase_id=item_id).result,
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

    r = corp.locations(location_list=towers).result
    towerset.add_mods(r, assets)

    idx = 0
    inc = 100
    while idx < len(modules):
        fetch_subset = modules[idx:idx+inc]
        idx += inc
        r = corp.locations(location_list=fetch_subset).result
        towerset.add_mods(r, assets)

    print towerset.eval_moongoo()

    warnings = towerset.find_warnings()
    if warnings:
        print '!!! WARNINGS !!!'
        for tower in warnings:
            print '%s "%s"' % (towerset._towers[tower].loc, towerset._towers[tower]._name)
            for warning in warnings[tower]:
                print '* %s' % warning

    print '=============================================='

if __name__ == "__main__":
    count = len(sys.argv) - 1
    for value in xrange(1, count, 2):
        process(int(sys.argv[value]), sys.argv[value + 1])
