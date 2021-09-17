import os.path

import requests
import json
import string
from collections import defaultdict
from logging import getLogger

import gspread as gs

from typing import List, Tuple, Dict, Callable

from gspread import Spreadsheet, Worksheet, Client
from gspread.auth import store_credentials

from bavli_reports import ROOT_DIR
from bavli_reports.models import BackgroundColor, Format, Range, WriteRequests, FormatRequest, format_cells

logger = getLogger(__name__)


DELIMITER: str = "~~~"
CREDENTIALS = os.path.join(ROOT_DIR, "credentials.json")
AUTHORIZATION = os.path.join(ROOT_DIR, "authorized_user.json")

write_requests = WriteRequests()


def refresh_token(authorized_user_filename: str):
    os.remove(AUTHORIZATION)
    # with open(authorized_user_filename, "r") as f:
    #     creds = json.load(f)
    #     params = {
    #         "grant_type": "refresh_token",
    #         "client_id": creds["client_id"],
    #         "client_secret": creds["client_secret"],
    #         "refresh_token": creds["refresh_token"]
    #     }
    #
    #     authorization_url = "https://www.googleapis.com/oauth2/v4/token"
    #
    #     r = requests.post(authorization_url, data=params)
    #
    #     if r.ok:
    #         return {
    #             **creds,
    #             "token": r.json()["access_token"]
    #         }
    #     else:
    #         return creds


def get_connection():
    gc: Client = gs.oauth(credentials_filename=CREDENTIALS, authorized_user_filename=AUTHORIZATION)
    if gc.auth.expired:
        creds = refresh_token(authorized_user_filename=AUTHORIZATION)
        gc = gs.oauth(credentials_filename=CREDENTIALS, authorized_user_filename=AUTHORIZATION)

    return gc


def get_report_by_url(url: str, connection: Client = None) -> Spreadsheet:
    if not connection:
        connection = get_connection()
    return connection.open_by_url(url)


def _cleanup_values(values: List[List], filter_by: Callable[[List], bool] = None) -> tuple[list[list], list[list]]:
    def default_filter(row_check: List) -> bool:
        house, zip_code = row_check[1:3]
        if house or zip_code:
            try:
                int(house)
                int(zip_code)
            except ValueError:
                return False
            else:
                return True
        raise ValueError(f"invalid row -> both identifiers are empty: ({house}, {zip_code})")

    if not filter_by:
        filter_by = default_filter

    valid_values = []
    invalid_values = []
    for row in values:
        try:
            valid_values.append(row) if filter_by(row) else invalid_values.append(row)
        except ValueError as e:
            logger.error(e)
            continue

    return valid_values, invalid_values


def _transform_values(values: List[List], name: str) -> Dict[Tuple, List]:
    to_return: Dict[Tuple, List] = defaultdict(list)
    for row in values:
        tup = tuple(row[1:3])
        to_return[tup].append(row[3:])

    return to_return


def extract_values(sheet: Worksheet, name: str = None) -> tuple[dict[tuple, list], dict[tuple, list]]:
    values: List[List] = sheet.get_values()[1:-2]
    valid_values, invalid_values = _cleanup_values(values)
    return _transform_values(valid_values, name), _transform_values(invalid_values, name)


def _get_next_row(sheet: Worksheet) -> int:
    cells = sheet.findall(DELIMITER)
    return (cells and cells[-1].row or 0) + 1


def write_legend(sheet: Worksheet):
    global write_requests
    values = [[
        "Found Match",
        "Diffs in matched rows",
        "In One but not the Other",
        "Invalids",
        "No match"
    ]]
    formats = [
        BackgroundColor.LIGHT_GREEN,
        BackgroundColor.YELLOW,
        BackgroundColor.ORANGE,
        BackgroundColor.PURPLE,
        BackgroundColor.RED
    ]

    vrange = Range.from_first_and_values(values)

    write_requests += 1
    sheet.update(*_add_separator(vrange, values))

    format_request = FormatRequest()
    for i, f in enumerate(formats):
        frange = f"{string.ascii_uppercase[i]}1:{string.ascii_uppercase[i]}1"

        format_request.add_request(format_cells(frange, f.value, sheet.id))

    write_requests += 1
    sheet.spreadsheet.batch_update(format_request.request)


def _add_separator(values_range: Range, values: List[List]):
    values_range.second_row += 1
    return values_range, values + [["~~~"]]


def write_values(sheet: Worksheet, values: List[List[str]], formatting: List[Tuple[Range, BackgroundColor]] = None):
    global write_requests

    start_row = _get_next_row(sheet)
    values_range = Range.from_first_and_values(values, "A", start_row)

    ranges, final_values = _add_separator(values_range, values)

    write_requests += 1
    sheet.update(str(ranges), final_values)

    format_request = FormatRequest()
    for r, f in formatting or []:
        if f == BackgroundColor.WHITE:
            continue

        r.add_to_rows(start_row - 1)
        format_request.add_request(format_cells(str(r), f.value, sheet.id))

    write_requests += 1
    sheet.spreadsheet.batch_update(format_request.request)


def create_worksheet(
        spreadsheet: Spreadsheet,
        name: str = "Report results",
        rows: int = 100,
        cols: int = 26
) -> Worksheet:
    global write_requests
    write_requests += 1
    return spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)
