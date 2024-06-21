import math

from mathutils import  Quaternion, Euler, Vector
from typing import Tuple, List, Any
from bpy.types import Armature
from mathutils import Matrix

from common.armature_props import AnmArmature
from common.bone_props import get_edit_matrix, get_matrix_world
from xfbin.xfbinlib import CurveFormat
from xfbin.xfbinlib import math



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



def convert_bone_value(anm_armature: AnmArmature, bone_name: str, data_path: str, curve_format: CurveFormat, values: List[Any], frame: int = 0) -> Tuple[Any]:
	armature: Armature = anm_armature.armature

	has_parent: bool = any(bone_name for bone in anm_armature.armature.data.bones if bone.parent)

	edit_matrix: Matrix = get_edit_matrix(armature, bone_name)
	

	def translate(seq: List[float]) -> Tuple[float]:
		if has_parent:
			loc, rot, _ = edit_matrix.decompose()
			translation = Vector(seq)
			translation.rotate(rot)

			return tuple(pos_m_to_cm_tuple((translation + loc)[:]))
		else:
			world_matrix: Matrix = get_matrix_world(armature, edit_matrix, bone_name)
			translation = Vector(seq) + world_matrix.to_translation().copy() # Add the armature's matrix world location to the translation
			print(world_matrix.to_translation().copy()[:])
			return tuple(pos_m_to_cm_tuple((translation)[:]))
			
			
	def rotate_quaternion(seq: List[float]) -> Tuple[int, int, int, int]:
		if has_parent:
			_, rot, _ = edit_matrix.decompose()
			rotation = Quaternion(seq)
			rotation = (rot @ rotation).inverted()
			# Swizzle the quaternion to match the game's format to x, y, z, w
			rotation = Quaternion((rotation.x, rotation.y, rotation.z, rotation.w))
			return tuple(rotation)
		else:
			world_matrix: Matrix = get_matrix_world(armature, edit_matrix, bone_name)
			rotation = world_matrix.to_quaternion().copy() @ Quaternion(seq)
			rotation = Quaternion((-rotation.x, -rotation.y, -rotation.z, rotation.w))
			return tuple([int(seq * QUAT_COMPRESS) for seq in rotation[:]])
			
			


	match data_path, curve_format:
		case 'location', CurveFormat.Vector3Linear:
			return math.Vec3Linear(frame * 100, translate(values))
		case 'location', CurveFormat.Vector3Fixed:
			return math.Vec3(translate(values))
		case 'rotation_quaternion', CurveFormat.QuaternionLinear:
			return math.Vec4Linear(frame * 100, rotate_quaternion(values))
		case 'scale', CurveFormat.Vector3Linear:
			scale = Vector([abs(seq) for seq in values])[:]
			return math.Vec3Linear(frame * 100, tuple(scale[:]))
		case 'scale', CurveFormat.Vector3Fixed:
			scale = Vector([abs(seq) for seq in values])[:]
			return math.Vec3(tuple(scale))
		


	

	return values

