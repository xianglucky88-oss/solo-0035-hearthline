from collections import defaultdict


def reconstruct(trays, events, horizon):
    by_tray = defaultdict(list)
    for event in events:
        by_tray[event['tray']].append(event)
    visits = {}
    issues = {}
    unresolved = []
    for tray in trays:
        visits[tray], issues[tray] = [], []
        opened = None
        for event in sorted(by_tray[tray], key=lambda item: (item['at'], item['kind'] != 'leave', item['id'])):
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
