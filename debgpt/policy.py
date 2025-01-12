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
from typing import Union, List
import requests
from .defaults import CACHE
from .cache import Cache


class DebianPolicy:
    '''
    Cache the plain text policy document and query its sections / subsections.
    '''
    NAME: str = 'Debian Policy'
    URL: str = 'https://www.debian.org/doc/debian-policy/policy.txt'
    SEP_SECTION: str = '***'
    SEP_SUBSECTION: str = '==='
    SEP_SUBSUBSECTION: str = '---'

    def __init__(self) -> None:
        cache = Cache(CACHE)
        # Check if the cache exists and read lines
        if self.URL not in cache:  # pragma: no cover
            r = requests.get(self.URL)
            cache[self.URL] = r.text
            lines = r.text.split('\n')
        else:
            lines = cache[self.URL].split('\n')

        # Scan the document and prepare the section indexes.
        self.lines: List[str] = [x.rstrip() for x in lines]
        self.indexes: list[str] = self.__scan_indexes()

    def __iter__(self):
        # Return an iterator over the section indexes.
        self.__cursor: int = 0
        return self

    def __next__(self) -> str:
        # Return the next section index.
        if self.__cursor < len(self.indexes):
            section = self.indexes[self.__cursor]
            self.__cursor += 1
            return self.__getitem__(section)
        else:
            raise StopIteration

    def __len__(self) -> int:
        # Return the number of sections in the document.
        return len(self.indexes)

    def __scan_indexes(self) -> list[str]:
        # Scan the document and return a list of all section indexes.
        ret: list[str] = []
        for i in range(1, len(self.lines)):
            cursur = self.lines[i]
            previous = self.lines[i - 1]
            if any(
                    cursur.startswith(x) for x in [
                        self.SEP_SECTION, self.SEP_SUBSECTION,
                        self.SEP_SUBSUBSECTION
                    ]):
                index = previous.split(' ')[0]
                if index.endswith('.'):
                    ret.append(index.rstrip('.'))
        return ret

    def __str__(self) -> str:
        # Return the entire document as a string.
        return '\n'.join(self.lines)

    def __getitem__(self, index: Union[str, int]) -> str:
        # if the index is an integer, map it to the real section number
        if isinstance(index, int):
            section = self.indexes[index]
            return self.__getitem__(section)
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


if __name__ == '__main__':  # pragma: no cover
    # Test the DebianPolicy class.
    p = DebianPolicy()
    print('Policy total length', len(str(p).encode()), 'bytes')
    for (sec, text) in zip(p.indexes, p):
        print('section', sec, 'length', len(text.encode()), 'bytes')

    # Test the DebianDevref class.
    d = DebianDevref()
    print('Devref total length', len(str(d).encode()), 'bytes')
    for (sec, text) in zip(d.indexes, d):
        print('section', sec, 'length', len(text.encode()), 'bytes')
