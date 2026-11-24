from dataclasses import dataclass, field

from .codec import canonical


@dataclass
class Reply:
    body: bytes
    content_type: str
    status: int = 200
    headers: dict = field(default_factory=dict)


def json_reply(value, status=200, **headers):
    return Reply(canonical(value).encode('utf-8'), 'application/json; charset=utf-8', status, headers)
