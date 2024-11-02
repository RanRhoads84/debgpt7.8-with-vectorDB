'''
MIT License

Copyright (c) 2024 Mo Zhou <lumin@debian.org>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
from types import SimpleNamespace
import sys
import os
import numpy as np
import pytest
from debgpt import defaults
from debgpt import retrieval


def test_vectorretriever_add(tmpdir):
    conf = defaults.Config()
    conf.db = os.path.join(tmpdir, 'test.db')
    embedding_frontend = conf.embedding_frontend
    api_key = conf[f'{embedding_frontend}_api_key']
    if api_key.startswith('your-') and api_key.endswith('-key'):
        pytest.skip(f'API Key for {embedding_frontend} not configured')
    retriever = retrieval.VectorRetriever(conf)
    # add some documents
    for i in range(2):
        retriever.add(f'temp{i}', f'fruit{i}')


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
        assert text in ['fruit', 'orange', 'apple']
        assert score >= 0.0 - 1e-5
        assert score <= 1.0 + 1e-5
        assert source is not None
        if i == 0:
            assert text == 'fruit'
            assert np.isclose(score, 1.0)
    print(results)
