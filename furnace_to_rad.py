#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path


RAD_MAGIC = b"RAD by REALiTY!!"
RAD_VERSION = 0x10
CHANNEL_COUNT = 9
MAX_PATTERNS = 32

NOTE_TO_RAD = {
    "C#": 1,
    "D-": 2,
    "D#": 3,
    "E-": 4,
    "F-": 5,
    "F#": 6,
    "G-": 7,
    "G#": 8,
    "A-": 9,
    "A#": 10,
    "B-": 11,
    "C-": 12,
}


@dataclass
class OpParams:
    am: int = 0
    vib: int = 0
    sus: int = 0
    ksr: int = 0
    mult: int = 0
    ksl: int = 0
    tl: int = 0
    ar: int = 0
    dr: int = 0
    sl: int = 0
    rr: int = 0
    ws: int = 0


@dataclass
class Instrument:
    furnace_id: int
    alg: int = 0
    fb: int = 0
    op0: OpParams = field(default_factory=OpParams)
    op1: OpParams = field(default_factory=OpParams)


@dataclass
class SongData:
    speed: int
    pattern_length: int
    orders: list[int]
    patterns_by_order: dict[int, list[str]]
    pattern_for_number: dict[int, list[str]]
    instruments: dict[int, Instrument]


def parse_int(value: str) -> int:
    return int(value.strip())


def parse_song(text: str) -> SongData:
    lines = text.splitlines()

    if "- system: Yamaha YM3812 (OPL2)" not in text:
        raise ValueError("This converter currently supports only OPL2 Furnace exports.")

    instruments = parse_instruments(lines)
    speed = parse_speed(lines)
    pattern_length = parse_pattern_length(lines)
    orders = parse_orders(lines)
    patterns_by_order = parse_order_patterns(lines)

    pattern_for_number: dict[int, list[str]] = {}
    for order_index, pattern_number in enumerate(orders):
        if pattern_number not in pattern_for_number:
            block = patterns_by_order.get(order_index)
            if block is None:
                raise ValueError(f"Missing pattern block for order {order_index:02X}.")
            pattern_for_number[pattern_number] = block

    return SongData(
        speed=speed,
        pattern_length=pattern_length,
        orders=orders,
        patterns_by_order=patterns_by_order,
        pattern_for_number=pattern_for_number,
        instruments=instruments,
    )


def parse_speed(lines: list[str]) -> int:
    # Find tick rate and speed
    tick_rate_line = next((line for line in lines if line.strip().startswith("- tick rate:")), None)
    speed_line = next((line for line in lines if line.strip().startswith("- speeds:")), None)
    
    if speed_line is None:
        raise ValueError("Could not find speed in Furnace text export.")
    
    # Parse tick rate (default 60Hz for most trackers)
    tick_rate = 60
    if tick_rate_line:
        tick_rate_text = tick_rate_line.split(":", 1)[1].strip()
        tick_rate = int(tick_rate_text)
    
    # Parse speed (ticks per row)
    speed_text = speed_line.split(":", 1)[1].strip()
    if "," in speed_text:
        speed_text = speed_text.split(",", 1)[0].strip()
    furnace_speed = int(speed_text)
    
    # Convert to RAD speed: RAD uses 50Hz timer
    # Furnace rows/sec = tick_rate / furnace_speed
    # RAD speed needed = 50 / (tick_rate / furnace_speed) = 50 * furnace_speed / tick_rate
    rad_speed = round(50 * furnace_speed / tick_rate)
    
    if rad_speed < 1:
        rad_speed = 1
    if rad_speed > 31:
        rad_speed = 31
    return rad_speed


def parse_pattern_length(lines: list[str]) -> int:
    pattern_length_line = next(
        (line for line in lines if line.strip().startswith("- pattern length:")),
        None,
    )
    if pattern_length_line is None:
        raise ValueError("Could not find pattern length in Furnace text export.")

    pattern_length = int(pattern_length_line.split(":", 1)[1].strip())
    if pattern_length < 1:
        raise ValueError("Pattern length must be at least 1.")
    if pattern_length > 64:
        raise ValueError("Pattern length above 64 is not supported by RAD.")
    return pattern_length


def parse_instruments(lines: list[str]) -> dict[int, Instrument]:
    in_instruments = False
    current_inst: Instrument | None = None
    current_op: OpParams | None = None
    instruments: dict[int, Instrument] = {}

    header_re = re.compile(r"^##\s+([0-9A-Fa-f]{2}):")

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        if stripped == "# Instruments":
            in_instruments = True
            continue
        if in_instruments and stripped == "# Wavetables":
            break
        if not in_instruments:
            continue

        match = header_re.match(stripped)
        if match:
            furnace_id = int(match.group(1), 16)
            current_inst = Instrument(furnace_id=furnace_id)
            instruments[furnace_id] = current_inst
            current_op = None
            continue

        if current_inst is None:
            continue

        if stripped.startswith("- operator 0:"):
            current_op = current_inst.op0
            continue
        if stripped.startswith("- operator 1:"):
            current_op = current_inst.op1
            continue

        if stripped.startswith("- ALG:"):
            current_inst.alg = parse_int(stripped.split(":", 1)[1])
            continue
        if stripped.startswith("- FB:"):
            current_inst.fb = parse_int(stripped.split(":", 1)[1])
            continue

        if current_op is None:
            continue

        if stripped.startswith("- AM:"):
            current_op.am = parse_int(stripped.split(":", 1)[1])
        elif stripped.startswith("- VIB:"):
            current_op.vib = parse_int(stripped.split(":", 1)[1])
        elif stripped.startswith("- SUS:"):
            current_op.sus = parse_int(stripped.split(":", 1)[1])
        elif stripped.startswith("- KSR:"):
            current_op.ksr = parse_int(stripped.split(":", 1)[1])
        elif stripped.startswith("- MULT:"):
            current_op.mult = parse_int(stripped.split(":", 1)[1])
        elif stripped.startswith("- KSL:"):
            current_op.ksl = parse_int(stripped.split(":", 1)[1])
        elif stripped.startswith("- TL:"):
            current_op.tl = parse_int(stripped.split(":", 1)[1])
        elif stripped.startswith("- AR:"):
            current_op.ar = parse_int(stripped.split(":", 1)[1])
        elif stripped.startswith("- DR:"):
            current_op.dr = parse_int(stripped.split(":", 1)[1])
        elif stripped.startswith("- SL:"):
            current_op.sl = parse_int(stripped.split(":", 1)[1])
        elif stripped.startswith("- RR:"):
            current_op.rr = parse_int(stripped.split(":", 1)[1])
        elif stripped.startswith("- WS:"):
            current_op.ws = parse_int(stripped.split(":", 1)[1])

    if not instruments:
        raise ValueError("No instruments parsed from Furnace text export.")
    return instruments


def parse_orders(lines: list[str]) -> list[int]:
    orders_start = None
    for index, line in enumerate(lines):
        if line.strip() == "orders:":
            orders_start = index
            break
    if orders_start is None:
        raise ValueError("Could not find orders section.")

    order_lines: list[str] = []
    in_block = False
    for line in lines[orders_start + 1 :]:
        stripped = line.strip()
        if stripped == "```":
            in_block = not in_block
            if not in_block:
                break
            continue
        if in_block and stripped:
            order_lines.append(stripped)

    if not order_lines:
        raise ValueError("Order list block is empty.")

    orders: list[int] = []
    for row in order_lines:
        if "|" not in row:
            continue
        _, right = row.split("|", 1)
        values = right.strip().split()
        if len(values) < CHANNEL_COUNT:
            raise ValueError(f"Order row has fewer than {CHANNEL_COUNT} channels: {row}")
        channel_values = [int(value, 16) for value in values[:CHANNEL_COUNT]]
        first = channel_values[0]
        if any(value != first for value in channel_values[1:]):
            raise ValueError(
                "Per-channel order lists differ; RAD supports one global order list only."
            )
        if first >= MAX_PATTERNS:
            raise ValueError(f"Pattern {first} is out of RAD range 0..31.")
        orders.append(first)

    if not orders:
        raise ValueError("No orders were parsed.")
    if len(orders) > 128:
        raise ValueError("Order list exceeds RAD maximum of 128 entries.")
    return orders


def parse_order_patterns(lines: list[str]) -> dict[int, list[str]]:
    sections: dict[int, list[str]] = {}
    current_order: int | None = None
    current_rows: list[str] = []

    order_header = re.compile(r"^----- ORDER\s+([0-9A-Fa-f]{2})")
    row_line = re.compile(r"^[0-9A-Fa-f]{2}\s+\|")

    for raw in lines:
        stripped = raw.strip()
        header_match = order_header.match(stripped)
        if header_match:
            if current_order is not None:
                sections[current_order] = current_rows
            current_order = int(header_match.group(1), 16)
            current_rows = []
            continue
        if current_order is not None and row_line.match(stripped):
            current_rows.append(stripped)

    if current_order is not None:
        sections[current_order] = current_rows

    if not sections:
        raise ValueError("No pattern data blocks found.")
    return sections


def opl_operator_registers(op: OpParams) -> tuple[int, int, int, int, int]:
    reg20 = (
        ((op.am & 1) << 7)
        | ((op.vib & 1) << 6)
        | ((op.sus & 1) << 5)
        | ((op.ksr & 1) << 4)
        | (op.mult & 0x0F)
    )
    reg40 = ((op.ksl & 0x03) << 6) | (op.tl & 0x3F)
    reg60 = ((op.ar & 0x0F) << 4) | (op.dr & 0x0F)
    reg80 = ((op.sl & 0x0F) << 4) | (op.rr & 0x0F)
    regE0 = op.ws & 0x03
    return reg20, reg40, reg60, reg80, regE0


def pack_rad_instrument(inst: Instrument) -> bytes:
    mod = inst.op0
    car = inst.op1

    car20, car40, car60, car80, carE0 = opl_operator_registers(car)
    mod20, mod40, mod60, mod80, modE0 = opl_operator_registers(mod)
    regC0 = ((inst.fb & 0x07) << 1) | (inst.alg & 0x01)

    return bytes(
        [
            car20,
            mod20,
            car40,
            mod40,
            car60,
            mod60,
            car80,
            mod80,
            regC0,
            carE0,
            modE0,
        ]
    )


def parse_effect(effect_token: str) -> tuple[int, int]:
    if effect_token == "....":
        return 0, 0
    if re.fullmatch(r"[0-9A-Fa-f]{4}", effect_token):
        effect_nibble = int(effect_token[0], 16)
        parameter = int(effect_token[2:], 16)
        if parameter > 99:
            parameter = 99
        return effect_nibble, parameter
    return 0, 0


def encode_note(note_token: str, instrument: int, effect: int, param: int) -> bytes:
    if note_token == "...":
        octave = 0
        note_value = 0
    elif note_token == "OFF":
        octave = 0
        note_value = 0x0F
    else:
        pitch = note_token[:2]
        octave = int(note_token[2])
        if pitch not in NOTE_TO_RAD:
            raise ValueError(f"Unsupported note token: {note_token}")
        note_value = NOTE_TO_RAD[pitch]
        
        # RAD octave boundary is at C#, Furnace is at C
        # So Furnace C-3 → RAD octave 2, note 12
        # But Furnace C#3 → RAD octave 3, note 1
        if pitch == "C-":
            octave -= 1

    byte0 = ((instrument >> 4) & 0x01) << 7
    byte0 |= (octave & 0x07) << 4
    byte0 |= note_value & 0x0F
    byte1 = ((instrument & 0x0F) << 4) | (effect & 0x0F)

    if effect:
        return bytes([byte0, byte1, param & 0x7F])
    return bytes([byte0, byte1])


def parse_pattern_row(row: str) -> tuple[int, list[tuple[str, str, int, int]]]:
    line_index_text, cells_text = row.split("|", 1)
    line_index = int(line_index_text.strip(), 16)
    cells = cells_text.split("|")
    if len(cells) < CHANNEL_COUNT:
        raise ValueError(f"Pattern row has fewer than {CHANNEL_COUNT} channels: {row}")

    channel_entries: list[tuple[str, str, int, int]] = []
    for channel in range(CHANNEL_COUNT):
        cell = cells[channel].strip()
        parts = cell.split()
        if len(parts) < 4:
            raise ValueError(f"Unexpected cell format: {cell}")

        note_token = parts[0]
        inst_token = parts[1]
        effect, parameter = parse_effect(parts[3])
        channel_entries.append((note_token, inst_token, effect, parameter))

    return line_index, channel_entries


def inject_pattern_break(
    row_entries: dict[int, list[tuple[str, str, int, int]]], pattern_length: int
) -> None:
    if pattern_length >= 64:
        return

    break_line = pattern_length - 1
    channel_entries = row_entries.setdefault(
        break_line,
        [("...", "..", 0, 0) for _ in range(CHANNEL_COUNT)],
    )

    for channel, (note_token, inst_token, effect, parameter) in enumerate(channel_entries):
        if effect == 0x0D and parameter == 0:
            return
        if effect == 0:
            channel_entries[channel] = (note_token, inst_token, 0x0D, 0)
            return

    raise ValueError(
        f"Cannot inject RAD pattern break on line {break_line:02X}; all channels already use effects."
    )


def encode_pattern(rows: list[str], used_instruments: set[int], pattern_length: int) -> bytes:
    encoded_lines: list[tuple[int, bytes]] = []
    row_entries: dict[int, list[tuple[str, str, int, int]]] = {}

    for row in rows:
        line_index, channel_entries = parse_pattern_row(row)
        row_entries[line_index] = channel_entries

    inject_pattern_break(row_entries, pattern_length)

    for line_index in sorted(row_entries):
        channel_entries = row_entries[line_index]

        channel_events: list[tuple[int, bytes]] = []
        for channel in range(CHANNEL_COUNT):
            note_token, inst_token, effect, parameter = channel_entries[channel]

            instrument = 0
            if inst_token != "..":
                furnace_inst = int(inst_token, 16)
                instrument = furnace_inst + 1
                used_instruments.add(furnace_inst)

            if note_token == "..." and instrument == 0 and effect == 0:
                continue

            note_bytes = encode_note(note_token, instrument, effect, parameter)
            channel_events.append((channel, note_bytes))

        if channel_events:
            packed = bytearray()
            for index, (channel, note_bytes) in enumerate(channel_events):
                channel_byte = channel
                if index == len(channel_events) - 1:
                    channel_byte |= 0x80
                packed.append(channel_byte)
                packed.extend(note_bytes)
            encoded_lines.append((line_index, bytes(packed)))

    if not encoded_lines:
        return b""

    output = bytearray()
    for line_number, packed in encoded_lines:
        marker = line_number
        if line_number == encoded_lines[-1][0]:
            marker |= 0x80
        output.append(marker)
        output.extend(packed)
    return bytes(output)


def build_rad(song: SongData) -> bytes:
    used_instruments: set[int] = set()

    pattern_data: dict[int, bytes] = {}
    for pattern_number, rows in song.pattern_for_number.items():
        pattern_data[pattern_number] = encode_pattern(rows, used_instruments, song.pattern_length)

    module = bytearray()
    module.extend(RAD_MAGIC)
    module.append(RAD_VERSION)
    module.append(song.speed & 0x1F)

    for furnace_id in sorted(used_instruments):
        rad_id = furnace_id + 1
        if rad_id < 1 or rad_id > 31:
            raise ValueError(f"Instrument id {furnace_id} is out of RAD range.")
        inst = song.instruments.get(furnace_id)
        if inst is None:
            raise ValueError(f"Pattern references missing instrument {furnace_id:02X}.")
        module.append(rad_id)
        module.extend(pack_rad_instrument(inst))
    module.append(0)

    module.append(len(song.orders))
    module.extend(song.orders)

    pattern_offset_table_pos = len(module)
    module.extend(b"\x00" * (MAX_PATTERNS * 2))

    pattern_offsets = [0] * MAX_PATTERNS
    for pattern_number in range(MAX_PATTERNS):
        data = pattern_data.get(pattern_number, b"")
        if not data:
            continue
        pattern_offsets[pattern_number] = len(module)
        module.extend(data)

    for index, offset in enumerate(pattern_offsets):
        pos = pattern_offset_table_pos + index * 2
        module[pos] = offset & 0xFF
        module[pos + 1] = (offset >> 8) & 0xFF

    return bytes(module)


def convert_file(input_path: Path, output_path: Path) -> None:
    text = input_path.read_text(encoding="utf-8")
    song = parse_song(text)
    rad = build_rad(song)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(rad)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a Furnace OPL2 text export to RAD tracker module format."
    )
    parser.add_argument("input", type=Path, help="Path to Furnace text export (.txt)")
    parser.add_argument("output", type=Path, help="Path to output .rad file")
    args = parser.parse_args()

    convert_file(args.input, args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
