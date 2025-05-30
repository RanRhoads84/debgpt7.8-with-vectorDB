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
# suppress all warnings.
from typing import List, Tuple
import textwrap
import sys
import re
import argparse
from . import defaults

console = defaults.console


def parse_args(argv: List[str]) -> argparse.Namespace:
    '''
    argparse with subparsers. Generate a config.toml template as byproduct.
    '''

    # helper functions
    def __add_arg_to_config(template,
                            parser,
                            argname,
                            formatter: callable = repr):
        '''
        We will create a template for the config.toml file, based on the
        help messages of the argument parser. In that sense I do not have
        to write everything twice, and this avoids many human errors.
        '''
        template += '\n'.join('# ' + x for x in textwrap.wrap(
            parser._option_string_actions['--' + argname].help))
        template += f'''\n{argname} = {formatter(getattr(conf, argname))}\n'''
        return template

    # if ~/.debgpt/config.toml exists, parse it to override the built-in defaults.
    _verbose = any(x in argv for x in ('-v', '--verbose'))
    conf = defaults.Config(verbose=_verbose)
    # override the loaded configurations again with command line arguments
    ag = argparse.ArgumentParser()

    # CLI Behavior / Frontend Arguments
    config_template = '''\
###################################
# Command Line Interface Behavior
###################################
\n'''
    _g = ag.add_argument_group('Command Line Interface Behavior')
    _g.add_argument('--quit',
                    '-q',
                    '-Q',
                    action='store_true',
                    help='directly quit after receiving the first response \
from LLM, instead of staying in interation.')
    _g.add_argument('--multiline',
                    '-M',
                    action='store_true',
                    help='enable multi-line input for prompt_toolkit. \
use Meta+Enter to accept the input instead.')
    _g.add_argument(
        '--hide_first',
        '-H',
        action='store_true',
        help='hide the first (generated) prompt; do not print argparse results'
    )
    _g.add_argument('--verbose',
                    '-v',
                    action='store_true',
                    help='verbose mode. helpful for debugging')
    _g.add_argument('--output',
                    '-o',
                    type=str,
                    default=None,
                    help='write the last LLM message to specified file')
    _g.add_argument('--system_message',
                    '-S',
                    type=str,
                    default=conf['system_message'],
                    help='send a system message to the LLM')
    _g.add_argument('--inplace',
                    '-i',
                    type=str,
                    default='',
                    help='read file and perform inplace edit to it. \
This option will toggle --quit and turn off markdown rendering.')
    _g.add_argument(
        '--inplace-git-add-commit',
        action='store_true',
        help=
        'automatically `git add` (no human review) and `git commit` the changes to git repo.'
    )
    _g.add_argument(
        '--inplace-git-add-p-commit',
        '-I',
        action='store_true',
        help=
        'automatically `git add -p` (with human review) and `git commit commit` the changes to git repo.'
    )
    _g.add_argument('--version',
                    action='store_true',
                    help='show DebGPT software version and quit.')
    _g.add_argument('--debgpt_home',
                    type=str,
                    default=conf['debgpt_home'],
                    help='directory to store cache and sessions.')
    _g.add_argument(
        '--frontend',
        '-F',
        type=str,
        default=conf['frontend'],
        choices=(
            # development and debugging
            'dryrun',
            'echo',
            # commercial services
            'openai',
            'anthropic',
            'google',
            'xai',
            # self-hosted services
            'llamafile',
            'ollama',
            'vllm',
            'zmq'),
        help=f"default frontend is {conf['frontend']}. Available \
choices are: (dryrun, zmq, openai, anthropic, google, zmq, llamafile, ollama, vllm).\
The 'dryrun' is a fake frontend that will \
do nothing other than printing the generated prompt. So that you can copy \
it to web-based LLMs in that case.")
    config_template = __add_arg_to_config(config_template, ag, 'frontend')

    _g.add_argument('--monochrome',
                    type=bool,
                    default=conf['monochrome'],
                    help='disable colorized output for prompt_toolkit.')
    config_template = __add_arg_to_config(config_template,
                                          _g,
                                          'monochrome',
                                          formatter=lambda x: str(x).lower())
    _g.add_argument('--render_markdown',
                    '--render',
                    action=argparse.BooleanOptionalAction,
                    default=conf['render_markdown'],
                    help='render the LLM output as markdown with rich.')
    config_template = __add_arg_to_config(config_template,
                                          _g,
                                          'render_markdown',
                                          formatter=lambda x: str(x).lower())

    _g.add_argument('--vertical_overflow',
                    type=str,
                    default=conf['vertical_overflow'],
                    choices=('ellipsis', 'visible'),
                    help='vertical overflow behavior for rich Live output. See https://rich.readthedocs.io/en/stable/live.html#vertical-overflow')
    config_template = __add_arg_to_config(config_template, _g,
                                          'vertical_overflow')

    # LLM Inference Arguments
    config_template += '''\n
#############################
# Common Frontend Arguments
#############################
\n'''
    _g = ag.add_argument_group('Common Frontend Arguments')
    _g.add_argument(
        '--temperature',
        '-T',
        type=float,
        default=conf['temperature'],
        help='''Sampling temperature. Typically ranges within [0,1]. \
Low values like 0.2 gives more focused (coherent) answer. \
High values like 0.8 gives a more random (creative) answer. \
Not suggested to combine this with with --top_p. See \
https://platform.openai.com/docs/api-reference/ \
    ''')
    config_template = __add_arg_to_config(config_template, _g, 'temperature')

    _g.add_argument('--top_p',
                    '-P',
                    type=float,
                    default=conf['top_p'],
                    help='Top-p (nucleus) sampling.')
    config_template = __add_arg_to_config(config_template, _g, 'top_p')

    # Specific to OpenAI Frontend
    config_template += '''\n
###########################
# OpenAI Frontend Options
###########################
\n'''
    _g = ag.add_argument_group('OpenAI Frontend Options')
    _g.add_argument('--openai_base_url',
                    type=str,
                    default=conf['openai_base_url'],
                    help='OpenAI API is a widely adopted standard. You can \
switch to other compatible service providers, or a self-hosted compatible \
server.')
    config_template = __add_arg_to_config(config_template, _g,
                                          'openai_base_url')

    _g.add_argument('--openai_api_key',
                    type=str,
                    default=conf['openai_api_key'],
                    help='API key is necessary to access services including \
OpenAI API server. https://platform.openai.com/api-keys')
    config_template = __add_arg_to_config(config_template, _g,
                                          'openai_api_key')

    _g.add_argument('--openai_model',
                    type=str,
                    default=conf['openai_model'],
                    help='For instance, gpt-3.5-turbo (4k context), \
gpt-3.5-turbo-16k (16k context), gpt-4, gpt-4-32k (32k context). \
Their prices vary. See https://platform.openai.com/docs/models .')
    config_template = __add_arg_to_config(config_template, _g, 'openai_model')

    _g.add_argument('--openai_embedding_model',
                    type=str,
                    default=conf['openai_embedding_model'],
                    help='the openai embedding model to use')
    config_template = __add_arg_to_config(config_template, _g,
                                          'openai_embedding_model')

    # Specific to Anthropic Frontend
    config_template += '''\n
##############################
# Anthropic Frontend Options
##############################
\n'''
    _g = ag.add_argument_group('Anthropic Frontend Options')
    _g.add_argument('--anthropic_base_url',
                    type=str,
                    default=conf['anthropic_base_url'],
                    help='the URL to the Anthropic JSON API service.')
    config_template = __add_arg_to_config(config_template, _g,
                                          'anthropic_base_url')

    _g.add_argument('--anthropic_api_key',
                    type=str,
                    default=conf['anthropic_api_key'],
                    help='Anthropic API key')
    config_template = __add_arg_to_config(config_template, _g,
                                          'anthropic_api_key')

    _g.add_argument(
        '--anthropic_model',
        type=str,
        default=conf['anthropic_model'],
        help='the anthropic model, e.g., claude-3-5-sonnet-20241022')
    config_template = __add_arg_to_config(config_template, _g,
                                          'anthropic_model')

    # Specific to Google Frontend
    config_template += '''\n
###########################
# Google Frontend Options
###########################
\n'''
    _g = ag.add_argument_group('Google Frontend Options')
    _g.add_argument('--google_api_key',
                    type=str,
                    default=conf['google_api_key'],
                    help='Google API key')
    config_template = __add_arg_to_config(config_template, _g,
                                          'google_api_key')

    _g.add_argument('--google_model',
                    type=str,
                    default=conf['google_model'],
                    help='the google model, e.g., gemini-1.5-flash')
    config_template = __add_arg_to_config(config_template, _g, 'google_model')

    _g.add_argument('--google_embedding_model',
                    type=str,
                    default=conf['google_embedding_model'],
                    help='the google embedding model to use')
    config_template = __add_arg_to_config(config_template, _g,
                                          'google_embedding_model')

    # Specific to Nvidia-NIM Frontend
    config_template += '''\n
##############################
# Nvidia-NIM Frontend Options
##############################
\n'''
    _g = ag.add_argument_group('Nvidia-NIM Frontend Options')
    _g.add_argument('--nvidia_base_url',
                    type=str,
                    default=conf['nvidia_base_url'],
                    help='the URL to the Nvidia NIM JSON API service.')
    config_template = __add_arg_to_config(config_template, _g,
                                          'nvidia_base_url')
    _g.add_argument('--nvidia_api_key',
                    type=str,
                    default=conf['nvidia_api_key'],
                    help='Nvidia API key')
    config_template = __add_arg_to_config(config_template, _g,
                                          'nvidia_api_key')
    _g.add_argument('--nvidia_model',
                    type=str,
                    default=conf['nvidia_model'],
                    help='the Nvidia model, e.g., deepseek-ai/deepseek-r1')
    config_template = __add_arg_to_config(config_template, _g,
                                          'nvidia_model')

    # Specific to xAI Frontend
    config_template += '''\n
########################
# xAI Frontend Options
########################
\n'''
    _g = ag.add_argument_group('xAI Frontend Options')
    _g.add_argument('--xai_api_key',
                    type=str,
                    default=conf['xai_api_key'],
                    help='xAI API key')
    config_template = __add_arg_to_config(config_template, _g, 'xai_api_key')

    _g.add_argument('--xai_model',
                    type=str,
                    default=conf['xai_model'],
                    help='the xAI model, e.g., grok-beta')
    config_template = __add_arg_to_config(config_template, _g, 'xai_model')

    # Specific to Llamafile Frontend
    config_template += '''\n
##############################
# Llamafile Frontend Options
##############################
\n'''
    _g = ag.add_argument_group('Llamafile Frontend Options')
    _g.add_argument('--llamafile_base_url',
                    type=str,
                    default=conf['llamafile_base_url'],
                    help='the URL to the llamafile JSON API service.')
    config_template = __add_arg_to_config(config_template, _g,
                                          'llamafile_base_url')

    # Specific to Ollama Frontend
    config_template += '''\n
#########################################################
# Ollama Frontend Options (OpenAI compatibility mode)
#########################################################
\n'''
    _g = ag.add_argument_group('Ollama Frontend Options')
    _g.add_argument('--ollama_base_url',
                    type=str,
                    default=conf['ollama_base_url'],
                    help='the URL to the Ollama JSON API service.')
    config_template = __add_arg_to_config(config_template, _g,
                                          'ollama_base_url')

    _g.add_argument('--ollama_model',
                    type=str,
                    default=conf['ollama_model'],
                    help='the model to use in Ollama. For instance, llama3.2')
    config_template = __add_arg_to_config(config_template, _g, 'ollama_model')

    # Specific to llamacpp Frontend
    config_template += '''\n
#########################################################
# llama.cpp Frontend Options (OpenAI compatibility mode)
#########################################################
\n'''
    _g = ag.add_argument_group('llama.cpp Frontend Options')
    _g.add_argument('--llamacpp_base_url',
                    type=str,
                    default=conf['llamacpp_base_url'],
                    help='the URL to the llama-server (llama.cpp) API.')
    config_template = __add_arg_to_config(config_template, _g,
                                          'llamacpp_base_url')

    # Specific to DeepSeek Frontend
    config_template += '''\n
#########################################################
# DeepSeek Frontend Options
#########################################################
\n'''
    _g = ag.add_argument_group('DeepSeek Frontend Options')
    _g.add_argument('--deepseek_base_url',
                    type=str,
                    default=conf['deepseek_base_url'],
                    help='the URL to the DeepSeek API service.')
    config_template = __add_arg_to_config(config_template, _g,
                                          'deepseek_base_url')

    _g.add_argument('--deepseek_api_key',
                    type=str,
                    default=conf['deepseek_api_key'],
                    help='DeepSeek API key')
    config_template = __add_arg_to_config(config_template, _g,
                                          'deepseek_api_key')

    _g.add_argument('--deepseek_model',
                    type=str,
                    default=conf['deepseek_model'],
                    help='the model to use in DeepSeek.')
    config_template = __add_arg_to_config(config_template, _g,
                                          'deepseek_model')

    # Specific to vLLM Frontend
    config_template += '''\n
#########################
# vLLM Frontend Options
#########################
\n'''
    _g = ag.add_argument_group('vLLM Frontend Options')
    _g.add_argument('--vllm_base_url',
                    type=str,
                    default=conf['vllm_base_url'],
                    help='the URL to the vllm JSON API service.')
    config_template = __add_arg_to_config(config_template, _g, 'vllm_base_url')

    _g.add_argument('--vllm_api_key',
                    type=str,
                    default=conf['vllm_api_key'],
                    help='vLLM API key is necessary to access services')
    config_template = __add_arg_to_config(config_template, _g, 'vllm_api_key')

    _g.add_argument('--vllm_model',
                    type=str,
                    default=conf['vllm_model'],
                    help='the model to use in vllm. For instance, llama3.2')
    config_template = __add_arg_to_config(config_template, _g, 'vllm_model')

    # Specific to ZMQ Frontend
    config_template += '''\n
##############################
# ZMQ Frontend Options
##############################
\n'''
    _g = ag.add_argument_group('ZMQ Frontend Options')
    _g.add_argument(
        '--zmq_backend',
        type=str,
        default=conf['zmq_backend'],
        help='the ZMQ backend URL that the frontend will connect to')
    config_template = __add_arg_to_config(config_template, _g, 'zmq_backend')

    # Embedding Models
    config_template += '''\n
#################################
# Embedding Frontend and Models
#################################
\n'''
    _g = ag.add_argument_group('Embedding Models')
    _g.add_argument('--embedding_frontend',
                    type=str,
                    default=conf['embedding_frontend'],
                    help='the embedding frontend to use')
    config_template = __add_arg_to_config(config_template, _g,
                                          'embedding_frontend')
    _g.add_argument('--embedding_dim',
                    type=int,
                    default=conf['embedding_dim'],
                    help='the embedding dimension')
    config_template = __add_arg_to_config(config_template, _g, 'embedding_dim')

    # Prompt Loaders (numbered list). You can specify them multiple times.
    # for instance, `debgpt -H -f foo.py -f bar.py`.
    config_template += '''\n
#####################
# MapReduce Options
#####################
\n'''
    # -- 1. Debian BTS
    _g = ag.add_argument_group('Prompt reader')
    # -- 4. Arbitrary Plain Text File(s)
    _g.add_argument(
        '--file',
        '-f',
        type=str,
        default=[],
        action='append',
        help='load specified files (plain text and pdfs), directories, \
or URLs in prompt. Many special specifiers are supported, \
including buildd:<package>, bts:<number>, archwiki:<keyword>, man:<man>, cmd:<cmd>, tldr:<tldr>'
    )
    # -- 998. The special query buider for mapreduce chunks
    _g.add_argument('--mapreduce',
                    '-x',
                    action='append',
                    type=str,
                    help='load any file or directory for an answer')
    _g.add_argument('--mapreduce_chunksize',
                    type=int,
                    default=conf['mapreduce_chunksize'],
                    help='context chunk size for mapreduce')
    config_template = __add_arg_to_config(config_template, _g,
                                          'mapreduce_chunksize')
    _g.add_argument('--mapreduce_parallelism',
                    type=int,
                    default=conf['mapreduce_parallelism'],
                    help='number of parallel processes in mapreduce')
    config_template = __add_arg_to_config(config_template, _g,
                                          'mapreduce_parallelism')

    _g.add_argument('--mapreduce_map_mode',
                    type=str,
                    default='compact',
                    choices=('compact', 'binary'),
                    help='mapping mode for mapreduce')
    _g.add_argument('--mapreduce_reduce_mode',
                    type=str,
                    default='compact',
                    choices=('compact', 'binary'),
                    help='reduction mode for mapreduce')

    # -- 999. The Question Template at the End of Prompt
    _g.add_argument('--ask',
                    '-A',
                    '-a',
                    type=str,
                    default='',
                    help="User question to append at the end of the prompt. ")

    # Task Specific Subparsers
    subps = ag.add_subparsers(dest='subparser_name', help='debgpt subcommands')

    # Specific to ZMQ Backend (self-hosted LLM Inference)
    ps_backend = subps.add_parser(
        'backend', help='start backend server (self-hosted LLM inference)')
    ps_backend.add_argument('--port',
                            '-p',
                            type=int,
                            default=11177,
                            help='port number "11177" looks like "LLM"')
    ps_backend.add_argument('--host', type=str, default='tcp://*')
    ps_backend.add_argument('--backend_impl',
                            type=str,
                            default='zmq',
                            choices=('zmq', ))
    ps_backend.add_argument('--max_new_tokens', type=int, default=512)
    ps_backend.add_argument('--llm', type=str, default='Mistral7B')
    ps_backend.add_argument('--device', type=str, default='cuda')
    ps_backend.add_argument('--precision', type=str, default='fp16')

    # Task: git
    ps_git = subps.add_parser('git', help='git command wrapper')
    git_subps = ps_git.add_subparsers(dest='git_subparser_name',
                                      help='git commands')
    # Task: git commit
    ps_git_commit = git_subps.add_parser(
        'commit',
        aliases=['co'],
        help='directly commit staged changes with auto-generated message')
    ps_git_commit.add_argument('--amend',
                               action='store_true',
                               help='amend the last commit')

    # subcommand: delete-cache
    _ = subps.add_parser('delete-cache', help='delete cache sqlite database')

    # subcommand: vdb (VectorDB)
    ps_vdb = subps.add_parser('vdb', help='VectorDB command')
    ps_vdb.add_argument('--db',
                        type=str,
                        default=conf['db'],
                        help='path to the VectorDB database')
    vdb_subps = ps_vdb.add_subparsers(dest='vdb_subparser_name',
                                      help='vdb subcommands')
    # subsubcommand: vdb ls
    ps_vdb_ls = vdb_subps.add_parser('ls',
                                     help='list all vectors in the database')
    ps_vdb_ls.add_argument('id',
                           type=str,
                           default=None,
                           nargs='?',
                           help='vector ID')

    # Task: replay
    ps_replay = subps.add_parser('replay',
                                 help='replay a conversation from a JSON file')
    ps_replay.add_argument('json_file_path',
                           type=str,
                           nargs='?',
                           help='path to the JSON file')

    # Task: stdin
    _ = subps.add_parser(
        'stdin',
        help='read stdin as the first prompt. Should combine with -Q.')

    # Task: pipe
    _ = subps.add_parser(
        'pipe',
        help='read stdin, print nothing other than LLM response to stdout. \
This option will automatically mandate --no-render_markdown, -Q and -H.')

    # Task: genconfig
    _ = subps.add_parser('genconfig',
                         aliases=['config.toml'],
                         help='generate config.toml file template')

    # Task: config or reconfigure
    _ = subps.add_parser('config', help='reconfigure debgpt with a wizard')

    # -- parse and sanitize
    ag = ag.parse_args(argv)
    ag.config_template = config_template

    # -- mandate argument requirements for some options
    if ag.inplace:
        # we will toggle --quit and turn off markdown rendering
        ag.quit = True
        ag.render_markdown = False
        # we assume the user wants to edit the file inplace, and provides
        # the editing instruction through --ask|-a. Here we will append
        # some addition prompt to reduce LLM noise.
        ag.ask += ' Just show me the result and do not say anything else. No need to enclose the result using "```".'
    if ag.subparser_name == 'stdin':
        ag.quit = True
    if ag.subparser_name == 'pipe':
        ag.quit = True
        ag.hide_first = True
        ag.render_markdown = False
        ag.ask += 'Just show the full result and do not say anything else. Do not enclose the result using "```".'

    return ag


def parse_args_order(argv: List[str]) -> List[str]:
    '''
    parse the order of selected arguments

    We want `debgpt -f file1.txt -f file2.txt` generate different results
    than    `debgpt -f file2.txt -f file1.txt`. But the standard argparse
    will not reserve the order.

    For example, we need to match
    -f, --file, -Hf (-[^-]*f), into --file
    '''
    order: List[str] = []

    def _match_ls(probe: str, long: str, short: str, dest: List[str]):
        if any(probe == x for x in (long, short)) \
                or any(probe.startswith(x+'=') for x in (long, short)) \
                or re.match(r'-[^-]*'+short[-1], probe):
            dest.append(long.lstrip('--'))

    def _match_l(probe: str, long: str, dest: List[str]):
        if probe == long or probe.startswith(long + '='):
            dest.append(long.lstrip('--'))

    for item in argv:
        _match_ls(item, '--mapreduce', '-x', order)
        _match_ls(item, '--retrieve', '-r', order)
        _match_ls(item, '--embed', '-e', order)
        _match_ls(item, '--file', '-f', order)
        _match_ls(item, '--inplace', '-i', order)
    return order


def parse(argv: List[str]) -> Tuple[argparse.Namespace, List[str]]:
    '''
    Parse the command line arguments and return the parsed arguments,
    as well as the argument order.
    '''
    args = vars(parse_args(argv))
    order = parse_args_order(argv)
    return args, order


def main(argv: List[str] = sys.argv[1:]):
    '''
    The main entry point of the program.
    '''
    args, order = parse(argv)
    console.print('args:', args)
    console.print('order:', order)


if __name__ == '__main__':  # pragma: no cover
    main()
