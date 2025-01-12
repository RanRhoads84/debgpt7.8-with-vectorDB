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
from debgpt import embeddings


@pytest.fixture
def conf() -> object:
    return defaults.Config()


def test_random_embedding_embed(conf):
    model = embeddings.RandomEmbedding(conf)
    vector = model.embed('hello world')
    assert vector.ndim == 1
    # test __call__
    emb = model('hello world')
    assert emb.ndim == 1
    assert np.isclose(np.linalg.norm(emb), 1.0)


def test_random_embedding_batch_embed(conf):
    model = embeddings.RandomEmbedding(conf)
    matrix = model.batch_embed(['hello world', 'goodbye world'])
    assert matrix.ndim == 2
    # test __call__
    emb = model(['hello world', 'goodbye world'])
    assert emb.ndim == 2
    assert np.isclose(np.linalg.norm(emb, axis=1), 1.0).all()


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
    assert np.isclose(np.linalg.norm(emb), 1.0)


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
    assert np.isclose(np.linalg.norm(emb, axis=1), 1.0).all()


def test_google_embedding_embed(conf):
    if conf.google_api_key == 'your-google-api-key':
        pytest.skip('Google API key is not provided')
    model = embeddings.GoogleEmbedding(conf)
    vector = model.embed('hello world')
    assert vector.ndim == 1
    assert np.isclose(np.linalg.norm(vector), 1.0)


def test_google_embedding_batch_embed(conf):
    if conf.google_api_key == 'your-google-api-key':
        pytest.skip('Google API key is not provided')
    model = embeddings.GoogleEmbedding(conf)
    matrix = model.batch_embed(['hello world', 'goodbye world'])
    assert matrix.ndim == 2
    assert np.isclose(np.linalg.norm(matrix, axis=1), 1.0).all()


def test_get_embedding_model(conf):
    model = embeddings.get_embedding_model(conf)
    assert model is not None
    vector = model.embed('hello world')
    assert vector.ndim == 1
    assert np.isclose(np.linalg.norm(vector), 1.0)


def test_embedding_main():
    embeddings.main(['hello world'])
