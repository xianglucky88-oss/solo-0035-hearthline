from .errors import Problem
from .fields import ident, number, obj, rows, text, unique


def parse_recipe(value, horizon):
    obj(value, 'id stages', '工艺卡')
    recipe_id = ident(value['id'], '工艺卡编号')
    stages = []
    for row in rows(value['stages'], '阶段', 8, 1):
        obj(row, 'zone label min_tenth max_tenth min_contiguous_s', '阶段')
        lower = number(row['min_tenth'], -500, 20000, '温度下限')
        upper = number(row['max_tenth'], -500, 20000, '温度上限')
        if lower > upper:
            raise Problem('阶段温度上下限倒置')
        stages.append({'zone': ident(row['zone'], '炉区编号'), 'label': text(row['label'], '阶段名称', 40),
                       'min_tenth': lower, 'max_tenth': upper,
                       'min_contiguous_s': number(row['min_contiguous_s'], 1, horizon, '连续达标秒数')})
    unique([stage['zone'] for stage in stages], '工艺卡炉区')
    return {'id': recipe_id, 'stages': stages}
