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
import rich
import numpy as np
import functools as ft
from rich.console import Console

console = Console(stderr=True)


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
        self.model = "text-embedding-3-small"

    def embed(self, text: str) -> np.ndarray:
        from openai import RateLimitError
        func = retry_ratelimit(self.client.embeddings.create, RateLimitError)
        response = func(input=text, model=self.model)
        vector = np.array(response.data[0].embedding)
        return vector

    def batch_embed(self, texts: List[str]) -> np.ndarray:
        from openai import RateLimitError
        func = retry_ratelimit(self.client.embeddings.create, RateLimitError)
        response = func(input=texts, model=self.model)
        matrix = np.array([x.embedding for x in response.data])
        return matrix


if __name__ == '__main__':
    model = OpenAIEmbedding()
    text = "Your text string goes here",
    embedding = model.embed(text)
    print(f'embedding({len(embedding)}):', embedding)
