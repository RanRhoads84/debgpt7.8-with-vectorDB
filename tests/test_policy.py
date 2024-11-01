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
import pytest
from debgpt.policy import DebianPolicy
from debgpt.policy import DebianDevref


@pytest.mark.parametrize('section', ('1', '4.6', '4.9.1'))
def test_policy(tmpdir: str, section: str) -> None:
    """
    Test the DebianPolicy class by checking specific sections.

    Args:
        tmpdir (str): The temporary directory to use for testing.
        section (str): The section of the Debian Policy to test.
    """
    policy = DebianPolicy(os.path.join(tmpdir, 'policy.txt'))
    # Print the specific section of the policy
    print(policy[section])
    # Convert the entire policy to a string
    whole = str(policy)
    # Assert that the entire policy string is longer than 1000 characters
    assert len(whole) > 1000


@pytest.mark.parametrize('section', ('2', '2.1', '3.1.1'))
def test_devref(tmpdir: str, section: str) -> None:
    """
    Test the DebianDevref class by checking specific sections.

    Args:
        tmpdir (str): The temporary directory to use for testing.
        section (str): The section of the Debian Developer's Reference to test.
    """
    devref = DebianDevref(os.path.join(tmpdir, 'devref.txt'))
    # Print the specific section of the developer's reference
    print(devref[section])
    # Convert the entire developer's reference to a string
    whole = str(devref)
    # Assert that the entire developer's reference string is longer than 1000 characters
    assert len(whole) > 1000
