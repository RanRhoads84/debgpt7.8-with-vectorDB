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
import os
import requests
from .defaults import console


class DebianPolicy:
    '''
    Cache the plain text policy document and query its sections / subsections.
    '''
    NAME: str = 'Debian Policy'
    URL: str = 'https://www.debian.org/doc/debian-policy/policy.txt'
    SEP_SECTION: str = '***'
    SEP_SUBSECTION: str = '==='
    SEP_SUBSUBSECTION: str = '---'

    def __init__(self, cache: str = 'policy.txt') -> None:
        # Check if the cache file exists, if not, download and cache it.
        if not os.path.exists(cache):
            r = requests.get(self.URL)
            with open(cache, 'wb') as f:
                f.write(r.content)
            console.log(f'DebianPolicy> cached {self.NAME} at {cache}')
        
        # Read the cached file into lines.
        with open(cache, 'rt') as f:
            self.lines: list[str] = [x.rstrip() for x in f.readlines()]

    def __str__(self) -> str:
        # Return the entire document as a string.
        return '\n'.join(self.lines)

    def __getitem__(self, index: str) -> str:
        # Retrieve a specific section, subsection, or subsubsection based on the index.
        sep: str = {
            1: self.SEP_SECTION,
            2: self.SEP_SUBSECTION,
            3: self.SEP_SUBSUBSECTION
        }[len(index.split('.'))]
        
        ret: list[str] = []
        prev: str = ''
        in_range: bool = False
        
        # Iterate over lines to find the specified section.
        for cursor in self.lines:
            if cursor.startswith(sep) and prev.startswith(f'{index}. '):
                # Start of the desired section
                ret.append(prev)
                ret.append(cursor)
                in_range = True
            elif cursor.startswith(sep) and in_range:
                # End of the desired section
                ret.pop(-1)
                in_range = False
                break
            elif in_range:
                # Within the desired section
                ret.append(cursor)
            prev = cursor
        
        return '\n'.join(ret)


class DebianDevref(DebianPolicy):
    NAME: str = "Debian Developer's Reference"
    URL: str = 'https://www.debian.org/doc/manuals/developers-reference/developers-reference.en.txt'

    def __init__(self, cache: str = 'devref.txt') -> None:
        # Initialize the DebianDevref class, inheriting from DebianPolicy.
        super().__init__(cache)
