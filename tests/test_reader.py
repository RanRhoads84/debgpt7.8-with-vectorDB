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
import pytest
from debgpt import reader
import os
import time
import numpy as np


def test_latest_file(tmpdir):
    for i in range(3):
        with open(tmpdir.join(f'test{i}.txt'), 'wt') as f:
            f.write(f'test{i}\n')
        time.sleep(1)
    files = [tmpdir.join(f'test{i}.txt') for i in range(3)]
    assert reader.latest_file(files) == tmpdir.join('test2.txt')
    assert reader.latest_glob(os.path.join(tmpdir, 'test*.txt')) == tmpdir.join('test2.txt')


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
    assert reader.read_file_pdf(os.path.join(tmpdir, "test.pdf")) == 'Hello World!'


def test_read_file(tmpdir):
    content = 'test test test\n'
    with open(tmpdir.join('test.txt'), 'wt') as f:
        f.write(content)
    assert reader.read_file_plaintext(tmpdir.join('test.txt')) == content
    assert reader.read_file(tmpdir.join('test.txt')) == content

def test_read_directory(tmpdir):
    content = 'test test test\n'
    with open(tmpdir.join('test.txt'), 'wt') as f:
        f.write(content)
    assert reader.read_directory(tmpdir) == [(tmpdir.join('test.txt'), content)]


def test_read_url(tmpdir):
    content = 'test test test\n'
    with open(tmpdir.join('test.txt'), 'wt') as f:
        f.write(content)
    url = 'file://' + str(tmpdir.join('test.txt'))
    assert reader.read_url(url) == content


@pytest.mark.parametrize('spec', ('src:pytorch', '1056388'))
def test_read_bts(spec: str):
    assert reader.read_bts(spec)

#@pytest.mark.parametrize('section', ('1', '4.6', '4.6.1'))
#def test_policy(section, tmp_path):
#    print(reader.policy(section, debgpt_home=tmp_path))
#
#
#@pytest.mark.parametrize('section', ('5.5', '1'))
#def test_devref(section, tmp_path):
#    print(reader.devref(section, debgpt_home=tmp_path))
#
#
#@pytest.mark.parametrize('p', ('pytorch', ))
#def test_buildd(p):
#    print(reader.buildd(p))
#
#
#@pytest.mark.parametrize(
#    'url', ('https://lists.debian.org/debian-project/2023/12/msg00029.html', ))
#def test_html(url):
#    print(reader.html(url, raw=False))
#
#
#def test_mapreduce_load_file(tmp_path):
#    policypath = os.path.join(tmp_path, 'policy.txt')
#    # just download the policy text file
#    reader.policy('1', debgpt_home=tmp_path)
#    chunks = reader.mapreduce_load_file(policypath)
#    for k, v in chunks.items():
#        encoded = '\n'.join(v).encode('utf-8')
#        print(k, len(encoded))
#        print(encoded.decode())
#
#
#def test_mapreduce_load_directory(tmp_path):
#    chunks = reader.mapreduce_load_directory('./debian')
#    for k, v in chunks.items():
#        encoded = '\n'.join(v).encode('utf-8')
#        print(k, len(encoded))
#        print(encoded.decode())
#
#
#def test_mapreduce_load_any_astext():
#    chunks = reader.mapreduce_load_any_astext('./debian')
#    for v in chunks:
#        print(v)
