from .errors import Problem
from .fields import ident, obj, rows, unique


def parse_slots(value, recipe):
    zones = {stage['zone'] for stage in recipe['stages']}
    slots = []
    for row in rows(value, '炉位', 32, 1):
        obj(row, 'id zone probe', '炉位')
        slot = {field: ident(row[field], '炉位标识') for field in ('id', 'zone', 'probe')}
        if slot['zone'] not in zones:
            raise Problem('炉位属于工艺卡以外的炉区')
        slots.append(slot)
    unique([slot['id'] for slot in slots], '炉位编号')
    unique([slot['probe'] for slot in slots], '炉位测点')
    if {slot['zone'] for slot in slots} != zones:
        raise Problem('每个工艺阶段至少要有一个炉位')
    return sorted(slots, key=lambda slot: slot['id'])
