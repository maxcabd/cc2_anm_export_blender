from dataclasses import dataclass
from binary_reader.binary_reader import *
from typing import List, Tuple, Dict, Union
from enum import IntEnum




anm_writer = BinaryReader(endianness=Endian.BIG, encoding='utf-8')  # Create a new BinaryReader (bytearray buffer is initialized automatically)


"""class AnmDataPath(IntEnum):
	UNKNOWN = -1

	LOCATION = 6
	LOCATION_NOKEY = 8
	ROTATION = -2
	ROTATION_EULER = 1
	ROTATION_QUATERNION = 17
	SCALE = 5
	TOGGLED = 11

	# Proper name not yet decided
	CAMERA = 10"""

class AnmCurveFormat(IntEnum):
    FLOAT3 = 5  # location/scale
    INT1_FLOAT3 = 6  # location/scale (with keyframe)
    FLOAT3ALT = 8  # rotation
    INT1_FLOAT4 = 10  # rotation quaternions (with keyframe)
    FLOAT1 = 11  # "toggled"
    INT1_FLOAT1 = 12 # camera
    SHORT1 = 15  # "toggled"
    SHORT3 = 16  # scale
    SHORT4 = 17  # rotation quaternions
    BYTE3 = 20  # lightdirc
    FLOAT3ALT2 = 21  # scale
    FLOAT1ALT = 22  # lightdirc
    FLOAT1ALT2 = 24  # material

@dataclass
class Clump(BrStruct):
	"""
	Clump data structure.
	"""
	clump_index: int
	bone_material_count: int
	model_count: int
	bone_material_indices : List[int]
	model_indices: List[int]

	def __br_write__(self, anm_writer: 'BinaryReader'):
		anm_writer.write_uint32(self.clump_index)
		anm_writer.write_uint16(self.bone_material_count)
		anm_writer.write_uint16(self.model_count)

		for index in self.bone_material_indices:
			anm_writer.write_uint32(index)
		
		for index in self.model_indices:
			anm_writer.write_uint32(index)

@dataclass
class AnmCoord(BrStruct):
	clump_index: int
	coord_index: int

	def __br_write__(self, anm_writer: 'BinaryReader'):
		anm_writer.write_int16(self.clump_index)
		anm_writer.write_uint16(self.coord_index)


@dataclass
class CoordParent(BrStruct):
	"""
	Coord Parent stores a list of short values of [clump index, parent node, clump index, child node...]
	"""
	anm_coords: List[AnmCoord]

	def __br_write__(self, anm_writer: 'BinaryReader'):
		for c in self.anm_coords:
			anm_writer.write_struct(c)

@dataclass
class CurveHeader(BrStruct):
	"""
	A curve header stores information about a curve.
	"""
	curve_index:  int
	curve_format: int
	frame_count:  int
	curve_flags:  int

	def __br_write__(self, anm_writer: 'BinaryReader'):
		anm_writer.write_uint16(self.curve_index)
		anm_writer.write_uint16(self.curve_format)
		anm_writer.write_uint16(self.frame_count)
		anm_writer.write_uint16(self.curve_flags)

@dataclass
class Curve(BrStruct):
	"""
	Where the values are stored.
	"""
	curve_format: AnmCurveFormat
	keyframes: Union[Tuple[int], Tuple[float], Dict[int, float]]
	
	def __br_write__(self, anm_writer: 'BinaryReader'):
		if self.curve_format == AnmCurveFormat.INT1_FLOAT3 or self.curve_format == AnmCurveFormat.INT1_FLOAT1:
			for frame, value in self.keyframes.items():
				anm_writer.write_int32(frame)
				anm_writer.write_float(value)
		
		if self.curve_format == AnmCurveFormat.SHORT4 or self.curve_format == AnmCurveFormat.SHORT3:
			for value in self.keyframes:
				anm_writer.write_int16(value)
		
		if self.curve_format == AnmCurveFormat.FLOAT3 or self.curve_format == AnmCurveFormat.FLOAT3ALT or self.curve_format == AnmCurveFormat.FLOAT1:
			for value in self.keyframes:
				anm_writer.write_float(value)
		
		
@dataclass
class Entry(BrStruct):
	"""
	Entries are the main data structure of an ANM file. 
	"""
	clump_index: int
	coord_index: int
	entry_format: int
	curve_count: int

	curve_headers: List[CurveHeader]
	curves: List[Curve]

	def __br_write__(self, anm_writer: 'BinaryReader'):
		anm_writer.write_int16(self.clump_index)
		anm_writer.write_int16(self.coord_index)

		anm_writer.write_uint16(self.entry_format)
		self.curve_count = len(self.curve_headers)
		anm_writer.write_uint16(self.curve_count)

		for curve_header in self.curve_headers:
			anm_writer.write_struct(curve_header)
		
		for curve in self.curves:
			anm_writer.write_struct(curve)
			

@dataclass
class Anm(BrStruct):
	"""
	ANM files are used to store animation data for models or other objects.
	"""
	anm_length: int
	frame_size: int
	entry_count: int
	loop: int
	clump_count: int
	other_entry_count: int
	coord_count: int

	clumps: List[Clump]
	coord_parents: CoordParent
	entries: List[Entry]

	def __br_write__(self, anm_writer: 'BinaryReader'):
		anm_writer.write_uint32(self.anm_length * 100)
		anm_writer.write_uint32(self.frame_size * 100)
		anm_writer.write_uint16(self.entry_count)
		anm_writer.write_uint16(self.loop)
		anm_writer.write_uint16(self.clump_count)
		anm_writer.write_uint16(self.other_entry_count)
		anm_writer.write_uint32(self.coord_count)

		for clump in self.clumps:
			anm_writer.write_struct(clump)
		if self.other_entry_count > 0:
			anm_writer.write_uint32(1)
		anm_writer.write_struct(self.coord_parents)

		for entry in self.entries:
			anm_writer.write_struct(entry)