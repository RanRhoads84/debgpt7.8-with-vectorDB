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
from rich.rule import Rule
from urllib.parse import urlparse
from urllib.request import urlopen
import urllib.parse
from . import policy as debian_policy
from . import reader
from .reader import Entry
from .defaults import console
from collections import namedtuple
from . import frontend


def entry2dict(entry: Entry,
               max_chunk_size: int = 8192
               ) -> Dict[Tuple[str, int, int], List[str]]:
    '''
    convert an Entry object to a chunked dictionary
    '''
    try:
        d = reader.chunk_lines(entry.content.split('\n'), max_chunk_size)
    except RecursionError:
        d = reader.chunk_lines_nonrecursive(entry.content.split('\n'),
                                            max_chunk_size)
    result = {}
    for (start, end), lines in d.items():
        result[(entry.path, start, end)] = lines
    return result


def entries2dict(entries: List[Entry],
                 max_chunk_size: int = 8192
                 ) -> Dict[Tuple[str, int, int], List[str]]:
    '''
    convert a list of Entry objects to a chunked dictionary

    Args:
        entries: a list of Entry objects
        max_chunk_size: the maximum chunk size in bytes
    Returns:
        a dictionary of chunked contents
    '''
    return ft.reduce(dict.__or__, [entry2dict(e, max_chunk_size) for e in entries])


def shorten(s: str, maxlen: int = 100) -> str:
    '''
    Shorten the string to a maximum length. Different from default textwrap
    behavior, we will shorten from the other side of the string.
    '''
    return textwrap.shorten(s[::-1], width=maxlen,
                            placeholder='......')[::-1]


def pad_chunk_before_map(chunk: str, question: str) -> str:
    '''
    process a chunk of text with a question
    '''
    template = 'Extract any information that is relevant to question '
    template += f'{repr(question)} from the following file part. '
    template += 'Note, if there is no relevant information, just briefly say nothing.'
    template += '\n\n\n'
    template += chunk
    return template


def mapreduce_super_long_context(spec: str, max_chunk_size: int,
                                 user_question: Optional[str] = None,
                                 debgpt_home: str = '.',
                                 verbose: bool = False) -> str:
    '''
    Divide and conquer any-length-context.

    This is a mechanism to chunk super long context , let LLM read chunk
    by chunk, providing chunk-wise response. Then we aggregate the chunk-wise
    response together using LLM again.

    Procedure:
      1. chunk a long input into pieces
      2. map each piece to LLM and get the result
      3. reduce (aggregate) the results using LLM
      4. return the aggregated LLM output
    '''
    assert max_chunk_size > 0
    # detect user question. If asked nothing, let LLM summarize by default.
    user_question = user_question if user_question else 'summarize the provided contents.'
    # read the specified texts
    chunks: List[Entry] = reader.read_and_chunk(spec, max_chunk_size=max_chunk_size, debgpt_home=debgpt_home)
    console.print(
        f'[bold]MapReduce[/bold]: Got {len(chunks)} chunks from {repr(spec)}'
    )
    if verbose:
        for i, chunk in enumerate(chunks):
            firstline = chunk.wrapfun_chunk('').split('\n')[0].rstrip(':')
            console.print(f'  [bold]Chunk {i}[/bold]: {firstline}...')
    exit(0)


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


def main(argv: List[str] = sys.argv[1:]):
    '''
    do mapreduce from command line
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', '-f', default=[], action='append', help='input file', required=True)
    parser.add_argument('--chunk-size', '-c', default=8192, type=int, help='chunk size')
    parser.add_argument('--ask', '-a', default='summarize the provided contents.', type=str, help='user question')
    parser.add_argument('--verbose', '-v', default=False, action='store_true', help='verbose mode')
    args = parser.parse_args(argv)

    # read the requested files
    if False:
        entries = []
        for file in args.file:
            entries.extend(reader.read_and_chunk(file, max_chunk_size=args.chunk_size))
        for entry in entries:
            console.print(Rule(entry.path))
            print(entry.wrapfun_chunk(entry.content))

    # do the mapreduce
    f = frontend.EchoFrontend()
    reduced = []
    for file in args.file:
        result = mapreduce_super_long_context(file, args.chunk_size, args.ask, verbose=args.verbose)


if __name__ == '__main__':  # pragma: no cover
    main()
