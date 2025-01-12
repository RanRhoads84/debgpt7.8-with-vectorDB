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
import textwrap
import sys
from typing import Union, List, Tuple
import sqlite3
import argparse
import numpy as np
import lz4.frame
from .defaults import console


class VectorDB:
    '''
    A class to manage a database of vectors using SQLite.

    Attributes:
        __dtype (np.dtype): The default data type for vectors.
        connection (sqlite3.Connection): The SQLite connection object.
        cursor (sqlite3.Cursor): The SQLite cursor object.
        dim (int): The dimension of the vectors.
    '''

    __dtype = np.float32

    def __init__(self, db_name: str = 'VectorDB.sqlite', dimension: int = 256):
        '''
        Initialize a VectorDB object. It is suggested to use a file name that
        contains both the embedding model and the embedding size to avoid
        errors.

        Args:
            db_name (str): The name of the database file. Defaults to 'VectorDB.sqlite'.
            dimension (int): The dimension of the vectors. Defaults to 256.
        '''
        console.log('Connecting to database:', db_name)
        self.connection: sqlite3.Connection = sqlite3.connect(db_name)
        self.cursor: sqlite3.Cursor = self.connection.cursor()
        self._create_table()
        self.dim: int = dimension

    def _create_table(self) -> None:
        '''
        Create the vectors table in the database if it doesn't exist.
        '''
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                text BLOB NOT NULL,
                vector BLOB NOT NULL
            )
        ''')
        self.connection.commit()

    def add(self, source: str, text: str, vector: Union[list,
                                                        np.ndarray]) -> None:
        '''
        Add a vector to the database. The vector is normalized before storage.

        Args:
            source (str): The source of the vector, e.g., file path, URL.
            text (str): The original text content corresponding to the vector.
            vector (Union[list, np.ndarray]): The vector to store.
        '''
        assert len(vector) >= self.dim
        vector_np: np.ndarray = np.array(vector, dtype=self.__dtype)
        vector_np_reduction: np.ndarray = vector_np[:self.dim]
        vector_np_reduction = vector_np_reduction / np.linalg.norm(
            vector_np_reduction)
        vector_bytes: bytes = vector_np_reduction.tobytes()
        text_compressed: bytes = lz4.frame.compress(text.encode())
        self.cursor.execute(
            'INSERT INTO vectors (source, text, vector) VALUES (?, ?, ?)', (
                source,
                text_compressed,
                vector_bytes,
            ))
        self.connection.commit()

    def _decode_row(self, row: List) -> List[Union[int, str, np.ndarray]]:
        '''
        Decode a row from the database into its original components.

        Args:
            row (List): The row from the database.

        Returns:
            List[Union[int, str, np.ndarray]]: The decoded components.
        '''
        idx, source, text_compressed, vector_bytes = row
        vector_np: np.ndarray = np.frombuffer(vector_bytes, dtype=self.__dtype)
        text_uncompressed: str = lz4.frame.decompress(text_compressed).decode()
        return [idx, source, text_uncompressed, vector_np]

    def get_byid(self, vector_id: int) -> List[Union[int, str, np.ndarray]]:
        '''
        Retrieve a row from the database by its ID.

        Args:
            vector_id (int): The ID of the vector to retrieve.

        Returns:
            List[Union[int, str, np.ndarray]]: The retrieved vector and its metadata.

        Raises:
            ValueError: If the vector with the specified ID is not found.
        '''
        self.cursor.execute('SELECT * FROM vectors WHERE id = ?',
                            (vector_id, ))
        result: Tuple = self.cursor.fetchone()
        if result:
            return self._decode_row(result)
        raise ValueError(f'Vector with id={vector_id} not found')

    def __getitem__(self, vector_id: int) -> List[Union[int, str, np.ndarray]]:
        '''
        Retrieve a row from the database by its ID using the index operator.

        Args:
            vector_id (int): The ID of the vector to retrieve.

        Returns:
            List[Union[int, str, np.ndarray]]: The retrieved vector and its metadata.

        Raises:
            ValueError: If the vector with the specified ID is not found.
        '''
        return self.get_byid(vector_id)

    def get_all(self) -> List[List[Union[int, str, np.ndarray]]]:
        '''
        Retrieve all rows from the vectors table.

        Returns:
            List[List[Union[int, str, np.ndarray]]]: All rows from the table.
        '''
        self.cursor.execute('SELECT * FROM vectors')
        results: List[Tuple] = self.cursor.fetchall()
        return [self._decode_row(row) for row in results]

    def as_array(self) -> Tuple[np.ndarray, np.ndarray]:
        '''
        Retrieve all IDs and vectors from the database as numpy arrays.

        Returns:
            Tuple[np.ndarray, np.ndarray]: Arrays of vector IDs and vectors.
        '''
        self.cursor.execute('SELECT id, vector FROM vectors')
        results: List[Tuple[int, bytes]] = self.cursor.fetchall()
        results = [(idx, np.frombuffer(vector, dtype=self.__dtype))
                   for idx, vector in results]
        # repack them into numpy arrays
        idxs, vectors = list(zip(*results))
        idxs_array: np.ndarray = np.array(idxs)
        matrix: np.ndarray = np.stack(vectors)
        return idxs_array, matrix

    def delete_byid(self, vector_id: int) -> None:
        '''
        Delete a vector from the database by its ID.

        Args:
            vector_id (int): The ID of the vector to delete.
        '''
        self.cursor.execute('DELETE FROM vectors WHERE id = ?', (vector_id, ))
        self.connection.commit()

    def close(self) -> None:
        '''
        Close the database connection.
        '''
        self.connection.close()

    def retrieve(self,
                 vector: np.ndarray,
                 topk: int = 3) -> List[List[Union[float, str]]]:
        '''
        Retrieve the nearest vectors from the database based on cosine similarity.

        Args:
            vector (np.ndarray): The vector to compare against.
            topk (int): The number of nearest vectors to retrieve. Defaults to 3.

        Returns:
            List[List[Union[float, str]]]: A list of the nearest vectors and their metadata.
        '''
        idxs, matrix = self.as_array()
        assert matrix.ndim == 2
        assert vector.ndim == 1
        vector = vector / np.linalg.norm(vector)
        cosine: np.ndarray = (matrix @ vector.reshape(-1, 1)).flatten()
        argsort: np.ndarray = np.argsort(cosine)[::-1][:topk]
        documents: List[List[Union[float, str]]] = []
        for idx, sim in zip(idxs[argsort], cosine[argsort]):
            _, source, text, _, = self.get_byid(int(idx))
            doc: List[Union[float, str]] = [sim, source, text]
            documents.append(doc)
        return documents

    def ls(self,
           id: Optional[int] = None
           ) -> List[List[Union[int, str, np.ndarray]]]:
        '''
        List all vectors in the database.

        Returns:
            List[List[Union[int, str, np.ndarray]]]: All vectors and their metadata.
        '''
        if id is not None:
            vectors: List[List[Union[int, str,
                                     np.ndarray]]] = [self.get_byid(id)]
        else:
            vectors: List[List[Union[int, str, np.ndarray]]] = self.get_all()
        for v in vectors:
            idx, source, text, vector = v
            console.print(
                f'id[{idx:5d}]',
                f'len(vector)={len(vector)},',
                f'len(text)={len(text):5d}',
                f'source={repr(source)},',
                f'text={textwrap.shorten(text, 32)}',
            )
        return vectors

    def show(self, idx: int) -> None:
        '''
        Show the vector with the given index.

        Args:
            idx (int): The index of the vector to show.
        '''
        vector: List[Union[int, str, np.ndarray]] = self.get_byid(idx)
        idx, source, text, vector = vector
        print(
            f'[{idx:4d}]',
            f'source={repr(source)},',
            f'text={repr(text)}',
            f'\nlen(vector)={len(vector)}',
            f'\nvector={vector}',
        )


def main(argv: List[str]) -> None:
    '''
    Main function to handle command-line interface for the VectorDB.

    Args:
        argv (List[str]): Command-line arguments.
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('--db',
                        type=str,
                        default='VectorDB.sqlite',
                        help='Database file name')
    subparsers = parser.add_subparsers(dest='action')
    _ = subparsers.add_parser('demo')
    parser_ls = subparsers.add_parser('ls')
    parser_ls.add_argument('id',
                           type=int,
                           default=None,
                           nargs='?',
                           help='ID of the vector to list')
    parser_show = subparsers.add_parser('show')
    parser_show.add_argument('id', type=int, help='ID of the vector to show')
    parser_rm = subparsers.add_parser('rm')
    parser_rm.add_argument('id', type=int, help='ID of the vector to remove')
    args = parser.parse_args(argv)

    if args.action == 'ls':
        db = VectorDB(args.db)
        db.ls(args.id)
        db.close()
    elif args.action == 'show':
        db = VectorDB(args.db)
        db.show(args.id)
        db.close()
    elif args.action == 'rm':
        db = VectorDB(args.db)
        db.delete_byid(args.id)
        console.log(f'Deleted vector with id={args.id}')
        db.close()
    elif args.action == 'demo':
        db = VectorDB(args.db)
        for i in range(10):
            v: np.ndarray = np.random.rand(256)
            db.add(f'vector_{i}', str(v), v)
        db.add('ones', str(np.ones(256)), np.ones(256))
        db.close()
    else:
        parser.print_help()


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
