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
import os
import pytest
from debgpt.policy import DebianPolicy
from debgpt.policy import DebianDevref


def test_policy(tmpdir: str) -> None:
    """
    Test the DebianPolicy class by checking specific sections.

    Args:
        tmpdir (str): The temporary directory to use for testing.
    """
    policy = DebianPolicy()
    # specific section of the policy, indexed by section number (as string)
    for section in ('1', '4.6', '4.9.1'):
        text = policy[section]
    # Convert the entire policy to a string
    whole = str(policy)
    assert len(whole) > 1000

    # test __iter__ and __next__
    for i, section in enumerate(policy):
        assert isinstance(section, str)
        assert len(section) > 0

    # test __len__
    assert len(policy) > 0

    # test __getitem__ with int
    for i in range(len(policy)):
        text = policy[i]
        assert len(text) > 0


@pytest.mark.parametrize('section', ('2', '2.1', '3.1.1'))
def test_devref(tmpdir: str, section: str) -> None:
    """
    Test the DebianDevref class by checking specific sections.

    Args:
        tmpdir (str): The temporary directory to use for testing.
        section (str): The section of the Debian Developer's Reference to test.
    """
    devref = DebianDevref()
    # Print the specific section of the developer's reference
    print(devref[section])
    # Convert the entire developer's reference to a string
    whole = str(devref)
    # Assert that the entire developer's reference string is longer than 1000 characters
    assert len(whole) > 1000
