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
import sys
import os
import argparse
import rich
import numpy as np
import functools as ft
from rich.console import Console
from . import defaults
console = defaults.console
conf = defaults.Config()


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
        self.client = OpenAI(api_key=args.openai_api_key,
                             base_url=args.openai_base_url)
        self.model = args.embedding_model
        self.dim = args.embedding_dim

    def embed(self, text: str) -> np.ndarray:
        from openai import RateLimitError
        func = retry_ratelimit(self.client.embeddings.create, RateLimitError)
        response = func(input=text, model=self.model, dimensions=self.dim)
        vector = np.array(response.data[0].embedding)
        return vector

    def batch_embed(self, texts: List[str]) -> np.ndarray:
        from openai import RateLimitError
        func = retry_ratelimit(self.client.embeddings.create, RateLimitError)
        response = func(input=texts, model=self.model)
        matrix = np.stack([x.embedding for x in response.data])[:, :self.dim]
        return matrix


def get_embedding_model(args: object) -> AbstractEmbeddingModel:
    if args.embedding_frontend == 'openai':
        return OpenAIEmbedding(args)
    else:
        raise ValueError('Invalid embedding frontend.')



def main(argv: List[str]) -> None:
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
    parser.add_argument('--embedding-dim',
                        type=int,
                        default=256,
                        help='Embedding dimension')
    parser.add_argument('--embedding-database',
                        type=str,
                        default='vectors.db',
                        help='Embedding database')
    parser.add_argument('--openai-api-key',
                        type=str,
                        default=conf['openai_api_key'],
                        help='OpenAI API key')
    parser.add_argument('--openai-base-url',
                        type=str,
                        default='https://api.openai.com/v1',
                        help='OpenAI base URL')
    parser.add_argument('text',
                        type=str,
                        nargs='?',
                        default='Your text string goes here',
                        help='Text to embed')
    args = parser.parse_args(argv)

    model = get_embedding_model(args)
    vector = model.embed(args.text)
    print(f'vector.shape:', vector.shape)
    print(f'vector.min:', vector.min())
    print(f'vector.max:', vector.max())
    print(f'vector.mean:', vector.mean())
    print(f'vector.std:', vector.std())
    print(f'vector[:10]:', vector[:10])
    print(f'vector[-10:]:', vector[-10:])

    matrix = model.batch_embed([args.text] * 3)
    print(f'matrix.shape:', matrix.shape)
    print(f'matrix.min:', matrix.min())
    print(f'matrix.max:', matrix.max())
    print(f'matrix.mean:', matrix.mean())
    print(f'matrix.std:', matrix.std())
    print(f'matrix[:, :10]:', matrix[:, :10])
    print(f'matrix[:, -10:]:', matrix[:, -10:])

if __name__ == '__main__':
    main(sys.argv[1:])
