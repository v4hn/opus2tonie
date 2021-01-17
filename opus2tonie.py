#!/usr/bin/python3

import argparse
import glob
import hashlib
import math
import struct
import time
import tonie_header_pb2

SAMPLE_RATE_KHZ = 48

ONLY_CONVERT_FRAMEPACKING = -1
OTHER_PACKET_NEEDED = -2
DO_NOTHING = -3

OPUS_TAGS = [
    bytearray(b"\x4F\x70\x75\x73\x54\x61\x67\x73\x0D\x00\x00\x00\x4C\x61\x76\x66\x35\x38\x2E\x32\x30\x2E\x31\x30\x30\x03\x00\x00\x00\x26\x00\x00\x00\x65\x6E\x63\x6F\x64\x65\x72\x3D\x6F\x70\x75\x73\x65\x6E\x63\x20\x66\x72\x6F\x6D\x20\x6F\x70\x75\x73\x2D\x74\x6F\x6F\x6C\x73\x20\x30\x2E\x31\x2E\x31\x30\x2A\x00\x00\x00\x65\x6E\x63\x6F\x64\x65\x72\x5F\x6F\x70\x74\x69\x6F\x6E\x73\x3D\x2D\x2D\x71\x75\x69\x65\x74\x20\x2D\x2D\x62\x69\x74\x72\x61\x74\x65\x20\x39\x36\x20\x2D\x2D\x76\x62\x72\x3B\x01\x00\x00\x70\x61\x64\x3D\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30"),
    bytearray(b"\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30\x30")
]


class OpusPacket:
    def __init__(self, filehandle, size=-1, last_size=-1, dont_parse_info=False):
        self.config_value = None
        self.stereo = None
        self.framepacking = None
        self.padding = None
        self.frame_count = None
        self.frame_size = None
        self.granule = None

        if filehandle is None:
            return
        self.size = size
        self.data = filehandle.read(self.size)
        self.spanning_packet = size == 255
        self.first_packet = last_size != 255

        if self.first_packet and not dont_parse_info:
            self.parse_segment_info()


    def get_frame_count(self):
        if self.framepacking == 0:
            return 1
        elif self.framepacking == 1:
            return 2
        elif self.framepacking == 2:
            return 2
        elif self.framepacking == 3:
            unpacked = struct.unpack("<B", self.data[1:2])
            return unpacked[0] & 63

    def get_padding(self):
        if self.framepacking != 3:
            return 0
        unpacked = struct.unpack("<BB", self.data[1:3])
        is_padded = (unpacked[0] >> 6) & 1
        if not is_padded:
            return 0

        padding = unpacked[1]
        total_padding = padding
        i = 3
        while padding == 255:
            padding = struct.unpack("<B", self.data[i:i + 1])
            total_padding = total_padding + padding[0] - 1
            i = i + 1
        return total_padding


    def get_frame_size(self):
        if (self.config_value == 16) or (self.config_value == 20) or (self.config_value == 24) or (self.config_value == 28):
            return 2.5
        elif (self.config_value == 17) or (self.config_value == 21) or (self.config_value == 25) or (self.config_value == 29):
            return 5
        elif (self.config_value == 18) or (self.config_value == 22) or (self.config_value == 26) or (self.config_value == 30):
            return 10
        elif (self.config_value == 19) or (self.config_value == 23) or (self.config_value == 27) or (self.config_value == 31):
            return 20
        else:
            raise RuntimeError("Please add frame size for config value {}".format(self.config_value))


    def calc_granule(self):
        return self.frame_size * self.frame_count * SAMPLE_RATE_KHZ


    def parse_segment_info(self):
        byte = struct.unpack("<B", self.data[0:1])[0]
        self.config_value = byte >> 3
        self.stereo = (byte & 4) >> 2
        self.framepacking = byte & 3
        self.padding = self.get_padding()
        self.frame_count = self.get_frame_count()
        self.frame_size = self.get_frame_size()
        self.granule = self.calc_granule()


    def write(self, filehandle):
        if len(self.data):
            filehandle.write(self.data)


    def convert_to_framepacking_three(self):
        if self.framepacking == 3:
            return

        toc_byte = struct.unpack("<B", self.data[0:1])[0]
        toc_byte = toc_byte | 0b11

        frame_count_byte = self.frame_count
        if self.framepacking == 2:
            frame_count_byte = frame_count_byte | 0b10000000  # vbr

        self.data = struct.pack("<BB", toc_byte, frame_count_byte) + self.data[1:]
        self.framepacking = 3


    def set_pad_count(self, count):
        assert self.framepacking == 3, "Only code 3 packets can contain padding!"
        assert self.padding == 0, "Packet already padded. Not supported yet!"

        frame_count_byte = struct.unpack("<B", self.data[1:2])[0]
        frame_count_byte = frame_count_byte | 0b01000000

        pad_count_data = bytes()
        val = count
        while val > 254:
            pad_count_data = pad_count_data + b"\xFF"
            val = val - 254
        pad_count_data = pad_count_data + struct.pack("<B", val)

        self.data = self.data[0:1] + struct.pack("<B", frame_count_byte) + pad_count_data + self.data[2:]


class OggPage:
    def __init__(self, filehandle):
        self.version = None
        self.page_type = None
        self.granule_position = None
        self.serial_no = None
        self.page_no = None
        self.checksum = None
        self.segment_count = None
        self.segments = None

        if filehandle is None:
            return
        self.parse_header(filehandle)
        self.parse_segments(filehandle)


    def parse_header(self, filehandle):
        header = filehandle.read(27)
        unpacked = struct.unpack("<BBQLLLB", header[4:27])
        self.version = unpacked[0]
        self.page_type = unpacked[1]
        self.granule_position = unpacked[2]
        self.serial_no = unpacked[3]
        self.page_no = unpacked[4]
        self.checksum = unpacked[5]
        self.segment_count = unpacked[6]


    def parse_segments(self, filehandle):
        table = filehandle.read(self.segment_count)
        self.segments = []
        last_length = -1
        dont_parse_info = (self.page_no == 0) or (self.page_no == 1)

        for length in table:
            segment = OpusPacket(filehandle, length, last_length, dont_parse_info)
            last_length = length
            self.segments.append(segment)

        if self.segments[len(self.segments)-1].spanning_packet:
            raise RuntimeError("Found an opus packet spanning ogg pages. This is not supported yet.")


    def correct_values(self, last_granule):
        if len(self.segments) > 255:
            raise RuntimeError("Too many segments: {} - max 255 allowed".format(len(self.segments)))
        granule = 0
        if not (self.page_no == 0) and not (self.page_no == 1):
            for segment in self.segments:
                if segment.first_packet:
                    granule = granule + segment.granule
        self.granule_position = last_granule + granule
        self.segment_count = len(self.segments)
        self.checksum = self.calc_checksum()


    def calc_checksum(self):
        data = b"OggS" + struct.pack("<BBQLLLB", self.version, self.page_type, self.granule_position, self.serial_no, self.page_no, 0, self.segment_count)
        for segment in self.segments:
            data = data + struct.pack("<B", segment.size)
        for segment in self.segments:
            data = data + segment.data

        crc = crc32(data)
        return crc

    def get_page_size(self):
        size = 27 + len(self.segments)
        for segment in self.segments:
            size = size + len(segment.data)
        return size


    def get_size_of_first_opus_packet(self):
        if not len(self.segments):
            return 0
        segment_size = self.segments[0].size
        size = segment_size
        i = 1
        while (segment_size == 255) and (i < len(self.segments)):
            segment_size = self.segments[i].size
            size = size + segment_size
            i = i + 1
        return size


    def get_segment_count_of_first_opus_packet(self):
        if not len(self.segments):
            return 0
        segment_size = self.segments[0].size
        count = 1
        while (segment_size == 255) and (count < len(self.segments)):
            segment_size = self.segments[count].size
            count = count + 1
        return count


    def insert_empty_segment(self, index_after, spanning_packet=False, first_packet=False):
        segment = OpusPacket(None)
        segment.first_packet = first_packet
        segment.spanning_packet = spanning_packet
        segment.size = 0
        segment.data = bytes()
        self.segments.insert(index_after + 1, segment)


    def get_opus_packet_size(self, seg_start):
        size = len(self.segments[seg_start].data)
        seg_start = seg_start + 1
        while (seg_start < len(self.segments)) and not self.segments[seg_start].first_packet:
            size = size + self.segments[seg_start].size
            seg_start = seg_start + 1
        return size


    def get_segment_count_of_packet_at(self, seg_start):
        seg_end = seg_start + 1
        while (seg_end < len(self.segments)) and not self.segments[seg_end].first_packet:
            seg_end = seg_end + 1
        return seg_end - seg_start


    def redistribute_packet_data_at(self, seg_start, pad_count):
        seg_count = self.get_segment_count_of_packet_at(seg_start)
        full_data = bytes()
        for i in range(0, seg_count):
            full_data = full_data + self.segments[seg_start + i].data
        full_data = full_data + bytes(pad_count)
        size = len(full_data)

        if size < 255:
            self.segments[seg_start].size = size
            self.segments[seg_start].data = full_data
            return

        needed_seg_count = math.ceil(size / 255)
        if (size % 255) == 0:
            needed_seg_count = needed_seg_count + 1
        segments_to_create = needed_seg_count - seg_count
        for i in range(0, segments_to_create):
            self.insert_empty_segment(seg_start + seg_count + i, i != (segments_to_create - 1))
        seg_count = needed_seg_count

        for i in range(0, seg_count):
            self.segments[seg_start + i].data = full_data[:255]
            self.segments[seg_start + i].size = len(self.segments[seg_start + i].data)
            full_data = full_data[255:]
        assert len(full_data) == 0


    def convert_packet_to_framepacking_three_and_pad(self, seg_start, pad=False, count=0):
        assert self.segments[seg_start].first_packet is True
        self.segments[seg_start].convert_to_framepacking_three()
        if pad:
            self.segments[seg_start].set_pad_count(count)
        self.redistribute_packet_data_at(seg_start, count)


    def calc_actual_padding_value(self, seg_start, bytes_needed):
        assert bytes_needed >= 0, "Page is already too large! Something went wrong."

        seg_end = seg_start + self.get_segment_count_of_packet_at(seg_start)
        size_of_last_segment = self.segments[seg_end - 1].size
        convert_framepacking_needed = self.segments[seg_start].framepacking != 3

        if bytes_needed == 0:
            return DO_NOTHING

        if (bytes_needed + size_of_last_segment) % 255 == 0:
            return OTHER_PACKET_NEEDED

        if bytes_needed == 1:
            if convert_framepacking_needed:
                return ONLY_CONVERT_FRAMEPACKING
            else:
                return 0

        new_segments_needed = 0
        if bytes_needed + size_of_last_segment >= 255:
            tmp_count = bytes_needed + size_of_last_segment - 255
            while tmp_count >= 0:
                tmp_count = tmp_count - 255 - 1
                new_segments_needed = new_segments_needed + 1

        if (bytes_needed + size_of_last_segment) % 255 == (new_segments_needed - 1):
            return OTHER_PACKET_NEEDED

        packet_bytes_needed = bytes_needed - new_segments_needed

        if packet_bytes_needed == 1:
            if convert_framepacking_needed:
                return ONLY_CONVERT_FRAMEPACKING
            else:
                return 0

        if convert_framepacking_needed:
            packet_bytes_needed = packet_bytes_needed - 1  # frame_count_byte
        packet_bytes_needed = packet_bytes_needed - 1  # padding_count_data is at least 1 byte
        size_of_padding_count_data = max(1, math.ceil(packet_bytes_needed / 254))
        check_size = math.ceil((packet_bytes_needed - size_of_padding_count_data + 1) / 254)

        if check_size != size_of_padding_count_data:
            return OTHER_PACKET_NEEDED
        else:
            return packet_bytes_needed - size_of_padding_count_data + 1


    def pad(self, pad_to):
        # print("page size before {}".format(self.get_page_size()))
        idx = len(self.segments) - 1
        while not self.segments[idx].first_packet:
            idx = idx - 1
            if idx < 0:
                raise RuntimeError("Could not find begin of last packet!")

        pad_count = pad_to - self.get_page_size()
        actual_padding = self.calc_actual_padding_value(idx, pad_count)

        if actual_padding == DO_NOTHING:
            return
        if actual_padding == ONLY_CONVERT_FRAMEPACKING:
            self.convert_packet_to_framepacking_three_and_pad(idx)
            return
        if actual_padding == OTHER_PACKET_NEEDED:
            self.pad_one_byte()
            self.pad(pad_to)
            return

        self.convert_packet_to_framepacking_three_and_pad(idx, True, actual_padding)
        # print("page size after {}".format(self.get_page_size()))
        assert self.get_page_size() == pad_to


    def pad_one_byte(self):
        i = 0
        while not (self.segments[i].first_packet and not self.segments[i].padding
                   and self.get_opus_packet_size(i) % 255 < 254):
            i = i + 1
            if i >= len(self.segments):
                raise RuntimeError("Page seems impossible to pad correctly")

        if self.segments[i].framepacking == 3:
            self.convert_packet_to_framepacking_three_and_pad(i, True, 0)
        else:
            self.convert_packet_to_framepacking_three_and_pad(i)


    def write_page(self, filehandle, sha1):
        data = b"OggS" + struct.pack("<BBQLLLB", self.version, self.page_type, self.granule_position, self.serial_no, self.page_no, self.checksum, self.segment_count)
        for segment in self.segments:
            data = data + struct.pack("<B", segment.size)
        sha1.update(data)
        filehandle.write(data)
        for segment in self.segments:
            sha1.update(segment.data)
            segment.write(filehandle)


    @staticmethod
    def from_page(other_page):
        new_page = OggPage(None)
        new_page.version = other_page.version
        new_page.page_type = other_page.page_type
        new_page.granule_position = other_page.granule_position
        new_page.serial_no = other_page.serial_no
        new_page.page_no = other_page.page_no
        new_page.checksum = 0
        new_page.segment_count = 0
        new_page.segments = []
        return new_page


    @staticmethod
    def seek_to_page_header(filehandle):
        current_pos = filehandle.seek(0, 1)
        size = filehandle.seek(0, 2)
        filehandle.seek(current_pos, 0)
        five_bytes = filehandle.read(5)
        while five_bytes and (filehandle.tell() + 5 < size):
            if five_bytes == b"OggS\x00":
                filehandle.seek(-5, 1)
                return True
            filehandle.seek(-4, 1)
            five_bytes = filehandle.read(5)
        return False


def create_table():
    a = []
    for i in range(256):
        k = i << 24
        for _ in range(8):
            k = (k << 1) ^ 0x04c11db7 if k & 0x80000000 else k << 1
        a.append(k & 0xffffffff)
    return a


def crc32(bytestream):
    crc = 0
    for byte in bytestream:
        lookup_index = ((crc >> 24) ^ byte) & 0xff
        crc = ((crc & 0xffffff) << 8) ^ crc_table[lookup_index]
    return crc


def check_identification_header(page):
    segment = page.segments[0]
    unpacked = struct.unpack("<8sBBHLH", segment.data[0:18])
    assert unpacked[0] == b"OpusHead", "Invalid opus file?"
    assert unpacked[1] == 1, "Invalid opus file?"
    assert unpacked[2] == 2, "Only stereo tracks are supported"
    assert unpacked[4] == SAMPLE_RATE_KHZ * 1000, "Sample rate needs to be 48 kHz"


def prepare_opus_tags(page):
    page.segments.clear()
    segment = OpusPacket(None)
    segment.size = len(OPUS_TAGS[0])
    segment.data = bytearray(OPUS_TAGS[0])
    segment.spanning_packet = True
    segment.first_packet = True
    page.segments.append(segment)

    segment = OpusPacket(None)
    segment.size = len(OPUS_TAGS[1])
    segment.data = bytearray(OPUS_TAGS[1])
    segment.spanning_packet = False
    segment.first_packet = False
    page.segments.append(segment)
    page.correct_values(0)
    return page


def copy_first_and_second_page(in_file, out_file, timestamp, sha):
    found = OggPage.seek_to_page_header(in_file)
    if not found:
        raise RuntimeError("First ogg page not found")
    page = OggPage(in_file)
    page.serial_no = timestamp
    check_identification_header(page)
    page.write_page(out_file, sha)

    found = OggPage.seek_to_page_header(in_file)
    if not found:
        raise RuntimeError("Second ogg page not found")
    page = OggPage(in_file)
    page.serial_no = timestamp
    page = prepare_opus_tags(page)
    page.write_page(out_file, sha)


def skip_first_two_pages(in_file):
    found = OggPage.seek_to_page_header(in_file)
    if not found:
        raise RuntimeError("First ogg page not found")
    page = OggPage(in_file)
    check_identification_header(page)

    found = OggPage.seek_to_page_header(in_file)
    if not found:
        raise RuntimeError("Second ogg page not found")
    OggPage(in_file)


def read_all_remaining_pages(in_file):
    remaining_pages = []

    found = OggPage.seek_to_page_header(in_file)
    while found:
        remaining_pages.append(OggPage(in_file))
        found = OggPage.seek_to_page_header(in_file)
    return remaining_pages


def resize_pages(old_pages, max_page_size, first_page_size, template_page, last_granule=0, start_no=2, set_last_page_flag=False):
    new_pages = []
    page = None
    page_no = start_no
    max_size = first_page_size

    new_page = OggPage.from_page(template_page)
    new_page.page_no = page_no

    while len(old_pages) or not (page is None):
        if page is None:
            page = old_pages.pop(0)

        size = page.get_size_of_first_opus_packet()
        seg_count = page.get_segment_count_of_first_opus_packet()

        if (size + seg_count + new_page.get_page_size() < max_size) and (len(new_page.segments) + seg_count < 256):
            for i in range(seg_count):
                new_page.segments.append(page.segments.pop(0))
            if not len(page.segments):
                page = None
        else:
            new_page.pad(max_size)
            new_page.correct_values(last_granule)
            last_granule = new_page.granule_position
            new_pages.append(new_page)

            new_page = OggPage.from_page(template_page)
            page_no = page_no + 1
            new_page.page_no = page_no
            max_size = max_page_size

    if len(new_page.segments):
        if set_last_page_flag:
            new_page.page_type = 4
        new_page.pad(max_size)
        new_page.correct_values(last_granule)
        new_pages.append(new_page)

    return new_pages


def append_to_filename(output_filename, suffix):
    pos = output_filename.rfind('.')
    if pos == -1:
        return output_filename + " " + suffix
    else:
        return output_filename[:pos] + " " + suffix + output_filename[pos:]


def fix_tonie_header(out_file, chapters, timestamp, sha):
    tonie_header = tonie_header_pb2.TonieHeader()

    tonie_header.dataHash = sha.digest()
    tonie_header.dataLength = out_file.seek(0, 1) - 0x1000
    tonie_header.timestamp = timestamp

    for chapter in chapters:
        tonie_header.chapterPages.append(chapter)

    tonie_header.padding = bytes(0x100)

    header = tonie_header.SerializeToString()
    pad = 0xFFC - len(header) + 0x100
    tonie_header.padding = bytes(pad)
    header = tonie_header.SerializeToString()

    out_file.seek(0)
    out_file.write(struct.pack(">L", len(header)))
    out_file.write(header)


crc_table = create_table()

parser = argparse.ArgumentParser(description='Create Tonie compatible file from Ogg opus file(s).')
parser.add_argument('output_filename', metavar='TARGET', type=str, help='the output file name')
group = parser.add_mutually_exclusive_group()
group.add_argument('--file', dest='single_file_name', metavar='FILE', action='store',
                    help='read only a single source file')
group.add_argument('--dir', dest='source_directory', metavar='DIR', action='store',
                    help='read all files in directory')
parser.add_argument('--ts', dest='user_timestamp', metavar='TIMESTAMP', action='store', help='set custom timestamp / bitstream serial')
parser.add_argument('--append-tonie-filename', action='store_true', help='append [500304E0] to filename')
parser.add_argument('--no-tonie-header', action='store_true', help='do not write Tonie header')

args = parser.parse_args()

if args.append_tonie_filename:
    out_filename = append_to_filename(args.output_filename, "[500304E0]")
else:
    out_filename = args.output_filename

with open(out_filename, "wb") as out_file:
    if not args.no_tonie_header:
        out_file.write(bytearray(0x1000))

    if args.user_timestamp:
        if args.user_timestamp.startswith("0x"):
            timestamp = int(args.user_timestamp, 16)
        else:
            timestamp = int(args.user_timestamp)
    else:
        timestamp = int(time.time())

    sha1 = hashlib.sha1()

    template_page = None
    chapters = []
    total_granule = 0
    next_page_no = 2
    max_size = 0x1000
    other_size = 0xE00
    last_track = False

    if args.single_file_name:
        files = [args.single_file_name]
    else:
        files = sorted(glob.glob("{}/*.opus".format(args.source_directory)))

    pad_len = math.ceil(math.log(len(files) + 1, 10))
    format_string = "[{{:0{}d}}/{:0{}d}] {{}}".format(pad_len, len(files), pad_len)

    for index in range(len(files)):
        fname = files[index]
        print(format_string.format(index+1, fname))
        if index == len(files) - 1:
            last_track = True

        with open(fname, "rb") as inFile:
            if next_page_no == 2:
                copy_first_and_second_page(inFile, out_file, timestamp, sha1)
            else:
                other_size = max_size
                skip_first_two_pages(inFile)

            pages = read_all_remaining_pages(inFile)

            if template_page is None:
                template_page = OggPage.from_page(pages[0])
                template_page.serial_no = timestamp

            if next_page_no == 2:
                chapters.append(0)
            else:
                chapters.append(next_page_no)

            new_pages = resize_pages(pages, max_size, other_size, template_page, total_granule, next_page_no, last_track)

            for new_page in new_pages:
                new_page.write_page(out_file, sha1)
            last_page = new_pages[len(new_pages) - 1]
            total_granule = last_page.granule_position
            next_page_no = last_page.page_no + 1

    if not args.no_tonie_header:
        fix_tonie_header(out_file, chapters, timestamp, sha1)