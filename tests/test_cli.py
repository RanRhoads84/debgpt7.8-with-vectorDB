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
from debgpt.cli import main

#@pytest.mark.parametrize('cmd', (
#    '-F dryrun',
#    '-F dryrun -Hf Makefile',
#    '-F dryrun -Qf Makefile',
#    '-F dryrun --tldr man',
#    '-F dryrun --man man',
#    '-F drurun --version',
#    '-F dryrun --cmd "man man"',
#))
#def test_cli_system_exit(cmd: str):
#    with pytest.raises(SystemExit):
#        main(cmd.split())
