# -*- coding: utf-8 -*-

import wsgiref.util

wsgiref.util._hoppish = {
    'connection': 1, 'keep-alive':1,
    'te':1, 'trailers':1, 'transfer-encoding':1,
    'upgrade':1
}.__contains__


