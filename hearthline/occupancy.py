from collections import defaultdict


def collisions(visits, unresolved):
    by_slot = defaultdict(list)
    for items in visits.values():
        for visit in items:
            by_slot[visit['slot']].append(visit)
    for claim in unresolved:
        by_slot[claim['slot']].append(claim)
    result = []
    for slot, items in sorted(by_slot.items()):
        active = []
        for visit in sorted(items, key=lambda item: (item['from'], item['tray'])):
            active = [prior for prior in active if prior['to'] > visit['from']]
            for prior in active:
                result.append({'slot': slot, 'trays': [prior['tray'], visit['tray']], 'from': visit['from'],
                               'to': min(prior['to'], visit['to']), 'sources': prior['sources'] + visit['sources'],
                               'tentative': bool(prior.get('open') or visit.get('open'))})
            active.append(visit)
    return result
