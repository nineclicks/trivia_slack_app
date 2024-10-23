import os
import json
import logging
from time import time
from typing import Union
from threading import Lock

from slack_sdk.web import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest

from .slack_message import SlackMessage
from .config import load_config
load_config() # You're gonna want to call this before getting any more env vars

SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
DISPLAY_NAME_CACHE_EXPIRE_SECONDS = int(os.getenv('DISPLAY_NAME_CACHE_EXPIRE_SECONDS', 60 * 60 * 6))
TRIVIA_DATABASE_PATH = os.environ.get('TRIVIA_DATABASE_PATH', 'trivia.db')
TRIVIA_CHANNEL = os.environ.get('TRIVIA_CHANNEL')
BOT_DISPLAY_NAME = os.environ.get('BOT_DISPLAY_NAME')
BOT_ICON_EMOJI = os.environ.get('BOT_ICON_EMOJI')
ADMIN_UID = os.environ.get('ADMIN_UID')
MIN_SECONDS_BEFORE_NEW = int(os.environ.get('MIN_SECONDS_BEFORE_NEW', 0))
MIN_MATCHING_CHARACTERS = int(os.environ.get('MIN_MATCHING_CHARACTERS', 5))
SCOREBOARD_SCHEDULE = json.loads(os.environ.get('SCOREBOARD_SCHEDULE', "[]"))
SCOREBOARD_SHOW_INCORRECT = bool(int(os.environ.get('SCOREBOARD_SHOW_INCORRECT', "0")))
SCOREBOARD_SHOW_PERCENT = bool(int(os.environ.get('SCOREBOARD_SHOW_PERCENT', "0")))

logger = logging.getLogger('trivia_slack_app')
_display_name_cache = {}
_display_name_lock = Lock()

def get_socket_client(slack_app_token: str=SLACK_APP_TOKEN, slack_bot_token: str=SLACK_BOT_TOKEN) -> SocketModeClient:
    """Get a Slack SocketModeClient using xapp and xoxb tokens

    :param slack_app_token: xapp-... token, defaults to SLACK_APP_TOKEN
    :type slack_app_token: str, optional
    :param slack_bot_token: xoxb-... token, defaults to SLACK_BOT_TOKEN
    :type slack_bot_token: str, optional
    :return: Slack SocketModeClient
    :rtype: SocketModeClient
    """

    return SocketModeClient(
        app_token=slack_app_token,
        web_client=WebClient(token=slack_bot_token)
    )

def get_display_name(client: SocketModeClient, uid: str) -> str:
    """Get the display name for a user by uid

    :param client: Slack SocketModeClient
    :type client: SocketModeClient
    :param uid: User UID for which to retrieve display name
    :type uid: str
    :return: User's display name
    :rtype: str
    """

    with _display_name_lock:
        if uid in _display_name_cache and _display_name_cache[uid]['expire'] > time():
            return _display_name_cache[uid]['name']
    
    display_name = '(unknown user)'
    try:
        user_info = client.web_client.users_info(user=uid)
        user_profile = user_info.get('user', {}).get('profile', {})
        display_name = user_profile.get('display_name_normalized') or user_profile.get('real_name_normalized') or '(unknown user)'
    except Exception as ex:
        if 'user_not_found' in str(ex):
            logger.error('get_display_name failed for uid %s. User not found.' % uid)
        else:
            logger.exception('get_display_name failed for uid %s. %s' % (uid, ex))

    _display_name_cache[uid] = {'name': display_name, 'expire': time() + DISPLAY_NAME_CACHE_EXPIRE_SECONDS}
    return display_name

def parse_message(req: SocketModeRequest) -> Union[SlackMessage, None]:
    """Return a SlackMessage if the request is a valid message or None

    :param req: Slack SocketModeRequest
    :type req: SocketModeRequest
    :return: SlackMessage or None
    :rtype: Union[SlackMessage, None]
    """
    
    self_uids = [a.get('user_id') for a in req.payload.get('authorizations')]
    event = req.payload.get('event', {})

    if (
        event.get('user') not in self_uids and # Do not respond to our own messages
        event.get('bot_id') is None and # Do not respond to any bot
        event.get('app_id') is None and # Do not respond to any app
        req.type == "events_api" and # Only care about events
        event["type"] == "message" and # Only care about messages
        event.get("subtype") is None and # Only care about normal messages
        (
            event.get('channel') == TRIVIA_CHANNEL or    # Message is in trivia channel
            event.get('channel_type') == 'im'            # or message is an IM
        )
    ):
        return SlackMessage(
            uid=event.get('user'),
            text=event.get('text'),
            ts=event.get('ts'),
            channel=event.get('channel'),
            channel_type=event.get('channel_type'),
            )
    
def format_question(client: SocketModeClient, question: dict) -> str:
    """Format a question dict as returned from TriviaCore

    :param question: TriviaCore question dict
    :type question: dict
    :return: Question formatted for a slack app message
    :rtype: str
    """

    user = question.get('winning_user')
    print('winning user', user)
    if user:
        print('uid', user.get('uid',''))
        username = get_display_name(client, user.get('uid',''))
        print('username', username)
        line1 = f'Correct: *{question["winning_answer"]}* '
        line1 += f'-- {username} (today: {user["score"]:,} #{user["rank"]})'
    else:
        line1 = f'Answer: *{question["winning_answer"]}*'

    line2 = f'({question["year"]}) *{question["category"]}* '
    line2 += f'for *{question["value"]}*'
    if question['comment']:
        line2 += f' _{question["comment"]}_'

    line3 = f'>{question["question"]}'

    return f'{line1}\n{line2}\n{line3}'
