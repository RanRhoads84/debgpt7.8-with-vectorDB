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

# The Entry namedtuple, core data structure for reader outputs
# path: str
# content: str
# wrapfun: callable
# wrapfun_chunk: callable
Entry = namedtuple('Entry', ['path', 'content', 'wrapfun', 'wrapfun_chunk'])


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " \
            + "AppleWebKit/537.36 (KHTML, like Gecko) " \
            + "Chrome/91.0.4472.124 Safari/537.36",
    'Accept':
    'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}


def latest_file(files: List[str]) -> str:
    '''
    return the latest file among the list of files
    '''
    latest = max(files, key=os.path.getmtime)
    return latest


def latest_glob(pattern: str) -> str:
    '''
    return the latest file that matches the glob pattern
    '''
    return latest_file(glob.glob(pattern))


def is_text_file(filepath: str) -> bool:
    '''
    check if the file is a text file

    Args:
        filepath (str): the path to the file
    Returns:
        bool: True if the file is a text file, False otherwise
    '''
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            f.read()
            return True
    except UnicodeDecodeError:
        return False


def read_file_plaintext(path: str) -> str:
    '''
    read the file and return the content as a string

    Args:
        path (str): the path to the file
    Returns:
        str: the content of the file
    '''
    with open(path, 'rt', encoding='utf-8') as f:
        content = f.read()
    return content


def read_sbuild(*, return_path: bool = False) -> str:
    '''
    load the latest sbuild buildlog. we will automatically figure out the
    latest buildlog file in the parent directory.
    '''
    if not os.path.exists('./debian'):
        raise FileNotFoundError(
            './debian directory not found. Cannot detect sbuild log location. Are you in the right directory?'
        )
    latest_build_log = latest_glob('../*.build')
    result = read_file_plaintext(latest_build_log)
    if return_path:
        return result, latest_build_log
    else:
        return result


def read_file_pdf(path: str) -> str:
    '''
    read the PDF file and return the content as a string

    Args:
        path (str): the path to the PDF file
    Returns:
        str: the content of the PDF file
    '''
    try:
        from pypdf import PdfReader
    except ImportError:
        print("Please install pypdf using 'pip install pypdf'")
        exit(1)
    # Load the PDF file
    reader = PdfReader(path)
    # Get the number of pages
    num_pages = len(reader.pages)
    # Extract text from each page
    text = ""
    for page_number in range(num_pages):
        page = reader.pages[page_number]
        text += page.extract_text()
    return text


def read_file(path: str) -> str:
    '''
    read the specified file and return the content as a string

    Args:
        path (str): the path to the file
    Returns:
        str: the content of the file
    '''
    if is_text_file(path):
        return read_file_plaintext(path)
    elif path.lower().endswith('.pdf'):
        return read_file_pdf(path)
    else:
        raise TypeError(f'Unsupported file type: {path}')


def read_directory(path: str) -> List[Tuple[str, str]]:
    '''
    read a whole directory

    Args:
        path (str): the path to the directory
    Returns:
        List[Tuple[str, str]]: a list of tuples, each tuple contains the path
        and the content
    '''
    SKIPLIST = ('.git', '__pycache__')
    contents: List[Tuple[str, str]] = []
    for root, _, files in os.walk(path):
        if any(x in root.split('/') for x in SKIPLIST):
            continue
        for file in files:
            path = os.path.join(root, file)
            try:
                content = read_file(path)
            except TypeError:
                console.log(f'Skipping unsupported file `{path}`.')
                content = ''
            contents.append((path, content))
    return contents


@tenacity.retry(stop=tenacity.stop_after_attempt(3),
                wait=tenacity.wait_fixed(5))
def read_url(url: str) -> str:
    '''
    read the content from the URL. We will detect the content type.

    Args:
        url (str): the URL to read
    Returns:
        str: the content from the URL
    '''
    # Special case: file://
    if url.startswith('file://'):
        # Parse the URL to extract the path
        parsed_url = urlparse(url)
        file_path = parsed_url.path
        # Open and read the file
        return read_file(file_path)
    # Send request to the URL
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        raise ValueError(f'Failed to read {url}')
    # dispatch content type
    if url.endswith('.pdf'):
        try:
            from pypdf import PdfReader
        except ImportError:
            console.log('Please install pypdf using `pip install pypdf`')
            return ''
        pdf_bytes = io.BytesIO(response.content)
        reader = PdfReader(pdf_bytes)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
        return text
    elif response.headers['Content-Type'].startswith('text/html'):
        soup = BeautifulSoup(response.text, features='html.parser')
        text = soup.get_text().strip()
        text = re.sub('\n\n+\n', '\n\n', text)
        text = [x.rstrip() for x in text.split('\n')]
        content = '\n'.join(text)
    else:
        # assume plain text, but it may not be utf-8
        try:
            content = response.text
        except UnicodeDecodeError:
            console.log(f'Failed to read {repr(url)} as utf-8. Giving up.')
            return ['']
    return content


def read_cmd(cmd: Union[str, List]) -> str:
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    stdout = subprocess.check_output(cmd).decode()
    lines = [x.rstrip() for x in stdout.split('\n')]
    return '\n'.join(lines)


def read_bts(spec: str) -> str:
    '''
    Read the bug report from the Debian BTS

    Args:
        spec (str): the bug report number, or the package name
    Returns:
        str: the content of the bug report
    '''
    url = f'https://bugs.debian.org/{spec}'
    r = requests.get(url)
    soup = BeautifulSoup(r.text, features="html.parser")
    if not spec.startswith('src:'):
        # delete useless system messages
        _ = [
            x.clear()
            for x in soup.find_all('p', attrs={'class': 'msgreceived'})
        ]
        _ = [
            x.clear()
            for x in soup.find_all('div', attrs={'class': 'infmessage'})
        ]
    text = soup.get_text().strip()
    text = re.sub('\n\n+\n', '\n\n', text)
    text = [x.strip() for x in text.split('\n')]

    # filter out useless information from the webpage
    if spec.startswith('src:'):
        # the lines from 'Options' to the end are useless
        text = text[:text.index('Options')]
    return '\n'.join(text)


def read_stdin() -> str:
    lines = [x.rstrip() for x in sys.stdin.readlines()]
    return '\n'.join(lines)


def google_search(query: str) -> List[str]:
    '''
    read the search results from Google

    Args:
        query (str): the search query
    Returns:
        List[str]: the search results, each element is a URL
    '''
    # Format the query for URL
    query = urllib.parse.quote_plus(query)
    # Send request to Google
    url = f"https://www.google.com/search?q={query}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        raise ValueError(f'Failed to read {url}: HTTP {response.status_code}')
    # Parse the response
    soup = BeautifulSoup(response.text, 'html.parser')
    # Find search results
    search_results = soup.find_all('div', class_='g')
    results = []
    for result in search_results:
        title = result.find('h3')
        link = result.find('a', href=True)
        if title and link:
            results.append(link.get('href'))
    return results


def read_archwiki(spec: str) -> str:
    '''
    Archwiki. e.g.,
    https://wiki.archlinux.org/title/Archiving_and_compression

    Args:
        spec (str): the spec of the ArchWiki page, e.g., Archiving_and_compression
    Returns:
        str: the content of the ArchWiki page
    '''
    url = f'https://wiki.archlinux.org/title/{spec}'
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, features='html.parser')
    text = soup.get_text().split('\n')
    return '\n'.join([x.rstrip() for x in text])


def read_buildd(spec: str, ):
    url = f'https://buildd.debian.org/status/package.php?p={spec}'
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, features='html.parser')
    text = soup.get_text().split('\n')
    return '\n'.join([x.rstrip() for x in text])


def read(spec: str, *, debgpt_home: str = '.') -> List[Entry]:
    '''
    Unified reader for reading text contents from various sources
    specified by the user. We will detect the type of the resource specified,
    and dispatch to the corresponding reader.

    Args:
        spec: the path or URL to the file
        debgpt_home: the home directory of debgpt
    Returns:
        List[Entry]: a list of tuples, each tuple contains the parsed spec and
        the content, and two wrapper functions to wrap the content with.
        The first wrapper wraps unchunked content, and the second wrapper
        wraps chunked content.
    '''

    # helper functions
    def create_wrapper(template: str, spec: str) -> callable:
        '''
        create a wrapper function to wrap the content with a template.
        The template should contain one placeholder for the spec.
        '''

        def _wrapper(content: str) -> str:
            lines = [template.format(spec)]
            lines.extend(['```'] + content.split('\n') + ['```', ''])
            return '\n'.join(lines)

        return _wrapper

    def create_chunk_wrapper(template: str, spec: str) -> callable:
        '''
        create a wrapper function to wrap the content with a template.
        The template should contain three placeholders for the spec, start, and end.
        '''

        def _wrapper(content: str, start: int, end: int) -> str:
            lines = [template.format(spec, start, end)]
            lines.extend(['```'] + content.split('\n') + ['```', ''])
            return '\n'.join(lines)

        return _wrapper

    results: List[Tuple[str, str]] = []
    # standard cases: file, directory, URL
    if os.path.exists(spec) and os.path.isfile(spec):
        parsed_spec = spec
        content = read_file(spec)
        wrapfun = create_wrapper('Here is the contents of file `{}`:', spec)
        wrapfun_chunk = create_chunk_wrapper(
            'Here is the contents of file {} (lines {}-{}):', spec)
        results.append((parsed_spec, content, wrapfun, wrapfun_chunk))
    elif os.path.exists(spec) and os.path.isdir(spec):
        wrapfun = create_wrapper('Here is the contents of file `{}`:', spec)
        wrapfun_chunk = create_chunk_wrapper(
            'Here is the contents of file {} (lines {}-{}):', spec)
        parsed_spec = spec
        contents = read_directory(spec)
        contents = [(x, y, wrapfun, wrapfun_chunk) for x, y in contents]
        results.extend(contents)
    elif any(spec.startswith(x) for x in ('file://', 'http://', 'https://')):
        parsed_spec = spec
        content = read_url(spec)
        wrapfun = create_wrapper('Here is the contents of URL {}:', spec)
        wrapfun_chunk = create_chunk_wrapper(
            'Here is the contents of URL {} (lines {}-{}):', spec)
        results.append((parsed_spec, content, wrapfun, wrapfun_chunk))
    # special cases: alphabetical order
    elif spec.startswith('archwiki:'):
        parsed_spec = spec[9:]
        content = read_archwiki(parsed_spec)
        wrapfun = create_wrapper('Here is the Arch Wiki about `{}`:',
                                 parsed_spec)
        wrapfun_chunk = create_chunk_wrapper(
            'Here is the Arch Wiki about {} (lines {}-{}):', parsed_spec)
        results.append((parsed_spec, content, wrapfun, wrapfun_chunk))
    elif spec.startswith('bts:'):
        parsed_spec = spec[4:]
        content = read_bts(parsed_spec)
        wrapfun = create_wrapper(
            'Here is the Debian Bug Tracking System page of {}:', parsed_spec)
        wrapfun_chunk = create_chunk_wrapper(
            'Here is the Debian BTS status of {} (lines {}-{}):', parsed_spec)
        results.append((parsed_spec, content, wrapfun, wrapfun_chunk))
    elif spec.startswith('buildd:'):
        parsed_spec = spec[7:]
        content = read_buildd(parsed_spec)
        wrapfun = create_wrapper('Here is the buildd status of package `{}`:',
                                 parsed_spec)
        wrapfun_chunk = create_chunk_wrapper(
            'Here is the buildd status of package {} (lines {}-{}):',
            parsed_spec)
        results.append((parsed_spec, content, wrapfun, wrapfun_chunk))
    elif spec.startswith('cmd:'):
        parsed_spec = spec[4:]
        content = read_cmd(parsed_spec)
        wrapfun = create_wrapper('Here is the output of command `{}`:',
                                 parsed_spec)
        wrapfun_chunk = create_chunk_wrapper(
            'Here is the output of command {} (lines {}-{}):', parsed_spec)
        results.append((parsed_spec, content, wrapfun, wrapfun_chunk))
    elif spec.startswith('devref:'):
        # e.g., devref:1 loads section 1, devref: loads the whole devref
        parsed_spec = spec[7:]
        content = debian_policy.DebianDevref(
            os.path.join(debgpt_home, 'devref.txt'))
        if parsed_spec:
            source = f'Debian Developer Reference document [{parsed_spec}]'
            content = content[parsed_spec]
            wrapfun = create_wrapper(
                'Here is the Debian Developer Reference document, section {}:',
                parsed_spec)
            wrapfun_chunk = create_chunk_wrapper(
                'Here is the Debian Developer Reference document, section {} (lines {}-{}):',
                parsed_spec)
            results.append((source, content, wrapfun, wrapfun_chunk))
        else:
            wrapfun = create_wrapper(
                'Here is the Debian Developer Reference document {}:',
                parsed_spec)
            wrapfun_chunk = create_chunk_wrapper(
                'Here is the Debian Developer Reference document {} (lines {}-{}):',
                parsed_spec)
            for sectionidx in content.indexes:
                source = f'Debian Developer Reference document [{sectionidx}]'
                section = content[sectionidx]
                results.append((source, section, wrapfun, wrapfun_chunk))
    elif spec.startswith('man:'):
        parsed_spec = spec[4:]
        content = read_cmd(f'man {parsed_spec}')
        wrapfun = create_wrapper('Here is the manual page of {}:', parsed_spec)
        wrapfun_chunk = create_chunk_wrapper(
            'Here is the manual page of {} (lines {}-{}):', parsed_spec)
        results.append((parsed_spec, content, wrapfun, wrapfun_chunk))
    elif spec.startswith('policy:'):
        # e.g., policy:1 loads section 1, policy: loads the whole policy
        parsed_spec = spec[7:]
        content = debian_policy.DebianPolicy(
            os.path.join(debgpt_home, 'policy.txt'))
        if parsed_spec:
            source = f'Debian Policy section [{parsed_spec}]'
            section = content[parsed_spec]
            wrapfun = create_wrapper(
                'Here is the Debian Policy document, section {}:', parsed_spec)
            wrapfun_chunk = create_chunk_wrapper(
                'Here is the Debian Policy document, section {} (lines {}-{}):',
                parsed_spec)
            results.append((source, section, wrapfun, wrapfun_chunk))
        else:
            wrapfun = create_wrapper('Here is the Debian Policy document {}:',
                                     parsed_spec)
            wrapfun_chunk = create_chunk_wrapper(
                'Here is the Debian Policy document {} (lines {}-{}):',
                parsed_spec)
            for sectionidx in content.indexes:
                source = f'Debian Policy section [{sectionidx}]'
                section = content[sectionidx]
                results.append((source, section, wrapfun, wrapfun_chunk))
    elif spec.startswith('sbuild:'):
        content, logpath = read_sbuild(return_path=True)
        wrapfun = create_wrapper('Here is the sbuild buildlog {}:', logpath)
        wrapfun_chunk = create_chunk_wrapper(
            'Here is the sbuild buildlog {} (lines {}-{}):', logpath)
        results.append((logpath, content, wrapfun, wrapfun_chunk))
    elif spec.startswith('tldr:'):
        parsed_spec = spec[5:]
        content = read_cmd(f'tldr {parsed_spec}')
        wrapfun = create_wrapper('Here is the tldr of {}:', parsed_spec)
        wrapfun_chunk = create_chunk_wrapper(
            'Here is the tldr of {} (lines {}-{}):', parsed_spec)
        results.append((parsed_spec, content, wrapfun, wrapfun_chunk))
    # special cases: stdin
    elif spec in ('stdin', '-'):
        parsed_spec = 'stdin'
        content = read_stdin()
        wrapfun = create_wrapper('Carefully read the following contents {}:',
                                 parsed_spec)
        wrapfun_chunk = create_chunk_wrapper(
            'Carefully read the following contents {} (lines {}-{}):',
            parsed_spec)
        results.append((parsed_spec, content, wrapfun, wrapfun_chunk))
    else:
        raise FileNotFoundError(
            f'File or resource {repr(spec)} not recognized')
    # convert the results to Entry (named tuple)
    results = [Entry(*x) for x in results]
    return results


def chunk_lines(
    lines: List[str],
    max_chunk_size: int,
    start: int = -1,
    end: int = -1,
) -> Dict[Tuple[int, int], List[str]]:
    '''
    Chunk the lines into pieces with the specified size.

    Args:
        lines (List[str]): the lines to chunk, always the full list of lines
        max_chunk_size (int): the maximum chunk size
        start (int): the start index of the lines
        end (int): the end index of the lines
    Returns:
        Dict[Tuple[int, int], List[str]]: a dictionary, each key is a tuple
        containing the start and end index of the chunked lines, and the value
        is the chunked lines.
    '''
    #print('DEBUG:', len(lines), len('\n'.join(lines[start:end]).encode('utf8')),
    #    'c', max_chunk_size, 'start', start, 'end', end)
    # deal with the unspecified param case. This allows chunk_lines(lines, 1000)
    # to work properly without specifying the start and end in another wrapper.
    if end < 0 and start < 0:
        return chunk_lines(lines, max_chunk_size, 0, len(lines))
    # real work
    chunk_size_in_bytes = len('\n'.join(lines[start:end]).encode('utf8'))
    if chunk_size_in_bytes <= max_chunk_size:
        return {(start, end): lines[start:end]}
    elif end - start == 1:
        return {(start, end): lines[start:end]}
    else:
        # split the lines into chunks
        middle = (start + end) // 2
        left = chunk_lines(lines, max_chunk_size, start, middle)
        right = chunk_lines(lines, max_chunk_size, middle, end)
        return {**left, **right}


def chunk_lines_nonrecursive(
        lines: List[str],
        max_chunk_size: int,
        start: int = -1,
        end: int = -1,
        ) -> Dict[Tuple[int, int], List[str]]:
    '''
    Chunk the lines into pieces with the specified size.

    Args:
        lines (List[str]): the lines to chunk, always the full list of lines
        max_chunk_size (int): the maximum chunk size
        start (int): the start index of the lines
        end (int): the end index of the lines
    Returns:
        Dict[Tuple[int, int], List[str]]: a dictionary, each key is a tuple
        containing the start and end index of the chunked lines, and the value
        is the chunked lines.
    '''
    if end < 0 and start < 0:
        return chunk_lines(lines, max_chunk_size, 0, len(lines))
    # real work
    result: Dict[Tuple[int, int], List[str]] = {}
    stack = [(start, end)]
    while stack:
        current_start, current_end = stack.pop()
        chunk_size_in_bytes = len('\n'.join(lines[current_start:current_end]).encode('utf8'))

        if chunk_size_in_bytes <= max_chunk_size:
            # if the chunk is within the size limit, we add it to the result
            result[(current_start, current_end)] = lines[current_start:current_end]
        elif current_end - current_start == 1:
            # if the chunk is too large but cannot be split, we add it to the result
            result[(current_start, current_end)] = lines[current_start:current_end]
        else:
            middle = (current_start + current_end) // 2
            stack.append((current_start, middle))
            stack.append((middle, current_end))
    return result



def chunk_entry(entry: Entry, max_chunk_size: int) -> List[Entry]:
    '''
    Chunk the content of the entry into pieces with the specified size.

    Args:
        entry (Entry): the entry to chunk
        max_chunk_size (int): the maximum chunk size
    Returns:
        List[Entry]: a list of entries, each entry contains a chunk of the content
    '''
    if max_chunk_size < 0:
        return [entry]
    results = []
    chunkdict = chunk_lines(entry.content.split('\n'), max_chunk_size)
    for (start, end), lines in chunkdict.items():
        content = '\n'.join(lines)
        wrapfun = ft.partial(entry.wrapfun_chunk, start=start, end=end)
        results.append(Entry(entry.path, content, wrapfun, wrapfun))
    return results


def read_and_chunk(spec: str,
                   *,
                   max_chunk_size: int = -1,
                   debgpt_home: str = '.') -> List[Entry]:
    '''
    Read contents from the specified resource and chunk the content into pieces.

    Args:
        spec (str): the path or URL to the file
        max_chunk_size (int): the maximum chunk size of the content. If the
            number is less than 0, we shall not chunk the contents.
        debgpt_home (str): the home directory of debgpt
    Returns:
        List[Entry]: a list of entries, each entry contains a chunk of the content
    '''
    entries = read(spec, debgpt_home=debgpt_home)
    if max_chunk_size > 0:
        entries = ft.reduce(list.__add__,
                            [chunk_entry(x, max_chunk_size) for x in entries])
    return entries


def read_and_wrap(spec: str,
                  *,
                  max_chunk_size: int = -1,
                  debgpt_home: str = '.') -> str:
    '''
    Read contents from the specified resource and wrap the content to make it
    suitable for prompting LLM.

    Args:
        spec (str): the path or URL to the file
        max_chunk_size (int): the maximum chunk size of the content. If the
            number is less than 0, we shall not chunk the contents.
        debgpt_home (str): the home directory of debgpt
    Returns:
        str: the wrapped content
    '''
    entries = read(spec, debgpt_home=debgpt_home)
    if max_chunk_size > 0:
        entries = ft.reduce(list.__add__,
                            [chunk_entry(x, max_chunk_size) for x in entries])
    wrapped: str = ''
    for entry in entries:
        wrapped += entry.wrapfun(entry.content)
    return wrapped


def main(argv: List[str] = sys.argv[1:]):
    '''
    read something and print to screen
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('--file',
                        '-f',
                        type=str,
                        default=[],
                        action='extend',
                        required=True,
                        nargs='+',
                        help='file,path,spec,etc to read')
    parser.add_argument('--wrap',
                        '-w',
                        action='store_true',
                        help='wrap the content with a template')
    parser.add_argument('--chunk',
                        '-c',
                        type=int,
                        default=-1,
                        help='chunk the content into pieces')
    parser.add_argument('--debgpt_home',
                        type=str,
                        default='.',
                        help='the home directory of debgpt')
    args = parser.parse_args(argv)

    tally = 0
    if args.wrap:
        for file in args.file:
            string = read_and_wrap(file,
                                   max_chunk_size=args.chunk,
                                   debgpt_home=args.debgpt_home)
            console.log('Specifier:', file)
            console.print(string)
            tally += 1
        console.print('Total number of texts:', tally)
    else:
        for file in args.file:
            entries = read(file, debgpt_home=args.debgpt_home)
            if args.chunk > 0:
                entries = ft.reduce(
                    list.__add__,
                    [chunk_entry(x, args.chunk) for x in entries])
            console.log('Specifier:', file)
            console.print(entries)
            tally += len(entries)
        console.print('Total number of entries:', tally)


if __name__ == '__main__':  # pragma: no cover
    main()
