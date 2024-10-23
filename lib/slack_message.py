from typing import Literal
from dataclasses import dataclass

@dataclass
class SlackMessage:
    uid: str
    text: str
    ts: str
    channel: str
    channel_type: Literal['channel', 'im']
