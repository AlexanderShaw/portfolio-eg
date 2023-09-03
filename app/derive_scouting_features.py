import pandas as pd
import numpy as np
import bisect

def round_down_in_list(x, _list):
    """
    Rounds down an integer x to a number in _list using binary search.
    """
    sorted_list = sorted(_list)
    i = bisect.bisect_right(sorted_list,x)
    return sorted_list[i-1]


def find_plateau(_list, threshold):
    """
    This function finds the value of the first non-zero plateau of *threshold* many numbers in a row in a list.
    """
    j = 0
    i = 0
    while i < threshold:
        hp_from_death = _list
        if hp_from_death[j] == hp_from_death[j+1] and hp_from_death[j] != 0:
            i += 1
        else:
            i = 0
        j += 1

    return hp_from_death[j]


def kill_does_not_matter(x, bomb_event, frame_player):
    """ Input is a row of a DF and the corresponding bomb_event and frame_player dataframe.
    This function decides if a kill (x) matters by the following logic:
    first three conditions: kill after bomb placed
    last two conditions: attacker and victim not in bombsite."""
    bombrounds = list(bomb_event.loc[bomb_event.bomb_action == 'plant'].round_num)
    
    if x.round_num in bombrounds:
        bombsite = 'Bombsite'+bomb_event.loc[(bomb_event.round_num == x.round_num) & (bomb_event.bomb_action == 'plant')].bomb_site.iloc[0]
        bombtick = bomb_event.loc[(bomb_event.round_num == x.round_num) & (bomb_event.bomb_action == 'plant')].tick.iloc[0]
        if (bombtick <= x.tick 
            and x.tick <= max(frame_player.loc[frame_player.round_num == x.round_num].tick)
            and x.attacker_area_name != bombsite
            and x.victim_area_name != bombsite): 
            
            return 1 # kill does NOT matter
        else:
            return 0
    else:
        return 0
    
def damage_done_before_death(x, damage):
    """
    This function computes the damage done approximately 3 sec before a death,
    where x is a row in a kill table."""
    dmg = damage.loc[(damage.attacker_name == x.victim_name) & 
          (damage.tick < x.tick + 128 * 3) &
          (damage.tick > x.tick - 128 * 3)].hp_damage_taken.sum() + damage.loc[(damage.attacker_name == x.victim_name) & 
          (damage.tick < x.tick + 128 * 3) &
          (damage.tick > x.tick - 128 * 3)].armor_damage_taken.sum()
    
    return dmg

def damage_taken(x, damage):
    """
    This function computes the damage done approximately 3 sec before a death,
    where x is a row in a kill table."""
    dmg = damage.loc[(damage.victim_name == x.victim_name) & 
          (damage.tick < x.tick + 128 * 3) &
          (damage.tick > x.tick - 128 * 3)].hp_damage_taken.sum() + damage.loc[(damage.victim_name == x.victim_name) & 
          (damage.tick < x.tick + 128 * 3) &
          (damage.tick > x.tick - 128 * 3)].armor_damage_taken.sum()
    
    return dmg
    

def add_kill_features(kill, bomb_event, frame_player, damage):
    """This function adds the following three features
    to the kill dataframe, using the bomb_event and frame_player
    data from the same match:
    victim_equipment_value
    victim_hp
    high_health_kill (1 if victim had > 75 hp)
    kill_does_not_matter (1 if kill occurs after plant,
        and away from bombsite)"""
    # Make DF with kill value in each column
    kills_renamed = kill.rename(columns = {'attacker_name' : 'name'})
    kills_renamed['tick'] = [round_down_in_list(x, list(frame_player.tick)) for x in list(kill.tick)]
    dff = pd.merge(kills_renamed, frame_player, on=['name', 'tick'])
    kill['victim_equipment_value'] = dff['equipment_value_freezetime_end']

    kills_renamed = kill.rename(columns = {'victim_name' : 'name'})
    kill['victim_hp'] = [
        find_plateau(
            list(frame_player[(frame_player.name == name) & (frame_player.tick < tick)].hp)[::-1],
            5
        )
        for tick, name in zip(list(kill.tick), list(kill.victim_name))]

    kill['high_health_kill'] = np.where(kill.victim_hp > 75 , 1 , 0)

    kill['kill_does_not_matter'] = kill.apply(lambda x: kill_does_not_matter(x, bomb_event, frame_player), axis=1)

    kill['damage_done_before_death'] = kill.apply(lambda x: damage_done_before_death(x, damage), axis=1)