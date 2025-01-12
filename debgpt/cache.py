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
from typing import Optional
from typing import Union, List, Tuple
import sqlite3
import lz4.frame


class Cache(dict):
    """
    A class that works like dictionary, but with a SQLite backend.
    The only data format supported in the cache is key (str) -> value (str),
    but we will automatically compress the value strings using lz4.
    We set 24 hours to expire for every cache entry.

    ChatGPT and Copilot really knows how to write this.
    """

    def __init__(self, db_name: str = 'Cache.sqlite') -> None:
        """
        Initialize the Cache with a SQLite database.

        Args:
            db_name (str): The name of the SQLite database file. Defaults to 'Cache.sqlite'.
        """
        self.connection: sqlite3.Connection = sqlite3.connect(db_name)
        self.cursor: sqlite3.Cursor = self.connection.cursor()
        self._create_table()
        self._cleanup_expired()

    def _cleanup_expired(self) -> None:
        """
        Clean up expired entries from the cache.
        """
        self.cursor.execute(
            'DELETE FROM cache WHERE stamp < DATETIME("now", "-1 month")')
        self.connection.commit()

    def _create_table(self) -> None:
        """
        Create the cache table if it doesn't exist.
        """
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT NOT NULL PRIMARY KEY,
                value BLOB NOT NULL,
                stamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.connection.commit()

    def __setitem__(self, key: str, value: str) -> None:
        """
        Set a key-value pair in the cache.

        Args:
            key (str): The key to set.
            value (str): The value to set, which will be compressed.

        Raises:
            TypeError: If key is not a string or value cannot be encoded to string.
        """
        value_compressed: bytes = lz4.frame.compress(value.encode())
        self.cursor.execute(
            'INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)',
            (key, value_compressed))
        self.connection.commit()

    def __getitem__(self, key: str) -> str:
        """
        Retrieve a value from the cache by key.

        Args:
            key (str): The key to look up.

        Returns:
            str: The decompressed value associated with the key.

        Raises:
            KeyError: If the key does not exist in the cache.
        """
        self.cursor.execute('SELECT value FROM cache WHERE key = ?', (key, ))
        result: Tuple = self.cursor.fetchone()
        if result:
            value_compressed: bytes = result[0]
            value: str = lz4.frame.decompress(value_compressed).decode()
            return value
        raise KeyError(f'Key {key} not found in cache')

    def __delitem__(self, key: str) -> None:
        """
        Delete a key-value pair from the cache.

        Args:
            key (str): The key to delete.

        Raises:
            KeyError: If the key does not exist in the cache.
        """
        self.cursor.execute('DELETE FROM cache WHERE key = ?', (key, ))
        if self.cursor.rowcount == 0:
            raise KeyError(f'Key {key} not found in cache')
        self.connection.commit()

    def __contains__(self, key: str) -> bool:
        """
        Check if a key exists in the cache.

        Args:
            key (str): The key to check for.

        Returns:
            bool: True if the key is in the cache, False otherwise.
        """
        self.cursor.execute('SELECT value FROM cache WHERE key = ?', (key, ))
        return self.cursor.fetchone() is not None

    def __iter__(self):
        """
        Yield keys from the cache.

        Returns:
            Iterator[str]: An iterator over the keys in the cache.
        """
        self.cursor.execute('SELECT key FROM cache')
        for row in self.cursor.fetchall():
            yield row[0]

    def __len__(self) -> int:
        """
        Return the number of items in the cache.

        Returns:
            int: The count of items in the cache.
        """
        self.cursor.execute('SELECT COUNT(*) FROM cache')
        return self.cursor.fetchone()[0]

    def keys(self) -> List[str]:
        """
        Return a list of all keys in the cache.

        Returns:
            List[str]: A list containing all keys.
        """
        self.cursor.execute('SELECT key FROM cache')
        return [row[0] for row in self.cursor.fetchall()]

    def values(self) -> List[str]:
        """
        Return a list of all values in the cache.

        Returns:
            List[str]: A list containing all decompressed values.
        """
        self.cursor.execute('SELECT value FROM cache')
        return [
            lz4.frame.decompress(row[0]).decode()
            for row in self.cursor.fetchall()
        ]

    def items(self) -> List[Tuple[str, str]]:
        """
        Return a list of all key-value pairs in the cache.

        Returns:
            List[Tuple[str, str]]: A list of tuples containing keys and decompressed values.
        """
        self.cursor.execute('SELECT key, value FROM cache')
        return [(row[0], lz4.frame.decompress(row[1]).decode())
                for row in self.cursor.fetchall()]

    def close(self) -> None:
        """
        Close the SQLite connection.
        """
        self.connection.close()

    def __del__(self):
        """
        Destructor to ensure the SQLite connection is closed.
        """
        self.connection.close()

    def clear(self) -> None:
        """
        Clear all items from the cache.
        """
        self.cursor.execute('DELETE FROM cache')
        self.connection.commit()

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a value from the cache or return a default.

        Args:
            key (str): The key to look up.
            default (Optional[str]): The default value to return if the key is not found.

        Returns:
            Optional[str]: The value if found, otherwise the default value.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def pop(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Remove the specified key and return the corresponding value.

        Args:
            key (str): The key to pop.
            default (Optional[str]): The value to return if the key is not found.

        Returns:
            Optional[str]: The value for the key if it exists, otherwise the default value.

        Raises:
            KeyError: If the key does not exist and no default is provided.
        """
        try:
            value: str = self[key]
            del self[key]
            return value
        except KeyError:
            return default

    def popitem(self) -> Tuple[str, str]:
        """
        Remove and return an arbitrary (key, value) pair from the cache.

        Returns:
            Tuple[str, str]: The key and value of the removed item.

        Raises:
            KeyError: If the cache is empty.
        """
        self.cursor.execute('SELECT key, value FROM cache LIMIT 1')
        row: Tuple = self.cursor.fetchone()
        if row:
            key: str = row[0]
            value: str = lz4.frame.decompress(row[1]).decode()
            del self[key]
            return (key, value)
        raise KeyError('popitem(): cache is empty')

    def setdefault(self, key: str, default: Optional[str] = None) -> str:
        """
        If key is in the cache, return its value. If not, insert key with a value of default and return default.

        Args:
            key (str): The key to look up or set.
            default (Optional[str]): The value to set if key is not in the cache. Defaults to None.

        Returns:
            str: The value for the key if it exists, otherwise the default value.
        """
        if key in self:
            return self[key]
        self[key] = default
        return default

    def update(self, other: Union[dict, 'Cache']) -> None:
        """
        Update the cache with the key/value pairs from other, overwriting existing keys.

        Args:
            other (Union[dict, Cache]): A dictionary or another Cache object to update from.
        """
        for key, value in other.items():
            self[key] = value
