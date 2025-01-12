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
import pytest
import shlex
from debgpt import arguments


@pytest.mark.parametrize('cmd', (
    '-F dryrun --version',
    '-F dryrun -f Makefile',
    '-F dryrun -f tldr:man',
    '-F dryrun -f man:man',
    '-F dryrun -f cmd:"man man"',
))
def test_parse_args(cmd: str):
    cmd_list = shlex.split(cmd)
    args = arguments.parse_args(cmd_list)
    assert args.frontend == 'dryrun'
    # add --hide_first|-H
    args = arguments.parse_args(cmd_list + ['--hide_first'])
    # add --quit|-Q|-q
    args = arguments.parse_args(cmd_list + ['--quit'])
    # test main
    arguments.main(cmd_list)


def test_parse_order():
    # case 1
    cmd = ['-F', 'dryrun', '-f', 'file1', '-f', 'file2', '-f', 'file3']
    order = arguments.parse_args_order(cmd)
    print(order)
    assert len(order) == 3
    for x in order:
        assert x == 'file'
    # case 2
    cmd = [
        '-F', 'dryrun', '-f', 'file1', '-x', 'map1', '-f', 'file2', '-f',
        'file3'
    ]
    order = arguments.parse_args_order(cmd)
    print(order)
    assert len(order) == 4
    for i, x in enumerate(order):
        assert x == ('file' if i != 1 else 'mapreduce')
    # test main
    arguments.main(cmd)
