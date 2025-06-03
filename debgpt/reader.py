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
from typing import List, Union, Dict, Tuple, Optional
import re
import requests
from bs4 import BeautifulSoup
import argparse
import io
import os
import subprocess
import functools as ft
import itertools as it
import sys
import glob
import shlex
import tenacity
from rich.rule import Rule
from rich.progress import track
import concurrent.futures
from urllib.parse import urlparse
import urllib.parse
from . import policy as debian_policy
from .defaults import console
from .defaults import CACHE
from collections import namedtuple
from .cache import Cache
from .nm_templates import NM_TEMPLATES

try:
    import pycurl
    __use_pycurl = True
except ImportError:
    __use_pycurl = False

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


def help():
    '''
    Show the list of supported reader specs.

    Use any of the following commands to show the help message:
        debgpt -f :
        debgpt -f ?
        debgpt -x :
        debgpt -x ?
    '''
    console.print(Rule('Supported reader specs (specifiied by -f or -x)'))
    console.print('The -f will read all information into the context, while -x will chunk the information into smaller pieces and perform MapReduce.')
    console.print('')
    console.print('===[General Reader Specs]===', style='bold')
    console.print(' • <file_path>       read plain text file or PDF file, e.g., "README.md", "manual.pdf"')
    console.print(' • <directory>       read all files under a directory')
    console.print(' • http://<...>      read plain text from http URL')
    console.print(' • https://<...>     read plain text from https URL')
    console.print(' • file://<...>      read plain text from file URL')
    console.print('')
    console.print('===[Special Reader Specs]===', style='bold')
    console.print(' • cmd:<cmd_line>    read the output of a command line, e.g., "cmd:\'git diff --staged\'" and ask the LLM to briefly summarize the changes.')
    console.print(' • google:<query>    load the topmost Google search results')
    console.print(' • man:<man>         read the manual page of a command, e.g., "man:debhelper-compat-upgrade-checklist" and ask the LLM to explain the change between compat 13 and compat 14.')
    console.print(' • tldr:<cmd>        read the tldr of a command, e.g., "tldr:curl" and ask the LLM to give a command line to download a URL into a destination in silent mode.')
    console.print(' • stdin             read from stdin')
    console.print(' • -                 read from stdin')
    console.print('')
    console.print('===[Linux Distribution Reader Specs]===', style='bold')
    console.print(' • archwiki:<name>   read ArchWiki page')
    console.print(' • bts:<bugnumber>   read Debian BTS bug report, e.g., "bts:src:pytorch", "bts:1056388".')
    console.print(' • buildd:<pkg>      read Debian buildd status, e.g., "buildd:glibc".')
    console.print(' • ldo:<list>        read the mailing list threads from lists.debian.org, e.g., "debian-ai/2024/11". Range syntax is suported, e.g., "debian-ai/2024,2025/01-12", "debian-ai/2025/04,05", "debian-ai/2025/:" (this means 01-12), "debian-ai/2021-2025/:". It is recommended to use this reader in MapReduce mode (-x) instead of plain read mode (-f).')
    console.print(' • nm:<template>     load the nm-templates question')
    console.print('')
    console.print(' • policy:           load whole Debian Policy, chunked into sections for MapReduce mode (-x). May ask, for instance, the LLM to explain the latest changes in the policy.')
    console.print(' • policy:all        load whole Debian Policy, full text in one single chunk. More suitable for the plain read mode (-f).')
    console.print(' • policy:<section>  load a specific section of Debian Policy, e.g., "policy:7.2" and ask the LLM to explain the difference between Depends and Pre-Depends.')
    console.print('')
    console.print(' • devref:           load whole Debian Devref, chunked into sections for MapReduce mode (-x).')
    console.print(' • devref:all        load whole Debian Devref, full text in one single chunk.')
    console.print(' • devref:<section>  load a specific section of Debian Devref, e.g., "devref:5.5".')
    console.print('')
    console.print(' • sbuild:           load the latest sbuild buildlog, and filter out the unimportant lines')
    console.print(' • sbuild:<path>     load the latest sbuild log from path, and filter out the unimportant lines')
    console.print('')
    console.print('===[Note]===', style='bold')
    console.print('The reader specs can be repeated multiple times, e.g.,')
    console.print('')
    console.print(' • debgpt -Hf pytorch/debian/control -f policy:7.4 -A "Explain what Conflicts+Replaces means in pytorch/debian/control based on the provided policy document"')
    console.print(' • debgpt -Hf pytorch/debian/rules -f policy:4.9.1 -A "Implement the support for the \'nocheck\' tag based on the example provided in the policy document."')
    console.print(Rule('Please specify one or multiple of the above specs.'))


def enable_cache(func: callable) -> callable:
    '''
    Enable caching for the function based on the first arg.

    Args:
        func (callable): the function to enable caching
    Returns:
        callable: the wrapper function
    '''

    def wrapper(*args, **kwargs):
        cache = Cache(CACHE)
        if args[0] in cache:
            return cache[args[0]]
        result = func(*args, **kwargs)
        cache[args[0]] = result
        return result

    return wrapper


def entry2dict(
        entry: Entry,
        max_chunk_size: int = 8192) -> Dict[Tuple[str, int, int], List[str]]:
    '''
    convert an Entry object to a chunked dictionary
    '''
    try:
        d = chunk_lines(entry.content.split('\n'), max_chunk_size)
    except RecursionError:
        d = chunk_lines_nonrecursive(entry.content.split('\n'), max_chunk_size)
    result = {}
    for (start, end), lines in d.items():
        result[(entry.path, start, end)] = lines
    return result


def entries2dict(
        entries: List[Entry],
        max_chunk_size: int = 8192) -> Dict[Tuple[str, int, int], List[str]]:
    '''
    convert a list of Entry objects to a chunked dictionary

    Args:
        entries: a list of Entry objects
        max_chunk_size: the maximum chunk size in bytes
    Returns:
        a dictionary of chunked contents
    '''
    return ft.reduce(dict.__or__,
                     [entry2dict(e, max_chunk_size) for e in entries])


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


def extract_build_changes(text):
  """
  ! written by Gemini 1.5 Pro
  Extracts the part of a string that starts with a Build header and
  ends with a Changes header, using regular expressions, excluding the markers.

  Args:
    text: A string containing the text to extract from.

  Returns:
    A string representing the extracted part, or None if no match is found.

  """
  start_pattern = r"\+[-]+\+\n\| Build +\|\n\+[-]+\+"
  end_pattern = r"\+[-]+\+\n\| Changes +\|\n\+[-]+\+"

  try:
    # Find the start and end positions using regex
    start_match = re.search(start_pattern, text)
    end_match = re.search(end_pattern, text)

    if start_match:
      if end_match:
        return text[start_match.end() : end_match.start()]
      else:
        return text[start_match.end() :]  # Match to the end if end_match is None
    else:
      return None
  except AttributeError:
    return None


def read_sbuild(path: Optional[str] = None, *, return_path: bool = False) -> str:
    '''
    load the latest sbuild buildlog. If no path is provided, we will
    automatically figure out the latest buildlog file in the parent directory.
    Additionally, we will filter the unimportant lines from the buildlog.
    '''
    if path is None:
        if not os.path.exists('./debian'):
            raise FileNotFoundError(
                './debian directory not found. Cannot detect sbuild log location. Are you in the right directory?'
            )
        latest_build_log = latest_glob('../*.build')
        result = read_file_plaintext(latest_build_log)
    else:
        latest_build_log = path
        result = read_file_plaintext(path)
    # filter out the unimportant lines
    result = extract_build_changes(result)
    return (result, latest_build_log) if return_path else result


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
            cursor = os.path.join(root, file)
            try:
                content = read_file(cursor)
            except TypeError:
                console.log(f'Skipping unsupported file `{path}`.')
                content = ''
            contents.append((cursor, content))
    return contents


@enable_cache
def read_url(url: str) -> str:
    '''
    Dispatcher based on the availability of the pycurl library.
    '''
    if __use_pycurl:
        return read_url__pycurl(url)
    else:
        return read_url__requests(url)


@tenacity.retry(stop=tenacity.stop_after_attempt(3),
                wait=tenacity.wait_fixed(5))
def read_url__pycurl(url: str) -> str:
    '''
    read the content from the URL using pycurl

    Args:
        url (str): the URL to read
    Returns:
        str: the content from the URL
    '''
    headers = {}

    # copied from pycurl: http://pycurl.io/docs/latest/quickstart.html
    def header_function(header_line):
        # HTTP standard specifies that headers are encoded in iso-8859-1.
        # On Python 2, decoding step can be skipped.
        # On Python 3, decoding step is required.
        header_line = header_line.decode('iso-8859-1')

        # Header lines include the first status line (HTTP/1.x ...).
        # We are going to ignore all lines that don't have a colon in them.
        # This will botch headers that are split on multiple lines...
        if ':' not in header_line:
            return

        # Break the header line into header name and value.
        name, value = header_line.split(':', 1)

        # Remove whitespace that may be present.
        # Header lines include the trailing newline, and there may be whitespace
        # around the colon.
        name = name.strip()
        value = value.strip()

        # Header names are case insensitive.
        # Lowercase name here.
        name = name.lower()

        # Now we can actually record the header name and value.
        # Note: this only works when headers are not duplicated, see below.
        headers[name] = value

    def _is_content_type_html(headers: dict) -> bool:
        if 'content-type' not in headers:
            return False
        content_type = headers['content-type']
        return content_type.startswith('text/html')

    buffer = io.BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(pycurl.FOLLOWLOCATION, 1)
    c.setopt(c.WRITEFUNCTION, buffer.write)
    c.setopt(c.HEADERFUNCTION, header_function)
    c.perform()
    status = c.getinfo(c.RESPONSE_CODE)
    c.close()
    if url.startswith('file://'):
        pass
    else:
        if status in (403, 404):
            # silently giveup and proceed
            return ''
        elif status != 200:
            console.log(f'Failed to read {url}: HTTP {status}')
            return ''
    try:
        content = buffer.getvalue().decode('utf-8')
        #console.log(f'Content-Type: {headers}')
        # if HTML, parse it
        if _is_content_type_html(headers):
            soup = BeautifulSoup(content, features='html.parser')
            text = soup.get_text().strip()
            text = re.sub('\n\n+\n', '\n\n', text)
            text = [x.rstrip() for x in text.split('\n')]
            content = '\n'.join(text)
        return content
    except UnicodeDecodeError:
        if url.endswith('.pdf'):
            try:
                from pypdf import PdfReader
            except ImportError:
                console.log('Please install pypdf using `pip install pypdf`')
                return ''
            pdf_bytes = io.BytesIO(buffer.getvalue())
            reader = PdfReader(pdf_bytes)
            text = ''
            for page in reader.pages:
                text += page.extract_text()
            return text
        else:
            console.print(f'Failed to read {repr(url)} as utf-8. Giving up.')
            return ''


@tenacity.retry(stop=tenacity.stop_after_attempt(3),
                wait=tenacity.wait_fixed(5))
def read_url__requests(url: str) -> str:
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


@enable_cache
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


def fetch_ldo_threads(spec: str, index: str = 'threads.html') -> List[str]:
    '''
    read the mail threads (including the links) from the lists.debian.org.
    Return a list of URLs to the emails.

    Example URL:
    https://lists.debian.org/debian-ai/2024/11/threads.html
                             ^^^^^^^^^^^^^^^^^
                             spec (Specifier)

    Special syntax ("*", ",", and ":"):
      * spec = debian-ai/2024,2025/11
        expands to debian-ai/2024/11 and debian-ai/2025/11
      * spec = debian-ai/2025/01:05
        expands to debian-ai/2025/01 ... debian-ai/2025/05,
        inclusively for both ends.
    '''
    # is the spec following the special range syntax?
    name, year, month = spec.split('/')
    if any(x in y for x in (',', ':') for y in (name, year, month)):
        # parse the name part
        if ':' in name:
            console.print(f'Error: Does not know how to expand "{name}".')
            return []
        elif ',' in name:
            name = name.split(',')
        else:
            name = [name]
        # parse the year part
        if ':' in year:
            start_year, end_year = year.split(':') 
            year = list(range(int(start_year), int(end_year) + 1))
            year = list(map(str, year))
        elif ',' in year:
            year = year.split(',')
        else:
            year = [year]
        # parse the month part
        if any(x == month for x in (':',)):
            # expand to all months
            month = list(range(1, 13))
            month = list(map(lambda x: f'{x:02d}', month))
        elif ':' in month:
            start_month, end_month = month.split(':')
            month = list(range(int(start_month), int(end_month) + 1))
            month = list(map(lambda x: f'{x:02d}', month))
        elif ',' in month:
            month = month.split(',')
        else:
            month = [month]
        # calculate the product
        allcombs = it.product(name, year, month)
        allcombs = ['/'.join(x) for x in allcombs]
        urls = ft.reduce(list.__add__, [fetch_ldo_threads(x) for x in allcombs])
        return urls

    url = f'https://lists.debian.org/{spec}/{index}'
    response = requests.get(url)
    if response.status_code != 200:
        console.log(f'Failed to read {url}: HTTP {response.status_code}')
        return list()
    soup = BeautifulSoup(response.text, features='html.parser')
    links = soup.find_all('a', href=re.compile(r'^msg.*'))
    links = [x.get('href') for x in links]
    urls = [f'https://lists.debian.org/{spec}/{x}' for x in links]
    console.log(f'Got {len(urls)} threads from {url}')

    # is there a next page? Expand this recursively until no next page.
    next_page = soup.find('a', text='next page')
    if next_page:
        next_index = next_page.get('href')
        next_urls = fetch_ldo_threads(spec, next_index)
        urls = urls + next_urls
    return urls


def read_ldo_threads(spec: str) -> List[Tuple[str, str]]:
    urls = fetch_ldo_threads(spec)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(track(executor.map(read_url, urls),
                             total=len(urls),
                             transient=True,
                             description='Reading l.d.o threads'))
    return [(x, y) for x, y in zip(urls, results)]


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


def read_google(spec: str, *, verbose: bool = False) -> List[Tuple[str, str]]:
    urls = google_search(spec)
    if not urls:
        console.log(f'No Google Search Results for {repr(spec)}.')
        return []
    if verbose:
        console.log(f'Google Search Results for {repr(spec)}:', urls)
    else:
        console.log(f'Got {len(urls)} Google Search Results for {repr(spec)}.')
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(track(executor.map(read_url, urls), total=len(urls)))
    return [(x, y) for x, y in zip(urls, results)]


@enable_cache
def read_archwiki(spec: str) -> str:  # pragma: no cover
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


@enable_cache
def read_buildd(spec: str):  # pragma: no cover
    url = f'https://buildd.debian.org/status/package.php?p={spec}'
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, features='html.parser')
    text = soup.get_text().split('\n')
    return '\n'.join([x.rstrip() for x in text])


def read(spec: str,
         *,
         user_question: Optional[str] = None,
         ) -> List[Entry]:
    '''
    Unified reader for reading text contents from various sources
    specified by the user. We will detect the type of the resource specified,
    and dispatch to the corresponding reader.

    Args:
        spec (str): the path or URL to the file
        user_question (str): the user question
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
    if spec in (':', '?'):
        help()
        raise SystemExit()
    elif os.path.exists(spec) and os.path.isfile(spec):
        parsed_spec = spec
        content = read_file(spec)
        wrapfun = create_wrapper('Here is the contents of file `{}`:', spec)
        wrapfun_chunk = create_chunk_wrapper(
            'Here is the contents of file {} (lines {}-{}):', spec)
        results.append(Entry(parsed_spec, content, wrapfun, wrapfun_chunk))
    elif os.path.exists(spec) and os.path.isdir(spec):
        parsed_spec = spec
        contents = read_directory(spec)
        for (fpath, fcontent) in contents:
            wrapfun = create_wrapper('Here is the contents of file `{}`:',
                                     fpath)
            wrapfun_chunk = create_chunk_wrapper(
                'Here is the contents of file {} (lines {}-{}):', fpath)
            entry = Entry(fpath, fcontent, wrapfun, wrapfun_chunk)
            results.append(entry)
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
    elif spec.startswith('nm:'):
        parsed_spec = spec[3:]
        content = NM_TEMPLATES[parsed_spec]
        wrapfun = create_wrapper('Here is the question {} from Debian nm-templates:',
                                 parsed_spec)
        results.append((parsed_spec, content, wrapfun, lambda x: x))
        if parsed_spec == 'pp1.PH7':
            if not os.path.exists('bad.licenses.tar.bz2'):
                console.print('[red]Downloading https://people.debian.org/~joerg/bad.licenses.tar.bz2 ...')
                os.system('wget -c https://people.debian.org/~joerg/bad.licenses.tar.bz2')
                os.system('tar xvf bad.licenses.tar.bz2')
            contents = read_directory('licenses')
            for (fpath, fcontent) in contents:
                wrapfun = create_wrapper('Here is the contents of file `{}`:',
                                         fpath)
                wrapfun_chunk = create_chunk_wrapper(
                    'Here is the contents of file {} (lines {}-{}):', fpath)
                entry = Entry(fpath, fcontent, wrapfun, wrapfun_chunk)
                results.append(entry)
        if parsed_spec == 'pp1e.PH9':
            ph9_url = 'https://www.debian.org/vote/2006/vote_001'
            contents = read_url(ph9_url)
            wrapfun = create_wrapper('Here is the contents of URL {}:', ph9_url)
            wrapfun_chunk = create_chunk_wrapper(
                    'Here is the contents of URL {} (lines {}-{}):', ph9_url)
            results.append((ph9_url, contents, wrapfun, wrapfun_chunk))
        if parsed_spec in ('pp2.BT6', 'pp2.BT8'):
            url1 = 'https://www.debian.org/Bugs/Reporting'
            results.extend(read(url1))
            url2 = 'https://www.debian.org/Bugs/Developer'
            results.extend(read(url2))
    elif spec.startswith('devref:'):
        # e.g., devref:1 loads section 1, devref: loads the whole devref
        parsed_spec = spec[7:]
        content = debian_policy.DebianDevref()
        if parsed_spec == 'all':
            source = 'Debian Developer Reference document'
            wrapfun = create_wrapper(
                'Here is the Debian Developer Reference document, {}:',
                'full contents')
            wrapfun_chunk = create_chunk_wrapper(
                'Here is the Debian Developer Reference document, {} (lines {}-{}):',
                'full contents')
            results.append((source, str(content), wrapfun, wrapfun_chunk))
        elif parsed_spec:
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
    elif spec.startswith('google:'):
        parsed_spec = spec[7:] if spec[7:] else user_question
        if not parsed_spec:
            raise ValueError('Please provide a search query.')
        for url, content in read_google(parsed_spec, verbose=False):
            wrapfun = create_wrapper('Here is the contents from URL `{}`:',
                                     url)
            wrapfun_chunk = create_chunk_wrapper(
                'Here is the contents from URL `{}` (lines {}-{}):', url)
            results.append((url, content, wrapfun, wrapfun_chunk))
    elif spec.startswith('ldo:') or spec.startswith('lists.debian.org:'):
        parsed_spec = spec[4:] if spec.startswith('ldo:') else spec[18:]
        pairs = read_ldo_threads(parsed_spec)
        for url, content in pairs:
            wrapfun = create_wrapper('Here is the contents from URL `{}`:',
                                     url)
            wrapfun_chunk = create_chunk_wrapper(
                'Here is the contents from URL `{}` (lines {}-{}):', url)
            results.append(Entry(url, content, wrapfun, wrapfun_chunk))
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
        content = debian_policy.DebianPolicy()
        if parsed_spec == 'all':
            source = 'Debian Policy document'
            wrapfun = create_wrapper('Here is the Debian Policy document, {}:',
                                     'full contents')
            wrapfun_chunk = create_chunk_wrapper(
                'Here is the Debian Policy document, {} (lines {}-{}):',
                'full contents')
            results.append((source, str(content), wrapfun, wrapfun_chunk))
        elif parsed_spec:
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
        if spec == 'sbuild:':
            content, logpath = read_sbuild(return_path=True)
        else:
            path = spec[7:]
            content, logpath = read_sbuild(path, return_path=True)
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
        return chunk_lines_nonrecursive(lines, max_chunk_size, 0, len(lines))
    # real work
    result: Dict[Tuple[int, int], List[str]] = {}
    stack = [(start, end)]
    while stack:
        current_start, current_end = stack.pop()
        chunk_size_in_bytes = len('\n'.join(
            lines[current_start:current_end]).encode('utf8'))

        if chunk_size_in_bytes <= max_chunk_size:
            # if the chunk is within the size limit, we add it to the result
            result[(current_start,
                    current_end)] = lines[current_start:current_end]
        elif current_end - current_start == 1:
            # if the chunk is too large but cannot be split, we add it to the result
            result[(current_start,
                    current_end)] = lines[current_start:current_end]
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
                   user_question: Optional[str] = None,
                   ) -> List[Entry]:
    '''
    Read contents from the specified resource and chunk the content into pieces.

    Args:
        spec (str): the path or URL to the file
        max_chunk_size (int): the maximum chunk size of the content. If the
            number is less than 0, we shall not chunk the contents.
    Returns:
        List[Entry]: a list of entries, each entry contains a chunk of the content
    '''
    entries = read(spec, user_question=user_question)
    if max_chunk_size > 0:
        entries = ft.reduce(list.__add__,
                            [chunk_entry(x, max_chunk_size) for x in entries])
    return entries


def read_and_wrap(spec: str,
                  *,
                  max_chunk_size: int = -1,
                  user_question: Optional[str] = None,
                  ) -> str:
    '''
    Read contents from the specified resource and wrap the content to make it
    suitable for prompting LLM.

    Args:
        spec (str): the path or URL to the file
        max_chunk_size (int): the maximum chunk size of the content. If the
            number is less than 0, we shall not chunk the contents.
    Returns:
        str: the wrapped content
    '''
    entries = read(spec, user_question=user_question)
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
    args = parser.parse_args(argv)

    tally = 0
    if args.wrap:
        for file in args.file:
            string = read_and_wrap(file, max_chunk_size=args.chunk)
            console.print(Rule())
            console.log('Specifier:', file)
            console.print(string)
            tally += 1
        console.print('Total number of texts:', tally)
    else:
        for file in args.file:
            entries = read(file)
            if args.chunk > 0:
                entries = ft.reduce(
                    list.__add__,
                    [chunk_entry(x, args.chunk) for x in entries])
            console.print(Rule())
            console.log('Specifier:', file)
            console.print(entries)
            tally += len(entries)
        console.print('Total number of entries:', tally)


if __name__ == '__main__':  # pragma: no cover
    main()
