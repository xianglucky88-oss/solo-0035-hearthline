from .errors import Problem
from .fields import ident, number, obj, rows, unique


def parse_readings(value, horizon, probes):
    readings = []
    for row in rows(value, '测点样本', 8000):
        obj(row, 'id probe at tenth valid', '测点样本')
        probe = ident(row['probe'], '测点编号')
        if probe not in probes or type(row['valid']) is not bool:
            raise Problem('测点样本须引用已登记测点并声明质量标记')
        readings.append({'id': ident(row['id'], '样本编号'), 'probe': probe, 'valid': row['valid'],
                         'at': number(row['at'], 0, horizon, '采样秒数'),
                         'tenth': number(row['tenth'], -500, 20000, '原始测温')})
    unique([row['id'] for row in readings], '样本编号')
    unique([(row['probe'], row['at']) for row in readings], '同测点采样秒数')
    return sorted(readings, key=lambda row: (row['probe'], row['at']))
