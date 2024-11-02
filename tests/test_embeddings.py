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
import pytest
from debgpt import defaults
from debgpt import embeddings


@pytest.fixture
def conf() -> object:
    return defaults.Config()


def test_openai_embedding_embed(conf):
    if conf.openai_api_key == 'your-openai-api-key':
        pytest.skip('OpenAI API key is not provided')
    model = embeddings.OpenAIEmbedding(conf)
    vector = model.embed('hello world')
    assert vector.ndim == 1
    print(f'vector.shape:', vector.shape)
    print(f'vector.min:', vector.min())
    print(f'vector.max:', vector.max())
    print(f'vector.mean:', vector.mean())
    print(f'vector.std:', vector.std())
    print(f'vector[:10]:', vector[:10])
    print(f'vector[-10:]:', vector[-10:])

    # test __call__
    emb = model('hello world')
    assert emb.ndim == 1


def test_openai_embedding_batch_embed(conf):
    if conf.openai_api_key == 'your-openai-api-key':
        pytest.skip('OpenAI API key is not provided')
    model = embeddings.OpenAIEmbedding(conf)
    matrix = model.batch_embed(['hello world', 'goodbye world'])
    assert matrix.ndim == 2
    print(f'matrix.shape:', matrix.shape)
    print(f'matrix.min:', matrix.min())
    print(f'matrix.max:', matrix.max())
    print(f'matrix.mean:', matrix.mean())
    print(f'matrix.std:', matrix.std())
    print(f'matrix[:, :10]:', matrix[:, :10])
    print(f'matrix[:, -10:]:', matrix[:, -10:])

    # test __call__
    emb = model(['hello world', 'goodbye world'])
    assert emb.ndim == 2


def test_gemini_embedding_embed(conf):
    if conf.gemini_api_key == 'your-google-gemini-api-key':
        pytest.skip('Gemini API key is not provided')
    model = embeddings.GeminiEmbedding(conf)
    vector = model.embed('hello world')
    assert vector.ndim == 1


def test_gemini_embedding_batch_embed(conf):
    if conf.gemini_api_key == 'your-google-gemini-api-key':
        pytest.skip('Gemini API key is not provided')
    model = embeddings.GeminiEmbedding(conf)
    matrix = model.batch_embed(['hello world', 'goodbye world'])
    assert matrix.ndim == 2



def test_embedding_main():
    embeddings.main(['hello world'])
