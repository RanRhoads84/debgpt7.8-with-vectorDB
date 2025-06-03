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
from debgpt import retrieval
from debgpt import reader


def test_vectorretriever_add(tmpdir):
    conf = defaults.Config()
    conf.db = os.path.join(tmpdir, 'test.db')
    embedding_frontend = conf.embedding_frontend
    if embedding_frontend == 'random':
        api_key = 'random-key'
    else:
        api_key = conf[f'{embedding_frontend}_api_key']
    if api_key.startswith('your-') and api_key.endswith('-key'):
        pytest.skip(f'API Key for {embedding_frontend} not configured')
    retriever = retrieval.VectorRetriever(conf)
    # add some documents
    for i in range(2):
        retriever.add(f'temp{i}', f'fruit{i}')


@pytest.mark.skipif(defaults.Config().embedding_frontend == 'random',
                    reason='this case is pointless for Random embedding')
def test_vectorretriever_retrieve_onfly(tmpdir):
    conf = defaults.Config()
    conf.db = os.path.join(tmpdir, 'test.db')
    embedding_frontend = conf.embedding_frontend
    api_key = conf[f'{embedding_frontend}_api_key']
    if api_key.startswith('your-') and api_key.endswith('-key'):
        pytest.skip(f'API Key for {embedding_frontend} not configured')
    retriever = retrieval.VectorRetriever(conf)
    # on-the-fly retrieval
    query = 'fruit'
    documents = ['fruit', 'sky', 'orange', 'dog', 'cat', 'apple', 'banana']
    results = retriever.retrieve_onfly(query, documents, topk=3)
    assert len(results) == 3
    for i, result in enumerate(results):
        score, source, text = result
        assert text in documents
        assert score >= 0.0 - 1e-5
        assert score <= 1.0 + 1e-5
        assert source is not None
        if i == 0:
            assert text == 'fruit'
            assert np.isclose(score, 1.0)
    print(results)


@pytest.mark.skipif(defaults.Config().embedding_frontend == 'random',
                    reason='this case is pointless for Random embedding')
def test_vectorretriever_retrieve_from_db(tmpdir):
    conf = defaults.Config()
    conf.db = os.path.join(tmpdir, 'test.db')
    embedding_frontend = conf.embedding_frontend
    api_key = conf[f'{embedding_frontend}_api_key']
    if api_key.startswith('your-') and api_key.endswith('-key'):
        pytest.skip(f'API Key for {embedding_frontend} not configured')
    retriever = retrieval.VectorRetriever(conf)
    # insert some documents
    vectors = retriever.batch_add(
        ['temp'] * 7,
        ['fruit', 'sky', 'orange', 'dog', 'cat', 'apple', 'banana'])
    assert len(vectors) == 7
    # retrieve from db
    query = 'fruit'
    results = retriever.retrieve_from_db(query, topk=3)
    assert len(results) == 3
    for i, result in enumerate(results):
        score, source, text = result
        assert text in ['fruit', 'orange', 'apple', 'banana']
        assert score >= 0.0 - 1e-5
        assert score <= 1.0 + 1e-5
        assert source is not None
        if i == 0:
            assert text == 'fruit'
            assert np.isclose(score, 1.0)
    print(results)


def test_retrieval_main(tmpdir):
    common_args = ['--db', os.path.join(tmpdir, 'test.db'), '-E', 'random']
    retrieval.main([*common_args, 'add', 'x'])
    retrieval.main([*common_args, 'add', 'y'])
    retrieval.main([*common_args, 'add', 'z'])
    retrieval.main([*common_args, 'ret', 'w'])
    retrieval.main([*common_args, 'retrieve', 'w'])
