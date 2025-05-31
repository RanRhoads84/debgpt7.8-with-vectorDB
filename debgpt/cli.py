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
from debgpt import version
from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import DiffLexer
from rich.markup import escape
from rich.panel import Panel
from rich.rule import Rule
from typing import Optional
import argparse
import difflib
import functools as ft
import os
import sys
import tempfile
import textwrap
import warnings

from . import arguments
from . import configurator
from . import defaults
from . import frontend
from . import mapreduce
from . import reader
from . import replay
from . import vectordb
from . import cache

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


def subcmd_delete_cache(ag) -> None:
    '''
    special task: delete cache
    '''
    os.remove(defaults.CACHE)
    console.log(f'Cache {defaults.CACHE} deleted.')
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
    msg += reader.read_cmd('git log --pretty=format:%s --max-count=10')
    msg += "```"
    msg += "\n"
    msg += "Change diff:\n"
    msg += "```\n"
    msg += reader.read_cmd('git diff --staged')
    msg += "```\n"
    msg += "\n"
    msg += 'Write a good git commit message subject line for the change diff shown above, using the project style visible in previous commits titles above.'
    frontend.interact_once(f, msg)
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
            textwrap.wrap(f"\n\nThe real prompt is: {repr(ag.ask)}", width=80))
        commit_message += '\n'
        commit_message += '\n'.join(
            textwrap.wrap(f"\n\nFrontend used: {repr(ag.frontend)}", width=80))
        commit_message += '\n'
        if ag.frontend == "openai":
            commit_message += '\n'.join(
                textwrap.wrap(f"\n\nOpenAI model: {repr(ag.openai_model)}",
                              width=80))
        elif ag.frontend == "google":
            commit_message += '\n'.join(
                textwrap.wrap(f"\n\nGoogle model: {repr(ag.google_model)}",
                              width=80))
        elif ag.frontend == "anthropic":
            commit_message += '\n'.join(
                textwrap.wrap(f"\n\nAnthropic model: {repr(ag.anthropic_model)}",
                              width=80))
        elif ag.frontend == "ollama":
            commit_message += '\n'.join(
                textwrap.wrap(f"\n\nOllama model: {repr(ag.ollama_model)}",
                              width=80))
        elif ag.frontend == "llamafile":
            commit_message += '\n'.join(
                textwrap.wrap(f"\n\nLlamafile model: {repr(ag.llamafile_model)}",
                              width=80))
        elif ag.frontend == "vllm":
            commit_message += '\n'.join(
                textwrap.wrap(f"\n\nVLLM model: {repr(ag.vllm_model)}", width=80))
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

    def _append_info(msg: str, info: str) -> str:
        msg = '' if msg is None else msg
        return msg + '\n' + info

    # following the argument order, dispatch to reader.* functions with
    # different function signatures
    for key in ag_order:
        if key == 'mapreduce':
            spec = ag.mapreduce.pop(0)
            aggregated = mapreduce.mapreduce_super_long_context(
                spec,
                ag.mapreduce_chunksize,
                ag.frontend_instance,
                ag.ask,
                ag.verbose,
                ag.mapreduce_map_mode == 'compact',
                ag.mapreduce_reduce_mode == 'compact',
                parallelism=ag.mapreduce_parallelism)
            msg = _append_info(msg, aggregated)
        elif key == 'retrieve':
            raise NotImplementedError(key)
        elif key == 'embed':
            raise NotImplementedError(key)
        elif key in ('file', ):
            spec = getattr(ag, key).pop(0)
            func = ft.partial(reader.read_and_wrap)
            msg = _append_info(msg, func(spec))
        elif key == 'inplace':
            # This is a special case. It reads the file as does by
            # `--file` (read-only), but `--inplace` (read-write) will write
            # the result back to the file. This serves code editing purpose.
            msg = _append_info(msg, reader.read_file(ag.inplace))
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


def _dispatch_subcommand(ag):
    if ag.subparser_name == 'vdb':
        if ag.vdb_subparser_name == 'ls':
            subcmd_vdb_ls(ag)
        else:
            subcmd_vdb(ag)
    elif ag.subparser_name == 'replay':
        subcmd_replay(ag)
    elif ag.subparser_name == 'delete-cache':
        subcmd_delete_cache(ag)
    elif ag.subparser_name == 'config':
        subcmd_config(ag)
    elif ag.subparser_name in ('genconfig', 'config.toml'):
        subcmd_genconfig(ag)
    elif ag.subparser_name == 'git':
        if ag.git_subparser_name == 'commit':
            ag.frontend_instance = frontend.create_frontend(ag)
            subcmd_git_commit(ag)
        else:
            subcmd_git(ag)
    elif ag.subparser_name is not None:
        raise NotImplementedError(
            f'Subcommand {ag.subparser_name} seems unimplemented.')
    else:
        # If no subparser specified, we go to the chatting mode.
        pass


def sideeffect_cache_refresh() -> None:
    '''
    handles the cache refresh, automatically delete the expired cache
    entries. We need to do this because the cache expire seems not
    thread safe and would cause trouble if we don't do it before
    entering anything with concurrent.futures.ThreadPoolExecutor.
    '''
    # triggers automatic cache expire
    c = cache.Cache(defaults.CACHE)
    c.close()


def sideeffect_output(ag: object, f: frontend.AbstractFrontend) -> None:
    '''
    handles the output specified by --output argument
    '''
    if ag.output is not None:
        if os.path.exists(ag.output):
            console.print(
                f'[red]! destination {ag.output} exists. Will not overwrite this file.[/red]'
            )
        else:
            with open(ag.output, 'wt') as fp:
                fp.write(f.session[-1]['content'])


def sideeffect_inplace(ag: object, f: frontend.AbstractFrontend) -> None:
    '''
    handles the inplace mode specified by --inplace argument
    '''
    if ag.inplace:
        # read original contents (for diff)
        with open(ag.inplace, 'rt') as fp:
            contents_orig = fp.read().splitlines(keepends=True)
            contents_orig[-1] = contents_orig[-1].rstrip('\n')
        # read the edited contents (for diff)
        contents_edit = f.session[-1]['content'].splitlines(keepends=True)
        contents_edit[-1] = contents_edit[-1].rstrip('\n')
        # write the edited contents back to the file
        lastnewline = '' if f.session[-1]['content'].endswith('\n') else '\n'
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


def main(argv=sys.argv[1:]):
    # parse args, argument order, and prepare debgpt_home
    ag = arguments.parse_args(argv)
    ag_order = arguments.parse_args_order(argv)
    if ag.verbose:
        ag_filtered = {k: v for (k, v) in vars(ag).items()
                       if k not in ('config_template')}
        ag_filtered = argparse.Namespace(**ag_filtered)
        console.log('Arguments (filtered):', ag_filtered)
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

    # refresh debgpt cache
    sideeffect_cache_refresh()

    # process subcommands. Note, the subcommands will exit() when finished.
    # some subcommands will require a frontend instance, such as git commit.
    _dispatch_subcommand(ag)

    # initialize the frontend
    f = frontend.create_frontend(ag)
    # some information collector require a frontend instance, such as mapreduce
    ag.frontend_instance = f

    # create task-specific prompts. note, some special tasks will exit()
    # in their subparser default function when then finished, such as backend,
    # version, etc. They will exit.
    msg = None  # ag.func(ag)
    if ag.subparser_name == 'pipe':
        msg = 'The following content are to be modified:\n```\n' + msg
        msg += '\n```\n\n'

    # gather all specified information in the initial prompt,
    # including --mapreduce, --retrieval, --embed, --file, --inplace, --ask.
    msg = gather_information_ordered(msg, ag, ag_order)

    # in dryrun mode, we simply print the generated initial prompts
    # then the user can copy the prompt, and paste them into web-based LLMs.
    if ag.frontend == 'dryrun':
        console.print(msg, markup=False)
        exit(0)

    pending_exc = None

    try:
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
        sideeffect_inplace(ag, f)

        # handle the --output argument
        sideeffect_output(ag, f)
    except Exception as e:
        # re-raise the exception later
        pending_exc = e
    finally:
        # let frontend dump session to json under debgpt_home
        f.dump()

    if pending_exc is not None:
        raise pending_exc

if __name__ == '__main__':
    main()
