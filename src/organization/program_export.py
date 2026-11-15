"""Excel export of an event's rammeprogram.

The layout follows the reference `Rammeprogram` spreadsheets:

* one row per 30 minutes, with the hour shown once in the left-hand time bar
* one column per day (extra columns when blocks overlap on the same day)
* the day header is merged across those columns
* a block is merged vertically from the first 30-minute slot it touches to the
  last one, so blocks that cross an hour line read as one cell
* category colours match the web calendar, and shared framework blocks use a
  dashed border
* a legend below the grid explains the colours and the dashed border

Only the block title is exported; content and responsible volunteers stay in
the web application.
"""

from __future__ import annotations

from io import BytesIO
from math import ceil

from django.utils import timezone
from django.utils.text import slugify
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

from .models import ProgramBlock

SLOT_MINUTES = 30
DEFAULT_START_HOUR = 6
DEFAULT_END_HOUR = 24
WEEKDAYS = (
    'Mandag', 'Tirsdag', 'Onsdag', 'Torsdag', 'Fredag', 'Lørdag', 'Søndag',
)

CATEGORY_COLOURS = {
    ProgramBlock.CATEGORY_FIXED: {
        'fill': 'FF733C',
        'ink': '2B1200',
        'label': 'Fast program',
    },
    ProgramBlock.CATEGORY_RECOMMENDED: {
        'fill': '00223A',
        'ink': 'FFFFFF',
        'label': 'Anbefaling',
    },
    ProgramBlock.CATEGORY_PLACEHOLDER: {
        'fill': '771B2A',
        'ink': 'FFFFFF',
        'label': 'Plads til eget program',
    },
    ProgramBlock.CATEGORY_PREPARATION: {
        'fill': '334730',
        'ink': 'FFFFFF',
        'label': 'Forberedelse',
    },
}

TITLE_FILL = PatternFill('solid', fgColor='00223A')
SUBTITLE_FILL = PatternFill('solid', fgColor='F1F3F5')
HEADER_FILL = PatternFill('solid', fgColor='00223A')
GUTTER_FILL = PatternFill('solid', fgColor='E9ECEF')
EMPTY_FILL = PatternFill('solid', fgColor='FBFBFC')

WHITE_SIDE = Side(style='thin', color='FFFFFF')
GRID_SIDE = Side(style='thin', color='D5DBE1')
DASHED_SIDE = Side(style='mediumDashed', color='FFFFFF')
GRID_BORDER = Border(
    left=GRID_SIDE, right=GRID_SIDE, top=GRID_SIDE, bottom=GRID_SIDE
)
BLOCK_BORDER = Border(
    left=WHITE_SIDE, right=WHITE_SIDE, top=WHITE_SIDE, bottom=WHITE_SIDE
)
FRAMEWORK_BORDER = Border(
    left=DASHED_SIDE, right=DASHED_SIDE, top=DASHED_SIDE, bottom=DASHED_SIDE
)


def _paint(
    worksheet,
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
    *,
    fill=None,
    font=None,
    alignment=None,
    border=None,
) -> None:
    """Apply styles to every cell in a range before it is merged."""
    for row in worksheet.iter_rows(
        min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col
    ):
        for cell in row:
            if fill is not None:
                cell.fill = fill
            if font is not None:
                cell.font = font
            if alignment is not None:
                cell.alignment = alignment
            if border is not None:
                cell.border = border


def _merge(worksheet, min_row: int, min_col: int, max_row: int, max_col: int) -> None:
    if (min_row, min_col) != (max_row, max_col):
        worksheet.merge_cells(
            start_row=min_row,
            start_column=min_col,
            end_row=max_row,
            end_column=max_col,
        )


def _block_slots(block, first_slot: int, slot_count: int) -> tuple[int, int]:
    """Return the half-open slot range covered by ``block``.

    A block that starts or ends between two 30-minute marks is widened to the
    slots it touches, so the exported cell never hides part of the block.
    """
    start_slot = (block.start_minutes // SLOT_MINUTES) - first_slot
    end_slot = ceil(block.end_minutes / SLOT_MINUTES) - first_slot
    start_slot = max(0, start_slot)
    end_slot = max(start_slot + 1, min(slot_count, end_slot))
    return start_slot, end_slot


def _assign_lanes(blocks, first_slot: int, slot_count: int):
    """Place a day's blocks side by side when they overlap.

    Returns ``(entries, lane_count)`` where each entry is
    ``(block, start_slot, end_slot, lane)``.
    """
    entries = [
        (block, *_block_slots(block, first_slot, slot_count))
        for block in blocks
    ]
    entries.sort(key=lambda entry: (entry[1], -entry[2], entry[0].pk))

    lane_ends: list[int] = []
    placed = []
    for block, start_slot, end_slot in entries:
        for lane, lane_end in enumerate(lane_ends):
            if start_slot >= lane_end:
                lane_ends[lane] = end_slot
                break
        else:
            lane = len(lane_ends)
            lane_ends.append(end_slot)
        placed.append((block, start_slot, end_slot, lane))

    return placed, max(1, len(lane_ends))


def _day_label(day) -> str:
    return f'{WEEKDAYS[day.weekday()]}\n{day:%d/%m}'


def _scope_filename(event, selected_team, all_teams) -> str:
    name = slugify(event.name) or f'event-{event.pk}'
    if all_teams:
        suffix = 'alle-teams'
    elif selected_team is not None:
        suffix = slugify(selected_team.name) or f'team-{selected_team.pk}'
    else:
        suffix = 'faelles'
    return f'rammeprogram-{name}-{suffix}.xlsx'


def build_program_workbook(
    *,
    event,
    blocks,
    days,
    scope_label: str,
    include_team_names: bool = False,
    exported_at=None,
) -> bytes:
    """Build the export and return the ``.xlsx`` bytes."""
    if exported_at is None:
        exported_at = timezone.localtime()
    blocks = list(blocks)
    days = list(days)

    start_hour = DEFAULT_START_HOUR
    if blocks:
        start_hour = min(start_hour, min(block.start_time.hour for block in blocks))
    end_hour = DEFAULT_END_HOUR
    if blocks:
        end_hour = max(end_hour, ceil(max(block.end_minutes for block in blocks) / 60))
    end_hour = max(start_hour + 1, end_hour)

    first_slot = start_hour * 60 // SLOT_MINUTES
    last_slot = end_hour * 60 // SLOT_MINUTES
    slot_count = last_slot - first_slot

    title_row = 1
    subtitle_row = 2
    header_row = 3
    first_grid_row = 4

    day_layouts = []
    next_column = 2
    for day in days:
        day_blocks = [block for block in blocks if block.day == day]
        placed, lane_count = _assign_lanes(day_blocks, first_slot, slot_count)
        columns = list(range(next_column, next_column + lane_count))
        day_layouts.append(
            {
                'day': day,
                'columns': columns,
                'entries': placed,
            }
        )
        next_column += lane_count

    last_column = max(2, next_column - 1)
    last_grid_row = first_grid_row + slot_count - 1

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Rammeprogram'
    worksheet.sheet_view.showGridLines = False

    # Title and context.
    worksheet.cell(title_row, 1, f'Rammeprogram - {event.name}')
    worksheet.cell(
        subtitle_row,
        1,
        f'{event.start_date:%d.%m.%Y} - {event.end_date:%d.%m.%Y} · '
        f'{scope_label} · Eksporteret {exported_at:%d.%m.%Y %H:%M}',
    )
    _paint(
        worksheet, title_row, title_row, 1, last_column,
        fill=TITLE_FILL,
        font=Font(color='FFFFFF', bold=True, size=16),
        alignment=Alignment(vertical='center', horizontal='left'),
    )
    _paint(
        worksheet, subtitle_row, subtitle_row, 1, last_column,
        fill=SUBTITLE_FILL,
        font=Font(color='495057', italic=True, size=10),
        alignment=Alignment(vertical='center', horizontal='left'),
    )
    _merge(worksheet, title_row, 1, title_row, last_column)
    _merge(worksheet, subtitle_row, 1, subtitle_row, last_column)

    # Column widths / row heights.
    worksheet.column_dimensions['A'].width = 9
    for layout in day_layouts:
        for column in layout['columns']:
            worksheet.column_dimensions[get_column_letter(column)].width = 22
    worksheet.row_dimensions[title_row].height = 30
    worksheet.row_dimensions[subtitle_row].height = 20
    worksheet.row_dimensions[header_row].height = 34
    for row in range(first_grid_row, last_grid_row + 1):
        worksheet.row_dimensions[row].height = 20

    # Header row: time gutter and one merged date header per day.
    worksheet.cell(header_row, 1, 'Tid')
    _paint(
        worksheet, header_row, header_row, 1, 1,
        fill=HEADER_FILL,
        font=Font(color='FFFFFF', bold=True, size=10),
        alignment=Alignment(horizontal='center', vertical='center'),
        border=GRID_BORDER,
    )
    for layout in day_layouts:
        first_column = layout['columns'][0]
        last_day_column = layout['columns'][-1]
        worksheet.cell(header_row, first_column, _day_label(layout['day']))
        _paint(
            worksheet, header_row, header_row, first_column, last_day_column,
            fill=HEADER_FILL,
            font=Font(color='FFFFFF', bold=True, size=11),
            alignment=Alignment(
                horizontal='center', vertical='center', wrap_text=True
            ),
            border=GRID_BORDER,
        )
        _merge(worksheet, header_row, first_column, header_row, last_day_column)

    # Empty grid cells, so the sheet reads as a table even without blocks.
    for row in range(first_grid_row, last_grid_row + 1):
        for layout in day_layouts:
            for column in layout['columns']:
                cell = worksheet.cell(row, column)
                cell.fill = EMPTY_FILL
                cell.border = GRID_BORDER

    # Hour bars in the left column, each merged over its two 30-minute slots.
    for hour in range(start_hour, end_hour):
        row = first_grid_row + (hour * 60 - first_slot * SLOT_MINUTES) // SLOT_MINUTES
        next_row = min(row + 2, last_grid_row + 1)
        worksheet.cell(row, 1, f'{hour:02d}.00')
        _paint(
            worksheet, row, next_row - 1, 1, 1,
            fill=GUTTER_FILL,
            font=Font(color='343A40', bold=True, size=9),
            alignment=Alignment(horizontal='right', vertical='top'),
            border=GRID_BORDER,
        )
        _merge(worksheet, row, 1, next_row - 1, 1)

    # Blocks. Titles only, as requested; the position carries the time.
    for layout in day_layouts:
        for block, start_slot, end_slot, lane in layout['entries']:
            column = layout['columns'][lane]
            row = first_grid_row + start_slot
            end_row = first_grid_row + end_slot - 1
            title = block.title
            if include_team_names and block.team is not None:
                title = f'{block.team.short_name}: {title}'

            palette = CATEGORY_COLOURS.get(
                block.category, CATEGORY_COLOURS[ProgramBlock.CATEGORY_FIXED]
            )
            fill = PatternFill('solid', fgColor=palette['fill'])
            border = (
                FRAMEWORK_BORDER if block.team_id is None else BLOCK_BORDER
            )
            worksheet.cell(row, column, title)
            _paint(
                worksheet, row, end_row, column, column,
                fill=fill,
                font=Font(color=palette['ink'], bold=True, size=10),
                alignment=Alignment(
                    horizontal='left',
                    vertical='center',
                    wrap_text=end_row > row,
                    shrink_to_fit=end_row == row,
                ),
                border=border,
            )
            _merge(worksheet, row, column, end_row, column)

    # Legend.
    legend_title_row = last_grid_row + 2
    legend_row = last_grid_row + 3
    worksheet.cell(legend_title_row, 1, 'Forklaring')
    _paint(
        worksheet, legend_title_row, legend_title_row, 1, last_column,
        font=Font(color='343A40', bold=True, size=11),
        alignment=Alignment(vertical='center'),
    )
    _merge(worksheet, legend_title_row, 1, legend_title_row, last_column)

    legend_entries = [
        (
            category['label'],
            PatternFill('solid', fgColor=category['fill']),
            category['ink'],
            BLOCK_BORDER,
        )
        for category in CATEGORY_COLOURS.values()
    ]
    legend_entries.append(
        ('Fælles program (stiplet kant)', TITLE_FILL, 'FFFFFF', FRAMEWORK_BORDER)
    )

    legend_column = 2
    legend_current_row = legend_row
    legend_rows = set()
    for label, fill, ink, border in legend_entries:
        if legend_column > last_column:
            legend_column = 2
            legend_current_row += 1
        worksheet.cell(legend_current_row, legend_column, label)
        _paint(
            worksheet, legend_current_row, legend_current_row,
            legend_column, legend_column,
            fill=fill,
            font=Font(color=ink, bold=True, size=10),
            alignment=Alignment(
                horizontal='center', vertical='center', wrap_text=True
            ),
            border=border,
        )
        legend_rows.add(legend_current_row)
        legend_column += 1

    for row in legend_rows:
        worksheet.row_dimensions[row].height = 32

    note_row = legend_current_row + 2
    worksheet.cell(
        note_row,
        1,
        'Kun titler eksporteres. Indhold og ansvarlige findes i bookingsystemet. '
        'Fælles programblokke har stiplet kant.',
    )
    _paint(
        worksheet, note_row, note_row, 1, last_column,
        font=Font(color='6C757D', italic=True, size=9),
        alignment=Alignment(vertical='center', wrap_text=True),
    )
    _merge(worksheet, note_row, 1, note_row, last_column)
    worksheet.row_dimensions[note_row].height = 26

    # Printing: landscape, fit to one page wide, repeat the title/header rows.
    worksheet.freeze_panes = f'B{first_grid_row}'
    worksheet.page_setup.orientation = 'landscape'
    worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0
    worksheet.sheet_properties.pageSetUpPr.fitToPage = True
    worksheet.print_options.horizontalCentered = True
    worksheet.page_margins = PageMargins(
        left=0.3, right=0.3, top=0.4, bottom=0.5
    )
    worksheet.print_title_rows = f'1:{header_row}'
    worksheet.print_area = (
        f'A1:{get_column_letter(last_column)}{note_row}'
    )

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def filename_for_export(event, selected_team, all_teams) -> str:
    return _scope_filename(event, selected_team, all_teams)
