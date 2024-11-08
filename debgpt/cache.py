'''
Copyright (C) 2024 Mo Zhou <lumin@debian.org>

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
from typing import Optional
import textwrap
import sys
from typing import Union, List, Tuple
import sqlite3
import argparse
import numpy as np
import lz4.frame
from .defaults import console


class Cache(dict):
    '''
    A class that works like dictionary, but with a SQLite backend.
    The only data format supported in the cache is key (str) -> value (str),
    but we will automatically compress the value strings using lz4.
    We set 24 hours to expire for every cache entry.

    ChatGPT and Copilot really knows how to write this.
    '''

    def __init__(self, db_name: str = 'Cache.sqlite'):
        self.connection: sqlite3.Connection = sqlite3.connect(db_name)
        self.cursor: sqlite3.Cursor = self.connection.cursor()
        self._create_table()
        self._cleanup_expired()

    def _cleanup_expired(self) -> None:
        self.cursor.execute('DELETE FROM cache WHERE stamp < DATETIME("now", "-1 day")')
        self.connection.commit()

    def _create_table(self) -> None:
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT NOT NULL PRIMARY KEY,
                value BLOB NOT NULL,
                stamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.connection.commit()

    def __setitem__(self, key: str, value: str) -> None:
        value_compressed: bytes = lz4.frame.compress(value.encode())
        self.cursor.execute('INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)',
                            (key, value_compressed))
        self.connection.commit()

    def __getitem__(self, key: str) -> str:
        self.cursor.execute('SELECT value FROM cache WHERE key = ?', (key, ))
        result: Tuple = self.cursor.fetchone()
        if result:
            value_compressed: bytes = result[0]
            value: str = lz4.frame.decompress(value_compressed).decode()
            return value
        raise KeyError(f'Key {key} not found in cache')

    def __delitem__(self, key: str) -> None:
        self.cursor.execute('DELETE FROM cache WHERE key = ?', (key, ))
        if self.cursor.rowcount == 0:
            raise KeyError(f'Key {key} not found in cache')
        self.connection.commit()

    def __contains__(self, key: str) -> bool:
        self.cursor.execute('SELECT value FROM cache WHERE key = ?', (key, ))
        return self.cursor.fetchone() is not None

    def __iter__(self):
        self.cursor.execute('SELECT key FROM cache')
        for row in self.cursor.fetchall():
            yield row[0]

    def __len__(self) -> int:
        self.cursor.execute('SELECT COUNT(*) FROM cache')
        return self.cursor.fetchone()[0]

    def keys(self) -> List[str]:
        self.cursor.execute('SELECT key FROM cache')
        return [row[0] for row in self.cursor.fetchall()]

    def values(self) -> List[str]:
        self.cursor.execute('SELECT value FROM cache')
        return [lz4.frame.decompress(row[0]).decode() for row in self.cursor.fetchall()]

    def items(self) -> List[Tuple[str, str]]:
        self.cursor.execute('SELECT key, value FROM cache')
        return [(row[0], lz4.frame.decompress(row[1]).decode()) for row in self.cursor.fetchall()]

    def close(self) -> None:
        self.connection.close()

    def __del__(self):
        self.connection.close()

    def clear(self) -> None:
        self.cursor.execute('DELETE FROM cache')
        self.connection.commit()

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            return self[key]
        except KeyError:
            return default

    def pop(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            value: str = self[key]
            del self[key]
            return value
        except KeyError:
            return default

    def popitem(self) -> Tuple[str, str]:
        self.cursor.execute('SELECT key, value FROM cache LIMIT 1')
        row: Tuple = self.cursor.fetchone()
        if row:
            key: str = row[0]
            value: str = lz4.frame.decompress(row[1]).decode()
            del self[key]
            return (key, value)
        raise KeyError('popitem(): cache is empty')

    def setdefault(self, key: str, default: Optional[str] = None) -> str:
        if key in self:
            return self[key]
        self[key] = default
        return default

    def update(self, other: Union[dict, 'Cache']) -> None:
        for key, value in other.items():
            self[key] = value
