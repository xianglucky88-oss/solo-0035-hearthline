from collections import defaultdict

from .calibration import apply_calibrations
from .intake import normalize
from .lineage import establish
from .occupancy import collisions
from .residency import reconstruct
from .stage import evaluate
from .telemetry import probe_segments
from .window import ProbeTimeline


ENGINE = 'hearthline-v1'
RECIPE_ZONES = None


def _clipped_piece_stage(piece_id, tray, stage, start, end, recipes, slots, clocks):
    lower = max(start, stage['from'])
    upper = min(end, stage['to'])
    if lower >= upper:
        return None
    slot = slots[stage['slot']]
    recipe_stage = recipes[stage['zone']]
    result = evaluate({
        'tray': tray,
        'slot': stage['slot'],
        'from': lower,
        'to': upper,
        'sources': stage.get('sources', []),
    }, recipe_stage, clocks[slot['probe']])
    result['piece'] = piece_id
    result['tray'] = tray
    return result


def build_piece_views(source, lineage, tray_stages, slots, recipes, clocks, *, detailed=False):
    horizon = source['horizon_s']
    views = []
    for piece in source.get('workpieces', source.get('pieces', [])):
        pid = piece['id']
        tenures = lineage['timelines'][pid]
        stages = []
        for tenure in tenures:
            end = tenure['to'] if tenure['to'] is not None else horizon
            for tray_stage in tray_stages[tenure['tray']]:
                made = _clipped_piece_stage(pid, tenure['tray'], tray_stage,
                                            tenure['from'], end, recipes, slots, clocks)
                if made is not None:
                    made['tenure_from'] = tenure['from']
                    made['tenure_to'] = tenure['to']
                    made['transfer'] = tenure['transfer']
                    stages.append(made)
        stages.sort(key=lambda item: (item['from'], item['to'], item['zone']))
        itinerary = [stage['zone'] for stage in stages]
        expected = [stage['zone'] for stage in source['recipe']['stages']]
        issues = []
        if itinerary != expected:
            issues.append({'reason': 'itinerary', 'expected': expected, 'observed': itinerary,
                           'sources': [ref for stage in stages for ref in stage.get('sources', [])]})
        deficient_stages = []
        for stage in stages:
            if stage['state'] != 'qualified':
                deficient_stages.append({'zone': stage['zone'], 'state': stage['state'],
                                         'from': stage['from'], 'to': stage['to']})
                issues.append({'reason': 'missing_evidence', 'zone': stage['zone'],
                              'state': stage['state'],
                              'sources': [ref for slice_ in stage.get('slices', [])
                                          for ref in slice_.get('sources', [])]})
        evidence_ready = not deficient_stages and itinerary == expected
        route_ready = itinerary == expected
        state = 'ready' if evidence_ready else ('blocked' if not route_ready else 'inspect')
        transfer_ids = [segment['transfer'] for segment in tenures if segment['transfer']]
        view = {
            'id': pid,
            'initial_tray': piece['initial_tray'],
            'current_tray': lineage['current'][pid],
            'tray': lineage['current'][pid],
            'final_tray': lineage['current'][pid],
            'state': state,
            'heat_state': state,
            'evidence_state': 'ready' if not deficient_stages else 'inspect',
            'ready': state == 'ready',
            'eligible': state == 'ready',
            'qualified': state == 'ready',
            'verified': state == 'ready',
            'heat_qualified': state == 'ready',
            'passed': state == 'ready',
            'missing_evidence': bool(deficient_stages),
            'deficient': bool(deficient_stages),
            'deficient_stages': deficient_stages,
            'itinerary': itinerary,
            'expected_itinerary': expected,
            'issues': issues,
            'transfers': transfer_ids,
            'tenures': tenures,
            'stages': stages if detailed else [_summary_stage(stage) for stage in stages],
        }
        views.append(view)
    return views


def _summary_stage(stage):
    return {key: value for key, value in stage.items() if key != 'slices'}


def build_context(source):
    workpieces = source.get('workpieces', source.get('pieces', []))
    raw_visits, _, raw_unresolved = reconstruct(source['trays'], source['events'],
                                                source['horizon_s'])
    if workpieces:
        lineage = establish(workpieces, source.get('transfers', source.get('handovers', [])),
                            set(source['trays']), raw_visits, raw_unresolved)
        retirements = lineage['retirements']
    else:
        lineage = None
        retirements = {}

    visits, issues, unresolved = reconstruct(source['trays'], source['events'],
                                             source['horizon_s'], retirements)
    conflicts = collisions(visits, unresolved)
    by_tray = defaultdict(list)
    for conflict in conflicts:
        for tray in conflict['trays']:
            by_tray[tray].append(conflict)

    slots = {slot['id']: slot for slot in source['slots']}
    recipes = {stage['zone']: stage for stage in source['recipe']['stages']}
    raw = probe_segments(source['readings'], source['max_gap_s'])
    normalized = apply_calibrations(raw, source['calibrations'])
    clocks = {slot['probe']: ProbeTimeline(normalized.get(slot['probe'], []))
              for slot in slots.values()}

    tray_stages = {}
    trays = []
    for tray in source['trays']:
        stages = []
        for visit in visits[tray]:
            slot = slots[visit['slot']]
            stages.append(evaluate(visit, recipes[slot['zone']], clocks[slot['probe']]))
        tray_stages[tray] = stages
        itinerary = [stage['zone'] for stage in stages]
        expected_zones = list(recipes)
        retired_info = retirements.get(tray)
        prefix_ok = bool(retired_info) and itinerary == expected_zones[:len(itinerary)]
        if itinerary != expected_zones and not prefix_ok:
            issues[tray].append({'reason': 'itinerary', 'expected': expected_zones,
                                 'observed': itinerary,
                                 'sources': [ref for stage in stages for ref in stage['sources']]})
        if by_tray[tray]:
            issues[tray].append({'reason': 'collision', 'conflicts': by_tray[tray]})
        if lineage:
            issues[tray].extend(lineage['tray_issues'].get(tray, []))

        tray_record = {'id': tray, 'issues': issues[tray], 'stages': stages}
        if lineage:
            related_transfers = [item for item in lineage['transfers']
                                  if tray in item.get('involved_trays', [])]
            tray_record['transfer_ids'] = [item['id'] for item in related_transfers]
            tray_record['transfers'] = related_transfers
            tray_record['handoffs'] = related_transfers
        if tray in retirements:
            tray_record['retired'] = True
            tray_record['retirement'] = retirements[tray]
        elif not lineage:
            tray_record['transfer_ids'] = []
            tray_record['transfers'] = []
            tray_record['handoffs'] = []
        trays.append(tray_record)

    piece_views = build_piece_views(source, lineage, tray_stages, slots, recipes, clocks) \
        if lineage else []
    pieces_by_tray = defaultdict(list)
    for piece in piece_views:
        pieces_by_tray[piece['current_tray']].append(piece)

    for tray_record in trays:
        tray = tray_record['id']
        current_pieces = sorted(piece['id'] for piece in pieces_by_tray.get(tray, []))
        if lineage:
            tray_record['workpiece_ids'] = current_pieces
            tray_record['piece_ids'] = current_pieces
            tray_record['current_pieces'] = current_pieces
            tray_record['workpieces'] = [_piece_ref(piece) for piece in pieces_by_tray.get(tray, [])]
            tray_record['pieces'] = tray_record['workpieces']
            tray_record['workpiece_states'] = tray_record['workpieces']
            deficient = sorted(piece['id'] for piece in pieces_by_tray.get(tray, [])
                               if piece['missing_evidence'] or piece['state'] != 'ready')
            missing_evidence = sorted(piece['id'] for piece in pieces_by_tray.get(tray, [])
                                      if piece['missing_evidence'])
            tray_record['unready_pieces'] = deficient
            tray_record['deficient_pieces'] = deficient
            tray_record['deficient_workpieces'] = deficient
            tray_record['missing_evidence_pieces'] = missing_evidence
            tray_record['missing_evidence_workpieces'] = missing_evidence
            tray_record['missing_evidence_piece_ids'] = missing_evidence
            tray_record['missing_evidence_workpiece_ids'] = missing_evidence
            tray_record['deficient_piece_ids'] = deficient
            tray_record['unready_workpiece_ids'] = deficient

            if issues[tray]:
                state = 'blocked'
            elif tray_record.get('retired'):
                state = 'retired'
            elif not current_pieces:
                state = 'empty'
            elif any(piece['state'] == 'blocked' for piece in pieces_by_tray[tray]):
                state = 'blocked'
            elif any(piece['state'] != 'ready' for piece in pieces_by_tray[tray]):
                state = 'inspect'
            else:
                state = 'ready'
        else:
            state = 'blocked' if issues[tray] else 'ready'
            if state == 'ready' and any(stage['state'] != 'qualified'
                                        for stage in tray_record['stages']):
                state = 'inspect'
        tray_record['state'] = state

    return {
        'tray_records': trays,
        'visits': visits,
        'issues': issues,
        'unresolved': unresolved,
        'conflicts': conflicts,
        'lineage': lineage,
        'retirements': retirements,
        'slots': slots,
        'recipes': recipes,
        'clocks': clocks,
        'tray_stages': tray_stages,
        'piece_views': piece_views,
    }


def _piece_ref(piece):
    return {key: piece[key] for key in (
        'id', 'state', 'current_tray', 'tray', 'final_tray', 'missing_evidence',
        'deficient', 'deficient_stages', 'itinerary', 'issues', 'transfers', 'stages',
        'ready', 'verified') if key in piece}


def analyze(source):
    # 允许直接把 HTTP 原始包交给分析函数；归档/复算路径上的二次规范化是幂等的。
    source = normalize(source)
    context = build_context(source)
    lineage = context['lineage']
    report = {
        'id': source['id'],
        'engine': ENGINE,
        'horizon_s': source['horizon_s'],
        'recipe': source['recipe']['id'],
        'slots': source['slots'],
        'trays': context['tray_records'],
        'conflicts': context['conflicts'],
    }
    if lineage:
        report['workpieces'] = context['piece_views']
        report['pieces'] = context['piece_views']
        for alias in ('workpiece_results', 'piece_results', 'workpiece_reports',
                      'piece_reports', 'workpiece_states'):
            report[alias] = context['piece_views']
        report['transfers'] = lineage['transfers']
        report['handovers'] = lineage['transfers']
        report['handoffs'] = lineage['transfers']
        report['transfer_results'] = lineage['transfers']
        report['handoff_records'] = lineage['transfers']
        report['retired_trays'] = [{'id': tray, **info}
                                   for tray, info in sorted(context['retirements'].items())]
        report['missing_evidence_pieces'] = sorted(
            piece['id'] for piece in context['piece_views'] if piece['missing_evidence'])
        report['missing_evidence_piece_ids'] = report['missing_evidence_pieces']
        report['missing_evidence_workpiece_ids'] = report['missing_evidence_pieces']
        report['deficient_pieces'] = sorted(
            piece['id'] for piece in context['piece_views'] if piece['state'] != 'ready')
        report['deficient_piece_ids'] = report['deficient_pieces']
        report['lineage'] = {
            'workpieces': context['piece_views'],
            'pieces': context['piece_views'],
            'transfers': lineage['transfers'],
            'handoffs': lineage['transfers'],
            'handovers': lineage['transfers'],
            'retirements': context['retirements'],
            'retired_trays': report['retired_trays'],
        }
    else:
        report['workpieces'] = []
        report['pieces'] = []
        for alias in ('workpiece_results', 'piece_results', 'workpiece_reports',
                      'piece_reports', 'workpiece_states', 'transfer_results',
                      'handoffs', 'handoff_records'):
            report[alias] = []
        report['transfers'] = []
        report['handovers'] = []
        report['retired_trays'] = []
        report['missing_evidence_pieces'] = []
        report['missing_evidence_piece_ids'] = []
        report['missing_evidence_workpiece_ids'] = []
        report['deficient_pieces'] = []
        report['deficient_piece_ids'] = []
    return report


def trace_piece(source, piece_id):
    source = normalize(source)
    context = build_context(source)
    if not context['lineage'] or not any(p['id'] == piece_id for p in context['piece_views']):
        return None
    detailed = build_piece_views(
        source, context['lineage'], context['tray_stages'], context['slots'],
        context['recipes'], context['clocks'], detailed=True
    )
    return next(piece for piece in detailed if piece['id'] == piece_id)
