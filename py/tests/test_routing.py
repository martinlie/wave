
# Copyright 2020 H2O.ai, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import unittest
from uuid import UUID
import h2o_wave
from unittest.mock import AsyncMock
from starlette.routing import compile_path
from h2o_wave import run_on, Q, AsyncSite, Expando


class FakeAuth:
    def __init__(self):
        self.username = ''
        self.subject = ''
        self.access_token = ''
        self.refresh_token = ''
        self._session_id = ''


def mock_q(args={}, events={}):
    return Q(site=AsyncSite(), mode='unicast', auth=FakeAuth(), client_id='', route='/', app_state=None,
             user_state=None, client_state=None, args=Expando(args), events=Expando(events), headers={})


arg_handlers = {
    'button': AsyncMock(),
    'checkbox': AsyncMock(),
}
path_handlers = {
    '#': AsyncMock(),
    '#page': AsyncMock(),
}
pattern_path_handlers = {
    '#page/donuts/{donut_name}': AsyncMock(),
    '#page/muffins/{muffin_name:str}': AsyncMock(),
    '#page/cakes/{cake_name:int}': AsyncMock(),
    '#page/pies/{pie_name:float}': AsyncMock(),
    '#page/orders/{order_id:uuid}': AsyncMock(),
}
pattern_arg_handlers = {
    'page/donuts/{donut_name}': AsyncMock(),
    'page/muffins/{muffin_name:str}': AsyncMock(),
    'page/cakes/{cake_name:int}': AsyncMock(),
    'page/pies/{pie_name:float}': AsyncMock(),
    'page/orders/{order_id:uuid}': AsyncMock(),
}
event_handlers = {
    'source.event': AsyncMock(),
}

# HACK: Monkey-patch routing arity checks - throws err on Python 3.10
# https://github.com/python/cpython/issues/96127.
h2o_wave.routing._get_arity = lambda x: 0

for k, h in arg_handlers.items():
    h2o_wave.routing._add_handler(k, h, None)
for k, h in path_handlers.items():
    rx, _, conv = compile_path(k[1:])
    h2o_wave.routing._path_handlers.append((rx, conv, h, 0))
for k, h in pattern_path_handlers.items():
    rx, _, conv = compile_path(k[1:])
    h2o_wave.routing._path_handlers.append((rx, conv, h, 2))
for k, h in pattern_arg_handlers.items():
    rx, _, conv = compile_path(k)
    h2o_wave.routing._arg_with_params_handlers.append((None, h, 2, rx, conv))
for k, h in event_handlers.items():
    source, event = k.split('.', 1)
    h2o_wave.routing._add_event_handler(source, event, h, None)


class TestRouting(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        handlers = {**arg_handlers, **path_handlers, **pattern_path_handlers, **pattern_arg_handlers, **event_handlers}
        for h in handlers.values():
            h.reset_mock()

    async def test_args(self):
        await run_on(mock_q(args={'button': True, '__wave_submission_name__': 'button'}))
        arg_handlers['button'].assert_called_once()

    async def test_args_false(self):
        await run_on(mock_q(args={'checkbox': False, '__wave_submission_name__': 'checkbox'}))
        arg_handlers['checkbox'].assert_called_once()

    async def test_args_empty_string(self):
        await run_on(mock_q(args={'checkbox': '', '__wave_submission_name__': 'checkbox'}))
        arg_handlers['checkbox'].assert_called_once()

    async def test_no_match(self):
        await run_on(mock_q(args={'__wave_submission_name__': 'checkbox'}))
        arg_handlers['checkbox'].assert_not_called()

    async def test_hash(self):
        await run_on(mock_q(args={'#': 'page', '__wave_submission_name__': '#'}))
        path_handlers['#page'].assert_called_once()

    async def test_empty_hash(self):
        await run_on(mock_q(args={'#': '', '__wave_submission_name__': '#'}))
        path_handlers['#'].assert_called_once()

    async def test_events(self):
        await run_on(mock_q(args={'__wave_submission_name__': 'source'}, events={'source': {'event': True}}))
        event_handlers['source.event'].assert_called_once()

    async def test_events_false(self):
        await run_on(mock_q(args={'__wave_submission_name__': 'source'}, events={'source': {'event': False}}))
        event_handlers['source.event'].assert_called_once()

    async def test_events_empty(self):
        await run_on(mock_q(args={'__wave_submission_name__': 'source'}, events={'source': {'event': ''}}))
        event_handlers['source.event'].assert_called_once()

    async def test_hash_pattern_matching(self):
        q = mock_q(args={'#': 'page/donuts/1', '__wave_submission_name__': '#'})
        await run_on(q)
        pattern_path_handlers['#page/donuts/{donut_name}'].assert_called_once_with(q, donut_name='1')

    async def test_hash_pattern_matching_str(self):
        q = mock_q(args={'#': 'page/muffins/1', '__wave_submission_name__': '#'})
        await run_on(q)
        pattern_path_handlers['#page/muffins/{muffin_name:str}'].assert_called_once_with(q, muffin_name='1')

    async def test_hash_pattern_matching_int(self):
        q = mock_q(args={'#': 'page/cakes/1', '__wave_submission_name__': '#'})
        await run_on(q)
        pattern_path_handlers['#page/cakes/{cake_name:int}'].assert_called_once_with(q, cake_name=1)

    async def test_hash_pattern_matching_float(self):
        q = mock_q(args={'#': 'page/pies/3.14', '__wave_submission_name__': '#'})
        await run_on(q)
        pattern_path_handlers['#page/pies/{pie_name:float}'].assert_called_once_with(q, pie_name=3.14)

    async def test_hash_pattern_matching_uuid(self):
        q = mock_q(args={'#': 'page/orders/123e4567-e89b-12d3-a456-426655440000', '__wave_submission_name__': '#'})
        await run_on(q)
        uuid = UUID('123e4567-e89b-12d3-a456-426655440000')
        pattern_path_handlers['#page/orders/{order_id:uuid}'].assert_called_once_with(q, order_id=uuid)

    async def test_arg_pattern_matching(self):
        q = mock_q(args={'page/donuts/1': True, '__wave_submission_name__': 'page/donuts/1'})
        await run_on(q)
        pattern_arg_handlers['page/donuts/{donut_name}'].assert_called_once_with(q, donut_name='1')

    async def test_arg_pattern_matching_str(self):
        q = mock_q(args={'page/muffins/1': True, '__wave_submission_name__': 'page/muffins/1'})
        await run_on(q)
        pattern_arg_handlers['page/muffins/{muffin_name:str}'].assert_called_once_with(q, muffin_name='1')

    async def test_arg_pattern_matching_int(self):
        q = mock_q(args={'page/cakes/1': True, '__wave_submission_name__': 'page/cakes/1'})
        await run_on(q)
        pattern_arg_handlers['page/cakes/{cake_name:int}'].assert_called_once_with(q, cake_name=1)

    async def test_arg_pattern_matching_float(self):
        q = mock_q(args={'page/pies/3.14': True, '__wave_submission_name__': 'page/pies/3.14'})
        await run_on(q)
        pattern_arg_handlers['page/pies/{pie_name:float}'].assert_called_once_with(q, pie_name=3.14)

    async def test_arg_pattern_matching_uuid(self):
        uuid_str = '123e4567-e89b-12d3-a456-426655440000'
        arg = f'page/orders/{uuid_str}'
        q = mock_q(args={arg: True, '__wave_submission_name__': arg})
        await run_on(q)
        pattern_arg_handlers['page/orders/{order_id:uuid}'].assert_called_once_with(q, order_id=UUID(uuid_str))
