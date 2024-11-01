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
import sys
from typing import Union, List
import sqlite3
import argparse
import numpy as np
import lz4.frame
from .defaults import console


class VectorDB:

    # default data type for vectors
    __dtype = np.float32

    def __init__(self, db_name: str = 'VectorDB.sqlite', dimension: int = 256):
        '''
        Initialize a VectorDB object.
        We assume the embedding model supports dimension reduction by
        truncation.
        '''
        console.log('Connecting to database:', db_name)
        self.connection = sqlite3.connect(db_name)
        self.cursor = self.connection.cursor()
        self._create_table()
        self.dim = dimension

    def _create_table(self):
        # Create table if it doesn't exist
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                text BLOB NOT NULL,
                model TEXT NOT NULL,
                vector BLOB NOT NULL
            )
        ''')
        self.connection.commit()

    def add_vector(self, source: str, text: str, model: str,
                   vector: Union[list, np.ndarray]):
        '''
        Add a vector to the database.
        Upon storage, we force the norm of the vector to be 1.

        Args:
            source: source of the vector, e.g., file path, url
            text: original text content corresponding to the vector
            model: embedding model name for the vector
            vector: the vector to store
        Returns:
            None
        '''
        # Convert vector to bytes for storage
        assert len(vector) >= self.dim
        vector_np = np.array(vector, dtype=self.__dtype)
        vector_np_reduction = vector_np[:self.dim]
        # normalize the vector
        vector_np_reduction = vector_np_reduction / np.linalg.norm(
            vector_np_reduction)
        vector_bytes = vector_np_reduction.tobytes()
        text_compressed = lz4.frame.compress(text.encode())
        self.cursor.execute(
            'INSERT INTO vectors (source, text, model, vector) VALUES (?, ?, ?, ?)',
            (
                source,
                text_compressed,
                model,
                vector_bytes,
            ))
        self.connection.commit()

    def _decode_row(self, row: List):
        idx, source, text_compressed, model, vector_bytes = row
        vector_np = np.frombuffer(vector_bytes, dtype=self.__dtype)
        text_uncompressed = lz4.frame.decompress(text_compressed).decode()
        return [idx, source, text_uncompressed, model, vector_np]

    def get_vector(self, vector_id: int) -> List[Union[str, np.ndarray]]:
        self.cursor.execute('SELECT * FROM vectors WHERE id = ?',
                            (vector_id, ))
        result = self.cursor.fetchone()
        if result:
            return self._decode_row(result)
        raise ValueError(f'Vector with id={vector_id} not found')

    def get_all_rows(self):
        self.cursor.execute('SELECT * FROM vectors')
        results = self.cursor.fetchall()
        return [self._decode_row(row) for row in results]

    def get_all_vectors(self):
        self.cursor.execute('SELECT id, vector FROM vectors')
        results = self.cursor.fetchall()
        return [(idx, np.frombuffer(vector, dtype=self.__dtype))
                for idx, vector in results]

    def get_all(self) -> List[np.ndarray]:
        idxs, vectors = list(zip(*self.get_all_vectors()))
        idxs = np.array(idxs)
        matrix = np.stack(vectors)
        return idxs, matrix

    def delete_vector(self, vector_id: int):
        self.cursor.execute('DELETE FROM vectors WHERE id = ?', (vector_id, ))
        self.connection.commit()

    def close(self):
        self.connection.close()

    def retrieve(self, vector: np.ndarray, topk: int = 3):
        '''
        Retrieve the nearest vector from the database.
        '''
        idxs, matrix = self.get_all()
        assert matrix.ndim == 2
        assert vector.ndim == 1
        vector = vector / np.linalg.norm(vector)
        cosine = (matrix @ vector.reshape(-1, 1)).flatten()
        #print('cosine', cosine)
        argsort = np.argsort(cosine)[::-1][:topk]
        #print('argsort', argsort)
        #print('idxs[argsort]', idxs[argsort])
        #print('cosine[argsort]', cosine[argsort])
        documents = []
        for idx, sim in zip(idxs[argsort], cosine[argsort]):
            _, source, text, _, _ = self.get_vector(int(idx))
            doc = [sim, source, text]
            documents.append(doc)
        return documents

    def ls(self):
        '''
        List all vectors in the database.
        '''
        vectors = self.get_all_rows()
        for v in vectors:
            idx, source, text, model, vector = v
            console.log(f'[{idx:4d}]', f'model={repr(model)},',
                        f'len(vector)={len(vector)}',
                        f'source={repr(source)},')
        return vectors

    def show(self, idx: int):
        '''
        Show the vector with the given index.
        '''
        vector = self.get_vector(idx)
        idx, source, text, model, vector = vector
        print(
            f'[{idx:4d}]',
            f'model={repr(model)},',
            f'len(vector)={len(vector)}',
            f'source={repr(source)},',
        )
        print('vector=', vector)
        print('text=', text)


def main(argv: List[str]):
    parser = argparse.ArgumentParser()
    parser.add_argument('--db',
                        type=str,
                        default='VectorDB.sqlite',
                        help='Database file name')
    subparsers = parser.add_subparsers(dest='action')
    parser_demo = subparsers.add_parser('demo')
    parser_create = subparsers.add_parser('create')
    parser_ls = subparsers.add_parser('ls')
    parser_show = subparsers.add_parser('show')
    parser_show.add_argument('id', type=int, help='ID of the vector to show')
    parser_rm = subparsers.add_parser('rm')
    parser_rm.add_argument('id', type=int, help='ID of the vector to remove')
    args = parser.parse_args(argv)

    if args.action == 'demo':
        # create a database for demo purposes
        db = VectorDB(args.db)
        # Adding vectors
        for i in range(10):
            v = np.random.rand(256)
            db.add_vector(f'vector_{i}', str(v), f'model_name', v)
        # make sure there is at least one vector with cosine=1 for normalized ones(256)
        db.add_vector(f'ones', str(np.ones(256)), f'model_name', np.ones(256))
        db.close()
    elif args.action == 'ls':
        db = VectorDB(args.db)
        db.ls()
        db.close()
    elif args.action == 'show':
        db = VectorDB(args.db)
        db.show(args.id)
        db.close()
    elif args.action == 'rm':
        db = VectorDB(args.db)
        db.delete_vector(args.id)
        console.log(f'Deleted vector with id={args.id}')
        db.close()
    else:
        parser.print_help()


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv)
