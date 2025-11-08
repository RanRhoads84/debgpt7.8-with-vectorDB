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
from .vector_service.client import VectorServiceClient

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
        self._vector_client: Optional[VectorServiceClient] = None
        self._vector_context_prompt: Optional[str] = None
        self._vector_top_k: int = getattr(args, 'vector_service_top_k', 0)
        conv_override = getattr(args, 'vector_service_conversation_id', '')
        self._vector_conversation_id = conv_override or str(self.uuid)
        if getattr(args, 'vector_service_enabled', False):
            self._vector_client = VectorServiceClient(
                getattr(args, 'vector_service_url', 'http://127.0.0.1:8000'),
                timeout=getattr(args, 'vector_service_timeout', 5.0),
                enabled=True,
                logger=console,
            )

    def reset(self):
        '''
        clear the context. No need to change UUID I think.
        '''
        self.session = []
        self._vector_context_prompt = None
        if self._vector_client is not None:
            self._vector_conversation_id = str(uuid.uuid4())

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
            self._vector_after_append(messages)
        elif isinstance(messages, str):
            # just append a new user dict
            new_message = {'role': 'user', 'content': messages}
            self.session.append(new_message)
            self._vector_after_append(new_message)
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
        if self._vector_client is not None:
            self._vector_client.close()

    def __len__(self):
        '''
        Calculate the number of messages from user and assistant in the session,
        excluding system message.
        '''
        return len([x for x in self.session if x['role'] != 'system'])

    @property
    def _vector_active(self) -> bool:
        client = getattr(self, '_vector_client', None)
        return client is not None and getattr(client, 'enabled', False)

    def _vector_after_append(self, message: Dict) -> None:
        if not self._vector_active:
            return
        client = getattr(self, '_vector_client', None)
        if client is None:
            return
        role = message.get('role')
        content = message.get('content', '').strip()
        if role == 'user':
            self._vector_prepare_context(content)
            client.save_message(
                conversation_id=self._vector_conversation_id,
                role='user',
                text=content,
            )
        elif role == 'assistant':
            client.save_message(
                conversation_id=self._vector_conversation_id,
                role='assistant',
                text=content,
            )
            self._vector_context_prompt = None

    def _vector_prepare_context(self, query: str) -> None:
        if not query:
            self._vector_context_prompt = None
            return
        if not self._vector_active or self._vector_top_k <= 0:
            self._vector_context_prompt = None
            return
        client = getattr(self, '_vector_client', None)
        if client is None:
            self._vector_context_prompt = None
            return
        results = client.query_context(
            conversation_id=self._vector_conversation_id,
            query=query,
            top_k=self._vector_top_k,
        )
        if not results:
            self._vector_context_prompt = None
            return
        lines = [
            'You have access to the following retrieved conversation snippets. '
            'Use them to ground your response when relevant.',
        ]
        for idx, item in enumerate(results, start=1):
            role = item.get('role', 'unknown')
            score = item.get('score')
            text = (item.get('text') or '').replace('\n', ' ').strip()
            if len(text) > 512:
                text = text[:509] + '...'
            header = f'{role}'
            if isinstance(score, (int, float)):
                header += f' (score={score:.3f})'
            lines.append(f'{idx}. {header}: {text}')
        lines.append('If none of the snippets apply, continue normally.')
        self._vector_context_prompt = '\n'.join(lines)

    def _messages_for_llm(self) -> List[Dict[str, str]]:
        base = list(self.session)
        if not base or not self._vector_context_prompt:
            return base
        if base[-1].get('role') != 'user':
            return base
        injected = {
            'role': 'system',
            'content': self._vector_context_prompt,
        }
        return base[:-1] + [injected, base[-1]]


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


class VectorEchoFrontend(AbstractFrontend):
    '''
    Like EchoFrontend but keeps the vector service plumbing enabled.
    '''
    NAME = 'VectorEchoFrontend'
    lossy_mode: bool = False
    lossy_rate: int = 2

    def __init__(self, args):
        super().__init__(args)
        self.stream = False
        self.monochrome = False
        self.multiline = False
        self.render_markdown = False

    def oneshot(self, message: str) -> str:
        if self.lossy_mode:
            return message[::self.lossy_rate]
        return message

    def query(self, messages: Union[List, Dict, str]) -> list:
        self.update_session(messages)
        new_input = self.session[-1]['content']
        response = new_input[::self.lossy_rate] if self.lossy_mode else new_input
        console_stdout.print(response)
        new_message = {'role': 'assistant', 'content': response}
        self.update_session(new_message)
        return self.session[-1]['content']


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
    # GitHub Copilot: runtime detection for sampling parameter support.
    # Track whether the backend has confirmed support for sampling params.
        self._sampling_params_supported: Optional[bool] = None
        # XXX: some models do not support system messages yet. nor temperature.
        if self.model not in ('o1-mini', 'o1-preview', 'o3-mini'):
            self.session.append(
                {"role": "system", "content": args.system_message})
            # GitHub Copilot: collect user-provided sampling params once per session.
            self.kwargs = self._collect_sampling_kwargs(args)
            if not self.kwargs:
                self._sampling_params_supported = False
        else:
            self.kwargs = {}
            self._sampling_params_supported = False
        if args.verbose:
            if self.kwargs:
                console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                            f"temperature={self.kwargs.get('temperature')}, " +
                            f"top_p={self.kwargs.get('top_p')}.")
            else:
                console.log(
                    f'{self.NAME}> model={repr(self.model)}, using server default sampling parameters.')

    # GitHub Copilot: helper to gather sampling kwargs while we probe API support.
    def _collect_sampling_kwargs(self, args) -> Dict[str, float]:
        sampling_kwargs: Dict[str, float] = {}
        for key in ('temperature', 'top_p'):
            if hasattr(args, key):
                value = getattr(args, key)
                if value is not None:
                    sampling_kwargs[key] = value
        return sampling_kwargs

    # GitHub Copilot: strip unsupported sampling params and retry once detected.
    def _handle_sampling_error(self, exc: Exception) -> bool:
        if not self.kwargs:
            return False
        message = str(exc).lower()
        token_map = {
            'temperature': ('temperature',),
            'top_p': ('top_p', 'top-p')
        }
        unsupported = [param for param, aliases in token_map.items()
                       if any(alias in message for alias in aliases) and param in self.kwargs]
        if not unsupported:
            return False
        for param in unsupported:
            self.kwargs.pop(param, None)
        if self.verbose:
            rejected = ', '.join(unsupported)
            console.log(
                f'{self.NAME}> model={repr(self.model)} rejected {rejected}; retrying without it.')
        if not self.kwargs:
            self._sampling_params_supported = False
            if self.verbose:
                console.log(
                    f'{self.NAME}> falling back to server default sampling parameters.')
        else:
            self._sampling_params_supported = None
        return True

    # GitHub Copilot: centralize create() calls so retries happen transparently.
    def _chat_completions_create(self, **kwargs):
        while True:
            if self.kwargs and self._sampling_params_supported is False:
                # Sampling params were disabled previously; re-evaluate in case they were reassigned.
                self._sampling_params_supported = None
            request_kwargs = dict(kwargs)
            if self.kwargs and self._sampling_params_supported is not False:
                request_kwargs.update(self.kwargs)
            try:
                completion = self.client.chat.completions.create(
                    **request_kwargs)
            except Exception as exc:
                if self.kwargs and self._sampling_params_supported is not False and self._handle_sampling_error(exc):
                    continue
                raise
            else:
                if self.kwargs:
                    self._sampling_params_supported = True
                return completion

    def oneshot(self, message: str) -> str:

        def _func() -> str:
            completions = self._chat_completions_create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": message
                }],
                stream=False)
            return completions.choices[0].message.content

        from openai import RateLimitError
        return retry_ratelimit(_func, RateLimitError)()

    def query(self, messages: Union[List, Dict, str]) -> list:
        # add the message into the session
        self.update_session(messages)
        if self.debug:
            console.log('send:', self.session[-1])
        request_messages = self._messages_for_llm()
        completion = self._chat_completions_create(
            model=self.model,
            messages=request_messages,
            stream=self.stream)
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
            if self.kwargs:
                console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                            f"temperature={self.kwargs.get('temperature')}, " +
                            f"top_p={self.kwargs.get('top_p')}.")
            else:
                console.log(
                    f'{self.NAME}> model={repr(self.model)}, using server default sampling parameters.')

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
        request_messages = self._messages_for_llm()
        if self.stream:
            chunks = []
            with self.client.messages.stream(model=self.model,
                                             messages=request_messages,
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
                messages=request_messages,
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
        prompt_text = self.session[-1]['content']
        if self._vector_context_prompt:
            prompt_text = (
                f"{self._vector_context_prompt}\n\nUser request:\n{prompt_text}")
        if self.stream:
            chunks = []
            response = self.chat.send_message(prompt_text,
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
            response = self.chat.send_message(prompt_text,
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
    # GitHub Copilot: reuse helper so sampling params degrade gracefully.
        self.kwargs = self._collect_sampling_kwargs(args)
        self._sampling_params_supported = None if self.kwargs else False
        if args.verbose:
            if self.kwargs:
                console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                            f"temperature={self.kwargs.get('temperature')}, " +
                            f"top_p={self.kwargs.get('top_p')}.")
            else:
                console.log(
                    f'{self.NAME}> model={repr(self.model)}, using server default sampling parameters.')


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
    # GitHub Copilot: reuse helper so sampling params degrade gracefully.
        self.kwargs = self._collect_sampling_kwargs(args)
        self._sampling_params_supported = None if self.kwargs else False
        if args.verbose:
            if self.kwargs:
                console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                            f"temperature={self.kwargs.get('temperature')}, " +
                            f"top_p={self.kwargs.get('top_p')}.")
            else:
                console.log(
                    f'{self.NAME}> model={repr(self.model)}, using server default sampling parameters.')


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
    # GitHub Copilot: reuse helper so sampling params degrade gracefully.
        self.kwargs = self._collect_sampling_kwargs(args)
        self._sampling_params_supported = None if self.kwargs else False
        if args.verbose:
            if self.kwargs:
                console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                            f"temperature={self.kwargs.get('temperature')}, " +
                            f"top_p={self.kwargs.get('top_p')}.")
            else:
                console.log(
                    f'{self.NAME}> model={repr(self.model)}, using server default sampling parameters.')


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
    # GitHub Copilot: reuse helper so sampling params degrade gracefully.
        self.kwargs = self._collect_sampling_kwargs(args)
        self._sampling_params_supported = None if self.kwargs else False
        if args.verbose:
            if self.kwargs:
                console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                            f"temperature={self.kwargs.get('temperature')}, " +
                            f"top_p={self.kwargs.get('top_p')}.")
            else:
                console.log(
                    f'{self.NAME}> model={repr(self.model)}, using server default sampling parameters.')


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
    # GitHub Copilot: reuse helper so sampling params degrade gracefully.
        self.kwargs = self._collect_sampling_kwargs(args)
        self._sampling_params_supported = None if self.kwargs else False
        if args.verbose:
            if self.kwargs:
                console.log(f'{self.NAME}> ' +
                            f"temperature={self.kwargs.get('temperature')}, " +
                            f"top_p={self.kwargs.get('top_p')}.")
            else:
                console.log(
                    f'{self.NAME}> using server default sampling parameters.')


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
            self.session.append(
                {"role": "system", "content": args.system_message})
        self.model = args.deepseek_model
        # GitHub Copilot: reuse helper so sampling params degrade gracefully.
        self.kwargs = self._collect_sampling_kwargs(args)
        self._sampling_params_supported = None if self.kwargs else False
        if args.verbose:
            if self.kwargs:
                console.log(f'{self.NAME}> model={repr(self.model)}, ' +
                            f"temperature={self.kwargs.get('temperature')}, " +
                            f"top_p={self.kwargs.get('top_p')}.")
            else:
                console.log(
                    f'{self.NAME}> model={repr(self.model)}, using server default sampling parameters.')


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
    # GitHub Copilot: reuse helper so sampling params degrade gracefully.
        self.kwargs = self._collect_sampling_kwargs(args)
        self._sampling_params_supported = None if self.kwargs else False
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
        self.update_session(content)
        baseline_len = len(self.session)
        request_messages = self._messages_for_llm()
        msg_json = json.dumps(request_messages)
        if self.debug:
            console.log('send:', msg_json)
        self.socket.send_string(msg_json)
        msg = self.socket.recv()
        new_session = json.loads(msg)
        _check(new_session)
        self.session = new_session
        if len(self.session) > baseline_len:
            for message in self.session[baseline_len:]:
                self._vector_after_append(message)
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
    elif args.frontend == 'vectorecho':
        frontend = VectorEchoFrontend(args)
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
