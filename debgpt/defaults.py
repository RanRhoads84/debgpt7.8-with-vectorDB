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
import os
try:
    import tomllib  # requires python >= 3.10
except:
    import pip._vendor.tomli as tomllib  # for python < 3.10
import rich
from rich.console import Console

# before we print anything, even before initializing class instances,
# we need to detect a special mode that does not allow any printing
# in stderr
if 'debgpt' in sys.argv[0] and 'pipe' in sys.argv:
    devnull = os.open(os.devnull, os.O_WRONLY)
    # Redirect stderr to /dev/null
    os.dup2(devnull, 2)

# default console that writes to stderr
console = Console(stderr=True)

########################
# Configuration handling
########################

HOME = os.path.expanduser('~/.debgpt')
CONFIG = os.path.join(HOME, 'config.toml')


class Config(object):

    def __init__(self,
                 home: str = HOME,
                 config: str = CONFIG,
                 verbose: bool = False):
        # The built-in defaults will be overridden by config file
        self.toml = {
            # CLI/Frontend Bebavior
            'frontend': 'openai',
            'debgpt_home': HOME,
            'monochrome': False,
            'render_markdown': True,
            # LLM Inference Parameters
            'temperature': 0.5,
            'top_p': 1.0,
            # OpenAI Frontend Specific
            'openai_base_url': 'https://api.openai.com/v1',
            'openai_model': 'gpt-4o',
            'openai_api_key': 'your-openai-api-key',
            # Anthropic Frontend Specific
            'anthropic_base_url': 'https://api.anthropic.com',
            'anthropic_api_key': 'your-anthropic-api-key',
            'anthropic_model': 'claude-3-5-sonnet-20241022',
            # Gemini Frontend Specific
            'gemini_api_key': 'your-google-gemini-api-key',
            'gemini_model': 'gemini-1.5-flash',
            # Llamafile Frontend Specific
            'llamafile_base_url': 'http://localhost:8080/v1',
            # Ollama Frontend Specific
            'ollama_base_url': 'http://localhost:11434/v1',
            'ollama_model': 'llama3.2',
            # vLLM Frontend Specific
            'vllm_base_url': 'http://localhost:8000/v1',
            'vllm_api_key': 'your-vllm-api-key',
            'vllm_model': 'NousResearch/Meta-Llama-3-8B-Instruct',
            # ZMQ Frontend Specific
            'zmq_backend': 'tcp://localhost:11177',
            # Prompt Composer Settings
            'mapreduce_chunksize': 65536,
            'mapreduce_parallelism': 8,
            # Embedding Settings
            'embedding_frontend': 'openai',
            'embedding_dim': 256,
            'embedding_model': 'text-embedding-3-small',
        }
        # the built-in defaults will be overridden by config file
        if not os.path.exists(home):
            if verbose:
                console.log(f'Creating directory {home}')
            os.mkdir(home)
        if os.path.exists(config):
            if verbose:
                console.log(f'Loading configuration from {config}')
            with open(config, 'rb') as f:
                content = tomllib.load(f)
                self.toml.update(content)
        # some arguments will be overrden by environment variables
        if (openai_api_key := os.getenv('OPENAI_API_KEY', None)) is not None:
            if verbose:
                console.print(f'Found environment variable OPENAI_API_KEY.')
            self.toml['openai_api_key'] = openai_api_key
        if (anthropic_api_key := os.getenv('ANTHROPIC_API_KEY',
                                           None)) is not None:
            if verbose:
                console.print(f'Found environment variable ANTHROPIC_API_KEY.')
            self.toml['anthropic_api_key'] = anthropic_api_key
        if (gemini_api_key := os.getenv('GOOGLE_API_KEY', None)) is not None:
            if verbose:
                console.print(f'Found environment variable GOOGLE_API_KEY.')
            self.toml['gemini_api_key'] = gemini_api_key
        # create default vector db name
        self.toml['db'] = os.path.join(
            home, 'VectorDB_{model}_dim{dim}.sqlite'.format(
                model=self.toml['embedding_model'],
                dim=self.toml['embedding_dim']))
        # all the above will be overridden by command line arguments
        pass

    def __getitem__(self, index):
        return self.toml.__getitem__(index)

    def __getattr__(self, index):
        return self.toml.__getitem__(index)


########################
# System Messages
########################

OPENAI_SYSTEM_MESSAGE = '''\
You are an excellent free software developer. You write high-quality code.
You aim to provide people with prefessional and accurate information.
You cherrish software freedom. You obey the Debian Social Contract and the
Debian Free Software Guideline. You follow the Debian Policy.'''
