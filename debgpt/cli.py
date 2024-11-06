'''
Copyright (C) 2024 Mo Zhou <lumin@debian.org>

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
# suppress all warnings.
import textwrap
import rich
import shlex
import sys
import os
import re
import difflib
import argparse
import concurrent.futures
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit import PromptSession
from rich.panel import Panel
from rich.rule import Rule
from rich.markup import escape
from rich.progress import track
from prompt_toolkit.styles import Style
from pygments import highlight
from pygments.lexers import DiffLexer
from pygments.formatters import TerminalFormatter
from typing import List, Optional
import warnings
import functools as ft
from . import defaults
from . import reader
from . import frontend
from . import configurator
from . import arguments
from debgpt import version
import os
import sys
from rich.panel import Panel
import tempfile
import textwrap
from . import frontend
from . import reader
from . import defaults
from . import vectordb
from . import replay

warnings.filterwarnings("ignore")

console = defaults.console


def subcmd_backend(ag) -> None:
    from . import backend
    b = backend.create_backend(ag)
    try:
        b.server()
    except KeyboardInterrupt:
        pass
    console.log('Server shut down.')
    exit(0)


def subcmd_replay(ag) -> None:
    if ag.json_file_path is None:
        json_path = reader.latest_glob(os.path.join(ag.debgpt_home, '*.json'))
        console.log('found the latest json:', json_path)
    else:
        json_path = ag.json_file_path
    replay.replay(json_path)
    exit(0)

def subcmd_config(ag) -> None:
    '''
    re-run the configurator.fresh_install_guide() to reconfigure.
    Ask the user whether to overwrite the existing config file.
    '''
    configurator.fresh_install_guide(
        os.path.expanduser('~/.debgpt/config.toml'))
    exit(0)


def subcmd_genconfig(ag) -> None:
    '''
    special task: generate config template, print and quit
    '''
    print(ag.config_template)  # should go to stdout
    exit(0)


def subcmd_vdb(ag) -> None:
    console.print("[red]debgpt: vdb: no subcommand specified.[/red]")
    exit(1)


def subcmd_vdb_ls(ag) -> None:
    vdb = vectordb.VectorDB(ag.db, ag.embedding_dim)
    vdb.ls(ag.id)
    exit(0)


def subcmd_git(ag) -> None:
    console.print("[red]debgpt: git: no subcommand specified.[/red]")
    exit(1)


def subcmd_git_commit(ag) -> None:
    f = ag.frontend_instance
    msg = "Previous commit titles:\n"
    msg += "```"
    msg += reader.command_line('git log --pretty=format:%s --max-count=10')
    msg += "```"
    msg += "\n"
    msg += "Change diff:\n"
    msg += "```\n"
    msg += reader.command_line('git diff --staged')
    msg += "```\n"
    msg += "\n"
    msg += 'Write a good git commit message subject line for the change diff shown above, using the project style visible in previous commits titles above.'
    frontend.query_once(f, msg)
    tmpfile = tempfile.mktemp()
    commit_message = f.session[-1]['content']
    if getattr(ag, 'inplace_git_add_commit', False) or getattr(
            ag, 'inplace_git_add_p_commit', False):
        # is the code automatically modified by debgpt --inplace?
        commit_message = 'DebGPT> ' + commit_message
        commit_message += '\n\n'
        commit_message += '\n'.join(
            textwrap.wrap(
                f"\n\nNote, the code changes are made by the command: {repr(sys.argv)}.",
                width=80))
        commit_message += '\n'
        commit_message += '\n'.join(
            textwrap.wrap(f"\n\nThe real prompt is: {ag.ask}.", width=80))
        commit_message += '\n'
        commit_message += '\n'.join(
            textwrap.wrap(f"\n\nFrontend used: {ag.frontend}.", width=80))
        commit_message += '\n'
        if ag.frontend == "openai":
            commit_message += '\n'.join(
                textwrap.wrap(f"\n\nOpenAI model: {ag.openai_model}.",
                              width=80))
        elif ag.frontend == "google":
            commit_message += '\n'.join(
                textwrap.wrap(f"\n\nGoogle model: {ag.google_model}.",
                              width=80))
        elif ag.frontend == "anthropic":
            commit_message += '\n'.join(
                textwrap.wrap(f"\n\nAnthropic model: {ag.anthropic_model}.",
                              width=80))
        elif ag.frontend == "ollama":
            commit_message += '\n'.join(
                textwrap.wrap(f"\n\nOllama model: {ag.ollama_model}.",
                              width=80))
        elif ag.frontend == "llamafile":
            commit_message += '\n'.join(
                textwrap.wrap(f"\n\nLlamafile model: {ag.llamafile_model}.",
                              width=80))
        elif ag.frontend == "vllm":
            commit_message += '\n'.join(
                textwrap.wrap(f"\n\nVLLM model: {ag.vllm_model}.", width=80))
    else:
        commit_message += "\n\n<Explain why change was made.>"
    commit_message += "\n\nNote, this commit message is generated by `debgpt git commit`."
    with open(tmpfile, 'wt') as tmp:
        tmp.write(commit_message)
    os.system(f'git commit -F {tmpfile}')
    os.remove(tmpfile)
    if ag.amend:
        os.system('git commit --amend')
    else:
        note_message = """
Please replace the <Explain why change was made.> in the git commit
message body by running:

    $ git commit --amend

or

    $ git citool --amend
"""
        console.print(Panel(note_message, title='Notice',
                            border_style='green'))

    exit(0)


def gather_information_ordered(msg: Optional[str], ag,
                               ag_order) -> Optional[str]:
    '''
    based on the argparse results, as well as the argument order, collect
    the specified information into the first prompt. If none specified,
    return None.
    '''
    __has_done_mapreduce = False

    def _append_info(msg: str, info: str) -> str:
        msg = '' if msg is None else msg
        return msg + '\n' + info

    # following the argument order, dispatch to reader.* functions with
    # different function signatures
    for key in ag_order:
        if key == 'mapreduce':
            # but we only do once for mapreduce
            if __has_done_mapreduce:
                continue
            msg = _append_info(msg, mapreduce_super_long_context(ag))
            __has_done_mapreduce = True
        elif key == 'retrieve':
            raise NotImplementedError(key)
        elif key == 'embed':
            raise NotImplementedError(key)
        elif key in ('file',):
            spec = getattr(ag, key).pop(0)
            func = ft.partial(reader.read_and_wrap, debgpt_home=ag.debgpt_home)
            msg = _append_info(msg, func(spec))
        elif key == 'inplace':
            # This is a special case. It reads the file as does by
            # `--file` (read-only), but `--inplace` (read-write) will write
            # the result back to the file. This serves code editing purpose.
            msg = _append_info(msg, reader.file(ag.inplace))
        else:
            raise NotImplementedError(key)

    # --ask should be processed as the last one
    if ag.ask:
        msg = '' if msg is None else msg
        msg += ('' if not msg else '\n') + ag.ask

    return msg


def _debgpt_is_not_configured(ag) -> bool:
    '''
    '''
    return all([
        ag.frontend == 'openai',
        ag.openai_api_key == 'your-openai-api-key',
        ag.openai_base_url == 'https://api.openai.com/v1',
        ag.subparser_name not in ('genconfig', 'config.toml'),
    ])


def main(argv=sys.argv[1:]):
    # parse args, argument order, and prepare debgpt_home
    ag = arguments.parse_args(argv)
    ag_order = arguments.parse_args_order(argv)
    if ag.verbose:
        console.log('Arguments:', ag)
        console.log('Argument Order:', ag_order)

    # process --version (if any) and exit normally.
    if ag.version:
        version()
        exit(0)

    # detect first-time launch (fresh install) where config is missing
    if _debgpt_is_not_configured(ag):
        configurator.fresh_install_guide(
            os.path.expanduser('~/.debgpt/config.toml'))
        exit(0)

    # process subcommands. Note, the subcommands will exit() when finished.
    if ag.subparser_name == 'vdb':
        if ag.vdb_subparser_name == 'ls':
            subcmd_vdb_ls(ag)
        else:
            subcmd_vdb(ag)
    elif ag.subparser_name == 'replay':
        subcmd_replay(ag)
    elif ag.subparser_name == 'config':
        subcmd_config(ag)
    elif ag.subparser_name in ('genconfig', 'config.toml'):
        subcmd_genconfig(ag)

    # initialize the frontend
    f = frontend.create_frontend(ag)
    #ag.frontend_instance = f

    # create task-specific prompts. note, some special tasks will exit()
    # in their subparser default function when then finished, such as backend,
    # version, etc. They will exit.
    msg = None  # ag.func(ag)
    if ag.subparser_name == 'pipe':
        msg = 'The following content are to be modified:\n```\n' + msg
        msg += '\n```\n\n'

    # gather all specified information in the initial prompt,
    # such as --file, --man, --policy, --ask
    msg = gather_information_ordered(msg, ag, ag_order)

    # in dryrun mode, we simply print the generated initial prompts
    # then the user can copy the prompt, and paste them into web-based
    # LLMs like the free web-based ChatGPT (OpenAI), claude.ai (Anthropic),
    # Bard (google), Gemini (google), huggingchat (huggingface), etc.
    if ag.frontend == 'dryrun':
        console.print(msg, markup=False)
        exit(0)

    # print the prompt and do the first query, if specified
    if msg is not None:
        if not ag.hide_first:
            console.print(Panel(escape(msg), title='Initial Prompt'))

        # query the backend
        frontend.interact_once(f, msg)

    # drop the user into interactive mode if specified (-i)
    if not ag.quit:
        frontend.interact_with(f)

    # inplace mode: write the LLM response back to the file
    if ag.inplace:
        # read original contents (for diff)
        with open(ag.inplace, 'rt') as fp:
            contents_orig = fp.read().splitlines(keepends=True)
        # read the edited contents (for diff)
        contents_edit = f.session[-1]['content'].splitlines(keepends=True)
        # write the edited contents back to the file
        lastnewline = '' if contents_edit[-1].endswith('\n') else '\n'
        with open(ag.inplace, 'wt') as fp:
            fp.write(f.session[-1]['content'] + lastnewline)
        # Highlight the diff using Pygments for terminal output
        diff = difflib.unified_diff(contents_orig, contents_edit, 'Original',
                                    'Edited')
        diff_str = ''.join(diff)
        highlighted_diff = highlight(diff_str, DiffLexer(),
                                     TerminalFormatter())
        console.print(Rule('DIFFERENCE'))
        print(highlighted_diff)  # rich will render within code [] and break it

        # further more, deal with git add and commit
        if ag.inplace_git_add_commit or ag.inplace_git_add_p_commit:
            # let the user review the changes
            if ag.inplace_git_add_p_commit:
                os.system(f'git add -p {ag.inplace}')
            else:
                os.system(f'git add {ag.inplace}')
            ag.amend = False  # no git commit --amend.
            subcmd_git_commit(ag)

    # dump session to json
    f.dump()
    if ag.output is not None:
        if os.path.exists(ag.output):
            console.print(
                f'[red]! destination {ag.output} exists. Will not overwrite this file.[/red]'
            )
        else:
            with open(ag.output, 'wt') as fp:
                fp.write(f.session[-1]['content'])


if __name__ == '__main__':
    main()
