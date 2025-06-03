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
__version__ = '0.7.8'
__copyright__ = '2024-2025, Mo Zhou <lumin@debian.org>'
__license__ = 'LGPL-3.0+'
# do not load all components.
# some components like llm, and backend, requires much more dependencies


def version() -> None:
    print(f'DebGPT {__version__}')
    print(f'Copyright {__copyright__}')
    print(f'Released under {__license__} license.')
