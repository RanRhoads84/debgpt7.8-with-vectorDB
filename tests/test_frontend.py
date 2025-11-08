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
from types import SimpleNamespace
import sys
import os
import numpy as np
import pytest
from debgpt import defaults
from debgpt import frontend


@pytest.fixture
def conf() -> object:
    return defaults.Config()


def test_echo_frontend_oneshot(conf):
    f = frontend.EchoFrontend()
    assert f.oneshot('hello world') == 'hello world'


def test_echo_frontend_call(conf):
    f = frontend.EchoFrontend()
    assert f('hello world') == 'hello world'
    q = {'role': 'user', 'content': 'hello world'}
    assert f(q) == 'hello world'
    assert f([q]) == 'hello world'


def test_echo_frontend_query(conf):
    f = frontend.EchoFrontend()
    assert len(f.session) == 0
    assert f.query('hello world') == 'hello world'
    assert len(f.session) == 2
    assert f.query('hello world') == 'hello world'
    assert len(f.session) == 4
    assert f.query('hello world') == 'hello world'
    assert len(f.session) == 6


class DummyFrontend(frontend.AbstractFrontend):
    NAME = 'DummyFrontend'
    stream = False

    def __init__(self, args):
        super().__init__(args)

    def oneshot(self, message: str) -> str:  # pragma: no cover - helper only
        return ''

    def query(self, messages):  # pragma: no cover - helper only
        self.update_session(messages)
        return ''


class _FakeVectorClient:

    def __init__(self):
        self.enabled = True
        self.queries = []
        self.saved = []

    def query_context(self, **kwargs):
        self.queries.append(kwargs)
        return [{'role': 'assistant', 'text': 'Use apt to manage packages.', 'score': 0.9}]

    def save_message(self, **kwargs):
        self.saved.append(kwargs)
        return 'fake-id'


def test_vector_context_injection(tmp_path):
    args = SimpleNamespace(
        debgpt_home=str(tmp_path),
        monochrome=False,
        multiline=False,
        render_markdown=False,
        vertical_overflow='visible',
        verbose=False,
        vector_service_enabled=False,
        vector_service_url='http://127.0.0.1:8000',
        vector_service_timeout=1.0,
        vector_service_top_k=2,
        vector_service_conversation_id='',
    )
    frontend_instance = DummyFrontend(args)
    fake_client = _FakeVectorClient()
    frontend_instance._vector_client = fake_client
    frontend_instance._vector_top_k = 2
    frontend_instance._vector_context_prompt = None

    frontend_instance.update_session(
        {'role': 'user', 'content': 'How do I update packages?'})
    assert fake_client.queries, 'vector context query should be triggered'
    assert fake_client.saved[0]['role'] == 'user'
    assert frontend_instance._vector_context_prompt is not None

    augmented = frontend_instance._messages_for_llm()
    assert augmented[-2]['role'] == 'system'
    assert 'Use apt' in augmented[-2]['content']

    frontend_instance.update_session(
        {'role': 'assistant', 'content': 'Use apt-get update'})
    assert len(fake_client.saved) == 2
    assert fake_client.saved[-1]['role'] == 'assistant'
    assert frontend_instance._vector_context_prompt is None
