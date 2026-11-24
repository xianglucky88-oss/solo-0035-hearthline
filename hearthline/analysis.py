from collections import defaultdict

from .calibration import apply_calibrations
from .occupancy import collisions
from .residency import reconstruct
from .stage import evaluate
from .telemetry import probe_segments
from .window import ProbeTimeline


ENGINE = 'hearthline-v1'


def analyze(source):
    visits, issues, unresolved = reconstruct(source['trays'], source['events'], source['horizon_s'])
    conflicts = collisions(visits, unresolved)
    by_tray = defaultdict(list)
    for conflict in conflicts:
        for tray in conflict['trays']:
            by_tray[tray].append(conflict)
    slots = {slot['id']: slot for slot in source['slots']}
    recipes = {stage['zone']: stage for stage in source['recipe']['stages']}
    raw = probe_segments(source['readings'], source['max_gap_s'])
    normalized = apply_calibrations(raw, source['calibrations'])
    clocks = {slot['probe']: ProbeTimeline(normalized.get(slot['probe'], [])) for slot in slots.values()}
    trays = []
    for tray in source['trays']:
        stages = []
        for visit in visits[tray]:
            slot = slots[visit['slot']]
            stages.append(evaluate(visit, recipes[slot['zone']], clocks[slot['probe']]))
        itinerary = [stage['zone'] for stage in stages]
        if itinerary != list(recipes):
            issues[tray].append({'reason': 'itinerary', 'expected': list(recipes), 'observed': itinerary,
                                 'sources': [ref for stage in stages for ref in stage['sources']]})
        if by_tray[tray]:
            issues[tray].append({'reason': 'collision', 'conflicts': by_tray[tray]})
        state = 'blocked' if issues[tray] else 'ready'
        if state == 'ready' and any(stage['state'] != 'qualified' for stage in stages):
            state = 'inspect'
        trays.append({'id': tray, 'state': state, 'issues': issues[tray], 'stages': stages})
    return {'id': source['id'], 'engine': ENGINE, 'horizon_s': source['horizon_s'],
            'recipe': source['recipe']['id'], 'slots': source['slots'], 'trays': trays, 'conflicts': conflicts}
