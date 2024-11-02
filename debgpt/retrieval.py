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
from typing import List, Union
import argparse
import rich
import numpy as np
import functools as ft
from rich.console import Console
from .defaults import console
from . import vectordb
from . import embedddings


class Retriever(object):

    def __init__(self, args: object):
        self.model = embeddings.get_embedding_model(args)
        self.vdb = vectordb.VectorDB(args.embedding_database, self.model.dim)

    def retrieve(self,
                 query: str,
                 documents: List[str],
                 topk: int = 3) -> List[str]:
        '''
        This function retrieves the top-k most relevant documents from the
        document list given a query. It does not modify the database, nor
        query the database.
        '''
        query_embedding = self.embedding.embed(query)
        document_embeddings = self.embedding.batch_embed(documents)
        scores = np.dot(document_embeddings, query_embedding)
        indices = np.argsort(scores)[::-1]
        return [documents[i] for i in indices][:topk]

    def add(self, source: str, text: str) -> np.ndarray:
        '''
        This function computes and adds a new vector to the database.
        '''
        model_name = self.model.model
        vector = self.model.embed(text)
        self.vdb.add(source, text, model_name, vector)
        return vector

    def retrieve_from_db(self, query: str, topk: int = 3) -> List[str]:
        '''
        This function retrieves the top-k most relevant documents from the
        database given a query.
        '''
        query_embedding = self.model.embed(query)
        scores, documents = self.vdb.retrieve(query_embedding, topk)
        return documents


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--embedding-frontend',
                        '-E',
                        type=str,
                        default='openai',
                        help='Embedding frontend')
    parser.add_argument('--embedding-model',
                        type=str,
                        default="text-embedding-3-small",
                        help='OpenAI embedding model')
    parser.add_argument('--embedding-dimension',
                        type=int,
                        default=256,
                        help='Embedding dimension')
    parser.add_argument('--embedding-database',
                        type=str,
                        default='vectors.db',
                        help='Embedding database')
    args = parser.parse_args()

    retriever = Retriever(args)
    vector = retriever.add('void', "Your text string goes here")
    print(f'embedding:', vector.shape)
