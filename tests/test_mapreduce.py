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
from typing import List, Union, Dict, Tuple
import pytest
from debgpt import mapreduce
from debgpt import frontend
from debgpt import reader
import os
import time
import numpy as np
import sys
import io
import itertools as it


@pytest.fixture
def frtnd():
    f = frontend.EchoFrontend()
    f.lossy_mode = True
    return f


@pytest.fixture
def chunk():
    return reader.Entry(
        path='path',
        content='content',
        wrapfun=lambda x: '{spec}: {content}'.format(spec='spec', content=x),
        wrapfun_chunk=lambda x: '{spec} (lines {start}-{end}): {content}'.
        format(spec='spec', content=x, start=0, end=-1),
    )


def test_shorten():
    string = 'a b c d e f g h i j k l m n o p q r s t u v w x y z' * 1000
    assert len(mapreduce.shorten(string)) <= 100


def test_pad_chunk_before_map(chunk):
    question = 'test question'
    filled_template = mapreduce.pad_chunk_before_map(chunk, question)
    assert isinstance(filled_template, str)
    assert filled_template
    assert len(filled_template) > len(chunk)


def test_map_chunk(chunk, frtnd):
    question = 'test question'
    result = mapreduce.map_chunk(chunk, question, frtnd, verbose=True)
    assert isinstance(result, str)
    assert result
    assert len(result) > 0


def test_map_serial(chunk, frtnd):
    chunks = [chunk] * 10
    question = 'test question'
    results = mapreduce.map_serial(chunks, question, frtnd)
    assert isinstance(results, list)
    assert len(results) == 10
    for result in results:
        assert isinstance(result, str)
        assert result
        assert len(result) > 0


def test_map_parallel(chunk, frtnd):
    chunks = [chunk] * 10
    question = 'test question'
    results = mapreduce.map_parallel(chunks, question, frtnd)
    assert isinstance(results, list)
    assert len(results) == 10
    for result in results:
        assert isinstance(result, str)
        assert result
        assert len(result) > 0


def test_pad_two_results_for_reduce():
    results = ['a', 'b']
    question = 'test question'
    filled_template = mapreduce.pad_two_results_for_reduce(*results, question)
    assert isinstance(filled_template, str)
    assert filled_template
    assert len(filled_template) > 0


def test_reduce_two_chunks(frtnd):
    question = 'test question'
    result = mapreduce.reduce_two_chunks('a',
                                         'b',
                                         question,
                                         frtnd,
                                         verbose=True)
    assert isinstance(result, str)
    assert result
    assert len(result) > 0


@pytest.mark.parametrize('repeat', range(1, 10))
def test_pad_many_results_for_reduce(repeat, frtnd):
    results = ['a'] * repeat
    question = 'test question'
    filled_template = mapreduce.pad_many_results_for_reduce(results, question)
    assert isinstance(filled_template, str)
    assert filled_template
    assert len(filled_template) > 0


@pytest.mark.parametrize('repeat', range(1, 10))
def test_reduce_many_chunks(repeat, frtnd):
    chunks = ['a'] * repeat
    question = 'test question'
    result = mapreduce.reduce_many_chunks(chunks,
                                          question,
                                          frtnd,
                                          verbose=True)
    assert isinstance(result, str)
    assert result
    assert len(result) > 0


def test_group_strings_by_length():
    strings = 'a b c d e f g h i j k l m n o p q r s t u v w x y z'.split()
    groups = mapreduce.group_strings_by_length(strings, 2)
    assert len(groups) == 13
    for group in groups:
        assert len(group) == 2


def test_reduce_serial(frtnd):
    chunks = ['abc'] * 100
    question = 'test question'
    result = mapreduce.reduce_serial(chunks, question, frtnd, verbose=True)
    assert isinstance(result, str)
    assert result
    assert len(result) > 0


def test_reduce_serial_compact(frtnd):
    chunks = ['abc'] * 100
    question = 'test question'
    result = mapreduce.reduce_serial_compact(chunks,
                                             question,
                                             frtnd,
                                             verbose=True,
                                             max_chunk_size=20)
    assert isinstance(result, str)
    assert result
    assert len(result) > 0


def test_reduce_parallel(frtnd):
    chunks = ['abc'] * 100
    question = 'test question'
    result = mapreduce.reduce_parallel(chunks, question, frtnd, verbose=True)
    assert isinstance(result, str)
    assert result
    assert len(result) > 0


def test_reduce_parallel_compact(frtnd):
    chunks = ['abc'] * 100
    question = 'test question'
    result = mapreduce.reduce_parallel_compact(chunks,
                                               question,
                                               frtnd,
                                               verbose=True,
                                               max_chunk_size=20)
    assert isinstance(result, str)
    assert result
    assert len(result) > 0


@pytest.mark.parametrize(
    'parallel,compact_map,compact_reduce,repeat,max_chunk_size',
    it.product([1, 2, 4], [True, False], [True, False], [1, 100], [20, 100]))
def test_mapreduce_super_long_context(tmpdir, frtnd, parallel, compact_map,
                                      compact_reduce, repeat, max_chunk_size):
    text = ['a b c d e f g h i j k l m n o p q r s t u v w x y z'] * repeat
    text = '\n'.join(text)
    with open(tmpdir / 'test.txt', 'wt') as f:
        f.write(text)
    spec = tmpdir.join('test.txt').strpath

    # do mapreduce
    aggregated = mapreduce.mapreduce_super_long_context(
        spec=spec,
        max_chunk_size=max_chunk_size,
        frtnd=frtnd,
        user_question='test question',
        verbose=True,
        compact_map_mode=compact_map,
        compact_reduce_mode=compact_reduce,
        parallelism=parallel,
    )
    assert isinstance(aggregated, str)
    assert aggregated
    assert len(aggregated) > 0
