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
from debgpt.cache import Cache


def test_cache_init(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache.close()


def test_cache_setitem(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'


def test_cache_getitem(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    assert cache['test key'] == 'test value'

    with pytest.raises(KeyError):
        _ = cache['non-exist key']


def test_cache_delitem(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    del cache['test key']

    with pytest.raises(KeyError):
        del cache['test key']


def test_cache_contains(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    assert 'test key' in cache
    assert 'non-exist key' not in cache


def test_cache_len(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    assert len(cache) == 1

    cache['test key 2'] = 'test value 2'
    assert len(cache) == 2

    del cache['test key']
    assert len(cache) == 1


def test_cache_iter(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    cache['test key 2'] = 'test value 2'
    assert set(cache) == {'test key', 'test key 2'}


def test_cache_keys(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    cache['test key 2'] = 'test value 2'
    assert set(cache.keys()) == {'test key', 'test key 2'}


def test_cache_values(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    cache['test key 2'] = 'test value 2'
    assert set(cache.values()) == {'test value', 'test value 2'}


def test_cache_items(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    cache['test key 2'] = 'test value 2'
    assert set(cache.items()) == {('test key', 'test value'),
                                  ('test key 2', 'test value 2')}


def test_cache_clear(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    cache['test key 2'] = 'test value 2'
    cache.clear()
    assert len(cache) == 0


def test_cache_del(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    cache['test key 2'] = 'test value 2'
    del cache


def test_cache_get(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    assert cache.get('test key') == 'test value'
    assert cache.get('non-exist key') is None
    assert cache.get('non-exist key', 'default') == 'default'


def test_cache_pop(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    assert cache.pop('test key') == 'test value'
    assert len(cache) == 0

    assert cache.pop('non-exist key') is None

    assert cache.pop('non-exist key', 'default') == 'default'


def test_cache_popitem(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    assert cache.popitem() == ('test key', 'test value')
    assert len(cache) == 0

    with pytest.raises(KeyError):
        cache.popitem()


def test_cache_update(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache.update({'test key': 'test value', 'test key 2': 'test value 2'})
    assert cache['test key'] == 'test value'
    assert cache['test key 2'] == 'test value 2'
    assert len(cache) == 2

    cache.update({'test key': 'test value 3'})
    assert len(cache) == 2
    assert cache['test key'] != 'test value'
    assert cache['test key'] == 'test value 3'


def test_cache_setdefault(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache.setdefault('test key', 'test value')
    assert cache['test key'] == 'test value'

    cache.setdefault('test key', 'test value 2')
    assert cache['test key'] == 'test value'


def test_cache_copy(tmpdir):
    db_path = str(tmpdir.join('test.db'))
    cache = Cache(db_path)
    cache['test key'] = 'test value'
    cache['test key 2'] = 'test value 2'
    cache_copy = cache.copy()
    assert cache_copy == cache
    assert cache_copy is not cache
