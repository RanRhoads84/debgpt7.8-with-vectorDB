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
import os
import pytest
import numpy as np
import tempfile
from debgpt.vectordb import VectorDB
from debgpt import vectordb


def _prepare_vdb(tmpdir: str, populate: bool = True) -> VectorDB:
    # create random vdb in pytest tmpdir
    temp_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    vdb = VectorDB(os.path.join(tmpdir, temp_file.name))
    # Adding random vectors
    for i in range(10):
        v = np.random.rand(256)
        vdb.add_vector(f'vector_{i}', str(v), f'model_name', v)
    # make sure there is at least one constant vector
    # it will make with cosine=1 for normalized np.ones(256) for
    # retrieval tests.
    vdb.add_vector(f'ones', str(np.ones(256)), f'model_name', np.ones(256))
    return vdb


def test_vectordb_init(tmpdir):
    vdb = _prepare_vdb(tmpdir, populate=False)
    assert vdb is not None
    vdb.close()


def test_vectordb_add_vector(tmpdir):
    vdb = _prepare_vdb(tmpdir)
    vdb.close()


def test_vectordb_get_vector(tmpdir):
    vdb = _prepare_vdb(tmpdir)
    # Getting vectors
    vec = vdb.get_vector(11)
    idx, source, text, model, vector = vec
    expected_vec = np.ones(256) / np.linalg.norm(np.ones(256))
    assert idx == 11
    assert source == 'ones'
    assert text == str(np.ones(256))
    assert model == 'model_name'
    assert np.allclose(vector, expected_vec)
    vdb.close()

def test_get_all_rows(tmpdir):
    vdb = _prepare_vdb(tmpdir)
    # get all rows
    allrows = vdb.get_all_rows()
    assert len(allrows) == 11
    # check every row
    for row in allrows:
        assert len(row) == 5
        assert isinstance(row[0], int)
        assert isinstance(row[1], str)
        assert isinstance(row[2], str)
        assert isinstance(row[3], str)
        assert isinstance(row[4], np.ndarray)
    vdb.close()

def test_get_all_vectors(tmpdir):
    vdb = _prepare_vdb(tmpdir)
    # get all rows
    allrows = vdb.get_all_vectors()
    assert len(allrows) == 11
    # check every row
    for row in allrows:
        assert len(row) == 2
        assert isinstance(row[0], int)
        assert isinstance(row[1], np.ndarray)
    vdb.close()

def test_get_all(tmpdir):
    vdb = _prepare_vdb(tmpdir)
    # get all rows
    idx, matrix = vdb.get_all()
    assert len(idx) == 11
    assert isinstance(matrix, np.ndarray)
    assert matrix.shape == (11, 256)
    vdb.close()

def test_delete_vector(tmpdir):
    vdb = _prepare_vdb(tmpdir)
    # get all rows
    allrows = vdb.get_all_rows()
    assert len(allrows) == 11
    # delete vector
    vdb.delete_vector(1)
    # get all rows
    allrows = vdb.get_all_rows()
    assert len(allrows) == 10
    vdb.close()

def test_retrieve(tmpdir):
    vdb = _prepare_vdb(tmpdir)
    # retrieve
    query_vector = np.ones(256) / np.linalg.norm(np.ones(256))
    documents = vdb.retrieve(query_vector, topk=3)
    assert len(documents) == 3
    for doc in documents:
        assert isinstance(doc, list)
        assert len(doc) == 3
        sim, source, text = doc
        assert isinstance(doc[0], float)
        assert isinstance(doc[1], str)
        assert isinstance(doc[2], str)
        if source == 'ones':
            assert np.isclose(sim, 1.0)
    vdb.close()

def test_vdb_ls(tmpdir):
    vdb = _prepare_vdb(tmpdir)
    vectordb.vdb_ls(vdb)
    vdb.close()
