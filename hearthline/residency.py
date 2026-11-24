from collections import defaultdict


def reconstruct(trays, events, horizon, retirements=None):
    if isinstance(retirements, (list, tuple, set, frozenset)):
        retirements = {tray: {} for tray in retirements}
    retirements = retirements or {}
    by_tray = defaultdict(list)
    for event in events:
        by_tray[event['tray']].append(event)
    visits = {}
    issues = {}
    unresolved = []
    for tray in trays:
        visits[tray], issues[tray] = [], []
        opened = None
        retirement = retirements.get(tray)
        if isinstance(retirement, dict):
            retired_at = retirement.get('at')
        else:
            retired_at = retirement
        for event in sorted(by_tray[tray], key=lambda item: (item['at'], item['kind'] != 'leave', item['id'])):
            # 退役秒的顺序是离位、交接、入位；因此该秒 enter 已在退役之后。
            post_retirement = (
                retired_at is not None and (
                    event['at'] > retired_at or
                    (event['at'] == retired_at and event['kind'] == 'enter')
                )
            )
            if post_retirement:
                issues[tray].append({
                    'reason': 'gate_retired',
                    'sources': [event['id']],
                    'retirement': retirement.get('transfer') if isinstance(retirement, dict) else None,
                    'aliases': ['retired_event', 'retired_ticket'],
                })
                continue
            if event['kind'] == 'enter' and opened is None:
                opened = event
            elif event['kind'] == 'leave' and opened and opened['slot'] == event['slot']:
                visits[tray].append({'tray': tray, 'slot': event['slot'], 'from': opened['at'],
                                     'to': event['at'], 'sources': [opened['id'], event['id']]})
                opened = None
            else:
                issues[tray].append({'reason': 'gate_pair', 'sources': [event['id']]})
        if opened:
            issues[tray].append({'reason': 'gate_open', 'sources': [opened['id']]})
            if opened['at'] < horizon:
                unresolved.append({'tray': tray, 'slot': opened['slot'], 'from': opened['at'],
                                   'to': horizon, 'sources': [opened['id']], 'open': True})
    return visits, issues, unresolved
