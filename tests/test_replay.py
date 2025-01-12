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
import json
from debgpt import replay

demo_session = [{
    "role": "system",
    "content": "system prompt"
}, {
    "role": "user",
    "content": "hi"
}, {
    "role": "assistant",
    "content": "Hello! How can I assist you today?"
}]

illegal_session = [
    {
        "role": "nobody",
        "content": "hi"
    },
]


def test_replay(tmpdir):
    with open(tmpdir.join('test_replay.json'), 'w') as f:
        json.dump(demo_session, f)
    sample_json_path = str(tmpdir.join('test_replay.json'))
    replay.replay(sample_json_path)
    replay.main([sample_json_path])
    replay.main([sample_json_path, '--render'])
    replay.main([sample_json_path, '--no-render'])


@pytest.mark.parametrize('render', (True, False))
def test_process_entry(render: bool):
    for entry in demo_session:
        replay.process_entry(entry, render)
    for entry in illegal_session:
        with pytest.raises(ValueError):
            replay.process_entry(entry, render)
