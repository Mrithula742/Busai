"""Explicit illustrative access and demand assumptions for the presentation planner."""
from copy import deepcopy


def illustrative_predictions(predictions):
    result = deepcopy(predictions)
    result['access_walk_minutes'] = {'SYN_A': 3, 'SYN_A_R': 3, 'SYN_B': 5, 'SYN_B_R': 5, 'SYN_C': 2, 'SYN_C_R': 2}
    result['scenario_demand'] = {'SYN_A': .65, 'SYN_A_R': .65, 'SYN_B': 1.2, 'SYN_B_R': 1.2, 'SYN_C': .8, 'SYN_C_R': .8}
    return result
