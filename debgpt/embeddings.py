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
from typing import List, Union, Callable, Any
import sys
import os
import argparse
import rich
import numpy as np
import functools as ft
from rich.console import Console
from . import defaults

console = defaults.console


def retry_ratelimit(func: Callable, exception: Exception, retry_interval: int = 15) -> Callable:
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
            except exception as e:
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

    def __init__(self) -> None:
        pass

    def embed(self, text: str) -> np.ndarray:
        '''
        Embed a single text string.

        Args:
            text (str): The text to embed.

        Returns:
            np.ndarray: The embedding vector.
        '''
        raise NotImplementedError('This is an abstract method.')

    def batch_embed(self, texts: List[str]) -> np.ndarray:
        '''
        Embed a batch of text strings.

        Args:
            texts (List[str]): List of texts to embed.

        Returns:
            np.ndarray: A matrix of embedding vectors.
        '''
        raise NotImplementedError('This is an abstract method.')

    def __call__(self, text: Union[str, List[str]]) -> np.ndarray:
        '''
        Call method to embed text or batch of texts.

        Args:
            text (Union[str, List[str]]): Text or list of texts to embed.

        Returns:
            np.ndarray: The embedding vector or matrix.
        '''
        if isinstance(text, str):
            return self.embed(text)
        elif isinstance(text, list):
            return self.batch_embed(text)
        else:
            raise ValueError('Invalid input type.')


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
        return matrix


class GeminiEmbedding(AbstractEmbeddingModel):
    '''
    Gemini embedding model implementation.

    Example model: "models/text-embedding-004"
    This model has a maximum dimension of 768.
    Example dimension: 256

    Reference:
    https://github.com/google-gemini/cookbook/blob/main/quickstarts/Embeddings.ipynb
    '''

    def __init__(self, args: object = None) -> None:
        import google.generativeai as genai
        genai.configure(api_key=args.gemini_api_key)
        self.client = genai
        self.model = args.gemini_embedding_model
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
        response = func(model=self.model, content=text,
                        output_dimensionality=self.dim)
        vector = np.array(response['embedding'])
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
        response = func(model=self.model, content=texts,
                        output_dimensionality=self.dim)
        matrix = np.stack(response['embedding'])[:, :self.dim]
        return matrix


def get_embedding_model(args: object) -> AbstractEmbeddingModel:
    '''
    Get the embedding model based on the provided arguments.

    Args:
        args (object): The arguments containing model configuration.

    Returns:
        AbstractEmbeddingModel: The instantiated embedding model.
    '''
    if args.embedding_frontend == 'openai':
        return OpenAIEmbedding(args)
    if args.embedding_frontend == 'gemini':
        return GeminiEmbedding(args)
    else:
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
    print(f'vector.shape:', vector.shape)
    print(f'vector.min:', vector.min())
    print(f'vector.max:', vector.max())
    print(f'vector.mean:', vector.mean())
    print(f'vector.std:', vector.std())
    print(f'vector[:10]:', vector[:10])
    print(f'vector[-10:]:', vector[-10:])


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
