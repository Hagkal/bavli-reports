import dataclasses
import datetime
import string
from enum import Enum

from gspread import Worksheet
from gspread.utils import a1_range_to_grid_range
from time import sleep
from typing import List, Tuple


class RowDiffs:
    @staticmethod
    def fit_rows(row1: list, row2: list):
        diff = len(row1) - len(row2)
        if diff:
            extend_row = row2 if diff > 0 else row1
            extend_row.extend([""] * diff)

    def __init__(self, bavli_row, external_row):
        RowDiffs.fit_rows(bavli_row, external_row)
        self.bavli_row = bavli_row
        self.external_row = external_row

    def find_diffs(self):
        return [i for i, val in enumerate(self.bavli_row) if val != self.external_row[i]]

    def prettify(self, key: tuple):
        return {
            ("bavli", *key): self.bavli_row,
            ("external", *key): self.external_row
        }


class BackgroundColor(Enum):
    RED = {"backgroundColor": {
        "red": 1.0,
        "green": 0.0,
        "blue": 0.0
    }}
    LIGHT_RED = {"backgroundColor": {
        "red": 0.9,
        "green": 0.7,
        "blue": 0.7
    }}
    YELLOW = {"backgroundColor": {
        "red": 1.0,
        "green": 1.0,
        "blue": 0.0
    }}
    ORANGE = {"backgroundColor": {
        "red": 1.0,
        "green": 0.7,
        "blue": 0.0
    }}
    PURPLE = {"backgroundColor": {
        "red": 0.7,
        "green": 0.7,
        "blue": 1.0
    }}
    LIGHT_GREEN = {"backgroundColor": {
        "red": 0.7,
        "green": 0.9,
        "blue": 0.7
    }}
    WHITE = {"backgroundColor": {
        "red": 0.0,
        "green": 0.0,
        "blue": 0.0
    }}


@dataclasses.dataclass
class Format:
    general_color: BackgroundColor
    cells_color: List[Tuple[int, int, BackgroundColor]] = dataclasses.field(default_factory=list)


class Range:
    @classmethod
    def from_first_and_values(cls, values: List[List], first_column="A", first_row=1):
        second_column = cls.int_to_column(len(values[0]))
        second_row = first_row + len(values) - 1
        return cls(first_column, first_row, second_column, second_row)

    @classmethod
    def int_to_column(cls, num):
        if num < 1:
            return ""
        if num // 26:
            return string.ascii_uppercase[(num // 26) - 1] + string.ascii_uppercase[num % 26 - 1]
        return string.ascii_uppercase[num % 26 - 1]

    def __init__(self, first_column="A", first_row=1, second_column="Z", second_row=1):
        self.first_column: str = first_column
        self.first_row: int = first_row
        self.second_column: str = second_column
        self.second_row: int = second_row

    def __str__(self):
        return f"{self.first_column}{self.first_row}:{self.second_column}{self.second_row}"

    def add_to_rows(self, num: int):
        self.first_row += num
        self.second_row += num


class WriteRequests:
    def __init__(self, quota: int = 60):
        self.qouta = quota
        self._write_requests = 0
        self.last_request: datetime.datetime = datetime.datetime.now()

    @property
    def write_requests(self):
        return self._write_requests

    @write_requests.setter
    def write_requests(self, val):
        if self._write_requests + val > self.qouta:
            next_request_time = self.last_request + datetime.timedelta(seconds=60)
            if datetime.datetime.now() < next_request_time:
                sleep((next_request_time - datetime.datetime.now()).seconds + 1)

        self._write_requests = (self._write_requests + val) % self.qouta

    def __add__(self, other):
        self.write_requests = other
        return self


class FormatRequest:
    def __init__(self):
        self.request = {
            "requests": []
        }

    def add_request(self, single_request):
        self.request.get("requests").append(single_request)


def format_cells(range_name, cell_format, ws_id):
    grid_range = a1_range_to_grid_range(range_name, ws_id)
    fields = "userEnteredFormat(%s)" % ','.join(cell_format.keys())

    return {
                "repeatCell": {
                    "range": grid_range,
                    "cell": {"userEnteredFormat": cell_format},
                    "fields": fields,
                }
            }
