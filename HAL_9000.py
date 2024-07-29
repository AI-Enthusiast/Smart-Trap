import threading
import time
import urllib.error

import slack
from slack import errors as slack_errors
import my_tools
import open_ai_test
import weather_bot
import plague_bot
import fire_watch
import live_trapping_bot
# import to parse config.ini
import configparser


config = configparser.ConfigParser()
config.read('config.ini')
my_tools.post_to_slack = True


def say_hi():
    # set up the Slack API client with your bot token
    slack_bot_hal9000 = config['SLACK']['hal_900_code']
    client = slack.WebClient(token=slack_bot_hal9000)
    # set the channel ID of the channel you want to listen for messages in
    channel_id = config['SLACK']['hal_900_chan']
    client.chat_postMessage(channel=channel_id, text='HAL 9000 is online')
    seen_msg = []
    i_since_clean = 0

    # listen for incoming messages in the channel
    while True:
        try:
            response = client.conversations_history(
                channel=channel_id,
                oldest=int(time.time()) - 120,  # only retrieve messages from the past 2 mins
                inclusive=True  # include the oldest message in the results
            )
            messages = response['messages']

            # loop through each message in the channel
            for message in messages:
                if "<@"+config['SLACK']['captain']+">" in message['text']:  # ID of HAL 9000
                    message_str = message['text'].replace( "<@"+config['SLACK']['captain']+">", '')
                    message_ts = message['ts']

                    # skip seen messages and hit them with a thumbs up
                    if not seen_msg.__contains__(message_ts):
                        seen_msg.append(message_ts)
                        client.reactions_add(channel=channel_id, name='thumbsup', timestamp=message['ts'])
                    else:
                        continue

                    print(message)
                    # check if the message is "hi"
                    if 'hi' in message_str.lower():
                        # send a response of "hello!" back to the user
                        client.chat_postMessage(channel=channel_id, text='hello!')

                    # Standard Bots
                    elif 'weather' in message_str.lower():
                        threading.Thread(target=weather_bot.weather_channel()).start()
                    elif 'plague' in message_str.lower():
                        threading.Thread(target=plague_bot.plague_inc()).start()
                    elif 'fire' in message_str.lower():
                        threading.Thread(target=fire_watch.fire_bot()).start()

                    # AI Toolkit
                    elif 'gpt' in message_str.lower():
                        msg = message_str[message_str.find(':') + 1:]
                        response = open_ai_test.chat_gpt(msg)
                        threading.Thread(target=my_tools.notification,
                                         args=[response, slack_bot_hal9000, 'bots']).start()
                    elif 'dalle' in message_str.lower():
                        msg = message_str[message_str.find(':') + 1:]
                        response = open_ai_test.dalle(msg)
                        threading.Thread(target=my_tools.notification,
                                         args=[response, slack_bot_hal9000, 'bots']).start()

                    # Live Trap
                    # dedupe motion frames recorded  from the live trap
                    elif 'dedupe' in message_str.lower() and 'livetrap' in message_str.lower():
                        threading.Thread(target=live_trapping_bot.clean_dupe_images()).start()
                    # arm or disarm the trap (ei motion detection and beep alarm)
                    elif 'arm' in message_str.lower() and 'trap' in message_str.lower() \
                            and 'alarm' not in message_str.lower():
                        if live_trapping_bot.alarm_mode:
                            threading.Thread(target=my_tools.notification,
                                             args=(
                                                 "The trap has been disarmed",
                                                 my_tools.slack_bot_mapach, 'bots')).start()
                        else:
                            threading.Thread(target=my_tools.notification,
                                             args=("The trap is armed",
                                                   my_tools.slack_bot_mapach, 'bots')).start()

                        live_trapping_bot.alarm_mode = not live_trapping_bot.alarm_mode
                        live_trapping_bot.motion_counter = 0
                        live_trapping_bot.triggered = False
                    # turn off the trap
                    elif ((('turn' in message_str.lower() or 'power' in message_str.lower()) and
                           ('off' in message_str.lower() or 'down' in message_str.lower())) or
                          'kill' in message_str.lower()) and 'trap' in message_str.lower():
                        live_trapping_bot.kill_switch = True
                    # turn on the trap
                    elif ('turn' in message_str.lower() or 'power' in message_str.lower()) and \
                            ('on' in message_str.lower() or 'up' in message_str.lower()) and \
                            'trap' in message_str.lower():
                        live_trapping_bot.kill_switch = False
                        threading.Thread(target=live_trapping_bot.trap_bot).start()
                    # set off the alarm manually
                    elif ('trigger' in message_str.lower() or 'set off' in message_str.lower() or
                          'turn on' in message_str.lower()) and 'alarm' in message_str.lower():
                        live_trapping_bot.alarm_mode = True
                        threading.Thread(target=live_trapping_bot.beep_alarm,
                                         args=[True]).start()
                    # toggle linux mode (should be done before turning on the live trap)
                    elif 'linux' in message_str.lower():
                        live_trapping_bot.win = not live_trapping_bot.win
                    # toggle headless mode (live feed)
                    elif 'server' in message_str.lower() or 'headless' in message_str.lower():
                        live_trapping_bot.headless = not live_trapping_bot.headless

                    # weedmaps
                    elif 'weedmaps' in message_str.lower():  # eg 'weedmaps: lon: 34.0522, lat: -118.2437, radius: 10'
                        msg = message_str[message_str.find(':') + 1:]

                    else:
                        msg = "I'm sorry, Dave. I'm afraid I can't do that"
                        threading.Thread(target=my_tools.notification,
                                         args=[msg, slack_bot_hal9000, 'bots']).start()

        except slack_errors.SlackApiError as e:
            print(f"I'm sorry, Dave. I'm afraid I can't do that: {e}")
        except urllib.error.URLError as e:
            print(f"I'm sorry, Dave. I'm afraid I can't do that: {e}")

        time.sleep(5)
        seen_msg.sort()


say_hi()
