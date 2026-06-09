"""Shared DRF pagination helpers.

`CappedPageNumberPagination` returns the standard
``{count, next, previous, results}`` envelope and lets the client pick a page
size via ``?page_size=`` up to a hard ``max_page_size`` cap — so a single
request can never serialize an unbounded slice of a growing table. Use it on
admin / large-collection list endpoints.
"""
from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class CappedPageNumberPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
