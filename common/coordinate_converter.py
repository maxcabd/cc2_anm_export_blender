import math
from mathutils import Matrix, Quaternion, Euler, Vector

from typing import Tuple, List, Dict

from common.bone_props import AnmBoneProperties

# https://github.com/SutandoTsukai181/cc2_xfbin_blender/blob/main/blender/common/coordinate_converter.py

def rot_to_blender(rot: Tuple[float, float, float]):
	return Euler(tuple(map(lambda x: math.radians(x), rot)), 'ZYX')


def pos_m_to_cm_tuple(pos: Tuple[float, float, float]) -> Tuple[float, float, float]:
	# From meter to centimeter
	return tuple(map(lambda x: x * 100, pos))


def rot_from_blender(rot: Euler) -> Tuple[float, float, float]:
	return tuple(map(lambda x: math.degrees(x), rot))

def convert_light_values(conversion_type: str, values: List) -> List:
	if conversion_type == "light_color":
		return list(map(lambda x: tuple([int(x * 0xFF) for y in x]), values))

	elif conversion_type == "light_strength":
		return list(map(lambda x: x, values))

	elif conversion_type == "light_pos":
		return list(map(lambda x: pos_m_to_cm_tuple((x)[:]), values))

	elif conversion_type == "light_radius":
		return list(map(lambda x: x * 100, values))

	elif conversion_type == "light_rot":
		converted = list(map(lambda rot: (-rot.x, -rot.y, -rot.z, rot.w), values))
		return list(map(lambda x: tuple([int(y * 0x4000) for y in x]), converted))
		
	elif conversion_type == "light_rot_euler":
		return list(map(lambda x: rot_from_blender((x.to_quaternion().inverted()).to_euler('ZYX')[:]), values))


def convert_to_anm_values(data_path: str, values: List, loc: Vector, rot: Quaternion, sca: Vector) -> List:
	if data_path == 'location':
		return list(map(lambda x: pos_m_to_cm_tuple((loc + x)[:]), values))
		
	if data_path == 'location_camera':
		return list(map(lambda x: pos_m_to_cm_tuple((x)[:]), values))

	if data_path == 'rotation_euler':
		return list(map(lambda x: rot_from_blender((rot @ x.to_quaternion().inverted()).to_euler('ZYX')[:]), values))

	if data_path == 'rotation_quaternion':
		converted = list(map(lambda x: (rot @ x).inverted(), values))
		converted = list(map(lambda rot: (rot.x, rot.y, rot.z, rot.w), converted))
		return list(map(lambda x: tuple([int(y * 0x4000) for y in x]), converted))

	if data_path == 'rotation_quaternion_camera':
		converted = list(map(lambda x: (rot).inverted(), values))
		converted = list(map(lambda rot: (-rot.x, -rot.y, -rot.z, rot.w), values))
		return list(map(lambda x: tuple([int(y * 0x4000) for y in x]), converted))

	if data_path == 'rotation_quaternion_euler':
		return list(map(lambda x: rot_from_blender((x.to_quaternion() @ rot.inverted()).to_euler('ZYX')[:]), values))

	if data_path == 'scale' and len(values) < 2:
		return list(map(lambda x: (Vector(([abs(y) for y in x])) * sca )[:], values))

	elif data_path == 'scale' and len(values) > 1:
		converted = list(map(lambda x: (Vector(([abs(y) for y in x])) * sca )[:], values))
		return list(map(lambda x: tuple([int(y * 0x1000) for y in x]), converted))
