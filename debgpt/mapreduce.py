'''
Copyright (C) 2024 Mo Zhou <lumin@debian.org>

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
from typing import List, Union, Dict, Tuple, Optional
import re
import requests
from bs4 import BeautifulSoup
import argparse
import io
import os
import subprocess
import functools as ft
import sys
import glob
import shlex
import mimetypes
import tenacity
import concurrent.futures
from urllib.parse import urlparse
from urllib.request import urlopen
import urllib.parse
from . import policy as debian_policy
from .defaults import console
from collections import namedtuple


def _mapreduce_chunk_lines(path: str, start: int, end: int, lines: List[str],
                           *, chunk_size: int):
    chunk_size_in_bytes = sum(len(x.encode('utf8')) for x in lines[start:end])
    if chunk_size_in_bytes < chunk_size:
        return {(path, start, end): lines[start:end]}
    elif end - start == 1:
        return {(path, start, end): lines[start:end]}
    else:
        # split the lines into chunks
        middle = (start + end) // 2
        left = _mapreduce_chunk_lines(path,
                                      start,
                                      middle,
                                      lines,
                                      chunk_size=chunk_size)
        right = _mapreduce_chunk_lines(path,
                                       middle,
                                       end,
                                       lines,
                                       chunk_size=chunk_size)
        return {**left, **right}


def _mapreduce_chunk_lines_norecussion(path: str, start: int, end: int,
                                       lines: List[str], *, chunk_size: int):
    '''
    the non-recursion version of the above function
    the above version seems to be problematic when dealing with large files

    this function is modified from re-written of the above function with chatgpt.
    '''
    result = {}
    stack = [(start, end)]
    lens = [len(line.encode('utf8')) for line in lines]

    while stack:
        current_start, current_end = stack.pop()
        chunk_size_in_bytes = sum(lens[current_start:current_end])

        if chunk_size_in_bytes < chunk_size:
            # If the chunk is within the size limit, add to result
            result[(path, current_start,
                    current_end)] = lines[current_start:current_end]
        elif current_end - current_start == 1:
            # If the chunk is too large, but only one line, add to result
            result[(path, current_start,
                    current_end)] = lines[current_start:current_end]
        else:
            # If the chunk is too large, split it and add to stack
            middle = (current_start + current_end) // 2
            stack.append((current_start, middle))
            stack.append((middle, current_end))
        print('number of lines:', len(lines), 'stack size:', len(stack))

    return result


def mapreduce_load_url(
    url: str,
    chunk_size: int = 8192,
) -> Dict[Tuple[str, int, int], List[str]]:
    '''
    load text contents from a URL and return the chunked contents
    '''
    with urlopen(url) as response:
        content = response.read().decode('utf-8')
        lines = content.splitlines()
    lines = [x.rstrip() for x in lines]
    chunkdict = _mapreduce_chunk_lines(url,
                                       0,
                                       len(lines),
                                       lines,
                                       chunk_size=chunk_size)
    return chunkdict


def mapreduce_load_file(
    path: str,
    chunk_size: int = 8192,
) -> Dict[Tuple[str, int, int], List[str]]:
    '''
    load the file and return the content as a list of lines
    '''
    # tell the file type and load the file as lines
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type == 'application/pdf':
        lines = _load_pdf(path)
    else:
        with open(path, 'rt') as f:
            lines = [x.rstrip() for x in f.readlines()]

    # chunk the lines
    try:
        chunkdict = _mapreduce_chunk_lines(path,
                                           0,
                                           len(lines),
                                           lines,
                                           chunk_size=chunk_size)
    except RecursionError:
        console.log(
            'Oops! falling back to non-recursion chunking due to RecursionError'
        )
        chunkdict = _mapreduce_chunk_lines_norecussion(path,
                                                       0,
                                                       len(lines),
                                                       lines,
                                                       chunk_size=chunk_size)
    return chunkdict


def mapreduce_load_directory(
    path: str,
    chunk_size: int = 8192,
) -> Dict[Tuple[str, int, int], List[str]]:
    '''
    load a whole directory and return the chunked contents
    '''
    all_chunks = dict()
    for root, _, files in os.walk(path):
        for file in files:
            path = os.path.join(root, file)
            if not is_text_file(path):
                continue
            chunkdict = mapreduce_load_file(path, chunk_size=chunk_size)
            all_chunks.update(chunkdict)
    return all_chunks


def mapreduce_parse_path(path: str, debgpt_home: str) -> str:
    '''
    parse the path string and return the actual path or URL.

    e.g. policy: -> <debgpt_home>/policy.txt
    '''
    if path.startswith(':'):
        if path == 'policy:':
            return os.path.join(debgpt_home, 'policy.txt')
        elif path == 'devref:':
            return os.path.join(debgpt_home, 'devref.txt')
        else:
            raise ValueError(f'Undefined special path {path}')
    elif path == 'sbuild:':
        if not os.path.exists('./debian'):
            raise FileNotFoundError(
                './debian directory not found. Are you in the right directory?'
            )
        return _latest_glob('../*.build')
    else:
        return path


def mapreduce_load_any(
    path: str,
    chunk_size: int = 8192,
    *,
    user_question: str = '',
    args: Optional[object] = None,
) -> Dict[Tuple[str, int, int], List[str]]:
    '''
    load file or directory and return the chunked contents
    '''
    if path == 'policy:':
        lines = debgpt_policy.DebianPolicy(
            os.path.join(args.debgpt_home, 'policy.txt')).lines
        return _mapreduce_chunk_lines('Debian Policy',
                                      0,
                                      len(lines),
                                      lines,
                                      chunk_size=chunk_size)

    elif path == 'devref:':
        lines = debgpt_policy.DebianDevref(
            os.path.join(args.debgpt_home, 'devref.txt')).lines
        return _mapreduce_chunk_lines('Debian Developer Reference',
                                      0,
                                      len(lines),
                                      lines,
                                      chunk_size=chunk_size)

    elif path == 'sbuild:':
        '''
        load the latest sbuild buildlog. we will automatically figure out the
        latest buildlog file in the parent directory.
        '''
        if not os.path.exists('./debian'):
            raise FileNotFoundError(
                './debian directory not found. Are you in the right directory?'
            )
        latest_build_log = _latest_glob('../*.build')
        return mapreduce_load_file(latest_build_log, chunk_size)

    elif path.startswith('google:'):
        query = path[7:] if len(path) > 7 else user_question
        urls = google_search(query)
        if args.verbose:
            console.log(f'Google Search Results for {repr(query)}:', urls)
        else:
            console.log(
                f'Got {len(urls)} Google Search Results for {repr(query)}.')
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(_load_url_parsed, url): url
                for url in urls
            }
            chunkdict = {}
            for future in concurrent.futures.as_completed(futures):
                url = futures[future]
                lines = future.result()
                chunkdict.update(
                    _mapreduce_chunk_lines(url,
                                           0,
                                           len(lines),
                                           lines,
                                           chunk_size=chunk_size))
        return chunkdict

    elif any(path.startswith(x) for x in ('file://', 'http://', 'https://')):
        return mapreduce_load_url(path, chunk_size=chunk_size)
    elif os.path.isdir(path):
        return mapreduce_load_directory(path, chunk_size=chunk_size)
    elif os.path.isfile(path):
        return mapreduce_load_file(path, chunk_size=chunk_size)
    else:
        raise FileNotFoundError(f'{path} not found')


def mapreduce_load_any_astext(
    path: Union[str | List[str]],
    chunk_size: int = 8192,
    *,
    user_question: str = '',
    args: Optional[object] = None,
) -> List[str]:
    '''
    load file or directory and return the contents as a list of lines
    '''
    # if list, reduce and concur recursively
    if isinstance(path, list):
        texts = [
            mapreduce_load_any_astext(p,
                                      chunk_size=chunk_size,
                                      user_question=user_question,
                                      args=args) for p in path
        ]
        texts = ft.reduce(list.__add__, texts)
        return texts
    # if str, deal with the concrete loading
    chunkdict = mapreduce_load_any(path,
                                   chunk_size=chunk_size,
                                   user_question=user_question,
                                   args=args)
    texts = []
    for (path, start, end), lines in chunkdict.items():
        txt = f'File: {path} (lines {start}-{end})\n'
        txt += '```\n'
        txt += '\n'.join(lines)
        txt += '\n```\n'
        texts.append(txt)
    return texts


def mapreduce_super_long_context(ag) -> str:
    '''
    We can add a mechanism to chunk super long context , let LLM read chunk
    by chunk, providing chunk-wise analysis. Then we aggregate the chunk-wise
    analysis together using LLM again.

    Procedure:
      1. chunk a long input into pieces
      2. map each piece to LLM and get the result
      3. reduce (aggregate) the results using LLM
      4. return the aggregated LLM output
    '''
    # TODO: parse special questions like does in gather_information_ordered()
    if ag.ask:
        user_question = ag.ask
    else:
        user_question = 'summarize the above contents.'

    chunks = reader.mapreduce_load_any_astext(ag.mapreduce,
                                              ag.mapreduce_chunksize,
                                              user_question=user_question,
                                              args=ag)
    console.print(
        f'[bold]MapReduce[/bold]: Got {len(chunks)} chunks from {ag.mapreduce}'
    )
    if ag.verbose:
        for i, chunk in enumerate(chunks):
            firstline = chunk.split('\n')[:1]
            console.print(f'  [bold]Chunk {i}[/bold]: {firstline}...')

    def _shorten(s: str, maxlen: int = 100) -> str:
        return textwrap.shorten(s[::-1], width=maxlen,
                                placeholder='......')[::-1]

    def _pad_chunk(chunk: str, question: str) -> str:
        '''
        process a chunk of text with a question
        '''
        template = 'Extract any information that is relevant to question '
        template += f'{repr(question)} from the following file part. '
        template += 'Note, if there is no relevant information, just briefly say nothing.'
        template += '\n\n\n'
        template += chunk
        return template

    # skip mapreduce if there is only one chunk
    if len(chunks) == 1:
        filepath = reader.mapreduce_parse_path(ag.mapreduce,
                                               debgpt_home=ag.debgpt_home)
        if any(
                filepath.startswith(x)
                for x in ('file://', 'http://', 'https://')):
            return reader.url(filepath)
        else:
            if filepath.endswith('.pdf'):
                return reader.pdf(filepath)
            else:
                return reader.file(filepath)

    def _process_chunk(chunk: str, question: str) -> str:
        '''
        process a chunk of text with a question
        '''
        template = _pad_chunk(chunk, question)
        if ag.verbose:
            console.log('mapreduce:send:', _shorten(template, 100))
        answer = ag.frontend_instance.oneshot(template)
        if ag.verbose:
            console.log('mapreduce:recv:', _shorten(answer, 100))
        return answer

    def _pad_two_results(a: str, b: str, question: str) -> str:
        template = 'Extract any information that is relevant to question '
        template += f'{repr(question)} from the following contents and aggregate them. '
        template += 'Note, if there is no relevant information, just briefly say nothing.'
        template += '\n\n\n'
        template += '```\n' + a + '\n```\n\n'
        template += '```\n' + b + '\n```\n\n'
        return template

    def _process_two_results(a: str, b: str, question: str) -> str:
        template = _pad_two_results(a, b, question)
        if ag.verbose:
            console.log('mapreduce:send:', _shorten(template, 100))
        answer = ag.frontend_instance.oneshot(template)
        if ag.verbose:
            console.log('mapreduce:recv:', _shorten(answer, 100))
        return answer

    # start the reduce of chunks from super long context
    if ag.mapreduce_parallelism > 1:
        '''
        Parallel processing. Note, we may easily exceed the TPM limit set
        by the service provider. We will automatically retry until success.
        '''
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=ag.mapreduce_parallelism) as executor:
            results = list(
                track(executor.map(lambda x: _process_chunk(x, user_question),
                                   chunks),
                      total=len(chunks),
                      description=f'MapReduce[{ag.mapreduce_parallelism}]:',
                      transient=True))
        while len(results) > 1:
            console.print(
                f'[bold]MapReduce[/bold]: reduced to {len(results)} intermediate results'
            )
            pairs = list(zip(results[::2], results[1::2]))
            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=ag.mapreduce_parallelism) as executor:
                new_results = list(
                    track(
                        executor.map(
                            lambda x: _process_two_results(*x, user_question),
                            pairs),
                        total=len(pairs),
                        description=f'Mapreduce[{ag.mapreduce_parallelism}]:',
                        transient=True))
            if len(results) % 2 == 1:
                new_results.append(results[-1])
            results = new_results
        aggregated_result = results[0]
    else:
        '''
        serial processing
        '''
        # mapreduce::first pass
        results = []
        for chunk in track(chunks,
                           total=len(chunks),
                           description='MapReduce: initial pass'):
            results.append(_process_chunk(chunk, user_question))
        # mapreduce::recursive processing
        while len(results) > 1:
            console.print(
                f'[bold]MapReduce[/bold]: reduced to {len(results)} intermediate results'
            )
            new_results = []
            for (a, b) in track(zip(results[::2], results[1::2]),
                                total=len(results) // 2,
                                description='Mapreduce: intermediate pass'):
                new_results.append(_process_two_results(a, b, user_question))
            if len(results) % 2 == 1:
                new_results.append(results[-1])
            results = new_results
        aggregated_result = results[0]
    return aggregated_result + '\n\n'
