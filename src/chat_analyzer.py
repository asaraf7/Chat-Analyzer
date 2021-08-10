import json
import re
from datetime import datetime
from json import JSONDecodeError
from time import time
from typing import Any, Dict, List
import matplotlib.pyplot as plt

import click
from tabulate import tabulate

import globals
from chat_functions import (
    calc_percentage, check_activity, find_conv_starters, interaction_curve_func, generate_graph_precentages
)

# Initialize the global variables
globals.init()

"""
Define Regex Patterns
"""
# For Signal chat exports
SDate = r'(?P<date>(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2}))'
STime = r'(?P<time>(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}))'
SDateTime = r'\[' + SDate + r' ' + STime + r'\]'
SUser = r'(?P<username>[^:]*):'
SMsg = SDateTime + r' ' + SUser + r'(?P<message>.*)'

# For Telegram chat exports
TDate = r'(?P<date>(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2}))'
TTime = r'(?P<time>(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):(?P<seconds>[0-9]{2}))'
TDateTime = TDate + r'T' + TTime

# For Whatsapp chat exports
WUser = r'(- (?P<username>[^:]*):)'  # To get the user's name
# To get the date
WDate = r'(?P<date>(?P<month>[0-9]{1,2})[-\/]{1}(?P<day>[0-9]{1,2})[-\/]{1}(?P<year>[0-9]{2}))'
# To get the time
WTime = r'(, (?P<time>(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2})) )'
# Finally to get the parsed message
WMsg = WDate + WTime + WUser + r'(?P<message>.*)'


def import_data(path_to_chatfile: str) -> List[Dict[str, Any]]:
    """
    Recognise, parse data from a chat export and return in a standard format.

    Return prototype:
    msgs = [
        {
            'username': <string>,
            'date': <datetime.date object>
            'month': <string>
            'day': <string>
            'year': <string>
            'time': <datetime.time object>
            'hour': <string>
            'minute': <string>
        }
    ]
    """
    try:
        f = open(path_to_chatfile, 'r')
    except FileNotFoundError:
        print('File not found!!')
        exit()

    msgs = []

    # Telegram export
    try:
        data = json.load(f)['chats']['list']
        print('Telegram chat recognized')
        chat_name = input('Enter the chat name: ')

        for chat in data:
            if chat['name'] == chat_name:
                chat_data = chat['messages']
                break
        else:
            print('Chat data not found!')
            exit()

        for msg in chat_data:
            date_match = re.search(TDateTime, msg['date'])
            if date_match and 'from' in msg:
                msgs.append({
                    'username': msg['from'],
                    'date': datetime.strptime(date_match.groupdict()['date'], '%Y-%M-%d').date(),
                    'month': date_match.groupdict()['month'],
                    'day': date_match.groupdict()['day'],
                    'year': date_match.groupdict()['year'],
                    'time': datetime.strptime(date_match.groupdict()['time'], '%H:%M:%S').time(),
                    'hour': date_match.groupdict()['hour'],
                    'minute': date_match.groupdict()['minute'],
                })

        return msgs
    except JSONDecodeError:
        pass
    except KeyError:
        try:
            f.seek(0)
            msgs = json.load(f)['messages']
            return msgs
        except KeyError:
            pass

    # Signal Export
    f.seek(0)
    isSignal = False
    for line in f:
        match = re.search(SMsg, line)
        if match:
            isSignal = True
            break

    if isSignal:
        f.seek(0)
        print('Signal chat recognized')
        for line in f:
            match = re.search(SMsg, line)
            if match:
                msgs.append({
                    'username': match.groupdict()['username'],
                    'date': datetime.strptime(match.groupdict()['date'], '%Y-%M-%d').date(),
                    'month': match.groupdict()['month'],
                    'day': match.groupdict()['day'],
                    'year': match.groupdict()['year'],
                    'time': datetime.strptime(match.groupdict()['time'], '%H:%M').time(),
                    'hour': match.groupdict()['hour'],
                    'minute': match.groupdict()['minute'],
                })
        return msgs

    # Whatsapp Export
    f.seek(0)
    for line in f:
        match = re.search(WMsg, line)
        if match:
            msgs.append({
                'username': match.groupdict()['username'],
                'date': datetime.strptime(match.groupdict()['date'], '%m/%d/%y').date(),
                'month': match.groupdict()['month'],
                'day': match.groupdict()['day'],
                'year': match.groupdict()['year'],
                'time': datetime.strptime(match.groupdict()['time'], '%H:%M').time(),
                'hour': match.groupdict()['hour'],
                'minute': match.groupdict()['minute'],
            })
    f.close()

    if len(msgs) == 0:
        print('Invalid file!')
        exit()

    return msgs


def export_data(msgs: List[Dict[str, Any]], filename: str) -> None:
    """Export the imported data to a json file in a standard format."""
    if not filename:
        filename = 'export.json'

    json_msgs = {'messages': msgs}

    with open(filename, 'w') as outfile:
        json.dump(json_msgs, outfile, default=str, indent=2)

    print("Chat data exported to {}".format(filename))


"""
The command line options
"""


@click.command()
@click.argument('path_to_chatfile')
@click.option('-u', '--username', nargs=1, type=str,
              help='Show results for a particular User only (Provide the username)')
@click.option('-c', '--constraint', nargs=2, type=str, help='Add date Constraints (format - mm/dd/yy)')
@click.option('-sG', '--show-graph', is_flag=True, help='Show graph(s) for the selected options if available')
@click.option('-p', '--percentage', is_flag=True, help='Show percentage contribution to the chat')
@click.option('-cS', '--conv-starters', is_flag=True,
              help='Get the frequecy at which each person has started the conversation')
@click.option('-a', '--activity', is_flag=True, help='Show hourwise activity of users')
@click.option('-iC', '--interaction-curve', is_flag=True,
              help='Tell whether the interaction of the user has increased or decreased')
@click.option('-e', '--export', is_flag=True, help='Export the data into a standard json format')
@click.option('-eP', '--export-path', nargs=1, type=str, help='Add the export path')
def controller(
        path_to_chatfile: str, username: str, percentage: bool, constraint: List[str], conv_starters: bool,
        activity: bool, interaction_curve: bool, show_graph: bool, export: bool, export_path: str) -> None:
    """The main CLI controller"""
    # Import the data
    msgs = import_data(path_to_chatfile)
    start = time()

    # Set the date constraints (if present)
    if constraint:
        start_date = datetime.strptime(constraint[0], '%m/%d/%y').date()
        end_date = datetime.strptime(constraint[1], '%m/%d/%y').date()
    else:
        start_date = None
        end_date = None

    if conv_starters:
        table_data = find_conv_starters(msgs, username)
        print(tabulate(table_data, headers='firstrow', tablefmt='fancy_grid',
              colalign=('center', 'center'), floatfmt='.4f'))

    if percentage:
        table_data, total_count = calc_percentage(msgs, username, start_date, end_date, show_graph)

        print('Total No. of Messages: {}\n'.format(total_count))
        print(tabulate(table_data, headers='firstrow', tablefmt='fancy_grid',
              colalign=('center', 'center', 'center'), floatfmt='.4f'))

        # For Graph
        if show_graph and globals.CAN_SHOW_GRAPH:
            print('\nShowing graph....')
            users, percs = generate_graph_precentages(table_data[1:])
            plt.pie(x=percs, autopct='%1.1f%%', shadow=True, startangle=90)
            plt.axis('equal')
            plt.legend(users)
            plt.tight_layout()
            plt.title('Percentage contribution of each user in the chat')
            plt.show()

    if activity:
        check_activity(msgs, username, start_date, end_date, show_graph)

    if interaction_curve:
        interaction_curve_func(
            msgs, username=username, start_date=start_date, end_date=end_date, show_graph=show_graph)

    if export:
        export_data(msgs, export_path)

    end = time()
    print('Program Finished')
    print('Total time taken: {} seconds'.format(end - start))


if __name__ == '__main__':
    controller()
