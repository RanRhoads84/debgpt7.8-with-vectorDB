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
from typing import List, Union, Callable, Any
import time
import sys
import argparse
import numpy as np
import functools as ft
from . import defaults

console = defaults.console


def retry_ratelimit(func: Callable,
                    exception: Exception,
                    retry_interval: int = 15) -> Callable:
    '''
    A decorator to retry the function call when exception occurs.

    OpenAI API doc provides some other methods to retry:
    https://platform.openai.com/docs/guides/rate-limits/error-mitigation

    Args:
        func (Callable): The function to be retried.
        exception (Exception): The exception to catch and retry upon.
        retry_interval (int): The interval in seconds to wait before retrying.

    Returns:
        Callable: A wrapped function with retry logic.
    '''

    @ft.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        while True:
            try:
                result = func(*args, **kwargs)
                break
            except exception:  # pragma: no cover
                console.log(
                    f'Rate limit reached. Will retry after {retry_interval} seconds.'
                )
                time.sleep(retry_interval)
        return result

    return wrapper


class AbstractEmbeddingModel(object):
    '''
    Abstract class for embedding models.
    '''

    # the model name
    model: str = 'none'

    # the embedding dimension (after reduction)
    dim: int = 0

    def __init__(self) -> None:  # pragma: no cover
        pass

    def embed(self, text: str) -> np.ndarray:  # pragma: no cover
        '''
        Embed a single text string.

        Args:
            text (str): The text to embed.

        Returns:
            np.ndarray: The embedding vector.
        '''
        raise NotImplementedError('This is an abstract method.')

    def batch_embed(self, texts: List[str]) -> np.ndarray:  # pragma: no cover
        '''
        Embed a batch of text strings.

        Args:
            texts (List[str]): List of texts to embed.

        Returns:
            np.ndarray: A matrix of embedding vectors (normalized).
        '''
        raise NotImplementedError('This is an abstract method.')

    def __call__(self, text: Union[str, List[str]]) -> np.ndarray:
        '''
        Call method to embed text or batch of texts.

        Args:
            text (Union[str, List[str]]): Text or list of texts to embed.

        Returns:
            np.ndarray: The embedding vector or matrix (normalized).
        '''
        if isinstance(text, str):
            return self.embed(text)
        elif isinstance(text, list):
            return self.batch_embed(text)
        else:  # pragma: no cover
            raise ValueError('Invalid input type.')


class RandomEmbedding(AbstractEmbeddingModel):
    '''
    Random embedding model for testing purposes.
    '''

    def __init__(self, args: object = None) -> None:
        self.model = 'random'
        self.dim = args.embedding_dim

    def embed(self, text: str) -> np.ndarray:
        '''
        Embed a single text string using random vectors.

        Args:
            text (str): The text to embed.

        Returns:
            np.ndarray: The embedding vector.
        '''
        vector = np.random.randn(self.dim)
        vector = vector / np.linalg.norm(vector)
        return vector

    def batch_embed(self, texts: List[str]) -> np.ndarray:
        '''
        Embed a batch of text strings using random vectors.

        Args:
            texts (List[str]): List of texts to embed.

        Returns:
            np.ndarray: A matrix of embedding vectors.
        '''
        matrix = np.random.randn(len(texts), self.dim)
        matrix = matrix / np.linalg.norm(matrix, axis=1)[:, np.newaxis]
        return matrix


class OpenAIEmbedding(AbstractEmbeddingModel):
    '''
    OpenAI embedding model implementation.
    '''

    def __init__(self, args: object = None) -> None:
        from openai import OpenAI
        self.client = OpenAI(api_key=args.openai_api_key,
                             base_url=args.openai_base_url)
        self.model = args.openai_embedding_model
        self.dim = args.embedding_dim

    def embed(self, text: str) -> np.ndarray:
        '''
        Embed a single text string using OpenAI.

        Args:
            text (str): The text to embed.

        Returns:
            np.ndarray: The embedding vector.
        '''
        from openai import RateLimitError
        func = retry_ratelimit(self.client.embeddings.create, RateLimitError)
        response = func(input=text, model=self.model, dimensions=self.dim)
        vector = np.array(response.data[0].embedding)
        vector = vector / np.linalg.norm(vector)
        return vector

    def batch_embed(self, texts: List[str]) -> np.ndarray:
        '''
        Embed a batch of text strings using OpenAI.

        Args:
            texts (List[str]): List of texts to embed.

        Returns:
            np.ndarray: A matrix of embedding vectors.
        '''
        from openai import RateLimitError
        func = retry_ratelimit(self.client.embeddings.create, RateLimitError)
        response = func(input=texts, model=self.model)
        matrix = np.stack([x.embedding for x in response.data])[:, :self.dim]
        matrix = matrix / np.linalg.norm(matrix, axis=1)[:, np.newaxis]
        return matrix


class GoogleEmbedding(AbstractEmbeddingModel):
    '''
    Google embedding model implementation.

    Example model: "models/text-embedding-004"
    This model has a maximum dimension of 768.
    Example dimension: 256

    Reference:
    https://github.com/google-gemini/cookbook/blob/main/quickstarts/Embeddings.ipynb
    '''

    def __init__(self, args: object = None) -> None:
        import google.generativeai as genai
        genai.configure(api_key=args.google_api_key)
        self.client = genai
        self.model = args.google_embedding_model
        self.dim = args.embedding_dim

    def embed(self, text: str) -> np.ndarray:
        '''
        Embed a single text string using Gemini.

        Args:
            text (str): The text to embed.

        Returns:
            np.ndarray: The embedding vector.
        '''
        from google.api_core.exceptions import ResourceExhausted
        func = retry_ratelimit(self.client.embed_content, ResourceExhausted)
        response = func(model=self.model,
                        content=text,
                        output_dimensionality=self.dim)
        vector = np.array(response['embedding'])
        vector = vector / np.linalg.norm(vector)
        return vector

    def batch_embed(self, texts: List[str]) -> np.ndarray:
        '''
        Embed a batch of text strings using Gemini.

        Args:
            texts (List[str]): List of texts to embed.

        Returns:
            np.ndarray: A matrix of embedding vectors.
        '''
        from google.api_core.exceptions import ResourceExhausted
        func = retry_ratelimit(self.client.embed_content, ResourceExhausted)
        response = func(model=self.model,
                        content=texts,
                        output_dimensionality=self.dim)
        matrix = np.stack(response['embedding'])[:, :self.dim]
        matrix = matrix / np.linalg.norm(matrix, axis=1)[:, np.newaxis]
        return matrix


def get_embedding_model(
        args: object) -> AbstractEmbeddingModel:  # pragma: no cover
    '''
    Get the embedding model based on the provided arguments.

    Args:
        args (object): The arguments containing model configuration.

    Returns:
        AbstractEmbeddingModel: The instantiated embedding model.
    '''
    if args.embedding_frontend == 'openai':
        return OpenAIEmbedding(args)
    elif args.embedding_frontend == 'google':
        return GoogleEmbedding(args)
    elif args.embedding_frontend == 'random':
        return RandomEmbedding(args)
    else:  # pragma: no cover
        raise ValueError('Invalid embedding frontend.')


def main(argv: List[str]) -> None:
    '''
    Main function to parse arguments and perform embedding.

    Args:
        argv (List[str]): Command-line arguments.
    '''
    conf = defaults.Config()
    parser = argparse.ArgumentParser()
    parser.add_argument('text',
                        type=str,
                        nargs='?',
                        default='Your text string goes here',
                        help='Text to embed')
    args = parser.parse_args(argv)

    model = get_embedding_model(conf)
    vector = model.embed(args.text)
    print('vector.shape:', vector.shape)
    print('vector.min:', vector.min())
    print('vector.max:', vector.max())
    print('vector.mean:', vector.mean())
    print('vector.std:', vector.std())
    print('vector[:10]:', vector[:10])
    print('vector[-10:]:', vector[-10:])


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
