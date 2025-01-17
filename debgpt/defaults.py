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
import sys
import os
import tomllib  # requires python >= 3.10
from rich.console import Console
from rich.traceback import install

install()

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
CACHE = os.path.join(HOME, 'cache.sqlite')


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
            # Embedding Settings
            'embedding_frontend': 'openai',
            'embedding_dim': 256,
            # Mapreduce Settings
            'mapreduce_chunksize': 65536,
            'mapreduce_parallelism': 8,
            # OpenAI Frontend Specific
            'openai_base_url': 'https://api.openai.com/v1',
            'openai_model': 'gpt-4o',
            'openai_embedding_model': 'text-embedding-3-small',
            'openai_api_key': 'your-openai-api-key',
            # Anthropic Frontend Specific
            'anthropic_base_url': 'https://api.anthropic.com',
            'anthropic_api_key': 'your-anthropic-api-key',
            'anthropic_model': 'claude-3-5-sonnet-20241022',
            # Gemini Frontend Specific
            'google_api_key': 'your-google-api-key',
            'google_model': 'gemini-1.5-flash',
            'google_embedding_model': 'models/text-embedding-004',
            # xAI Frontend Specific
            'xai_api_key': 'your-xai-api-key',
            'xai_model': 'grok-beta',
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
                console.log('Found environment variable OPENAI_API_KEY.')
            self.toml['openai_api_key'] = openai_api_key
        if (anthropic_api_key := os.getenv('ANTHROPIC_API_KEY',
                                           None)) is not None:
            if verbose:
                console.log('Found environment variable ANTHROPIC_API_KEY.')
            self.toml['anthropic_api_key'] = anthropic_api_key
        if (google_api_key := os.getenv('GOOGLE_API_KEY', None)) is not None:
            if verbose:
                console.log('Found environment variable GOOGLE_API_KEY.')
            self.toml['google_api_key'] = google_api_key
        # create default vector db name
        emb_model = self.toml[f'{self.embedding_frontend}_embedding_model']
        self.toml['db'] = os.path.join(
            home, 'VectorDB_{model}_dim{dim}.sqlite'.format(
                model=emb_model, dim=self.toml['embedding_dim']))
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
Debian Free Software Guideline. You follow the Debian Policy. You must
always cite resources in your response when applicable, and provide the
URL links in plain text format in the response.'''
