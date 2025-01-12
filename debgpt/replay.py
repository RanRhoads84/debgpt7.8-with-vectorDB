'''
Copyright (C) 2024-2025 Mo Zhou <lumin@debian.org>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''
from typing import List
import sys
from rich.markup import escape
from rich.panel import Panel
from rich.markdown import Markdown
import json
import argparse
from typing import Dict, Any
from .defaults import console


def process_entry(entry: Dict[str, Any], render: bool) -> None:
    """
    Processes a single chat entry and prints it to the console.

    Args:
        entry (Dict[str, Any]): A dictionary representing a chat entry with keys 'role' and 'content'.
        render (bool): A flag indicating whether to render assistant messages with rich Markdown.
    
    Raises:
        ValueError: If the entry role is unknown.
    """
    if entry['role'] == 'user':
        title = 'User Input'
        border_style = 'cyan'
        content = Panel(escape(entry['content']),
                        title=title,
                        border_style=border_style)
    elif entry['role'] == 'assistant':
        if render:
            content = Markdown(entry['content'])
        else:
            content = escape(entry['content'])
    elif entry['role'] == 'system':
        title = 'System Message'
        border_style = 'red'
        content = Panel(escape(entry['content']),
                        title=title,
                        border_style=border_style)
    else:
        raise ValueError(f'unknown role in {entry}')

    if render and entry['role'] != 'assistant':
        console.print(content)
    elif not render and entry['role'] == 'assistant':
        print(content)
    else:
        console.print(content)


def replay(path: str, render: bool = True) -> None:
    """
    Replays chat messages from a JSON file.

    Args:
        path (str): The file path to the JSON file containing chat messages.
        render (bool): A flag indicating whether to render assistant messages with rich Markdown.
    """
    with open(path) as f:
        J = json.load(f)

    for entry in J:
        process_entry(entry, render)


def main(argv: List[str] = sys.argv[1:]) -> None:
    """
    The main function to parse command-line arguments and initiate the replay of chat messages.
    """
    parser = argparse.ArgumentParser(
        description='Replay chat messages from a JSON file.')
    parser.add_argument('input_file',
                        metavar='FILE',
                        help='JSON file containing the chat messages')
    parser.add_argument(
        '--render',
        action=argparse.BooleanOptionalAction,
        default=True,
        help='Render assistant messages with rich Markdown (default: True)')
    args = parser.parse_args(argv)
    replay(args.input_file, args.render)


if __name__ == '__main__':  # pragma: no cover
    main()
