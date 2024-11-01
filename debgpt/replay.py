'''
MIT License

Copyright (c) 2024 Mo Zhou <lumin@debian.org>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
from rich.markup import escape
from rich.panel import Panel
from rich.markdown import Markdown
import json
import argparse
import rich
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


def main() -> None:
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
    args = parser.parse_args()
    replay(args.input_file, args.render)


if __name__ == '__main__':
    main()
