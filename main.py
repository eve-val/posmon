#!/usr/bin/env python

from evelink.account import Account
from evelink.api import API, APIError
from evelink.cache.shelf import ShelveCache
from evelink.corp import Corp
from evelink.map import Map
from sde import initialize as sde_initialize, SDE, TowerSet, Location
from datetime import datetime

import ConfigParser
import json
import logging
import sys


def process(api_key, format='text', config=None):
    sde = SDE()
    config = tower_config(config)
    character, cache_ts, towerset = pull_pos_info(sde, api_key, config)
    if format == 'text':
        output_text(character, cache_ts, towerset)
    elif format == 'json':
        output_json(sde, character, cache_ts, towerset)


def output_text(character, cache_ts, towerset):
    print 'Towers for "%s" corporation' % character['corp']['name']
    print 'Values cached as of %s (%0.2f hours ago)\n\n' % (
        cache_ts,
        (datetime.utcnow() - cache_ts).total_seconds() / 3600.)

    print towerset.eval_moongoo()

    warnings = towerset.find_warnings()
    if warnings:
        print '!!! WARNINGS !!!'
        for tower in warnings:
            print '%s "%s"' % (towerset._towers[tower].loc, towerset._towers[tower]._name)
            for warning in warnings[tower]:
                print '* %s' % warning

    print '=============================================='


def output_json(sde, character, cache_ts, towerset):
    output = {}

    output['corporation'] = character['corp']['name']
    output['cache_ts'] = str(cache_ts)
    output['towers'] = []
    for tower_data in towerset._towers.itervalues():
        tower = {}
        output['towers'].append(tower)

        tower['type_id'] = tower_data._type_id
        tower['type_name'] = tower_data._type_name
        tower['location'] = {
            'region_id': tower_data.loc._region_id,
            'region_name': tower_data.loc.region,
            'system_id': tower_data.loc._system_id,
            'system_name': tower_data.loc.system,
        }
        if tower_data.loc.type == 'orbit':
            tower['location']['orbit_id'] = tower_data.loc._orbit_id
            tower['location']['orbit_name'] = tower_data.loc.orbit
        tower['fuel'] = tower_data._fuel
        tower['stront'] = tower_data._stront
        tower['fuel_per_hour'] = tower_data._fph
        tower['stront_per_hour'] = tower_data._sph
        tower['name'] = tower_data._name
        tower['moongoo_mods'] = []
        for mod_id, mod_data in tower_data._mods.iteritems():
            if mod_id not in tower_data._moongoo_mods:
                continue
            mod = {}
            tower['moongoo_mods'].append(mod)

            mod['type_id'] = mod_data._type_id
            mod['type_name'] = sde.typename(mod['type_id'])
            mod['capacity'] = mod_data._capacity
            mod['contents'] = []
            for type_id, quantity in mod_data._contents:
                mod['contents'].append({
                    'type_id': type_id,
                    'type_name': sde.typename(type_id),
                    'type_volume': sde.volume(type_id),
                    'quantity': quantity,
                })
        tower['warnings'] = tower_data._warnings

    print json.dumps(output)


def pull_pos_info(sde, api_key, config):
    corp = Corp(api_key)

    my_character = Account(api_key).key_info().result['characters'].values()[0]
    my_alliance = my_character['alliance']['id'] if 'alliance' in my_character else None
    logging.info('Fetching info for "%s" corporation' % my_character['corp']['name'])

    sov = Map(api_key).sov_by_system().result[0]

    towerset = TowerSet(sde, config)
    towerset.add_all(corp.starbases().result)

    def details_cb(item_id):
        try:
            return corp.starbase_details(starbase_id=item_id).result
        except APIError as e:
            if e.code == '114':
                return None
            raise
    towerset.enrich(details_cb,
                    lambda solar_id: (solar_id in sov and
                                      sov[solar_id]['alliance_id'] == my_alliance),
                    my_alliance)

    modules = []
    towers = []
    assets = {}

    assets_api = corp.assets()
    assets_result = assets_api.result
    assets_timestamp = datetime.utcfromtimestamp(assets_api.timestamp)

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
        if not locations:
            return
        try:
            r = corp.locations(location_list=locations).result
            towerset.add_mods(r, assets)
        except APIError as e:
            # 135: Owner is not the owner of all itemIDs or a non-existant itemID was passed in. If you are not trying to scrape the API, please ensure your input are valid locations associated with the key owner.
            if e.code == '135':
                if len(locations) == 1:
                    logging.warn("strange location: %r" % locations[0])
                else:
                    # recurse until we've got all the locations we *can* get
                    mid = len(locations) // 2
                    add_all_mods(locations[:mid])
                    add_all_mods(locations[mid:])
            else:
                raise
    add_all_mods(towers)
    for chunk in range(0, len(modules), 100):
        add_all_mods(modules[chunk:chunk+100])

    return my_character, assets_timestamp, towerset


def tower_config(config):
    res = dict()
    for section in config.sections():
        if not section.startswith("tower:"):
            continue

        tower = section[6:]
        sect = dict()
        for k,v in config.items(section):
            if v.lower() == "true":
                v = True
            elif v.lower() == "false":
                v = False
            try:
                v = float(v)
            except ValueError:
                pass
            sect[k] = v

        if tower == "default":
            res[tower] = sect
            continue
        l = Location(location_string=tower)
        res[l._location_id] = sect

    return res


def keys_from_args(args):
    return [(int(args[i]), args[i+1]) for i in range(1, len(args)-1, 2)]


def keys_from_config(config):
    return [(config.getint(section, 'keyID'), config.get(section, 'vCode'))
            for section in config.sections() if section.startswith('key:')]

if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

    config = ConfigParser.RawConfigParser()
    config.read('posmon.ini')

    print config.get('posmon', 'sde_db_uri')
    sde_initialize(config.get('posmon', 'sde_db_uri'))

    if len(sys.argv) > 1:
        keys = keys_from_args(sys.argv)
    else:
        keys = keys_from_config(config)
    for key_id, vcode in keys:
        api_key = API(api_key=(key_id, vcode),
                      cache=ShelveCache('/tmp/eveapi'))
        if len(sys.argv) > 1:
            process(api_key, format=sys.argv[1], config=config)
        else:
            process(api_key, config=config)
