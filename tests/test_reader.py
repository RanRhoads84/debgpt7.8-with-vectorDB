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
from typing import List, Union, Dict, Tuple
import pytest
from debgpt import reader
import os
import time
import numpy as np
import sys
import io


def test_entry2chunk():
    entry = reader.Entry('void', '\n'.join(['a', 'b', 'c', 'd', 'e']),
                         lambda x: x, lambda x: x)
    print('entry:', entry)
    cdict = reader.entry2dict(entry, 2)
    assert len(cdict) == 5
    print('cdict:', cdict)
    cdict = reader.entries2dict([entry], 2)
    assert len(cdict) == 5


def test_latest_file(tmpdir):
    for i in range(3):
        with open(tmpdir.join(f'test{i}.txt'), 'wt') as f:
            f.write(f'test{i}\n')
        time.sleep(1)
    files = [tmpdir.join(f'test{i}.txt') for i in range(3)]
    assert reader.latest_file(files) == tmpdir.join('test2.txt')
    assert reader.latest_glob(os.path.join(
        tmpdir, 'test*.txt')) == tmpdir.join('test2.txt')


def test_is_text_file(tmpdir):
    block = np.random.randn(100).tobytes()
    with open(tmpdir.join('test.bin'), 'wb') as f:
        f.write(block)
    assert not reader.is_text_file(tmpdir.join('test.bin'))
    with open(tmpdir.join('test.txt'), 'wt') as f:
        f.write('test test test\n')
    assert reader.is_text_file(tmpdir.join('test.txt'))


def test_read_pdf(tmpdir):
    try:
        from fpdf import FPDF
    except ImportError:
        pytest.skip('fpdf not installed')

    def _create_pdf(file_path):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Hello World!", ln=True, align='C')
        pdf.output(file_path)

    _create_pdf(tmpdir.join("test.pdf"))
    assert reader.read_file_pdf(os.path.join(tmpdir,
                                             "test.pdf")) == 'Hello World!'
    assert reader.read_file(os.path.join(tmpdir, "test.pdf")) == 'Hello World!'

    contents = reader.read(os.path.join(tmpdir, "test.pdf"))
    assert len(contents) == 1
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        assert content[0].endswith('test.pdf')
        assert content[1] == 'Hello World!'
        wrapped = content[2](content[1])
        assert isinstance(wrapped, str)
        assert content[1] in wrapped
        wrapped = content[3](content[1], 1, -1)
        assert isinstance(wrapped, str)
        assert content[1] in wrapped

    # read and wrap it
    context = reader.read_and_wrap(str(tmpdir.join('test.pdf')))
    assert isinstance(context, str)
    assert len(context) > 0


def test_read_file(tmpdir):
    content = 'test test test\n'
    with open(tmpdir.join('test.txt'), 'wt') as f:
        f.write(content)
    assert reader.read_file_plaintext(tmpdir.join('test.txt')) == content
    assert reader.read_file(tmpdir.join('test.txt')) == content

    contents = reader.read(str(tmpdir.join('test.txt')))
    assert len(contents) == 1
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        assert content[0].endswith('test.txt')
        assert 'test' in content[1]
        wrapped = content[2](content[1])
        assert isinstance(wrapped, str)
        assert content[1] in wrapped
        wrapped = content[3](content[1], 1, -1)
        assert isinstance(wrapped, str)
        assert content[1] in wrapped

    # non-existing file
    with pytest.raises(FileNotFoundError):
        reader.read_file('non-existing-file')
    with pytest.raises(FileNotFoundError):
        reader.read('non-existing-file')

    # read and wrap a file
    context = reader.read_and_wrap(str(tmpdir.join('test.txt')))
    assert isinstance(context, str)
    assert len(context) > 0


def test_read_directory(tmpdir):
    content = 'test test test\n'
    with open(tmpdir.join('test.txt'), 'wt') as f:
        f.write(content)
    assert reader.read_directory(tmpdir) == [(tmpdir.join('test.txt'), content)
                                             ]

    contents = reader.read(str(tmpdir))
    assert len(contents) == 1
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        assert content[0].endswith('test.txt')
        assert 'test' in content[1]
        wrapped = content[2](content[1])
        assert isinstance(wrapped, str)
        assert content[1] in wrapped
        wrapped = content[3](content[1], 1, -1)
        assert isinstance(wrapped, str)
        assert content[1] in wrapped

    # read and wrap it
    context = reader.read_and_wrap(str(tmpdir))
    assert isinstance(context, str)
    assert len(context) > 0


def test_read_url_file(tmpdir):
    content = 'test test test\n'
    with open(tmpdir.join('test.txt'), 'wt') as f:
        f.write(content)
    url = 'file://' + str(tmpdir.join('test.txt'))
    assert reader.read_url(url) == content

    contents = reader.read(url)
    assert len(contents) > 0
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        assert content[0].endswith('test.txt')
        assert 'test' in content[1]
        wrapped = content[2](content[1])
        assert isinstance(wrapped, str)
        assert content[1] in wrapped
        wrapped = content[3](content[1], 1, -1)
        assert isinstance(wrapped, str)
        assert content[1] in wrapped

    # read and wrap it
    context = reader.read_and_wrap(url)
    assert isinstance(context, str)
    assert len(context) > 0


@pytest.mark.parametrize('url', (
    'http://google.com',
    'https://google.com/',
    'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf',
    'https://httpbin.org/robots.txt',
    'https://lists.debian.org/debian-project/2023/12/msg00029.html',
))
def test_read_url_http(url):
    assert len(reader.read_url(url)) > 0

    # read as entries
    contents = reader.read(url)
    assert len(contents) > 0
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        assert content[0] == url
        assert content[1] in content[2](content[1])
        assert content[1] in content[3](content[1], 1, -1)

    # read and wrap it
    context = reader.read_and_wrap(url)
    assert isinstance(context, str)
    assert len(context) > 0


@pytest.mark.timeout(10)
@pytest.mark.parametrize('spec', ('src:pytorch', '1056388'))
def test_read_bts(spec: str):
    # read directly
    assert reader.read_bts(spec)
    # read as entries
    contents = reader.read(f'bts:{spec}')
    assert len(contents) > 0
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        assert content[0] == spec
        assert content[1] in content[2](content[1])
        assert content[1] in content[3](content[1], 1, -1)
    # read and wrap
    context = reader.read_and_wrap(f'bts:{spec}')
    assert isinstance(context, str)
    assert len(context) > 0


@pytest.mark.parametrize('spec', ('man creat', ['man', 'creat']))
def test_read_cmd(spec: Union[str, List[str]]):
    assert reader.read_cmd(spec)
    if isinstance(spec, list):
        return
    contents = reader.read(f'cmd:{spec}')
    assert len(contents) > 0
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        assert content[0] == spec
        assert content[1] in content[2](content[1])
        assert content[1] in content[3](content[1], 1, -1)
    # read and wrap
    context = reader.read_and_wrap(f'cmd:{spec}')
    assert isinstance(context, str)
    assert len(context) > 0


def test_read_man():
    contents = reader.read('man:creat')
    assert len(contents) > 0
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        assert content[0] == 'creat'
        assert content[1] in content[2](content[1])
        assert content[1] in content[3](content[1], 1, -1)
    # read and wrap
    context = reader.read_and_wrap('man:creat')
    assert isinstance(context, str)
    assert len(context) > 0


def test_read_tldr():
    contents = reader.read('tldr:tar')
    assert len(contents) > 0
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        assert content[0] == 'tar'
        assert content[1] in content[2](content[1])
        assert content[1] in content[3](content[1], 1, -1)
    # read and wrap
    context = reader.read_and_wrap('tldr:tar')
    assert isinstance(context, str)
    assert len(context) > 0


def test_read_stdin(monkeypatch):
    test_input = 'test test test\ntest test test'
    monkeypatch.setattr(sys, 'stdin', io.StringIO(test_input))
    assert reader.read_stdin() == test_input
    # read as entries
    monkeypatch.setattr(sys, 'stdin', io.StringIO(test_input))
    contents = reader.read('stdin')
    assert len(contents) == 1
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        assert content[0] == 'stdin'
        assert content[1] in content[2](content[1])
        assert content[1] in content[3](content[1], 1, -1)
    # read and wrap
    monkeypatch.setattr(sys, 'stdin', io.StringIO(test_input))
    context = reader.read_and_wrap('stdin')
    assert isinstance(context, str)
    assert len(context) > 0


def test_google_search(keyword='python programming'):
    results = reader.google_search(keyword)
    print('google search results:', results)
    assert len(results) > 0
    for r in results:
        assert r.startswith('http')


@pytest.mark.flaky(reruns=3, reruns_delay=5)
@pytest.mark.parametrize('keyword', ('python programming', 'debian'))
def test_read_google(keyword: str):
    results: List[Tuple[str, str]] = reader.read_google(keyword)
    assert len(results) > 0
    for url, content in results:
        assert url.startswith('http')
        assert isinstance(content, str)
        assert len(content) >= 0


@pytest.mark.parametrize('keyword', ('Archiving_and_compression', ))
def test_read_archwiki(keyword):
    assert reader.read_archwiki(keyword)
    contents = reader.read(f'archwiki:{keyword}')
    assert len(contents) > 0
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        assert content[0] == keyword
        assert content[1] in content[2](content[1])
        assert content[1] in content[3](content[1], 1, -1)


@pytest.mark.parametrize('package', ('debgpt', 'pytorch'))
def test_read_buildd(package):
    assert reader.read_buildd(package)
    contents = reader.read(f'buildd:{package}')
    assert len(contents) > 0
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        assert content[0] == package
        assert content[1] in content[2](content[1])
        assert content[1] in content[3](content[1], 1, -1)


@pytest.mark.parametrize('section', ('all', '', '1', '4.6', '4.6.1'))
def test_policy(section, tmpdir):
    contents = reader.read(f'policy:{section}')
    assert len(contents) >= 1
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        wrapped = content[2](content[1])
        assert isinstance(wrapped, str)
        assert content[1] in wrapped
        wrapped = content[3](content[1], 1, -1)
        assert isinstance(wrapped, str)
        assert content[1] in wrapped


@pytest.mark.parametrize('section', ('all', '', '5.5', '1'))
def test_devref(section, tmpdir):
    contents = reader.read(f'devref:{section}')
    assert len(contents) >= 1
    for content in contents:
        assert isinstance(content[0], str)
        assert isinstance(content[1], str)
        assert callable(content[2])
        assert callable(content[3])
        wrapped = content[2](content[1])
        assert isinstance(wrapped, str)
        assert content[1] in wrapped
        wrapped = content[3](content[1], 1, -1)
        assert isinstance(wrapped, str)
        assert content[1] in wrapped


@pytest.mark.parametrize('spec', (
    'test.txt',
    'policy:1',
    'devref:1',
    'bts:src:pytorch',
    'bts:1056388',
    'archwiki:Archiving_and_compression',
    'tldr:tar',
    'man:creat',
    'cmd:man creat',
))
def test_read_main(spec: str, tmpdir: object):
    if spec == 'test.txt':
        with open(tmpdir.join('test.txt'), 'wt') as f:
            f.write('test test test\n')
        reader.main(['-f', 'file://' + str(tmpdir.join('test.txt'))])
        reader.main(['-f', str(tmpdir)])
        reader.main(['-f', str(tmpdir.join('test.txt'))])
        reader.main(['-w', '-f', str(tmpdir.join('test.txt'))])
    else:
        reader.main(['-f', spec])
        reader.main(['-w', '-f', spec])
        reader.main(['-c', '1024', '-f', spec])
        reader.main(['-w', '-c', '1024', '-f', spec])


def test_chunk_lines():
    lines = 'test test test test test test'.split()
    print('lines:', lines)

    chunks = reader.chunk_lines(lines, 15)
    print('chunks:', chunks)
    assert len(chunks) == 2
    chunks_nr = reader.chunk_lines_nonrecursive(lines, 15)
    print('chunks_nr:', chunks_nr)
    assert len(chunks_nr) == 2

    chunks = reader.chunk_lines(lines, 5)
    assert len(chunks) == 6
    chunks_nr = reader.chunk_lines_nonrecursive(lines, 5)
    assert len(chunks_nr) == 6

    chunks = reader.chunk_lines(lines, 1)
    assert len(chunks) == 6
    chunks_nr = reader.chunk_lines_nonrecursive(lines, 1)
    assert len(chunks_nr) == 6
