import re

from .errors import Problem


TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,39}\Z')


def obj(value, wanted, label):
    if not isinstance(value, dict) or set(value) != set(wanted.split()):
        raise Problem(f'{label}字段应为 {wanted}')
    return value


def ident(value, label):
    if not isinstance(value, str) or not TOKEN.fullmatch(value):
        raise Problem(f'{label}须为 1 至 40 位字母、数字、短横线或下划线，首位为字母或数字')
    return value


def number(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise Problem(f'{label}须为 {low} 至 {high} 的整数')
    return value


def text(value, label, limit=200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise Problem(f'{label}须填写，最多 {limit} 字')
    if any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise Problem(f'{label}包含无效字符')
    return value.strip()


def rows(value, label, limit, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= limit:
        raise Problem(f'{label}须有 {minimum} 至 {limit} 条记录')
    return value


def unique(values, label):
    if len(set(values)) != len(values):
        raise Problem(f'{label}重复')
