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
from .vectordb import VectorDB


def retry_ratelimit(func: callable,
                    exception: Exception,
                    retry_interval: int = 15):
    '''
    a decorator to retry the function call when exception occurs.

    OpenAI API doc provides some other methods to retry:
    https://platform.openai.com/docs/guides/rate-limits/error-mitigation
    '''

    @ft.wraps(func)
    def wrapper(*args, **kwargs):
        while True:
            try:
                result = func(*args, **kwargs)
                break
            except exception as e:
                console.log(
                    f'Rate limit reached. Will retry after {retry_interval} seconds.'
                )
                time.sleep(15)
        return result

    return wrapper


class AbstractEmbeddingModel(object):

    # the model name
    model = 'none'

    # the embedding dimension (after reduction)
    dim = 0

    def __init__(self):
        pass

    def embed(self, text: str) -> np.ndarray:
        raise NotImplementedError('This is an abstract method.')

    def batch_embed(self, texts: List[str]) -> np.ndarray:
        raise NotImplementedError('This is an abstract method.')

    def __call__(self, text: Union[str, List[str]]) -> np.ndarray:
        if isinstance(text, str):
            return self.embed(text)
        elif isinstance(text, list):
            return self.batch_embed(text)
        else:
            raise ValueError('Invalid input type.')


class OpenAIEmbedding(AbstractEmbeddingModel):

    def __init__(self, args: object = None):
        from openai import OpenAI
        self.client = OpenAI()
        self.model = args.embedding_model
        self.dim = args.embedding_dimension

    def embed(self, text: str) -> np.ndarray:
        from openai import RateLimitError
        func = retry_ratelimit(self.client.embeddings.create, RateLimitError)
        response = func(input=text, model=self.model)
        vector = np.array(response.data[0].embedding)[:self.dim]
        return vector

    def batch_embed(self, texts: List[str]) -> np.ndarray:
        from openai import RateLimitError
        func = retry_ratelimit(self.client.embeddings.create, RateLimitError)
        response = func(input=texts, model=self.model)
        matrix = np.stack([x.embedding for x in response.data])[:, :self.dim]
        return matrix


class Retriever(object):

    def __init__(self, args: object):
        self.model = get_embedding_model(args)
        self.vdb = VectorDB(args.embedding_database, self.model.dim)

    def retrieve(self, query: str, documents: List[str]) -> List[str]:
        query_embedding = self.embedding.embed(query)
        document_embeddings = self.embedding.batch_embed(documents)
        scores = np.dot(document_embeddings, query_embedding)
        indices = np.argsort(scores)[::-1]
        return [documents[i] for i in indices]

    def add(self, source: str, text: str) -> np.ndarray:
        model_name = self.model.model
        vector = self.model.embed(text)
        self.vdb.add_vector(source, text, model_name, vector)
        return vector


def get_embedding_model(args: object) -> AbstractEmbeddingModel:
    if args.embedding_frontend == 'openai':
        return OpenAIEmbedding(args)
    else:
        raise ValueError('Invalid embedding frontend.')



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
