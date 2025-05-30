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
from typing import List, Optional
import argparse
import functools as ft
import sys
import concurrent.futures
import textwrap
from rich.progress import track
from rich.rule import Rule
from . import reader
from .reader import Entry
from .defaults import console
from . import frontend

_VERBOSE_WRAP_LENGTH = 512


def shorten(s: str, maxlen: int = 100) -> str:
    '''
    Shorten the string to a maximum length. Different from default textwrap
    behavior, we will shorten from the other side of the string.
    '''
    return textwrap.shorten(s, width=maxlen)


def pad_chunk_before_map(chunk: Entry, question: str) -> str:
    '''
    process a chunk of text with a question
    '''
    template = 'Extract any information that is relevant to question '
    template += f'{repr(question)} from the following file part. '
    template += 'Note, if there is no relevant information, just briefly say nothing.'
    template += '\n\n\n'
    template += chunk.wrapfun_chunk(chunk.content)
    return template


def group_chunks_by_length(chunks: List[Entry],
                           max_length: int) -> List[List[Entry]]:
    '''
    group as many as possible chunks together while maximum length is not
    exceeded. Note, this function differs from group_strings_by_length in that
    it groups chunks instead of strings. And it does not mandate the merge
    of at least two chunks in each group.

    Args:
        chunks: a list of chunks
        max_length: the maximum length of each group, in bytes
    Returns:
        a list of groups of chunks, each group is a list of chunks
    '''
    assert max_length > 0
    grouped_chunks = []
    current_group = []
    current_length = 0

    for chunk in chunks:
        chunk_length = len(chunk.content.encode("utf-8"))
        _will_overlength = current_length + chunk_length > max_length

        # check if adding the current chunk exceeds the max_length
        if _will_overlength:
            # if it does, save the current group and start a new one
            grouped_chunks.append(current_group)
            current_group = [chunk]
            current_length = chunk_length
        else:
            # otherwise, add the chunk to the current group
            current_group.append(chunk)
            current_length += chunk_length

    # don't forget to add the last group if it has any chunks
    if current_group:
        grouped_chunks.append(current_group)

    return grouped_chunks


def pad_chunks_before_map(chunks: List[Entry], question: str) -> str:
    '''
    process a list of chunks of text with a question
    '''
    template = 'Extract any information that is relevant to question '
    template += f'{repr(question)} from the following file parts. '
    template += 'Note, if there is no relevant information, just briefly say nothing.'
    template += '\n\n\n'
    for chunk in chunks:
        template += chunk.wrapfun_chunk(chunk.content)
        template += '\n\n'  # add some separation between chunks
    return template


def map_chunk(chunk: Entry,
              question: str,
              frtnd: frontend.AbstractFrontend,
              verbose: bool = False) -> str:
    '''
    process a chunk of text with a question
    '''
    padded_input = pad_chunk_before_map(chunk, question)
    if verbose:
        console.print(
            f'[white on blue]map:({len(padded_input)})->[/white on blue]',
            shorten(padded_input, _VERBOSE_WRAP_LENGTH))
    answer = frtnd.oneshot(padded_input)
    if verbose:
        console.print('f[white on red]map:<-({len(answer)})[/white on red]',
                      shorten(answer, _VERBOSE_WRAP_LENGTH))
    return answer


def map_chunks(chunks: List[Entry],
               question: str,
               frtnd: frontend.AbstractFrontend,
               verbose: bool = False) -> str:
    '''
    process a list of chunks of text with a question
    
    This function is used for the compact map mode.
    '''
    padded_input = pad_chunks_before_map(chunks, question)
    if verbose:
        console.print(
            f'[white on blue]map:({len(padded_input)})->[/white on blue]',
            shorten(padded_input, _VERBOSE_WRAP_LENGTH))
    answer = frtnd.oneshot(padded_input)
    if verbose:
        console.print(f'[white on red]map:<-({len(answer)})[/white on red]',
                      shorten(answer, _VERBOSE_WRAP_LENGTH))
    return answer


def map_serial(chunks: List[Entry],
               user_question: str,
               frtnd: frontend.AbstractFrontend,
               verbose: bool = False) -> List[str]:
    '''
    This is the first pass of mapreduce. We map each chunk to LLM and get the
    result. This is a serial implementation.
    '''
    results = []
    for chunk in track(chunks, total=len(chunks), description='MapReduce:'):
        results.append(map_chunk(chunk, user_question, frtnd, verbose=verbose))
    return results


def map_serial_compact(chunks: List[Entry],
                       user_question: str,
                       frtnd: frontend.AbstractFrontend,
                       verbose: bool = False,
                       max_chunk_size: int = -1) -> List[str]:
    '''
    This is the first pass of mapreduce. We map each chunk to LLM and get the
    result. This is a serial implementation.
    '''
    results = []
    grouped_chunks = group_chunks_by_length(chunks, max_chunk_size)
    console.print(
        f'[bold]MapReduce[/bold]: mapping {len(chunks)} chunks ({len(grouped_chunks)} groups)'
    )
    for pack in track(grouped_chunks,
                      total=len(grouped_chunks),
                      description='MapReduce:'):
        results.append(map_chunks(pack, user_question, frtnd, verbose=verbose))
    return results


def map_parallel(chunks: List[Entry],
                 user_question: str,
                 frtnd: frontend.AbstractFrontend,
                 verbose: bool = False,
                 parallelism: int = 2) -> List[str]:
    '''
    This is the first pass of mapreduce. We map each chunk to LLM and get the
    result. This is a parallel implementation.
    '''
    worker = ft.partial(map_chunk,
                        question=user_question,
                        frtnd=frtnd,
                        verbose=verbose)
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallelism) as ex:
        results = list(
            track(ex.map(worker, chunks),
                  total=len(chunks),
                  description=f'MapReduce[{parallelism}]:',
                  transient=True))
    return results


def map_parallel_compact(chunks: List[Entry],
                         user_question: str,
                         frtnd: frontend.AbstractFrontend,
                         verbose: bool = False,
                         parallelism: int = 2,
                         max_chunk_size: int = -1) -> List[str]:
    '''
    This is the first pass of mapreduce. We map each chunk to LLM and get the
    result. This is a parallel implementation, and we use compact mode.
    '''
    worker = ft.partial(map_chunks,
                        question=user_question,
                        frtnd=frtnd,
                        verbose=verbose)
    grouped_chunks = group_chunks_by_length(chunks, max_chunk_size)
    console.print(
        f'[bold]MapReduce[/bold]: mapping {len(chunks)} chunks ({len(grouped_chunks)} groups)'
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallelism) as ex:
        results = list(
            track(ex.map(worker, grouped_chunks),
                  total=len(grouped_chunks),
                  description=f'MapReduce[{parallelism}]:',
                  transient=True))
    return results


def pad_two_results_for_reduce(a: str, b: str, question: str) -> str:
    template = 'Extract any information that is relevant to question '
    template += f'{repr(question)} from the following contents and aggregate them. '
    template += 'Note, if there is no relevant information, just briefly say nothing.'
    template += '\n\n\n'
    template += '```\n' + a + '\n```\n\n'
    template += '```\n' + b + '\n```\n\n'
    return template


def reduce_two_chunks(a: str,
                      b: str,
                      question: str,
                      frtnd: frontend.AbstractFrontend,
                      verbose: bool = False) -> str:
    padded_input = pad_two_results_for_reduce(a, b, question)
    if verbose:
        console.print(
            f'[white on blue]reduce:({len(padded_input)})->[/white on blue]',
            shorten(padded_input, _VERBOSE_WRAP_LENGTH))
    answer = frtnd.oneshot(padded_input)
    if verbose:
        console.print(
            f'[white on red]reduce:<-({len(padded_input)})[/white on red]',
            shorten(answer, _VERBOSE_WRAP_LENGTH))
    return answer


def pad_many_results_for_reduce(results: List[str], question: str) -> str:
    template = 'Extract any information that is relevant to question '
    template += f'{repr(question)} from the following contents and aggregate them. '
    template += 'Note, if there is no relevant information, just briefly say nothing.'
    template += '\n\n\n'
    for r in results:
        template += '```\n' + r + '\n```\n\n'
    return template


def reduce_many_chunks(results: List[str],
                       question: str,
                       frtnd: frontend.AbstractFrontend,
                       verbose: bool = False) -> str:
    padded_input = pad_many_results_for_reduce(results, question)
    if verbose:
        console.print(
            f'[white on blue]reduce:({len(padded_input)})->[/white on blue]',
            shorten(padded_input, _VERBOSE_WRAP_LENGTH))
    answer = frtnd.oneshot(padded_input)
    if verbose:
        console.print(
            f'[white on red]reduce:<-({len(padded_input)})[/white on red]',
            shorten(answer, _VERBOSE_WRAP_LENGTH))
    return answer


def group_strings_by_length(strings: List[str],
                            max_length: int) -> List[List[str]]:
    '''
    group as many as possible strings together while maximum length is not exceeded.
    To ensure convergence to one single string in the end, we will force reduce
    at least two strings in each group.

    Args:
        strings: a list of strings
        max_length: the maximum length of each group, in bytes
    Returns:
        a list of groups of strings, each group is a list of strings
    '''
    assert max_length > 0
    grouped_strings = []
    current_group = []
    current_length = 0

    for string in strings:
        string_length = len(string.encode("utf-8"))
        _will_overlength = current_length + string_length > max_length
        _will_overrule = len(current_group) >= 2

        # Check if adding the current string exceeds the max_length, and
        # if the current group has less than two strings
        if _will_overlength and _will_overrule:
            # If it does, save the current group and start a new one
            grouped_strings.append(current_group)
            current_group = [string]
            current_length = string_length
        else:
            # Otherwise, add the string to the current group
            current_group.append(string)
            current_length += string_length

    # Don't forget to add the last group if it has any strings
    if current_group:
        grouped_strings.append(current_group)

    return grouped_strings


def reduce_serial(results: List[str],
                  question: str,
                  frtnd: frontend.AbstractFrontend,
                  verbose: bool = False) -> str:
    '''
    recursive reduction of multiple results, until only one result is left.
    We do this binary reduction in serial mode.
    '''
    while len(results) > 1:
        console.print(
            f'[bold]MapReduce[/bold]: reducing {len(results)} intermediate results'
        )
        new_results = []
        for (a, b) in track(zip(results[::2], results[1::2]),
                            total=len(results) // 2,
                            description='Mapreduce:'):
            new_results.append(
                reduce_two_chunks(a, b, question, frtnd, verbose))
        if len(results) % 2 == 1:
            new_results.append(results[-1])
        results = new_results
    return results[0]


def reduce_serial_compact(results: List[str],
                          question: str,
                          frtnd: frontend.AbstractFrontend,
                          verbose: bool = False,
                          max_chunk_size: int = -1) -> str:
    '''
    recursive reduction of multiple results, until only one result is left.
    We do this compact (non-binary) reduction in serial mode.
    '''
    while len(results) > 1:
        console.print(
            f'[bold]MapReduce[/bold]: reducing {len(results)} intermediate results'
        )
        new_results = []
        groups = group_strings_by_length(results, max_chunk_size)
        for pack in track(groups, total=len(groups), description='Mapreduce:'):
            new_results.append(
                reduce_many_chunks(pack, question, frtnd, verbose))
        results = new_results
    return results[0]


def reduce_parallel(results: List[str],
                    question: str,
                    frtnd: frontend.AbstractFrontend,
                    verbose: bool = False,
                    parallelism: int = 2) -> str:
    '''
    recursive reduction of multiple results, until only one result is left
    '''
    worker = ft.partial(reduce_two_chunks,
                        question=question,
                        frtnd=frtnd,
                        verbose=verbose)
    while len(results) > 1:
        pairs = list(zip(results[::2], results[1::2]))
        console.print(
            f'[bold]MapReduce[/bold]: reducing {len(results)} intermediate results ({len(pairs)} pairs)'
        )
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=parallelism) as ex:
            new_results = list(
                track(ex.map(lambda x: worker(*x), pairs),
                      total=len(pairs),
                      description=f'Mapreduce[{parallelism}]:',
                      transient=True))
        if len(results) % 2 == 1:
            new_results.append(results[-1])
        results = new_results
    return results[0]


def reduce_parallel_compact(results: List[str],
                            question: str,
                            frtnd: frontend.AbstractFrontend,
                            verbose: bool = False,
                            parallelism: int = 2,
                            max_chunk_size: int = -1) -> str:
    '''
    recursive reduction of multiple results, until only one result is left
    '''
    worker = ft.partial(reduce_many_chunks,
                        question=question,
                        frtnd=frtnd,
                        verbose=verbose)
    while len(results) > 1:
        groups = group_strings_by_length(results, max_chunk_size)
        console.print(
            f'[bold]MapReduce[/bold]: reducing {len(results)} intermediate results ({len(groups)} groups)'
        )
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=parallelism) as ex:
            new_results = list(
                track(ex.map(worker, groups),
                      total=len(groups),
                      description=f'Mapreduce[{parallelism}]:',
                      transient=True))
        results = new_results
    return results[0]


def mapreduce_super_long_context(
    spec: str,
    max_chunk_size: int,
    frtnd: frontend.AbstractFrontend,
    user_question: Optional[str] = None,
    verbose: bool = False,
    compact_map_mode: bool = True,
    compact_reduce_mode: bool = True,
    parallelism: int = 1,
) -> str:
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

    Note, with parallel processing, we may easily exceed the Token Per Minute
    (TPM) limit set by the service provider. We will automatically retry until
    success.

    Args:
        spec: the input specification
        max_chunk_size: the maximum chunk size in bytes
        frtnd: the frontend object
        user_question: the user question
        verbose: verbose mode
        compact_reduce_mode: use compact reduce mode, instead of binary reduction
        parallelism: the parallelism
    Returns:
        the aggregated result from LLM after mapreduce, as a string
    '''
    assert max_chunk_size > 0

    # detect user question. If asked nothing, let LLM summarize by default.
    user_question = user_question if user_question else 'summarize the provided contents.'

    # read the specified texts
    chunks: List[Entry] = reader.read_and_chunk(spec,
                                                max_chunk_size=max_chunk_size,
                                                user_question=user_question)
    console.print(
        f'[bold]MapReduce[/bold]: Initialized with {len(chunks)} chunks from {repr(spec)}')
    if verbose:
        for i, chunk in enumerate(chunks):
            firstline = chunk.wrapfun_chunk('').split('\n')[0].rstrip(':')
            console.print(f'  [bold]Chunk {i}[/bold]: {firstline}...')

    # skip mapreduce if there is only one chunk
    if len(chunks) == 1:
        return chunks[0].wrapfun_chunk(chunks[0].content)
    assert len(chunks) > 1  # at least two chunks

    # map phase
    if parallelism > 1 and compact_map_mode:
        intermediate_results = map_parallel_compact(
            chunks,
            user_question,
            frtnd,
            verbose=verbose,
            parallelism=parallelism,
            max_chunk_size=max_chunk_size)
    elif parallelism > 1:
        intermediate_results = map_parallel(chunks,
                                            user_question,
                                            frtnd,
                                            verbose=verbose,
                                            parallelism=parallelism)
    elif compact_map_mode:
        intermediate_results = map_serial_compact(
            chunks,
            user_question,
            frtnd,
            verbose=verbose,
            max_chunk_size=max_chunk_size)
    else:
        intermediate_results = map_serial(chunks,
                                          user_question,
                                          frtnd,
                                          verbose=verbose)

    # reduce phase
    if parallelism > 1 and compact_reduce_mode:
        aggregated_result = reduce_parallel_compact(
            intermediate_results,
            user_question,
            frtnd,
            verbose=verbose,
            parallelism=parallelism,
            max_chunk_size=max_chunk_size)
    elif parallelism > 1:
        aggregated_result = reduce_parallel(intermediate_results,
                                            user_question,
                                            frtnd,
                                            verbose=verbose,
                                            parallelism=parallelism)
    elif compact_reduce_mode:
        aggregated_result = reduce_serial_compact(
            intermediate_results,
            user_question,
            frtnd,
            verbose=verbose,
            max_chunk_size=max_chunk_size)
    else:
        aggregated_result = reduce_serial(intermediate_results,
                                          user_question,
                                          frtnd,
                                          verbose=verbose)

    # pad the final result and return
    return aggregated_result + '\n\n'


def main(argv: List[str] = sys.argv[1:]):  # pragma: no cover
    '''
    do mapreduce from command line
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('--file',
                        '-f',
                        default=[],
                        action='append',
                        help='input file',
                        required=True)
    parser.add_argument('--chunk-size',
                        '-c',
                        default=8192,
                        type=int,
                        help='chunk size')
    parser.add_argument('--ask',
                        '-a',
                        default='summarize the provided contents.',
                        type=str,
                        help='user question')
    parser.add_argument('--verbose',
                        '-v',
                        default=False,
                        action='store_true',
                        help='verbose mode')
    parser.add_argument('--parallelism',
                        '-j',
                        default=1,
                        type=int,
                        help='parallelism')
    args = parser.parse_args(argv)

    # read the requested files
    if False:
        entries = []
        for file in args.file:
            entries.extend(
                reader.read_and_chunk(file, max_chunk_size=args.chunk_size))
        for entry in entries:
            console.print(Rule(entry.path))
            print(entry.wrapfun_chunk(entry.content))

    # do the mapreduce
    f = frontend.EchoFrontend()
    f.lossy_mode = True
    reduced = []
    for file in args.file:
        result = mapreduce_super_long_context(file,
                                              args.chunk_size,
                                              f,
                                              args.ask,
                                              verbose=args.verbose,
                                              compact_reduce_mode=True,
                                              parallelism=args.parallelism)
        reduced.append(result)
    console.print(reduced)


if __name__ == '__main__':  # pragma: no cover
    main()
