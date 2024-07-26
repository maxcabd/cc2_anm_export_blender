import bpy
from os import path
from collections import defaultdict
from typing import Dict, List

from bpy_extras.io_utils import ExportHelper
from bpy.props import (EnumProperty, StringProperty, BoolProperty)
from bpy.types import Operator, Bone, ActionGroup, FCurve


from ..xfbin.xfbin_lib import *

from .common.helpers import *
from .common.bone_props import *
from .common.armature_props import *
from .common.coordinate_converter import *


class ExportAnmXfbin(Operator, ExportHelper):
	"""Export current collection as XFBIN file"""
	bl_idname = 'export_scene.xfbin'
	bl_label = 'Export animation XFBIN'

	filename_ext = '.xfbin'

	filter_glob: StringProperty(default='*.xfbin', options={'HIDDEN'})

	def collection_callback(self, context):
		items = set()
		active_col = bpy.context.collection

		if active_col:
			items.add((active_col.name, active_col.name, ''))

		items.update([(c.name, c.name, '') for c in bpy.data.collections])

		return list([i for i in items if i[0] != 'Collection'])
	
	def collection_update(self, context):
		pass


	collection: EnumProperty(
		items=collection_callback,
		name='Collection',
		description='The collection to be exported. All animations in the collection will be converted and put in the same XFBIN',
	)

	inject_to_xfbin: BoolProperty(
		name='Inject to existing XFBIN',
		description='If True, will add (or overwrite) the exportable animations as pages in the selected XFBIN.\n'
		'If False, will create a new XFBIN and overwrite the old file if it exists.\n\n'
		'NOTE: If True, the selected path has to be an XFBIN file that already exists, and that file will be overwritten',
		default=False,
	)

	def draw(self, context):
		layout = self.layout

		layout.label(text='Select a collection to export:')
		layout.prop_search(self, 'collection', bpy.data, 'collections')

		if self.collection:
			inject_row = layout.row()
			inject_row.prop(self, 'inject_to_xfbin')
		

		 
	def execute(self, context):
		import time

		start_time = time.time()
		exporter = AnmXfbinExporter(self, self.filepath, self.as_keywords(ignore=('filter_glob',)))
		exporter.export_collection(context)

		elapsed_s = "{:.2f}s".format(time.time() - start_time)
		self.report({'INFO'}, f'Finished exporting {exporter.collection.name} in {elapsed_s}')
		return {'FINISHED'}
	
class AnmXfbinExporter:
	xfbin: Xfbin

	def __init__(self, operator: Operator, filepath: str, export_settings: dict):
		self.operator = operator
		self.filepath = filepath
		self.collection: bpy.types.Collection = bpy.data.collections[export_settings.get('collection')]
		self.inject_to_xfbin = export_settings.get('inject_to_xfbin')


	
	def export_collection(self, context):
		self.xfbin = Xfbin()
		self.xfbin.version = 121

		if self.inject_to_xfbin:
			if not path.isfile(self.filepath):
				raise Exception(f'Cannot inject XFBIN - File does not exist: {self.filepath}')

			self.xfbin = read_xfbin(self.filepath)

		anm_chunks_obj = self.collection.objects.get(f'{XFBIN_ANIMATIONS_OBJ} [{self.collection.name}]')
		anm_chunks_data = anm_chunks_obj.xfbin_anm_chunks_data

		for anm_chunk in anm_chunks_data.anm_chunks:
			page = XfbinPage()
			page.struct_infos.append(NuccStructInfo("", "nuccChunkNull", ""))

		
			for clump in self.make_anm_armatures(anm_chunk):
				page.struct_infos.extend(clump.nucc_struct_infos)
				page.struct_references.extend(clump.nucc_struct_references)
				
		
			if anm_chunk.cameras:
				for camera_chunk in anm_chunk.cameras:
					camera = bpy.data.objects[camera_chunk.name]
					struct_info = NuccStructInfo(camera_chunk.name, "nuccChunkCamera", camera_chunk.path)
					nucc_camera = NuccCamera()
					nucc_camera.struct_info = struct_info
					nucc_camera.fov = fov_from_blender(camera.data.sensor_width, camera.data.lens)
					page.structs.append(nucc_camera)
			
			
			nucc_anm: NuccAnm = self.make_anm(anm_chunk, page.struct_infos)
			page.structs.append(nucc_anm)
			

			if self.inject_to_xfbin:
				# Replace the old anm page with the new one
				for i, page in enumerate(self.xfbin.pages):
					if any([struct_info.chunk_name == anm_chunk.name for struct_info in page.struct_infos]):
						self.xfbin.pages[i] = page
						break

			else:
				self.xfbin.pages.append(page)

			
		write_xfbin(self.xfbin, self.filepath)


	def make_anm_armatures(self, anm_chunk: XfbinAnmChunkPropertyGroup) -> List[AnmArmature]:
		"""
		Return list of armatures that contain animation data.
		"""
		anm_armatures: List[AnmArmature] = list()

		for index, clump in enumerate(anm_chunk.anm_clumps):
			arm_obj: Armature = bpy.data.objects[clump.name]

			if arm_obj.animation_data:
				if index == 0:
					action = bpy.data.actions.get(f'{anm_chunk.name}')
				else:
					action = arm_obj.animation_data.action

				arm_obj.animation_data_create()
				arm_obj.animation_data.action = action
				anm_armatures.append(AnmArmature(arm_obj))

		return anm_armatures


	def make_anm(self, anm_chunk: XfbinAnmChunkPropertyGroup, struct_infos: List[NuccStructInfo]) -> NuccAnm:
		"""
		Return NuccAnm object from AnmProp object.
		"""
		anm_armatures = self.make_anm_armatures(anm_chunk)

		anm = NuccAnm()
		anm.struct_info = NuccStructInfo(f"{anm_chunk.name}", "nuccChunkAnm", anm_chunk.path)

		anm.is_looped = anm_chunk.is_looped
		anm.frame_count = anm_chunk.frame_count * 100

		# Combined struct references from all armatures for this animation
		struct_references: List[NuccStructReference] = [ref for armature in anm_armatures for ref in armature.nucc_struct_references]

		anm.clumps.extend(self.make_anm_clump(anm_armatures, struct_references))
		anm.coord_parents.extend(self.make_anm_coords(anm_armatures))

		for armature in anm_armatures:
			anm.entries.extend(self.make_coord_entries(armature, struct_references, anm.clumps))

		if anm_chunk.cameras:
			for index, camera_chunk in enumerate(anm_chunk.cameras):
				camera = bpy.data.objects[camera_chunk.name]
				anm.entries.extend(self.make_camera_entries(camera, index))
				anm.other_entries_indices.append(len(struct_infos) + index)

		return anm
			
	def make_anm_clump(self, anm_armatures: List[AnmArmature], struct_references: List[NuccStructReference]) -> List[AnmClump]:
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


	def make_anm_coords(self, anm_armatures: List[AnmArmature]) -> List[CoordParent]:
		"""
		Return list of CoordParent objects from AnmArmature object.
		"""
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


	def make_coord_entries(self, anm_armature: AnmArmature, struct_references: List[NuccStructReference], clumps: List[AnmClump]) -> List[AnmEntry]:
		entries: List[AnmEntry] = list()

		
		# Filter the groups that aren't in anm_armature.anm_bones
		bone_names: List[str] = [bone.name for bone in anm_armature.anm_bones]
		groups: List[ActionGroup] = [group for group in anm_armature.action.groups.values() if group.name in bone_names]

		for group in groups:
			# ------------------- fcurves -------------------
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

			channels: List[FCurve] = group.channels

			for fcurve in channels:
				data_path = fcurve.data_path[fcurve.data_path.rindex('.') + 1:] if '.' in fcurve.data_path else ''

				if curves := channel_dict.get(data_path):
					curves[fcurve.array_index] = fcurve
				else:
					print(f'Warning: Ignoring curve with unsupported data path {fcurve.data_path} and index {fcurve.array_index}')

			
			# ------------------- entry -------------------
			clump_reference_index: int = struct_references.index(anm_armature.nucc_struct_references[0])
			clump_index: int = next((clump_index for clump_index, clump in enumerate(clumps) if clump.clump_index == clump_reference_index), None)

			coord_reference_index: int = struct_references.index(NuccStructReference(group.name, NuccStructInfo(group.name, "nuccChunkCoord", anm_armature.chunk_path)))
			coord_index: int = next((coord_index for coord_index, coord in enumerate(clumps[clump_index].bone_material_indices) if coord == coord_reference_index), None)
			
			entry = AnmEntry()
			entry.coord = AnmCoord(clump_index, coord_index)
			entry.entry_format = EntryFormat.Coord


			# ------------------- location -------------------
			location_track_header = TrackHeader()
			location_track = Track()

			location_keyframes: Dict[int, List[float]] = defaultdict(list)

			for i in range(3):
				if not location_curves[i]:
					continue

				axis_co = [0] * 2 * len(location_curves[i].keyframe_points)
				location_curves[i].keyframe_points.foreach_get('co', axis_co)

				axis_iter = iter(axis_co)

				for frame, value in zip(axis_iter, axis_iter):
					location_keyframes[int(frame)].append(value)
					

			for frame, value in location_keyframes.items():
				if len(location_keyframes.items()) > 1:
					location_track_header.track_index = 0
					location_track_header.key_format = NuccAnmKeyFormat.Vector3Linear
					location_track_header.frame_count = len(location_keyframes.items()) + 1 # Increment for null track value

					converted_value = convert_bone_value(anm_armature, group.name, 'location', location_track_header, value, frame)
					location_track.keys.append(converted_value)

				else:
					location_track_header.track_index = 0
					location_track_header.key_format = NuccAnmKeyFormat.Vector3Fixed
					location_track_header.frame_count = 1

					converted_value: NuccAnmKey = convert_bone_value(anm_armature, group.name, 'location', location_track_header, value, frame)
					location_track.keys.append(converted_value)

			if len(location_keyframes.items()) > 1:
				null_key = NuccAnmKey.Vec3Linear(-1, location_track.keys[-1].values)
				location_track.keys.append(null_key)

			entry.tracks.append(location_track)
			entry.track_headers.append(location_track_header)
		

			# ------------------- rotation quaternion -------------------
			rotation_track_header = TrackHeader()
			rotation_track = Track()

			rotation_keyframes: Dict[int, List[float]] = defaultdict(list)

			if any(quaternion_curves):
				for i in range(4):
					axis_co = [0] * 2 * len(quaternion_curves[i].keyframe_points)
					quaternion_curves[i].keyframe_points.foreach_get('co', axis_co)

					axis_iter = iter(axis_co)

					for frame, value in zip(axis_iter, axis_iter):
						rotation_keyframes[int(frame)].append(value)

				for frame, value in rotation_keyframes.items():
						rotation_track_header.track_index = 1
						rotation_track_header.key_format = NuccAnmKeyFormat.QuaternionLinear
						rotation_track_header.frame_count = len(rotation_keyframes.items()) + 1

						converted_value: NuccAnmKey  = convert_bone_value(anm_armature, group.name, 'rotation_quaternion', rotation_track_header, value, frame)
						rotation_track.keys.append(converted_value)

				null_key = NuccAnmKey.Vec4Linear(-1, rotation_track.keys[-1].values)
				rotation_track.keys.append(null_key)
				
				entry.tracks.append(rotation_track)
				entry.track_headers.append(rotation_track_header)

			elif any(rotation_curves):
				for i in range(3):
					axis_co = [0] * 2 * len(rotation_curves[i].keyframe_points)
					rotation_curves[i].keyframe_points.foreach_get('co', axis_co)

					axis_iter = iter(axis_co)

					for frame, value in zip(axis_iter, axis_iter):
						rotation_keyframes[int(frame)].append(value)
				
				for frame, value in rotation_keyframes.items():
					rotation_track_header.track_index = 1
					rotation_track_header.key_format = NuccAnmKeyFormat.EulerXYZFixed
					rotation_track_header.frame_count = len(rotation_keyframes.items())

					converted_value: NuccAnmKey = convert_bone_value(anm_armature, group.name, 'rotation_euler', rotation_track_header, value, frame)
					rotation_track.keys.append(converted_value)
			
				entry.tracks.append(rotation_track)
				entry.track_headers.append(rotation_track_header)


			# ------------------- scale -------------------
			scale_track_header = TrackHeader()
			scale_track = Track()

			scale_keyframes: Dict[int, List[float]] = defaultdict(list)

			for i in range(3):
				if not scale_curves[i]:
					continue

				axis_co = [0] * 2 * len(scale_curves[i].keyframe_points)
				scale_curves[i].keyframe_points.foreach_get('co', axis_co)

				axis_iter = iter(axis_co)

				for frame, value in zip(axis_iter, axis_iter):
					scale_keyframes[int(frame)].append(value)

				
			for frame, value in scale_keyframes.items():
				if len(scale_keyframes.items()) > 1:
					scale_track_header.track_index = 2
					scale_track_header.key_format = NuccAnmKeyFormat.Vector3Linear
					scale_track_header.frame_count = len(scale_keyframes.items()) + 1

					converted_value = convert_bone_value(anm_armature, group.name, 'scale', scale_track_header, value, frame)
					scale_track.keys.append(converted_value)
				else:
					scale_track_header.track_index = 2
					scale_track_header.key_format = NuccAnmKeyFormat.Vector3Fixed
					scale_track_header.frame_count = 1

					converted_value = convert_bone_value(anm_armature, group.name, 'scale', scale_track_header, value, frame)
					scale_track.keys.append(converted_value)
			
			if len(scale_keyframes.items()) > 1:
				null_key: NuccAnmKey = NuccAnmKey.Vec3Linear(-1, scale_track.keys[-1].values)
				scale_track.keys.append(null_key)
			
			entry.tracks.append(scale_track)
			entry.track_headers.append(scale_track_header)
		
			# ------------------- toggled -------------------
			toggle_track_header = TrackHeader()
			toggle_track = Track()

			toggle_keyframes: Dict[int, List[float]] = defaultdict(list)

			if any(toggle_curves):
				for i in range(1):
					if not toggle_curves[i]:
						continue

					#Get keyframes
					axis_co = [0] * 2 * len(toggle_curves[i].keyframe_points)
					toggle_curves[i].keyframe_points.foreach_get('co', axis_co)

					axis_iter = iter(axis_co)

					for frame, value in zip(axis_iter, axis_iter):
						toggle_keyframes[int(frame)].append(value)
				
				for frame, value in toggle_keyframes.items():
					toggle_track_header.track_index = 3
					toggle_track_header.key_format = NuccAnmKeyFormat.FloatFixed
					toggle_track_header.frame_count = len(toggle_keyframes.items())

					toggle_track.keys.append(NuccAnmKey.Float(value[0]))
			else: # If there is no toggle channel, we should still add it
				toggle_track_header.track_index = 3
				toggle_track_header.key_format = NuccAnmKeyFormat.FloatFixed
				toggle_track_header.frame_count = 1

				toggle_track.keys.append(NuccAnmKey.Float(1.0))
				
			entry.tracks.append(toggle_track)
			entry.track_headers.append(toggle_track_header)


			entries.append(entry)

		return entries


	def make_camera_entries(self, camera: bpy.types.Camera, other_index: int) -> List[AnmEntry]:
		context = bpy.context

		entries: List[AnmEntry] = list()

		translations: List[Vector] = list()
		rotations: List[Vector] = list()
		fov: List[float] = list()


		# Get the camera's location + rotation matrix for each frame and the FOV
		for frame in range(context.scene.frame_start, context.scene.frame_end + 1):
			# Last sanity check to see if camera has animation data
			if not camera.animation_data:
				continue

			context.scene.frame_set(frame)

			translations.append(camera.matrix_world.to_translation().copy())
			rotations.append( camera.matrix_world.to_quaternion().copy())
			fov.append(fov_from_blender(camera.data.sensor_width, camera.data.lens))


		# ------------------- entry -------------------
		entry = AnmEntry()
		entry.coord = AnmCoord(-1, other_index)
		entry.entry_format = EntryFormat.Camera

		
		# ------------------- location -------------------
		location_track_header = TrackHeader()
		location_track = Track()

		for frame, value in enumerate(translations):
			if len(translations) > 1:
				location_track_header.track_index = 0
				location_track_header.key_format = NuccAnmKeyFormat.Vector3Linear
				location_track_header.frame_count = len(translations) + 1

				converted_value: NuccAnmKey = convert_object_value("location", value[:], frame)

				location_track.keys.append(converted_value)

			
		
		null_key: NuccAnmKey = NuccAnmKey.Vec3Linear(-1, location_track.keys[-1].values)
		location_track.keys.append(null_key)

		entry.tracks.append(location_track)
		entry.track_headers.append(location_track_header)

		# ------------------- rotation quaternion -------------------
		rotation_track_header = TrackHeader()
		rotation_track = Track()

		for frame, value in enumerate(rotations):
			if len(rotations) > 1:
				rotation_track_header.track_index = 1
				rotation_track_header.key_format = NuccAnmKeyFormat.QuaternionShortTable
				rotation_track_header.frame_count = len(rotations)

				converted_value: NuccAnmKey = convert_object_value("rotation_quaternion", value[:])

				rotation_track.keys.append(converted_value)
		
	
		entry.tracks.append(rotation_track)
		entry.track_headers.append(rotation_track_header)

		# ------------------- FOV -------------------
		fov_track_header = TrackHeader()
		fov_track = Track()

		for frame, value in enumerate(fov):
			if len(fov) > 1:
				fov_track_header.track_index = 2
				fov_track_header.key_format = NuccAnmKeyFormat.FloatLinear
				fov_track_header.frame_count = len(fov) + 1

				converted_value: NuccAnmKey = convert_object_value("fov", [value], frame)

				fov_track.keys.append(converted_value)
		
		null_key = NuccAnmKey.FloatLinear(-1, fov_track.keys[-1].values)
		fov_track.keys.append(null_key)

		entry.tracks.append(fov_track)
		entry.track_headers.append(fov_track_header)

		entries.append(entry)


		return entries



def menu_func_export(self, context):
	self.layout.operator(ExportAnmXfbin.bl_idname, text='XFBIN Animation Container (.xfbin)')