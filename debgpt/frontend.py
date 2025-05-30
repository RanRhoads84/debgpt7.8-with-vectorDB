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
from typing import List, Dict, Union, Optional
import argparse
import os
import json
import uuid
import sys
import time
import functools as ft
import shlex

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style
from rich.console import Console, Group
from rich.live import Live
from rich.status import Status
from rich.markdown import Markdown
from rich.markup import escape
from rich.text import Text
from rich.padding import Padding
from rich.panel import Panel
from rich.style import Style as richStyle

from . import defaults

console = defaults.console
console_stdout = Console()


def _check(messages: List[Dict]):
    '''
    communitation protocol.
    both huggingface transformers and openapi api use this
    '''
    assert isinstance(messages, list)
    assert all(isinstance(x, dict) for x in messages)
    assert all('role' in x.keys() for x in messages)
    assert all('content' in x.keys() for x in messages)
    assert all(isinstance(x['role'], str) for x in messages)
    assert all(isinstance(x['content'], str) for x in messages)
    assert all(x['role'] in ('system', 'user', 'assistant') for x in messages)


def retry_ratelimit(func: callable,
                    exception: Exception,
                    retry_interval: int = 15):
    '''
    a decorator to retry the function call when exception occurs.

    OpenAI API doc provides some other methods to retry:
    https://platform.openai.com/docs/guides/rate-limits/error-mitigation
    '''

    @ft.wraps(func)
    def wrapper(*args, **kwargs):
        while True:
            try:
                result = func(*args, **kwargs)
                break
            except exception:
                console.log(
                    f'Rate limit reached. Will retry after {retry_interval} seconds.'
                )
                time.sleep(15)
        return result

    return wrapper


class AbstractFrontend():
    '''
    The frontend instance holds the whole chat session. The context is the whole
    session for the next LLM query. Historical chats is also a part of the
    context for following up questions. You may feel LLMs smart when they
    get information from the historical chat in the same session.
    '''

    NAME = 'AbstractFrontend'

    def __init__(self, args):
        self.uuid = uuid.uuid4()
        self.session = []
        self.debgpt_home = args.debgpt_home
        self.monochrome = args.monochrome
        self.multiline = args.multiline
        self.render_markdown = args.render_markdown
        self.vertical_overflow = args.vertical_overflow
        self.verbose = args.verbose
        console.log(f'{self.NAME}> Starting conversation {self.uuid}')

    def reset(self):
        '''
        clear the context. No need to change UUID I think.
        '''
        self.session = []

    def oneshot(self, message: str) -> str:
        '''
        Generate response text from the given question, without history.
        And do not print anything. Just return the response text silently.

        Args:
            message: a string, the question.
        Returns:
            a string, the response text.
        '''
        raise NotImplementedError('please override AbstractFrontend.oneshot()')

    def query(self, messages: List[Dict]) -> str:
        '''
        Generate response text from the given chat history. This function
        will also handle printing and rendering.

        Args:
            messages: a list of dict, each dict contains a message.
        Returns:
            a string, the response text.
        the messages format can be found in _check(...) function above.
        '''
        raise NotImplementedError('please override AbstractFrontend.query()')

    def update_session(self, messages: Union[List, Dict, str]) -> None:
        if isinstance(messages, list):
            # reset the chat with provided message list
            self.session = messages
        elif isinstance(messages, dict):
            # just append a new dict
            self.session.append(messages)
        elif isinstance(messages, str):
            # just append a new user dict
            self.session.append({'role': 'user', 'content': messages})
        else:
            raise TypeError(type(messages))
        _check(self.session)

    def __call__(self, *args, **kwargs):
        try:
            res = self.query(*args, **kwargs)
            return res
        except Exception as e:
            # this will only appear in dumped session files
            self.update_session({'role': 'system', 'content': str(e)})
            raise e

    def dump(self):
        fpath = os.path.join(self.debgpt_home, str(self.uuid) + '.json')
        with open(fpath, 'wt') as f:
            json.dump(self.session, f, indent=2)
        console.log(f'{self.NAME}> Conversation saved at {fpath}')

    def __len__(self):
        '''
        Calculate the number of messages from user and assistant in the session,
        excluding system message.
        '''
        return len([x for x in self.session if x['role'] != 'system'])


class EchoFrontend(AbstractFrontend):
    '''
    A frontend that echoes the input text. Don't worry, this is just for
    running unit tests.
    '''
    NAME = 'EchoFrontend'
    lossy_mode: bool = False
    lossy_rate: int = 2

    def __init__(self, args: Optional[object] = None):
        # do not call super().__init__(args) here.
        self.session = []
        self.stream = False
        self.monochrome = False
        self.multiline = False
        self.render_markdown = False

    def oneshot(self, message: str) -> str:
        if self.lossy_mode:
            return message[::self.lossy_rate]
        else:
            return message

    def query(self, messages: Union[List, Dict, str]) -> list:
        self.update_session(messages)
        new_input = self.session[-1]['content']
        if self.lossy_mode:
            response = new_input[::self.lossy_rate]
        else:
            response = new_input
        console_stdout.print(response)
        new_message = {'role': 'assistant', 'content': response}
        self.update_session(new_message)
        return self.session[-1]['content']

    def dump(self):
        pass


class OpenAIFrontend(AbstractFrontend):
    '''
    https://platform.openai.com/docs/quickstart?context=python
    '''
    NAME: str = 'OpenAIFrontend'
    debug: bool = False
    stream: bool = True
    
    def __init__(self, args):
        super().__init__(args)
        try:
            from openai import OpenAI
        except ImportError:
            console.log('please install OpenAI package: "pip install openai"')
            exit(1)
        self.client = OpenAI(api_key=args.openai_api_key,
                             base_url=args.openai_base_url)
        self.model = args.openai_model
        # XXX: some models do not support system messages yet. nor temperature.
        if self.model not in ('o1-mini', 'o1-preview', 'o3-mini'):
            self.session.append({"role": "system", "content": args.system_message})
            self.kwargs = {'temperature': args.temperature, 'top_p': args.top_p}
        else:
            self.kwargs = {}
        if args.verbose:
            console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                        f'temperature={args.temperature}, top_p={args.top_p}.')

    def oneshot(self, message: str) -> str:

        def _func() -> str:
            _callable = self.client.chat.completions.create
            completions = _callable(model=self.model,
                                    messages=[{
                                        "role": "user",
                                        "content": message
                                    }],
                                    **self.kwargs)
            return completions.choices[0].message.content

        from openai import RateLimitError
        return retry_ratelimit(_func, RateLimitError)()

    def query(self, messages: Union[List, Dict, str]) -> list:
        # add the message into the session
        self.update_session(messages)
        if self.debug:
            console.log('send:', self.session[-1])
        completion = self.client.chat.completions.create(model=self.model,
                                                         messages=self.session,
                                                         stream=self.stream,
                                                         **self.kwargs)
        # if the stream is enabled, we will print the response in real-time.
        if self.stream:
            n_tokens: int = 0
            time_start_end: List[float] = [0.0, 0.0]
            think, chunks = [], []
            cursor = chunks
            if self.render_markdown:
                with Live(Markdown(''), vertical_overflow=self.vertical_overflow) as live:
                    time_start_end[0] = time.time()
                    for chunk in completion:
                        if hasattr(chunk.choices[0].delta, 'reasoning_content'):
                            if chunk.choices[0].delta.reasoning_content:
                                rpiece = chunk.choices[0].delta.reasoning_content
                                think.append(rpiece)
                        if chunk.choices[0].delta.content:
                            piece = chunk.choices[0].delta.content
                            n_tokens += 1
                            if piece == '</think>' and len(think) > 0:
                                cursor = chunks
                            elif piece == '<think>':
                                cursor = think
                            else:
                                cursor.append(piece)
                        else:
                            continue
                        # join chunks
                        buffer_think = ''.join(think)
                        part1 = Text(buffer_think)
                        part1 = Padding(part1, (0, 2),
                                        style=richStyle(dim=True, italic=True))
                        buffer_chunk = ''.join(chunks)
                        part2 = Markdown(buffer_chunk)
                        group = Group(part1, part2)
                        live.update(group, refresh=True)
                    time_start_end[1] = time.time()
            else:
                time_start_end[0] = time.time()
                for chunk in completion:
                    if chunk.choices[0].delta.reasoning_content:
                        piece = chunk.choices[0].delta.reasoning_content
                        think.append(piece)
                        print(piece, end="", flush=True)
                    if chunk.choices[0].delta.content:
                        piece = chunk.choices[0].delta.content
                        n_tokens += 1
                        chunks.append(piece)
                        print(piece, end="", flush=True)
                    else:
                        continue
                time_start_end[1] = time.time()
            generated_text = ''.join(chunks)
            if not generated_text.endswith('\n'):
                print()
                sys.stdout.flush()
            # print the generation token per second (TPS) in verbose mode
            if self.verbose:
                _gtps = n_tokens / (time_start_end[1] - time_start_end[0])
                console.log(
                    f'{self.NAME}({self.model})> {_gtps:.2f} generation tokens per second.')
        else:
            reasoning_content = completion.choices[0].delta.reasoning_content
            generated_text = completion.choices[0].message.content
            if self.render_markdown:
                console_stdout.print(Panel(Markdown(reasoning_content)))
                console_stdout.print(Markdown(generated_text))
            else:
                console_stdout.print(Panel(reasoning_content))
                console_stdout.print(escape(generated_text))
        new_message = {'role': 'assistant', 'content': generated_text}
        self.update_session(new_message)
        if self.debug:
            console.log('recv:', self.session[-1])
        return self.session[-1]['content']


class AnthropicFrontend(AbstractFrontend):
    '''
    https://docs.anthropic.com/en/api/getting-started
    But we are currently using OpenAI API.

    The max_token limit for each model can be found here:
    https://docs.anthropic.com/en/docs/about-claude/models
    '''
    NAME = 'AnthropicFrontend'
    debug: bool = False
    stream: bool = True
    max_tokens: int = 4096

    def __init__(self, args):
        super().__init__(args)
        try:
            from anthropic import Anthropic
        except ImportError:
            console.log(
                'please install Anthropic package: "pip install anthropic"')
            exit(1)
        self.client = Anthropic(api_key=args.anthropic_api_key,
                                base_url=args.anthropic_base_url)
        self.model = args.anthropic_model
        self.kwargs = {'temperature': args.temperature, 'top_p': args.top_p}
        if args.verbose:
            console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                        f'temperature={args.temperature}, top_p={args.top_p}.')

    def oneshot(self, message: str) -> str:

        def _func():
            _callable = self.client.messages.create
            completion = _callable(model=self.model,
                                   messages=[{
                                       "role": "user",
                                       "content": message
                                   }],
                                   max_tokens=self.max_tokens,
                                   **self.kwargs)
            return completion.content[0].text

        from anthropic import RateLimitError
        return retry_ratelimit(_func, RateLimitError)()

    def query(self, messages: Union[List, Dict, str]) -> list:
        # add the message into the session
        self.update_session(messages)
        if self.debug:
            console.log('send:', self.session[-1])
        if self.stream:
            chunks = []
            with self.client.messages.stream(model=self.model,
                                             messages=self.session,
                                             max_tokens=self.max_tokens,
                                             **self.kwargs) as stream:
                if self.render_markdown:
                    with Live(Markdown(''), vertical_overflow=self.vertical_overflow) as live:
                        for chunk in stream.text_stream:
                            chunks.append(chunk)
                            live.update(Markdown(''.join(chunks)),
                                        refresh=True)
                else:
                    for chunk in stream.text_stream:
                        chunks.append(chunk)
                        print(chunk, end="", flush=True)
            generated_text = ''.join(chunks)
            if not generated_text.endswith('\n'):
                print()
                sys.stdout.flush()
        else:
            completion = self.client.messages.create(
                model=self.model,
                messages=self.session,
                max_tokens=self.max_tokens,
                stream=self.stream,
                **self.kwargs)
            generated_text = completion.content[0].text
            if self.render_markdown:
                console_stdout.print(Markdown(generated_text))
            else:
                console_stdout.print(escape(generated_text))
        new_message = {'role': 'assistant', 'content': generated_text}
        self.update_session(new_message)
        if self.debug:
            console.log('recv:', self.session[-1])
        return self.session[-1]['content']


class GoogleFrontend(AbstractFrontend):
    '''
    https://ai.google.dev/gemini-api/docs
    '''
    NAME = 'GoogleFrontend'
    debug: bool = False
    stream: bool = True

    def __init__(self, args):
        super().__init__(args)
        try:
            import google.generativeai as genai
        except ImportError:
            console.log(
                'please install gemini package: "pip install google-generativeai"'
            )
            exit(1)
        genai.configure(api_key=args.google_api_key)
        self.client = genai.GenerativeModel(args.google_model)
        self.chat = self.client.start_chat()
        self.kwargs = genai.types.GenerationConfig(
            temperature=args.temperature, top_p=args.top_p)
        if args.verbose:
            console.log(f'{self.NAME}> model={repr(args.google_model)}, ' +
                        f'temperature={args.temperature}, top_p={args.top_p}.')

    def oneshot(self, message: str, *, retry: bool = True) -> str:

        def _func():
            _callable = self.client.generate_content
            result = _callable(message, generation_config=self.kwargs)
            return result.text

        from google.api_core.exceptions import ResourceExhausted
        return retry_ratelimit(_func, ResourceExhausted)()

    def query(self, messages: Union[List, Dict, str]) -> list:
        # add the message into the session
        self.update_session(messages)
        if self.debug:
            console.log('send:', self.session[-1])
        if self.stream:
            chunks = []
            response = self.chat.send_message(self.session[-1]['content'],
                                              stream=True,
                                              generation_config=self.kwargs)
            if self.render_markdown:
                with Live(Markdown(''), vertical_overflow=self.vertical_overflow) as live:
                    for chunk in response:
                        chunks.append(chunk.text)
                        live.update(Markdown(''.join(chunks)), refresh=True)
            else:
                for chunk in response:
                    chunks.append(chunk.text)
                    print(chunk.text, end="", flush=True)
            generated_text = ''.join(chunks)
        else:
            response = self.chat.send_message(self.session[-1]['content'],
                                              generation_config=self.kwargs)
            generated_text = response.text
            if self.render_markdown:
                console_stdout.print(Markdown(generated_text))
            else:
                console_stdout.print(escape(generated_text))
        new_message = {'role': 'assistant', 'content': generated_text}
        self.update_session(new_message)
        if self.debug:
            console.log('recv:', self.session[-1])
        return self.session[-1]['content']


class XAIFrontend(OpenAIFrontend):
    '''
    https://console.x.ai/
    '''
    NAME = 'xAIFrontend'

    def __init__(self, args):
        super().__init__(args)
        from openai import OpenAI
        self.client = OpenAI(api_key=args.xai_api_key,
                             base_url='https://api.x.ai/v1/')
        self.session.append({"role": "system", "content": args.system_message})
        self.model = args.xai_model
        self.kwargs = {'temperature': args.temperature, 'top_p': args.top_p}
        if args.verbose:
            console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                        f'temperature={args.temperature}, top_p={args.top_p}.')


class NvidiaFrontend(OpenAIFrontend):
    '''
    This is a frontend for Nvidia's NIM/NeMo service.
    https://build.nvidia.com/
    '''
    NAME = 'Nvidia-Frontend'

    def __init__(self, args):
        super().__init__(args)
        from openai import OpenAI
        self.client = OpenAI(api_key=args.nvidia_api_key,
                             base_url=args.nvidia_base_url)
        self.session.append({"role": "system", "content": args.system_message})
        self.model = args.nvidia_model
        self.kwargs = {'temperature': args.temperature, 'top_p': args.top_p}
        if args.verbose:
            console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                        f'temperature={args.temperature}, top_p={args.top_p}.')


class LlamafileFrontend(OpenAIFrontend):
    '''
    https://github.com/Mozilla-Ocho/llamafile
    '''
    NAME = 'LlamafileFrontend'

    def __init__(self, args):
        AbstractFrontend.__init__(self, args)
        from openai import OpenAI
        self.client = OpenAI(api_key='no-key-required',
                             base_url=args.llamafile_base_url)
        self.session.append({"role": "system", "content": args.system_message})
        self.model = 'llamafile from https://github.com/Mozilla-Ocho/llamafile'
        self.kwargs = {'temperature': args.temperature, 'top_p': args.top_p}
        if args.verbose:
            console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                        f'temperature={args.temperature}, top_p={args.top_p}.')


class OllamaFrontend(OpenAIFrontend):
    '''
    https://github.com/ollama/ollama
    '''
    NAME = 'OllamaFrontend'

    def __init__(self, args):
        AbstractFrontend.__init__(self, args)
        from openai import OpenAI
        self.client = OpenAI(api_key='no-key-required',
                             base_url=args.ollama_base_url)
        self.session.append({"role": "system", "content": args.system_message})
        self.model = args.ollama_model
        self.kwargs = {'temperature': args.temperature, 'top_p': args.top_p}
        if args.verbose:
            console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                        f'temperature={args.temperature}, top_p={args.top_p}.')


class LlamacppFrontend(OpenAIFrontend):
    '''
    https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md
    '''
    NAME = 'LlamacppFrontend'

    def __init__(self, args):
        AbstractFrontend.__init__(self, args)
        from openai import OpenAI
        self.client = OpenAI(api_key='no-key-required',
                             base_url=args.llamacpp_base_url)
        self.session.append({"role": "system", "content": args.system_message})
        self.model = 'model-is-specified-at-the-llama-server-arguments'
        self.kwargs = {'temperature': args.temperature, 'top_p': args.top_p}
        if args.verbose:
            console.log(f'{self.NAME}> ' +
                        f'temperature={args.temperature}, top_p={args.top_p}.')


class DeepSeekFrontend(OpenAIFrontend):
    '''
    https://api-docs.deepseek.com/
    '''
    NAME = 'DeepSeekFrontend'

    def __init__(self, args):
        AbstractFrontend.__init__(self, args)
        from openai import OpenAI
        self.client = OpenAI(api_key=args.deepseek_api_key,
                             base_url=args.deepseek_base_url)
        if args.deepseek_model not in ('deepseek-reasoner'):
            # see the usage recommendations at
            # https://huggingface.co/deepseek-ai/DeepSeek-R1
            self.session.append({"role": "system", "content": args.system_message})
        self.model = args.deepseek_model
        self.kwargs = {'temperature': args.temperature, 'top_p': args.top_p}
        if args.verbose:
            console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                        f'temperature={args.temperature}, top_p={args.top_p}.')


class vLLMFrontend(OpenAIFrontend):
    '''
    https://docs.vllm.ai/en/stable/serving/openai_compatible_server.html
    '''
    NAME = 'vLLMFrontend'

    def __init__(self, args):
        AbstractFrontend.__init__(self, args)
        from openai import OpenAI
        self.client = OpenAI(api_key='your-vllm-api-key',
                             base_url=args.vllm_base_url)
        self.session.append({"role": "system", "content": args.system_message})
        self.model = args.vllm_model
        self.kwargs = {'temperature': args.temperature, 'top_p': args.top_p}
        if args.verbose:
            console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                        f'temperature={args.temperature}, top_p={args.top_p}.')


class ZMQFrontend(AbstractFrontend):
    '''
    ZMQ frontend communicates with a self-hosted ZMQ backend.
    '''
    NAME = 'ZMQFrontend'
    debug: bool = False
    stream: bool = False

    def __init__(self, args):
        import zmq
        super().__init__(args)
        self.zmq_backend = args.zmq_backend
        self.socket = zmq.Context().socket(zmq.REQ)
        self.socket.connect(self.zmq_backend)
        console.log(
            f'{self.NAME}> Connected to ZMQ backend {self.zmq_backend}.')
        #
        if hasattr(args, 'temperature'):
            console.log(
                'warning! --temperature not yet supported for this frontend')
        if hasattr(args, 'top_p'):
            console.log('warning! --top_p not yet supported for this frontend')

    def query(self, content: Union[List, Dict, str]) -> list:
        if isinstance(content, list):
            self.session = content
        elif isinstance(content, dict):
            self.session.append(content)
        elif isinstance(content, str):
            self.session.append({'role': 'user', 'content': content})
        _check(self.session)
        msg_json = json.dumps(self.session)
        if self.debug:
            console.log('send:', msg_json)
        self.socket.send_string(msg_json)
        msg = self.socket.recv()
        self.session = json.loads(msg)
        _check(self.session)
        if self.debug:
            console.log('recv:', self.session[-1])
        return self.session[-1]['content']


def get_username():
    try:
        import getpass
        return getpass.getuser()
    except Exception:
        pass
    try:
        import pwd
        return pwd.getpwuid(os.getuid())[0]
    except Exception:
        pass
    try:
        return os.getlogin()
    except Exception:
        pass
    # common shell env
    for env in ('USER', 'USERNAME', 'LOGNAME'):
        if u := os.environ.get(env):
            return u
    # final fallback
    return 'user'


def create_frontend(args):
    if args.frontend == 'zmq':
        frontend = ZMQFrontend(args)
    elif args.frontend == 'openai':
        frontend = OpenAIFrontend(args)
    elif args.frontend == 'anthropic':
        frontend = AnthropicFrontend(args)
    elif args.frontend == 'google':
        frontend = GoogleFrontend(args)
    elif args.frontend == 'xai':
        frontend = XAIFrontend(args)
    elif args.frontend == 'nvidia':
        frontend = NvidiaFrontend(args)
    elif args.frontend == 'llamafile':
        frontend = LlamafileFrontend(args)
    elif args.frontend == 'ollama':
        frontend = OllamaFrontend(args)
    elif args.frontend == 'llamacpp':
        frontend = LlamacppFrontend(args)
    elif args.frontend == 'deepseek':
        frontend = DeepSeekFrontend(args)
    elif args.frontend == 'vllm':
        frontend = vLLMFrontend(args)
    elif args.frontend == 'dryrun':
        frontend = None
    elif args.frontend == 'echo':
        frontend = EchoFrontend(args)
    else:
        raise NotImplementedError
    return frontend


def interact_once(f: AbstractFrontend, text: str) -> None:
    '''
    we have prepared text -- let frontend send it to LLM, and this function
    will print the LLM reply.

    f: any frontend instance from the current source file.
    text: the text to be sent to LLM.
    '''
    if f.stream:
        end = '' if not f.render_markdown else '\n'
        if f.monochrome:
            lprompt = escape(f'LLM[{2+len(f)}]> ')
            console.print(lprompt, end=end, highlight=False, markup=False)
        else:
            lprompt = f'[bold green]LLM[{2+len(f)}]>[/bold green] '
            console.print(lprompt, end=end)
        _ = f(text)
    else:
        with Status('LLM', spinner='line'):
            _ = f(text)


def interact_with(f: AbstractFrontend) -> None:
    # create prompt_toolkit style
    if f.monochrome:
        prompt_style = Style([('prompt', 'bold')])
    else:
        prompt_style = Style([('prompt', 'bold fg:ansibrightcyan'),
                              ('', 'bold ansiwhite')])

    # Completer with several keywords keywords to be completed
    class CustomCompleter(Completer):

        def get_completions(self, document, complete_event):
            # Get the current text before the cursor
            text_before_cursor = document.text_before_cursor

            # Check if the text starts with '/'
            if text_before_cursor.startswith('/'):
                # Define the available keywords
                keywords = ['/quit', '/save', '/reset']

                # Generate completions for each keyword
                for keyword in keywords:
                    if keyword.startswith(text_before_cursor):
                        yield Completion(keyword, -len(text_before_cursor))

    # start prompt session
    prompt_session = PromptSession(style=prompt_style,
                                   multiline=f.multiline,
                                   completer=CustomCompleter())

    # if multiline is enabled, print additional help message
    if f.multiline:
        console.print(
            'In multiline mode, please press [Meta+Enter], or [Esc] followed by [Enter] to send the message.'
        )

    # loop
    user = get_username()
    try:
        while text := prompt_session.prompt(
                f'{user}[{1+len(f)}]> '):
            # parse escaped interaction commands
            if text.startswith('/'):
                cmd = shlex.split(text)
                if cmd[0] == '/save':
                    # save the last LLM reply to a file
                    if len(cmd) != 2:
                        console.print('syntax error: /save <path>')
                        continue
                    path = cmd[-1]
                    with open(path, 'wt') as fp:
                        fp.write(f.session[-1]['content'])
                    console.log(f'The last LLM response is saved at {path}')
                elif cmd[0] == '/reset':
                    if len(cmd) != 1:
                        console.print('syntax error: /reset')
                        continue
                    f.reset()
                elif cmd[0] == '/quit':
                    if len(cmd) != 1:
                        console.print('syntax error: /quit')
                        continue
                    break
                else:
                    console.print(f'unknown command: {cmd[0]}')
            else:
                interact_once(f, text)
    except EOFError:
        pass
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    ag = argparse.ArgumentParser()
    ag.add_argument('--zmq_backend', '-B', default='tcp://localhost:11177')
    ag.add_argument('--frontend',
                    '-F',
                    default='zmq',
                    choices=('dryrun', 'zmq', 'openai', 'anthropic', 'google',
                             'llamafile', 'ollama', 'vllm'))
    ag.add_argument('--debgpt_home', default=os.path.expanduser('~/.debgpt'))
    ag = ag.parse_args()
    console.print(ag)

    frontend = create_frontend(ag)
    f = frontend
    import IPython
    IPython.embed(colors='neutral')
