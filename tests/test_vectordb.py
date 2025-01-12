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
import os
import pytest
import numpy as np
import tempfile
from debgpt.vectordb import VectorDB
from debgpt import vectordb


def _prepare_vdb(tmpdir: str, populate: bool = True) -> VectorDB:
    """
    Prepare a VectorDB instance with random vectors for testing.

    Args:
        tmpdir (str): Temporary directory path.
        populate (bool): Flag to indicate whether to populate the database with vectors.

    Returns:
        VectorDB: An instance of the VectorDB class.
    """
    # Create a temporary file for the database
    temp_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    vdb = VectorDB(os.path.join(tmpdir, temp_file.name))
    # Adding random vectors
    for i in range(10):
        v = np.random.rand(256)
        vdb.add(f'vector_{i}', str(v), v)
    # Add a constant vector for retrieval tests
    vdb.add(f'ones', str(np.ones(256)), np.ones(256))
    return vdb


def test_vectordb_init(tmpdir):
    """
    Test initialization of the VectorDB.
    """
    vdb = _prepare_vdb(tmpdir, populate=False)
    assert vdb is not None
    vdb.close()


def test_vectordb_add(tmpdir):
    """
    Test adding vectors to the VectorDB.
    """
    vdb = _prepare_vdb(tmpdir)
    vdb.close()


def test_vectordb_get_byid(tmpdir):
    """
    Test retrieving a vector from the VectorDB.
    """
    vdb = _prepare_vdb(tmpdir)
    # Retrieve vector with index 11
    row = vdb.get_byid(11)
    idx, source, text, vector = row
    expected_vec = np.ones(256) / np.linalg.norm(np.ones(256))
    assert idx == 11
    assert source == 'ones'
    assert text == str(np.ones(256))
    assert np.allclose(vector, expected_vec)
    # Retrieve vector with index 11 using __index__ method
    row = vdb[11]
    idx, source, text, vector = row
    assert idx == 11
    assert source == 'ones'
    assert text == str(np.ones(256))
    assert np.allclose(vector, expected_vec)
    # Test retrieving a non-existent vector
    with pytest.raises(ValueError):
        vdb.get_byid(999)
    vdb.close()


def test_get_all(tmpdir):
    """
    Test retrieving all rows from the VectorDB.
    """
    vdb = _prepare_vdb(tmpdir)
    allrows = vdb.get_all()
    assert len(allrows) == 11
    # Validate each row
    for row in allrows:
        assert len(row) == 4
        assert isinstance(row[0], int)
        assert isinstance(row[1], str)
        assert isinstance(row[2], str)
        assert isinstance(row[3], np.ndarray)
    vdb.close()


def test_as_array(tmpdir):
    """
    Test retrieving all indices and vectors from the VectorDB.
    """
    vdb = _prepare_vdb(tmpdir)
    idx, matrix = vdb.as_array()
    assert len(idx) == 11
    assert isinstance(matrix, np.ndarray)
    assert matrix.shape == (11, 256)
    vdb.close()


def test_delete_byid(tmpdir):
    """
    Test deleting a vector from the VectorDB.
    """
    vdb = _prepare_vdb(tmpdir)
    allrows = vdb.get_all()
    assert len(allrows) == 11
    # Delete vector with index 1
    vdb.delete_byid(1)
    allrows = vdb.get_all()
    assert len(allrows) == 10
    vdb.close()


def test_retrieve(tmpdir):
    """
    Test retrieving similar vectors from the VectorDB.
    """
    vdb = _prepare_vdb(tmpdir)
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
    """
    Test listing vectors in the VectorDB.
    """
    vdb = _prepare_vdb(tmpdir)
    vdb.ls()
    vdb.close()


def test_vdb_show(tmpdir):
    """
    Test showing a specific vector in the VectorDB.
    """
    vdb = _prepare_vdb(tmpdir)
    vdb.show(1)
    vdb.close()


def test_main_demo(tmpdir):
    """
    Test running the demo command in the main function.
    """
    temp_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    path = os.path.join(tmpdir, temp_file.name)
    vectordb.main(['--db', path, 'demo'])


def test_main_ls(tmpdir):
    """
    Test running the list command in the main function.
    """
    temp_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    path = os.path.join(tmpdir, temp_file.name)
    vdb = VectorDB(os.path.join(tmpdir, temp_file.name))
    # Adding random vectors
    for i in range(10):
        v = np.random.rand(256)
        vdb.add(f'vector_{i}', str(v), v)
    vdb.close()
    vectordb.main(['--db', path, 'ls'])
    vectordb.main(['--db', path, 'ls', '1'])


def test_main_show(tmpdir):
    """
    Test running the show command in the main function.
    """
    temp_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    path = os.path.join(tmpdir, temp_file.name)
    vectordb.main(['--db', path, 'demo'])
    vectordb.main(['--db', path, 'show', '1'])
    # Test showing a non-existent vector
    with pytest.raises(ValueError):
        vectordb.main(['--db', path, 'show', '999'])


def test_main_rm(tmpdir):
    """
    Test running the remove command in the main function.
    """
    temp_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    path = os.path.join(tmpdir, temp_file.name)
    vectordb.main(['--db', path, 'demo'])
    vectordb.main(['--db', path, 'rm', '1'])


def test_main_help(tmpdir):
    """
    Test running the help command in the main function.
    """
    temp_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    path = os.path.join(tmpdir, temp_file.name)
    vectordb.main([])
    # Test the help command
    with pytest.raises(SystemExit):
        vectordb.main(['--help'])
