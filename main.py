import os
import sys
import bpy
from collections import defaultdict
from typing import Dict, List, Union
from bpy.types import Armature, Bone, FCurve	

directory, filename = os.path.split(os.path.abspath(bpy.context.space_data.text.filepath))
sys.path.append(directory)

from xfbin.xfbinlib import *
from xfbin.xfbinlib import math


from common.bone_props import *
from common.armature_props import *
from common.coordinate_converter import *


IS_LOOPED = True 
OPTIMIZE = True 

ANM_CHUNK_PATH: str = "c\\crsel\\3nrt\\anm\\3nrtcharsel00.max"


def camera_exists() -> bool:
	""" Return True if Camera exists AND has animation data, and False otherwise."""
	cam = bpy.context.scene.camera

	if cam and cam.animation_data: 
		return True
	else: 
		return False
	  

def make_anm_armatures() -> List[AnmArmature]:
	"""
	Return list of armatures that contain animation data.
	"""
	anm_armatures: List[AnmArmature] = list()

	for obj in bpy.context.selected_objects:
		if obj.type == "ARMATURE":
			arm_obj = bpy.data.objects[obj.name]

			if arm_obj.animation_data:
				anm_armatures.append(AnmArmature(arm_obj))

	return anm_armatures



class AnmProp:
	""" 
	Represents an Action object in Blender. 
	"""
	def __init__(self, anm_armatures: List[AnmArmature] = None):

		self.armatures = anm_armatures
	
	

def make_anm(anm_prop: AnmProp) -> NuccAnm:
	"""
	Return NuccAnm object from AnmProp object.
	"""
	anm = NuccAnm()
	anm.struct_info = NuccStructInfo(f"{anm_prop.armatures[0].action.name}", "nuccChunkAnm", ANM_CHUNK_PATH)
	anm.is_looped = IS_LOOPED
	anm.frame_count = bpy.context.scene.frame_end * 100

	# Combined struct references from all armatures for this AnmProp
	struct_references: List[NuccStructReference] = [ref for armature in anm_prop.armatures for ref in armature.nucc_struct_references]

	anm.clumps.extend(make_anm_clump(anm_prop.armatures, struct_references))
	anm.coord_parents.extend(make_anm_coords(anm_prop.armatures))
	anm.entries.extend(make_coord_entries(anm_prop.armatures, struct_references, anm.clumps))
		
	return anm
		
def make_anm_clump(anm_armatures: List[AnmArmature], struct_references: List[NuccStructReference]) -> List[AnmClump]:
	clumps: List[AnmClump] = list()


	for anm_armature in anm_armatures:
		clump = AnmClump()

		if anm_armature.models:
			clump.clump_index = struct_references.index(NuccStructReference(anm_armature.models[0], NuccStructInfo(anm_armature.name, "nuccChunkClump", anm_armature.chunk_path)))
				
		else:
			clump.clump_index = struct_references.index(NuccStructReference(anm_armature.bones[0], NuccStructInfo(anm_armature.name, "nuccChunkClump", anm_armature.chunk_path)))
				
		bone_material_indices: List[int] = list()

		bone_indices: List[int] = [struct_references.index(NuccStructReference(bone, NuccStructInfo(bone, "nuccChunkCoord", anm_armature.chunk_path))) for bone in anm_armature.bones]
		mat_indices: List[int] = [struct_references.index(NuccStructReference(mat, NuccStructInfo(mat, "nuccChunkMaterial", anm_armature.chunk_path))) for mat in anm_armature.materials]
		model_indices: List[int] = [struct_references.index(NuccStructReference(model, NuccStructInfo(model, "nuccChunkModel", anm_armature.chunk_path))) for model in anm_armature.models]

		bone_material_indices.extend([*bone_indices, *mat_indices])


		clump.bone_material_indices = bone_material_indices
		clump.model_indices = model_indices

		clumps.append(clump)

	return clumps


def make_anm_coords(anm_armatures: List[AnmArmature]) -> List[CoordParent]:
	"""
	Return list of CoordParent objects from AnmArmature object.
	"""
	#arm_obj: Armature = anm_armature.armature # Blender armature object
	coord_parents: List[CoordParent] = list()

	# Get list of child bones for each bone in armature
	for armature_index, anm_armature in enumerate(anm_armatures):
		armature_obj = anm_armature.armature

		child_bones: List[Bone] = [bone for bone in anm_armature.armature.data.bones if bone.parent]

		for bone in child_bones:
			parent = AnmCoord(armature_index, anm_armature.bones.index(bone.parent.name))
			child = AnmCoord(armature_index, anm_armature.bones.index(bone.name))

			coord_parents.append(CoordParent(parent, child))

			
		# Handle case where bone has constraints
		for bone in armature_obj.data.bones:
			if ("Copy Transforms" in anm_armatures[armature_index].armature.pose.bones[bone.name].constraints):
				parent_armature = next((arm for arm in anm_armatures if arm.armature == armature_obj.pose.bones[bone.name].constraints["Copy Transforms"].target), None)
				parent_clump_index = anm_armatures.index(parent_armature)
				parent = AnmCoord(parent_clump_index, parent_armature.bones.index(armature_obj.pose.bones[bone.name].constraints["Copy Transforms"].subtarget))
				child = AnmCoord(armature_index, anm_armature.bones.index(bone.name))

				coord_parents.append(CoordParent(parent, child))
		

	return coord_parents



def make_coord_entries(anm_armatures: List[AnmArmature], struct_references: List[NuccStructReference], clumps: List[AnmClump]) -> List[AnmEntry]:
	entries: List[AnmEntry] = []

	for anm_armature in anm_armatures:
		# Filter the groups that aren't in anm_armature.anm_bones
		groups = [group for group in anm_armature.action.groups.values() if group.name in [bone.name for bone in anm_armature.anm_bones]]

		for i, group in enumerate(groups):
			clump_reference_index = struct_references.index(anm_armature.nucc_struct_references[0])
			clump_index = next((clump_index for clump_index, clump in enumerate(clumps) if clump.clump_index == clump_reference_index), None)

			coord_reference_index = struct_references.index(NuccStructReference(group.name, NuccStructInfo(group.name, "nuccChunkCoord", anm_armature.chunk_path)))
			coord_index = next((coord_index for coord_index, coord in enumerate(clumps[clump_index].bone_material_indices) if coord == coord_reference_index), None)
			
			entry = AnmEntry()
			entry.coord = AnmCoord(clump_index, coord_index)
			entry.entry_format = EntryFormat.Coord

			# Get the edit bone matrix for the bone
			edit_matrix = get_edit_matrix(anm_armature.armature, group.name)
			


			location_curves: List[FCurve] = [None] * 3
			rotation_curves: List[FCurve] = [None] * 3 # Euler rotations
			quaternion_curves: List[FCurve] = [None] * 4
			scale_curves: List[FCurve] = [None] * 3
			toggle_curves: List[FCurve] = [None] * 1

			channel_dict = {
				'location': location_curves,
				'rotation_euler': rotation_curves,
				'rotation_quaternion': quaternion_curves,
				'scale': scale_curves,
				'toggled': toggle_curves,
			}

			channels = group.channels

			for fcurve in channels:
				data_path = fcurve.data_path[fcurve.data_path.rindex('.') + 1:] if '.' in fcurve.data_path else ''

				if curves := channel_dict.get(data_path):
					curves[fcurve.array_index] = fcurve
				else:
					print(f'Warning: Ignoring curve with unsupported data path {fcurve.data_path} and index {fcurve.array_index}')

			# ------------------- location -------------------
			location_curve_header = CurveHeader()
			location_anm_curves: List[Curve] = list()

			location_keyframes: Dict[int, List[float]] = defaultdict(list)

			for i in range(3):
				if not location_curves[i]:
					continue

				#Get keyframes
				axis_co = [0] * 2 * len(location_curves[i].keyframe_points)
				location_curves[i].keyframe_points.foreach_get('co', axis_co)

				axis_iter = iter(axis_co)

				for frame, value in zip(axis_iter, axis_iter):
					location_keyframes[int(frame)].append(value)
					
			for frame, value in location_keyframes.items():
					if len(location_keyframes.items()) > 1:

						converted_value = convert_bone_value(anm_armature, group.name, 'location', CurveFormat.Vector3Linear, value, frame)
						location_curve = Curve(CurveFormat.Vector3Linear, converted_value)
						location_anm_curves.append(location_curve)

						location_curve_header.curve_index = 0
						location_curve_header.curve_format = CurveFormat.Vector3Linear
						location_curve_header.frame_count = len(location_keyframes.items())
						location_curve_header.curve_size = 12
					else:
						converted_value = convert_bone_value(anm_armature, group.name, 'location', CurveFormat.Vector3Fixed, value)
						location_curve = Curve(CurveFormat.Vector3Fixed, converted_value)
						location_anm_curves.append(location_curve)

						location_curve_header.curve_index = 0
						location_curve_header.curve_format = location_curve.curve_format
						location_curve_header.frame_count = 1

			if len(location_anm_curves) > 1:
				null_keyframe = math.Vec3Linear(-1, location_anm_curves[-1].keyframe.channels)
				null_curve = Curve(CurveFormat.Vector3Linear, null_keyframe)
				location_anm_curves.append(null_curve)
				location_curve_header.frame_count += 1

			entry.curve_headers.append(location_curve_header)
			entry.curves.extend(location_anm_curves)

			# ------------------- rotation quaternion -------------------
			quaternion_curve_header = CurveHeader()
			quaternion_anm_curves: List[Curve] = list()

			quaternion_keyframes = defaultdict(list)

			if any(quaternion_curves):
				for i in range(4):
					axis_co = [0] * 2 * len(quaternion_curves[i].keyframe_points)
					quaternion_curves[i].keyframe_points.foreach_get('co', axis_co)

					axis_iter = iter(axis_co)

					for frame, value in zip(axis_iter, axis_iter):
						quaternion_keyframes[int(frame)].append(value)
					
				# Construct output format for each frame
				for frame, value in quaternion_keyframes.items():	
						converted_value = convert_bone_value(anm_armature, group.name, 'rotation_quaternion', CurveFormat.QuaternionLinear, value, frame)
						quaternion_curve = Curve(CurveFormat.QuaternionLinear, converted_value)
						quaternion_anm_curves.append(quaternion_curve)

						quaternion_curve_header.curve_index = 1
						quaternion_curve_header.curve_format = quaternion_curve.curve_format
						quaternion_curve_header.frame_count = len(quaternion_keyframes.items())
						quaternion_curve_header.curve_size = 12
				
				null_keyframe = math.Vec4Linear(-1, quaternion_anm_curves[-1].keyframe.channels)
				null_curve = Curve(CurveFormat.QuaternionLinear, null_keyframe)
				quaternion_anm_curves.append(null_curve)
				quaternion_curve_header.frame_count += 1

				entry.curve_headers.append(quaternion_curve_header)
				entry.curves.extend(quaternion_anm_curves)

			# ------------------- scale -------------------
			scale_curve_header = CurveHeader()
			scale_anm_curves: List[Curve] = list()

			scale_keyframes = defaultdict(list)

			for i in range(3):
				if not scale_curves[i]:
					continue
			
				# Get keyframes
				axis_co = [0] * 2 * len(scale_curves[i].keyframe_points)
				scale_curves[i].keyframe_points.foreach_get('co', axis_co)

				axis_iter = iter(axis_co)

				for frame, value in zip(axis_iter, axis_iter):
					scale_keyframes[int(frame)].append(value)
					
			for frame, value in scale_keyframes.items():
				if len(scale_keyframes.items()) > 1:
					converted_value = convert_bone_value(anm_armature, group.name, 'scale', CurveFormat.Vector3Linear, value, frame)
					scale_curve = Curve(CurveFormat.Vector3Linear, converted_value)
					scale_anm_curves.append(scale_curve)

					scale_curve_header.curve_index = 2
					scale_curve_header.curve_format = CurveFormat.Vector3Linear
					scale_curve_header.curve_size =  12
				else:
					converted_value = convert_bone_value(anm_armature, group.name, 'scale', CurveFormat.Vector3Fixed, value)
					scale_curve = Curve(CurveFormat.Vector3Fixed, converted_value)
					entry.curves.append(scale_curve)

					scale_curve_header.curve_index = 2
					scale_curve_header.frame_count = 1


			if len(scale_anm_curves) > 1:
				null_keyframe = math.Vec3Linear(-1, scale_anm_curves[-1].keyframe.channels)
				null_curve = Curve(CurveFormat.Vector3Linear, null_keyframe)
				scale_anm_curves.append(null_curve)
				scale_curve_header.frame_count += 1

				
			entry.curves.extend(scale_anm_curves)

			scale_curve_header.frame_count = len(scale_anm_curves)
			entry.curve_headers.append(scale_curve_header)

			

			# ------------------- toggled -------------------
			toggle_curve_header = CurveHeader()
			toggle_anm_curves: List[Curve] = list()

			toggle_keyframes = defaultdict(list)

			if any(toggle_curves):
				for i in range(1):
					if not toggle_curves[i]:
						continue

					# Get keyframes
					axis_co = [0] * 2 * len(toggle_curves[i].keyframe_points)
					toggle_curves[i].keyframe_points.foreach_get('co', axis_co)

					axis_iter = iter(axis_co)

					for frame, value in zip(axis_iter, axis_iter):
						toggle_keyframes[int(frame)].append(value)

				# Construct output format for each frame
				for frame, value in toggle_keyframes.items():
					toggle_curve = Curve(CurveFormat.FloatFixed, math.Float(value[0]))
					toggle_anm_curves.append(toggle_curve)

					toggle_curve_header.curve_index = 3
					toggle_curve_header.curve_format = toggle_curve.curve_format
					toggle_curve_header.frame_count = len(toggle_anm_curves)
					toggle_curve_header.curve_size = 4
				
				entry.curve_headers.append(toggle_curve_header)
				entry.curves.extend(toggle_anm_curves)
			

			entries.append(entry)

	

	return entries


def clean_anm_curves(anm_curves: List[Curve]) -> List[Curve]:
	"""
	Return list of AnmCurves
	"""
	cleaned_curves: List[Curve] = list()

	for curve in anm_curves:
		if len(curve.keyframe.channels) > 1:
			cleaned_curves.append(curve)

	return cleaned_curves


	
def main():
	xfbin = Xfbin()
	xfbin.version = 121

	anm_props = [AnmProp(make_anm_armatures())]

	for prop in anm_props:

		page = XfbinPage()


		"""camera = NuccCamera()
		camera.struct_info = NuccStructInfo("camera01", "nuccChunkCamera", ANM_CHUNK_PATH)
		camera.fov = 45.0

		page.structs.append(camera)"""

		anm = make_anm(prop)

		page.structs.append(anm)


		page.struct_infos.append(NuccStructInfo("", "nuccChunkNull", ""))
		
		for armature in prop.armatures:
			page.struct_infos.extend(armature.nucc_struct_infos)
			page.struct_references.extend(armature.nucc_struct_references)

		
		

	xfbin.pages.append(page)
			
		

	write_xfbin(xfbin, directory + "\\test.xfbin")



	

if __name__ == '__main__':
	main()