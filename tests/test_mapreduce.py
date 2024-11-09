'''
Copyright (C) 2024 Mo Zhou <lumin@debian.org>

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
from debgpt import mapreduce
import os
import time
import numpy as np
import sys
import io

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
