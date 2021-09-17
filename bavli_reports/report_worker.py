import logging
from typing import Tuple, List, Dict, Callable

from gspread import WorksheetNotFound

from bavli_reports.google_connection import get_report_by_url, extract_values, create_worksheet, write_values, \
    write_legend, get_connection
from bavli_reports.models import RowDiffs, BackgroundColor, Format, Range

BAVLI_REPORT: str = "https://docs.google.com/spreadsheets/d/1nwvOZ1P2jzKfUuQnfA3eslZp9VK-FbhYbw5Npnue9T0/edit#gid=96750267"
EXTERNAL_REPORT: str = "https://docs.google.com/spreadsheets/d/1nwvOZ1P2jzKfUuQnfA3eslZp9VK-FbhYbw5Npnue9T0/edit#gid=96750267"

logger = logging.getLogger(__name__)


def get_match_row(truth, check):
    for row in check:
        if row[0] == truth[0]:
            return row
    return []


def scan_by_key(key: Tuple, values: List[List]) -> Tuple[Dict, List[RowDiffs]]:
    bavli = values[0]
    external = values[1]

    matches: List[RowDiffs] = []
    mismatch_bavli = []
    mismatch_external = external.copy()

    for row in bavli:
        matched_external_row = get_match_row(row, mismatch_external)
        if matched_external_row:
            mismatch_external.remove(matched_external_row)
            matches.append(RowDiffs(row, matched_external_row))
        else:
            mismatch_bavli.append(row)

    mismatches = {("bavli", *key): mismatch_bavli} if mismatch_bavli else {}
    mismatches.update({("external", *key): mismatch_external} if mismatch_external else {})

    return mismatches, matches


def format_to_gsheet_values(values: Dict[Tuple, List], sort: bool = True) -> List[List]:
    to_return: List[List] = []
    for k, v in values.items():
        if type(v) == list:
            for inner_list in v:
                to_return.append([*k, *inner_list])
        else:
            to_return.append([*k, *v])

    return sort and sorted(to_return, key=lambda x: tuple(x[1:])) or to_return


def get_formatting_settings(values: List[List], colors: Tuple[BackgroundColor, BackgroundColor]) -> List[Tuple[Range, BackgroundColor]]:
    if not values:
        return []

    def get_key(line):
        return line[1:3]

    cur_color = colors[0]
    inspecting_key = get_key(values[0])
    to_return: List[Tuple[Range, BackgroundColor]] = []
    cur_range = Range(second_column=Range.int_to_column(len(values[0])))
    for i, row in enumerate(values):
        cur_key = get_key(row)
        if cur_key != inspecting_key:
            cur_range.second_row = i
            to_return.append((cur_range, cur_color))

            cur_color = colors[0] if cur_color == colors[1] else colors[1]
            cur_range = Range(first_row=i+1, second_column=cur_range.second_column)
            inspecting_key = cur_key

    cur_range.second_row = len(values)
    to_return.append((cur_range, cur_color))
    return to_return


def do_report_work(
        bavli_report_url: str = BAVLI_REPORT,
        external_report_url: str = EXTERNAL_REPORT,
        show_matches: bool = False,
        logging_func: Callable = logger.info
):
    logging_func("Getting connecting to Google")
    connection = get_connection()

    logging_func("Fetching google sheets")
    bavli_sheet = get_report_by_url(bavli_report_url, connection=connection)
    external_sheet = get_report_by_url(external_report_url, connection=connection)

    logging_func("Getting the good parts out of it")
    bavli_values, invalid_values = extract_values(bavli_sheet.sheet1, "bavli")
    external_values, invalid_external_values = extract_values(
        external_sheet.sheet1 if external_report_url != EXTERNAL_REPORT else external_sheet.get_worksheet(1),
        "external"
    )
    def create_named_key(name: str, key: tuple): return name, *key

    logging_func("Cutting, shuffling, mixing, cooking and grilling the data")
    # those which are present in one sheet but not the other
    outliers = {
        **{create_named_key("bavli", k): v for k, v in bavli_values.items() if k not in external_values},
        **{create_named_key("external", k): v for k, v in external_values.items() if k not in bavli_values},
    }
    # invalids
    invalids = {
        **{create_named_key("bavli", k): v for k, v in invalid_values.items()},
        **{create_named_key("external", k): v for k, v in invalid_external_values.items()}
    }

    intersection = {
        k: [bavli_values[k], external_values[k]] for k in bavli_values.keys() if k in external_values
    }
    # those which are present on both but value is a mismatch
    mismatches = {}
    all_matches: List[RowDiffs] = []
    for k, v in intersection.items():
        misses, matches = scan_by_key(k, v)
        mismatches.update(misses)
        all_matches.extend(matches)

    try:
        logging_func("Shit is smelling good! Im creating a new sheet for the report now")
        new_worksheet = bavli_sheet.worksheet("Report results")
    except WorksheetNotFound:
        new_worksheet = create_worksheet(bavli_sheet, rows=(
            len(mismatches) + len(all_matches)*2 + len(invalids) + len(outliers) + 150
        ))

    write_legend(new_worksheet)

    vals_to_write = format_to_gsheet_values(mismatches)
    formats = get_formatting_settings(vals_to_write, (BackgroundColor.RED, BackgroundColor.LIGHT_RED))
    write_values(sheet=new_worksheet, values=vals_to_write, formatting=formats)

    vals_to_write = format_to_gsheet_values(outliers)
    formats = get_formatting_settings(vals_to_write, (BackgroundColor.PURPLE, BackgroundColor.WHITE))
    write_values(sheet=new_worksheet, values=vals_to_write, formatting=formats)

    vals_to_write = format_to_gsheet_values(invalids)
    formats = get_formatting_settings(vals_to_write, (BackgroundColor.ORANGE, BackgroundColor.WHITE))
    write_values(sheet=new_worksheet, values=vals_to_write, formatting=formats)

    if show_matches:
        pass

    TAB = " " * 4
    logging_func("DONE!")
    logging_func("")
    logging_func("Here is what i found:")
    logging_func(
        f"{TAB}There are {len(mismatches)} mismatches marked red and light red. You should go over them to see whats wrong.",
        level=logging.ERROR
    )
    logging_func(
        f"{TAB}There are {len(outliers)} rows marked in purple. Those bitches are found in one sheet but not the other for some reason",
        level=logging.DEBUG
    )
    logging_func(
        f"{TAB}There are {len(invalids)} rows marked in orange. Those lil MF are simply invalid to what we said (house number or zip code are not numbers)",
        level=logging.WARNING
    )
    if show_matches:
        logging_func(
            f"{TAB}There are {len(all_matches)} matched rows! Wohoo, those are marked light green and are matching. Note that some might different values in some parts(such as `notes`)",
            level=logging.NOTSET
        )
