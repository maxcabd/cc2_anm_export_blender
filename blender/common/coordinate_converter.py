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



def convert_bone_value(anm_armature: AnmArmature, bone_name: str, data_path: str,
					   track_header: TrackHeader, values: List[float], frame: int = 0) -> NuccAnmKey:
	armature: Armature = anm_armature.armature

	has_parent: bool = any(bone_name for bone in anm_armature.armature.data.bones if bone.parent)

	edit_matrix: Matrix = get_edit_matrix(armature, bone_name)
	

	def translate(seq: List[float]) -> Tuple[float]:
		if has_parent:
			loc, rot, _ = edit_matrix.decompose()
			translation = Vector(seq)
			translation.rotate(rot)

			return tuple(pos_m_to_cm_tuple((translation + loc)[:]))
		
	
	def rotate_euler(seq: List[float]) -> Tuple[int, int, int]:
		if has_parent:
			_, rot, _ = edit_matrix.decompose()
			rotation = rot @ Euler(seq).to_quaternion().inverted().to_euler('ZYX')
			rotation = rot_to_blender(rotation)
			return tuple(rot_from_blender(rotation))
					
	def rotate_quaternion(seq: List[float]) -> Tuple[int, int, int, int]:
		if has_parent:
			_, rot, _ = edit_matrix.decompose()
			rotation = Quaternion(seq)
			rotation = (rot @ rotation).inverted()
			# Swizzle the quaternion to match the game's format to x, y, z, w
			rotation = Quaternion((rotation.x, rotation.y, rotation.z, rotation.w))
			return tuple(rotation)
	
	match data_path, track_header.key_format:
		case 'location', NuccAnmKeyFormat.Vector3Fixed:
			return NuccAnmKey.Vec3(translate(values))
		
		case 'location', NuccAnmKeyFormat.Vector3Linear:
			return NuccAnmKey.Vec3Linear(frame * 100, translate(values))
		
		case 'rotation_euler', NuccAnmKeyFormat.EulerXYZFixed:
			return NuccAnmKey.Vec3(rotate_euler(values))
		
		case 'rotation_quaternion', NuccAnmKeyFormat.QuaternionLinear:
			return NuccAnmKey.Vec4Linear(frame * 100, rotate_quaternion(values))
		
		case 'rotation_quaternion', NuccAnmKeyFormat.QuaternionShortTable:
			return NuccAnmKey.ShortVec4(tuple([int(y * QUAT_COMPRESS) for y in rotate_quaternion(values)]))	
		
		case 'scale', NuccAnmKeyFormat.Vector3Linear:
			scale = Vector([abs(seq) for seq in values])[:]
			return NuccAnmKey.Vec3Linear(frame * 100, tuple(scale[:]))
		
		case 'scale', NuccAnmKeyFormat.Vector3Fixed:
			scale = Vector([abs(seq) for seq in values])[:]
			return NuccAnmKey.Vec3(tuple(scale))
		
	return values


def convert_object_value(data_path: str, values: List[float], frame: int = 0) -> NuccAnmKey:
	"""
	Used for converting objects that are not bones, such as cameras and lights.
	
	"""
	def translate(seq: List[float]) -> Tuple[float]:
		return tuple(pos_m_to_cm_tuple(seq))
	
	def rotate_quaternion(seq: List[float]) -> Tuple[int, int, int, int]:
		rotation = Quaternion(seq)

		# Swizzle the quaternion to match the game's format to x, y, z, w
		rotation = Quaternion((-rotation.x, -rotation.y, -rotation.z, rotation.w))
		rotation = tuple([int(y * QUAT_COMPRESS) for y in rotation])
		return tuple(rotation)
	

	match data_path:
		case 'location':
			return NuccAnmKey.Vec3Linear(frame * 100, translate(values))
		
		case 'rotation_quaternion':
			return NuccAnmKey.ShortVec4(rotate_quaternion(values))
		
		case 'fov':
			return NuccAnmKey.FloatLinear(frame * 100, values[0])
		
		case 'color':
			color = [int(x * 255) for x in values]
			return NuccAnmKey.Color(tuple(color))
	
	return values