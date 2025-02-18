import math

from mathutils import  Quaternion, Euler, Vector
from typing import Tuple, List, Any
from bpy.types import Armature
from mathutils import Matrix

from ..common.armature_props import AnmArmature
from ..common.bone_props import get_edit_matrix
from ...xfbin.xfbin_lib import NuccAnmKeyFormat, NuccAnmKey, TrackHeader




QUAT_COMPRESS = 0x4000
SCALE_COMPRESS = 0x1000

# Helper functions
def to_radians(degrees: float) -> float:
	return math.radians(degrees)

def to_degrees(radians: float) -> float:
	return math.degrees(radians)

def meters_to_centimeters(meters: float) -> float:
	return meters * 100

def to_fixed_point(value: float, scale: int) -> int:
	return int(value * scale)

# Conversion functions
def rot_to_blender(rot: Tuple[float, float, float]) -> Euler:
	return Euler(tuple(map(to_radians, rot)), 'ZYX')

def pos_m_to_cm_tuple(pos: Tuple[float, float, float]) -> Tuple[float, float, float]:
	return tuple(map(meters_to_centimeters, pos))

def rot_from_blender(rot: Euler) -> Tuple[float, float, float]:
	return tuple(map(to_degrees, rot))

def fov_from_blender(sensor_width: float, lens: float) -> float:
	return 2 * math.atan((0.5 * sensor_width) / lens) * 180 / math.pi



def convert_bone_value(loc, rot, scale, data_path: str, track_header: TrackHeader, values: List[float], frame: int = 0) -> NuccAnmKey:
	def translate(seq: List[float]) -> Tuple[float]:
		translation = Vector(seq)
		translation.rotate(rot)
		return tuple(pos_m_to_cm_tuple((loc + translation)))

	def rotate_euler(seq: List[float]) -> Tuple[int, int, int]:
		return tuple(math.degrees(x) for x in seq)

	def rotate_quaternion(seq: List[float]) -> Tuple[int, int, int, int]:
		rotation = Quaternion(seq)
		rotation = (rot @ rotation).inverted()
		rotation = Quaternion((rotation.x, rotation.y, rotation.z, rotation.w))
		return tuple(rotation)

	def scale_vector(seq: List[float]) -> Tuple[float, float, float]:
		new_scale = Vector(seq)
		new_scale = scale * Vector(new_scale)
		return tuple(new_scale)

	match data_path, track_header.key_format:
		case 'location', NuccAnmKeyFormat.Vector3Fixed:
			return NuccAnmKey.Vec3(translate(values))
		case 'location', NuccAnmKeyFormat.Vector3Linear:
			return NuccAnmKey.Vec3Linear(frame * 100, translate(values))
		case 'rotation_euler', NuccAnmKeyFormat.EulerXYZFixed | NuccAnmKeyFormat.EulerInterpolated:
			return NuccAnmKey.Vec3(rotate_euler(values))
		case 'rotation_quaternion', NuccAnmKeyFormat.QuaternionLinear:
			return NuccAnmKey.Vec4Linear(frame * 100, rotate_quaternion(values))
		case 'rotation_quaternion', NuccAnmKeyFormat.QuaternionShortTable:
			return NuccAnmKey.ShortVec4(tuple([int(y * QUAT_COMPRESS) for y in rotate_quaternion(values)]))
		case 'scale', NuccAnmKeyFormat.Vector3Linear:
			return NuccAnmKey.Vec3Linear(frame * 100, scale_vector(values))
		case 'scale', NuccAnmKeyFormat.Vector3Fixed:
			return NuccAnmKey.Vec3(scale_vector(values))
	return values

def convert_object_value(sensor_width, data_path: str, values: List[float], frame: int = 0) -> NuccAnmKey:
	def translate(seq: List[float]) -> Tuple[float]:
		return tuple(s * 100 for s in seq)

	def rotate_quaternion(seq: List[float]) -> Tuple[int, int, int, int]:
		rotation = Quaternion(seq).inverted()
		rotation = Quaternion((rotation.x, rotation.y, rotation.z, rotation.w))
		return tuple(rotation)

	def rotate_euler(seq: List[float]) -> Tuple[int, int, int]:
		rotation = Euler(seq).to_quaternion().inverted()
		rotation = Quaternion((rotation.x, rotation.y, rotation.z, rotation.w))
		return tuple(rotation)

	def to_fov(sensor_width: float, lens: float) -> float:
		return 2 * math.atan((0.5 * sensor_width) / lens) * 180 / math.pi

	match data_path:
		case 'location':
			return NuccAnmKey.Vec3Linear(int(frame) * 100, translate(values))
		case 'rotation_quaternion':
			return NuccAnmKey.Vec4Linear(int(frame) * 100, rotate_quaternion(values))
		case 'rotation_euler':
			return NuccAnmKey.Vec4Linear(int(frame) * 100, rotate_euler(values))
		case 'fov':
			return NuccAnmKey.FloatLinear(int(frame) * 100, to_fov(sensor_width, values[0]))
		case 'color':
			color = [int(x * 255) for x in values]
			return NuccAnmKey.Color(tuple(color))
	return values


def convert_light_values(data_path, values, key_format = None, frame = 0) -> NuccAnmKey:
	def translate(seq: List[float]):
		return tuple(s * 100 for s in seq)

	def rotate_quaternion(seq: List[float]) -> Tuple[int, int, int, int]:
		rotation = Quaternion(seq).inverted()
		rotation = Quaternion((rotation.x, rotation.y, rotation.z, rotation.w))
		return tuple(int(x * QUAT_COMPRESS) for x in rotation)

	def rotate_euler(seq: List[float]) -> Tuple[int, int, int]:
		#invert the x axis
		#seq = [seq[0], -seq[1], seq[2]]
		rotation = Euler(seq).to_quaternion().inverted()
		rotation = (rotation.x, rotation.y, rotation.z, rotation.w)
		return tuple(int(x * QUAT_COMPRESS) for x in rotation)

	match data_path, key_format:
		case 'location', NuccAnmKeyFormat.Vector3Linear:
			return NuccAnmKey.Vec3Linear(int(frame) * 100, translate(values))
		case 'location', NuccAnmKeyFormat.Vector3Fixed:
			return NuccAnmKey.Vec3(translate(values))
		case 'location', NuccAnmKeyFormat.Vector3Table:
			return NuccAnmKey.Vec3(translate(values))
		case 'rotation_quaternion', NuccAnmKeyFormat.QuaternionShortTable:
			return NuccAnmKey.ShortVec4(rotate_quaternion(values))
		case 'rotation_euler', NuccAnmKeyFormat.QuaternionShortTable:
			return NuccAnmKey.ShortVec4(rotate_euler(values))
		case 'xfbin_scene.lightdir_color', NuccAnmKeyFormat.ColorRGBTable:
			color = (int(x * 255) for x in values)
			return NuccAnmKey.Color(tuple(color))
		case "xfbin_scene.lightpoint_color0", NuccAnmKeyFormat.ColorRGBTable:
			color = (int(x * 255) for x in values)
			return NuccAnmKey.Color(tuple(color))
		case "xfbin_scene.ambient_color", NuccAnmKeyFormat.ColorRGBTable:
			color = (int(x * 255) for x in values)
			return NuccAnmKey.Color(tuple(color))

		case "xfbin_scene.lightdir_intensity", NuccAnmKeyFormat.FloatLinear:
			return NuccAnmKey.Float(values[0])
		case "xfbin_scene.lightdir_intensity", NuccAnmKeyFormat.FloatTable:
			return NuccAnmKey.Float(values[0])
		case "xfbin_scene.lightdir_intensity", NuccAnmKeyFormat.FloatFixed:
			return NuccAnmKey.Float(values[0])

		case "xfbin_scene.lightpoint_intensity0", NuccAnmKeyFormat.FloatLinear:
			return NuccAnmKey.Float(values[0])
		case "xfbin_scene.lightpoint_intensity0", NuccAnmKeyFormat.FloatTable:
			return NuccAnmKey.Float(values[0])
		case "xfbin_scene.lightpoint_intensity0", NuccAnmKeyFormat.FloatFixed:
			return NuccAnmKey.Float(values[0])

		case "xfbin_scene.lightpoint_range0", NuccAnmKeyFormat.FloatLinear:
			return NuccAnmKey.Float(round(values[0]) * 100)
		case "xfbin_scene.lightpoint_range0", NuccAnmKeyFormat.FloatTable:
			return NuccAnmKey.Float(round(values[0]) * 100)
		case "xfbin_scene.lightpoint_range0", NuccAnmKeyFormat.FloatFixed:
			return NuccAnmKey.Float(round(values[0]) * 100)

		case "xfbin_scene.lightpoint_attenuation0", NuccAnmKeyFormat.FloatLinear:
			return NuccAnmKey.Float(round(values[0]))
		case "xfbin_scene.lightpoint_attenuation0", NuccAnmKeyFormat.FloatTable:
			return NuccAnmKey.Float(round(values[0]))
		case "xfbin_scene.lightpoint_attenuation0", NuccAnmKeyFormat.FloatFixed:
			return NuccAnmKey.Float(round(values[0]))

		case "xfbin_scene.ambient_intensity", NuccAnmKeyFormat.FloatTable:
			return NuccAnmKey.Float(values[0])

		case _:
			raise ValueError(f"Unsupported data path: {data_path}")

	return values