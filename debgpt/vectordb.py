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
from typing import Union, List
import sqlite3
import argparse
import numpy as np
from .defaults import console


class VectorDB:

    # default data type for vectors
    __dtype = np.float32

    def __init__(self, db_name='VectorDB.sqlite'):
        console.log('Connecting to database:', db_name)
        self.connection = sqlite3.connect(db_name)
        self.cursor = self.connection.cursor()
        self._create_table()

    def _create_table(self):
        # Create table if it doesn't exist
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                text TEXT NOT NULL,
                model TEXT NOT NULL,
                vector BLOB NOT NULL
            )
        ''')
        self.connection.commit()

    def add_vector(self, source: str, text: str, model: str,
                   vector: Union[list, np.ndarray]):
        # Convert vector to bytes for storage
        vector_bytes = np.array(vector, dtype=self.__dtype).tobytes()
        self.cursor.execute(
            'INSERT INTO vectors (source, text, model, vector) VALUES (?, ?, ?, ?)',
            (
                source,
                text,
                model,
                vector_bytes,
            ))
        self.connection.commit()

    def _decode_row(self, row: List):
        idx, source, text, model, vector_bytes = row
        vector_np = np.frombuffer(vector_bytes, dtype=self.__dtype)
        return [idx, source, text, model, vector_np]

    def get_vector(self, vector_id) -> List[Union[str, np.ndarray]]:
        self.cursor.execute('SELECT * FROM vectors WHERE id = ?',
                            (vector_id, ))
        result = self.cursor.fetchone()
        if result:
            return self._decode_row(result)
        return None

    def get_all_vectors(self):
        self.cursor.execute('SELECT * FROM vectors')
        results = self.cursor.fetchall()
        return [self._decode_row(row) for row in results]

    def delete_vector(self, vector_id):
        self.cursor.execute('DELETE FROM vectors WHERE id = ?', (vector_id, ))
        self.connection.commit()

    def close(self):
        self.connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')
    parser_demo = subparsers.add_parser('demo')
    parser_create = subparsers.add_parser('create')
    parser_ls = subparsers.add_parser('ls')
    parser_show = subparsers.add_parser('show')
    parser_show.add_argument('id', type=int, help='ID of the vector to show')
    parser_rm = subparsers.add_parser('rm')
    parser_rm.add_argument('id', type=int, help='ID of the vector to remove')
    args = parser.parse_args()

    if args.action == 'demo':
        # Example usage, and create a database for debugging purposes
        db = VectorDB()

        # Adding vectors
        v1 = [1.0, 2.0, 3.0]
        db.add_vector('v1', str(v1), 'embedding model', v1)
        v2 = [4.0, 5.0, 6.0]
        db.add_vector('v2', str(v2), 'embedding model', v2)
        db.add_vector('v3', str(v2), 'embedding model', v2)

        # Retrieve a vector
        vector = db.get_vector(1)
        print(f'Vector with ID 1: {vector}')

        # Retrieve all vectors
        vectors = db.get_all_vectors()
        print('All vectors:', vectors)

        # Delete a vector
        db.delete_vector(1)
        print('id 1 deleted')

        # Retrieve all vectors
        vectors = db.get_all_vectors()
        print('All vectors:', vectors)

        # Closing the database connection
        db.close()
    elif args.action == 'create':
        db = VectorDB()
        db.close()
    elif args.action == 'ls':
        db = VectorDB()
        vectors = db.get_all_vectors()
        for v in vectors:
            idx, source, text, model, vector = v
            print(f'[{idx}]', f'source={repr(source)},',
                  f'model={repr(model)},', f'len(vector)={len(vector)}')
        db.close()
    elif args.action == 'show':
        db = VectorDB()
        vector = db.get_vector(args.id)
        if vector:
            idx, source, text, model, vector = vector
            print(f'[{idx}]', f'source={repr(source)},',
                  f'model={repr(model)},', f'len(vector)={len(vector)}')
            print('vector=', vector)
        else:
            print(f'Vector with id={args.id} not found')
        db.close()
    elif args.action == 'rm':
        db = VectorDB()
        db.delete_vector(args.id)
        db.close()
        console.log(f'Deleted vector with id={args.id}')
    else:
        parser.print_help()
