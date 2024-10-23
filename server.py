from threading import Event

from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from trivia_core import TriviaCore

from lib import helpers

client = helpers.get_socket_client()
team_id = client.web_client.team_info()['team']['id']
trivia = TriviaCore(
    database_path=helpers.TRIVIA_DATABASE_PATH,
    platform=team_id,
    admin_uid=helpers.ADMIN_UID,
    min_seconds_before_new=helpers.MIN_SECONDS_BEFORE_NEW,
    scoreboard_schedule=helpers.SCOREBOARD_SCHEDULE,
    min_matching_characters=helpers.MIN_MATCHING_CHARACTERS,
    scoreboard_show_incorrect=helpers.SCOREBOARD_SHOW_INCORRECT,
    scoreboard_show_percent=helpers.SCOREBOARD_SHOW_PERCENT,
)

def slack_test(client: SocketModeClient, message: helpers.SlackMessage):
    results = []
    try:
        res = client.web_client.reactions_add(
            channel=message.channel,
            timestamp=message.ts,
            name='white_check_mark',
        )
        results.append(('Reaction Add', True, ''))
    except Exception as ex:
        helpers.logger.exception(ex)
        results.append(('Reaction Add', False, str(ex)))

    try:
        display_name = helpers.get_display_name(client, message.uid)
        results.append(('Get Display Name', True, f'Your display name is "{display_name}"'))
    except Exception as ex:
        helpers.logger.exception(ex)
        results.append(('Get Display Name', False, str(ex)))

    try:
        client.web_client.chat_postMessage(
            channel=message.channel,
            text='This is a test!',
            username=helpers.BOT_DISPLAY_NAME,
            icon_emoji=helpers.BOT_ICON_EMOJI,
        )
        results.append(('Post Message', True, ''))
    except Exception as ex:
        helpers.logger.exception(ex)
        results.append(('Post Message', False, str(ex)))

    try:
        client.web_client.chat_postEphemeral(
            channel=message.channel,
            user=message.uid,
            text='This is an ephemeral chat test!',
            username=helpers.BOT_DISPLAY_NAME,
            icon_emoji=helpers.BOT_ICON_EMOJI,
        )
        results.append(('Post Ephemeral Message', True, ''))
    except Exception as ex:
        helpers.logger.exception(ex)
        results.append(('Post Ephemeral Message', False, str(ex)))

    text = '\n'.join([f"{':white_check_mark:' if y else ':negative_squared_cross_mark:'} *{x}*{': ' if z else ''}{z}" for x, y, z in results])

    try:
        client.web_client.chat_postMessage(
            channel=message.channel,
            text=text,
            username=helpers.BOT_DISPLAY_NAME,
            icon_emoji=helpers.BOT_ICON_EMOJI,
        )
        helpers.logger.info(str(results))
    except Exception:
        helpers.logger.error(str(results))

def handle_message(client: SocketModeClient, req: SocketModeRequest):
    response = SocketModeResponse(envelope_id=req.envelope_id)
    client.send_socket_mode_response(response)
    message = helpers.parse_message(req)
    if message is None:
        return
    
    if message.text.replace(' ', '').lower().startswith('!slacktest'):
        return slack_test(client, message)


    trivia.handle_message(
        uid=message.uid,
        text=message.text,
        message_payload=message
    )

@trivia.on_correct_answer
def corrent_answer(message: helpers.SlackMessage, _):
    try:
        client.web_client.reactions_add(
            channel = helpers.TRIVIA_CHANNEL,
            name = 'white_check_mark',
            timestamp = message.ts,
        )
    except Exception as ex:
        helpers.logger.exception(ex)

@trivia.on_error
def error(message_payload: helpers.SlackMessage, text):
    client.web_client.reactions_add(
        channel=message_payload.channel,
        name='x',
        timestamp=message_payload.ts
    )
    client.web_client.chat_postEphemeral(
        channel=message_payload.channel,
        user=message_payload.uid,
        text=text,
        username=helpers.BOT_DISPLAY_NAME,
        icon_emoji=helpers.BOT_ICON_EMOJI,
    )

@trivia.on_get_display_name
def get_display_name(uid):
    return helpers.get_display_name(client, uid)

@trivia.on_post_message
def post_message(text):
    client.web_client.chat_postMessage(
        channel=helpers.TRIVIA_CHANNEL,
        text=text,
        username=helpers.BOT_DISPLAY_NAME,
        icon_emoji=helpers.BOT_ICON_EMOJI,
    )

@trivia.on_post_question
def post_question(question):
    text = helpers.format_question(client, question)
    client.web_client.chat_postMessage(
        channel=helpers.TRIVIA_CHANNEL,
        text=text,
        username=helpers.BOT_DISPLAY_NAME,
        icon_emoji=helpers.BOT_ICON_EMOJI,
    )

@trivia.on_post_reply
def post_reply(text: str, message_payload: helpers.SlackMessage):
    client.web_client.chat_postMessage(
        channel=message_payload.channel,
        text=text,
        username=helpers.BOT_DISPLAY_NAME,
        icon_emoji=helpers.BOT_ICON_EMOJI,
    )

@trivia.on_pre_format
def pre_format(message):
    return f'```{message}```'

client.socket_mode_request_listeners.append(handle_message)
client.connect()
Event().wait()
