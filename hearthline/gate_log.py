from .errors import Problem
from .fields import ident, number, obj, rows, unique


def parse_events(value, horizon, trays, slots):
    events = []
    for row in rows(value, '过门记录', 1600):
        obj(row, 'id tray slot at kind', '过门记录')
        eid, tray, slot = (ident(row[key], '过门标识') for key in ('id', 'tray', 'slot'))
        if tray not in trays or slot not in slots:
            raise Problem('过门记录引用未知料盘或炉位')
        if row['kind'] not in ('enter', 'leave'):
            raise Problem('过门类型仅接受 enter 或 leave')
        events.append({'id': eid, 'tray': tray, 'slot': slot, 'kind': row['kind'],
                       'at': number(row['at'], 0, horizon, '过门秒数')})
    unique([row['id'] for row in events], '过门记录编号')
    return sorted(events, key=lambda row: (row['at'], row['id']))
