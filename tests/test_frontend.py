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
