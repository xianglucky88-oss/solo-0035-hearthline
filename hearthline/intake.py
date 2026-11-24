from .calibration import parse_calibrations
from .fields import ident, number, obj, rows, unique
from .gate_log import parse_events
from .plant import parse_slots
from .probe_log import parse_readings
from .recipe import parse_recipe


def normalize(value):
    obj(value, 'id horizon_s max_gap_s recipe slots trays events readings calibrations', '炉次包')
    run_id = ident(value['id'], '炉次编号')
    horizon = number(value['horizon_s'], 1, 86400, '炉次时域')
    max_gap = number(value['max_gap_s'], 1, horizon, '最大采样间隔')
    recipe = parse_recipe(value['recipe'], horizon)
    slots = parse_slots(value['slots'], recipe)
    trays = sorted(ident(tray, '料盘编号') for tray in rows(value['trays'], '料盘', 100, 1))
    unique(trays, '料盘编号')
    probes = {slot['probe'] for slot in slots}
    return {'id': run_id, 'horizon_s': horizon, 'max_gap_s': max_gap, 'recipe': recipe,
            'slots': slots, 'trays': trays,
            'events': parse_events(value['events'], horizon, set(trays), {slot['id'] for slot in slots}),
            'readings': parse_readings(value['readings'], horizon, probes),
            'calibrations': parse_calibrations(value['calibrations'], horizon, probes)}
