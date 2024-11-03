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
from .task import task_backend, task_git, task_git_commit, task_replay
from .task import task_vdb, task_vdb_ls
from . import defaults
from . import reader
from . import frontend
from . import configurator

warnings.filterwarnings("ignore")

console = defaults.console


def generate_config_file(ag) -> None:
    '''
    special task: generate config template, print and quit
    '''
    print(ag.config_template)  # should go to stdout
    exit(0)


def reconfigure(ag) -> None:
    '''
    re-run the configurator.fresh_install_guide() to reconfigure.
    Force rewrite.
    '''
    configurator.fresh_install_guide(
        os.path.expanduser('~/.debgpt/config.toml'))
    exit(0)


def mapreduce_super_long_context(ag) -> str:
    '''
    We can add a mechanism to chunk super long context , let LLM read chunk
    by chunk, providing chunk-wise analysis. Then we aggregate the chunk-wise
    analysis together using LLM again.

    Procedure:
      1. chunk a long input into pieces
      2. map each piece to LLM and get the result
      3. reduce (aggregate) the results using LLM
      4. return the aggregated LLM output
    '''
    # TODO: parse special questions like does in gather_information_ordered()
    if ag.ask:
        user_question = ag.ask
    else:
        user_question = 'summarize the above contents.'

    chunks = reader.mapreduce_load_any_astext(ag.mapreduce,
                                              ag.mapreduce_chunksize,
                                              user_question=user_question,
                                              args=ag)
    console.print(
        f'[bold]MapReduce[/bold]: Got {len(chunks)} chunks from {ag.mapreduce}'
    )
    if ag.verbose:
        for i, chunk in enumerate(chunks):
            firstline = chunk.split('\n')[:1]
            console.print(f'  [bold]Chunk {i}[/bold]: {firstline}...')

    def _shorten(s: str, maxlen: int = 100) -> str:
        return textwrap.shorten(s[::-1], width=maxlen,
                                placeholder='......')[::-1]

    def _pad_chunk(chunk: str, question: str) -> str:
        '''
        process a chunk of text with a question
        '''
        template = 'Extract any information that is relevant to question '
        template += f'{repr(question)} from the following file part. '
        template += 'Note, if there is no relevant information, just briefly say nothing.'
        template += '\n\n\n'
        template += chunk
        return template

    # skip mapreduce if there is only one chunk
    if len(chunks) == 1:
        filepath = reader.mapreduce_parse_path(ag.mapreduce,
                                               debgpt_home=ag.debgpt_home)
        if any(
                filepath.startswith(x)
                for x in ('file://', 'http://', 'https://')):
            return reader.url(filepath)
        else:
            if filepath.endswith('.pdf'):
                return reader.pdf(filepath)
            else:
                return reader.file(filepath)

    def _process_chunk(chunk: str, question: str) -> str:
        '''
        process a chunk of text with a question
        '''
        template = _pad_chunk(chunk, question)
        if ag.verbose:
            console.log('mapreduce:send:', _shorten(template, 100))
        answer = ag.frontend_instance.oneshot(template)
        if ag.verbose:
            console.log('mapreduce:recv:', _shorten(answer, 100))
        return answer

    def _pad_two_results(a: str, b: str, question: str) -> str:
        template = 'Extract any information that is relevant to question '
        template += f'{repr(question)} from the following contents and aggregate them. '
        template += 'Note, if there is no relevant information, just briefly say nothing.'
        template += '\n\n\n'
        template += '```\n' + a + '\n```\n\n'
        template += '```\n' + b + '\n```\n\n'
        return template

    def _process_two_results(a: str, b: str, question: str) -> str:
        template = _pad_two_results(a, b, question)
        if ag.verbose:
            console.log('mapreduce:send:', _shorten(template, 100))
        answer = ag.frontend_instance.oneshot(template)
        if ag.verbose:
            console.log('mapreduce:recv:', _shorten(answer, 100))
        return answer

    # start the reduce of chunks from super long context
    if ag.mapreduce_parallelism > 1:
        '''
        Parallel processing. Note, we may easily exceed the TPM limit set
        by the service provider. We will automatically retry until success.
        '''
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=ag.mapreduce_parallelism) as executor:
            results = list(
                track(executor.map(lambda x: _process_chunk(x, user_question),
                                   chunks),
                      total=len(chunks),
                      description=f'MapReduce[{ag.mapreduce_parallelism}]:',
                      transient=True))
        while len(results) > 1:
            console.print(
                f'[bold]MapReduce[/bold]: reduced to {len(results)} intermediate results'
            )
            pairs = list(zip(results[::2], results[1::2]))
            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=ag.mapreduce_parallelism) as executor:
                new_results = list(
                    track(
                        executor.map(
                            lambda x: _process_two_results(*x, user_question),
                            pairs),
                        total=len(pairs),
                        description=f'Mapreduce[{ag.mapreduce_parallelism}]:',
                        transient=True))
            if len(results) % 2 == 1:
                new_results.append(results[-1])
            results = new_results
        aggregated_result = results[0]
    else:
        '''
        serial processing
        '''
        # mapreduce::first pass
        results = []
        for chunk in track(chunks,
                           total=len(chunks),
                           description='MapReduce: initial pass'):
            results.append(_process_chunk(chunk, user_question))
        # mapreduce::recursive processing
        while len(results) > 1:
            console.print(
                f'[bold]MapReduce[/bold]: reduced to {len(results)} intermediate results'
            )
            new_results = []
            for (a, b) in track(zip(results[::2], results[1::2]),
                                total=len(results) // 2,
                                description='Mapreduce: intermediate pass'):
                new_results.append(_process_two_results(a, b, user_question))
            if len(results) % 2 == 1:
                new_results.append(results[-1])
            results = new_results
        aggregated_result = results[0]
    return aggregated_result + '\n\n'


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
        if key in ('file', 'tldr', 'man', 'buildd', 'pynew', 'archw', 'pdf'):
            spec = getattr(ag, key).pop(0)
            func = getattr(reader, key)
            msg = _append_info(msg, func(spec))
        elif key == 'cmd':
            cmd_line = ag.cmd.pop(0)
            msg = _append_info(msg, reader.command_line(cmd_line))
        elif key == 'bts':
            bts_id = ag.bts.pop(0)
            msg = _append_info(msg, reader.bts(bts_id, raw=ag.bts_raw))
        elif key == 'html':
            url = ag.html.pop(0)
            msg = _append_info(msg, reader.html(url, raw=False))
        elif key in ('policy', 'devref'):
            spec = getattr(ag, key).pop(0)
            func = getattr(reader, key)
            msg = _append_info(msg, func(spec, debgpt_home=ag.debgpt_home))
        elif key == 'inplace':
            # This is a special case. It reads the file as does by
            # `--file` (read-only), but `--inplace` (read-write) will write
            # the result back to the file. This serves code editing purpose.
            msg = _append_info(msg, reader.file(ag.inplace))
        elif key == 'mapreduce':
            # but we only do once for mapreduce
            if __has_done_mapreduce:
                continue
            msg = _append_info(msg, mapreduce_super_long_context(ag))
            __has_done_mapreduce = True
        else:
            raise NotImplementedError(key)

    # --ask should be processed as the last one
    if ag.ask:
        msg = '' if msg is None else msg
        msg += ('' if not msg else '\n') + ag.ask

    return msg


def main(argv=sys.argv[1:]):
    # parse args and prepare debgpt_home
    ag = parse_args(argv)
    if ag.version:
        version()
        exit(0)
    # detect first-time launch (fresh install)
    whether_show_fresh_install_guide = all([
        ag.frontend == 'openai',
        ag.openai_api_key == 'your-openai-api-key',
        ag.openai_base_url == 'https://api.openai.com/v1',
        ag.subparser_name not in ('genconfig', 'genconf', 'config.toml'),
    ])
    if whether_show_fresh_install_guide:
        configurator.fresh_install_guide(
            os.path.expanduser('~/.debgpt/config.toml'))
        exit(0)

    # parse argument order
    ag_order = parse_args_order(argv)
    if ag.verbose:
        console.log('Argument Order:', ag_order)

    # initialize the frontend
    f = frontend.create_frontend(ag)
    ag.frontend_instance = f

    # create task-specific prompts. note, some special tasks will exit()
    # in their subparser default function when then finished, such as backend,
    # version, etc. They will exit.
    msg = ag.func(ag)
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
        frontend.query_once(f, msg)

    # drop the user into interactive mode if specified (-i)
    if not ag.quit:
        interactive_mode(f, ag)

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
            task_git_commit(ag)

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
