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
from cProfile import Profile
import pstats

class ExportAnmXfbin(Operator, ExportHelper):
	"""Export current collection as XFBIN file"""
	bl_idname = 'export_anm_scene.xfbin'
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
		name='Inject to an existing XFBIN',
		description='If True, will add (or overwrite) the exportable animations as pages in the selected XFBIN.\n'
		'If False, will create a new XFBIN and overwrite the old file if it exists.\n\n'
		'NOTE: If True, the selected path has to be an XFBIN file that already exists, and that file will be overwritten',
		default=True,
	)

	"""inject_to_clump: BoolProperty(
		name='Inject to an existing Clump',
		description='If True, will add (or overwrite) the Clump animation(s) in the selected ANM in the XFBIN\n'
		'If False, will create a new Clump and overwrite the old file if it exists.\n\n'
		'NOTE: "Inject to existing XFBIN" has to be enabled for this option to take effect\n',					
		default=True,
	)"""

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
  
		#profiler = Profile()
		#profiler.enable()
		exporter.export_collection(context)

		'''profiler.disable()
		stats = pstats.Stats(profiler)
		stats.strip_dirs()
		stats.sort_stats('cumulative')
		stats.print_stats()'''
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
		else:
			self.inject_to_clump = False

		for obj in self.collection.objects:
			if obj.name.startswith(XFBIN_ANMS_OBJ):
				anm_chunks_obj = obj

		anm_chunks_data = anm_chunks_obj.xfbin_anm_chunks_data

		for anm_chunk in anm_chunks_data.anm_chunks:

			page = XfbinPage()
			page.struct_infos.append(NuccStructInfo("", "nuccChunkNull", ""))


			anm_chunk_name = anm_chunk.name.split(' (')[0] if ' (' in anm_chunk.name else anm_chunk.name # Remove suffix if it exists
   
			anm_clumps = self.make_anm_armatures(anm_chunk)

			for clump in anm_clumps:
				page.struct_infos.extend(clump.nucc_struct_infos.get_armature_info())
				page.struct_references.extend(clump.nucc_struct_references)

	
			if anm_chunk.cameras:
				for camera_chunk in anm_chunk.cameras:
					camera = bpy.data.objects[camera_chunk.name]
					camera_name = camera_chunk.name.split(' (')[0] if ' (' in camera_chunk.name else camera_chunk.name # Remove suffix if it exists

					nucc_camera = NuccCamera()
					nucc_camera.struct_info = NuccStructInfo(camera_name, "nuccChunkCamera", camera_chunk.path)
					
					nucc_camera.fov = fov_from_blender(camera.data.sensor_width, camera.data.lens)
					page.structs.append(nucc_camera)
			
			if anm_chunk.lightdircs:
				for light_prop in anm_chunk.lightdircs:
					lightdirc = bpy.data.objects.get(light_prop.name)
					if not lightdirc:
						continue
					lightdirc_name = light_prop.name.split(' (')[0] if ' (' in light_prop.name else light_prop.name

					nucc_lightdirc = NuccLightDirc()
					nucc_lightdirc.s
					nucc_lightdirc.struct_info = NuccStructInfo(lightdirc_name, "nuccChunkLightDirc", light_prop.path)

					nucc_lightdirc.color = lightdirc.data.color
					nucc_lightdirc.energy = lightdirc.data.energy

					converted_value: List[int] = convert_object_value("rotation_quaternion", lightdirc.matrix_world.to_quaternion().copy()[:]).values
					nucc_lightdirc.rotation = list(map(lambda x: x / QUAT_COMPRESS, converted_value))

					page.structs.append(nucc_lightdirc)
			
			if anm_chunk.lightpoints:
				for light_prop in anm_chunk.lightpoints:
					lightpoint = bpy.data.objects.get(light_prop.name)
					if not lightpoint:
						continue
					lightpoint_name = light_prop.name.split(' (')[0] if ' (' in light_prop.name else light_prop.name

					nucc_lightpoint = NuccLightPoint()
					nucc_lightpoint.struct_info = NuccStructInfo(lightpoint_name, "nuccChunkLightPoint", light_prop.path)

					nucc_lightpoint.color = lightpoint.data.color
					nucc_lightpoint.energy = lightpoint.data.energy

					converted_value: List[int] = convert_object_value("location", lightpoint.matrix_world.to_translation().copy()[:]).values
					nucc_lightpoint.location = converted_value

					nucc_lightpoint.radius = lightpoint.data.shadow_soft_size
					
					if lightpoint.data.use_custom_distance:
						nucc_lightpoint.cutoff = lightpoint.data.cutoff_distance
					else:
						nucc_lightpoint.cutoff = 0.0

					page.structs.append(nucc_lightpoint)
			
			if anm_chunk.ambients:
				for light_prop in anm_chunk.ambients:
					ambient_obj = bpy.data.objects.get(light_prop.name)
					if not ambient_obj:
						continue
					ambient_name = light_prop.name.split(' (')[0] if ' (' in light_prop.name else light_prop.name

					nucc_ambient = NuccAmbient()
					nucc_ambient.struct_info = NuccStructInfo(ambient_name, "nuccChunkAmbient", light_prop.path)

					nucc_ambient.color = ambient_obj.data.color
					nucc_ambient.energy = ambient_obj.data.energy

					page.structs.append(nucc_ambient)
			
			
			nucc_anm: NuccAnm = self.make_anm(anm_chunk, anm_clumps, page.struct_infos)
			page.structs.append(nucc_anm)
			

			if self.inject_to_xfbin:
				# Add page or overwrite existing page
				for i, p in enumerate(self.xfbin.pages):
					if any(struct_info.chunk_name == anm_chunk_name for struct_info in p.struct_infos):
						self.xfbin.pages[i] = page
						break
				else:
					self.xfbin.pages.append(page)
			else:
				self.xfbin.pages.append(page)

			
			
		write_xfbin(self.xfbin, self.filepath)


	def make_anm_armatures(self, anm_chunk: XfbinAnmChunkPropertyGroup) -> List[AnmArmature]:
		"""
		Return list of armatures that contain animation data.
		"""
		anm_armatures: List[AnmArmature] = list()

		for index, clump_props in enumerate(anm_chunk.anm_clumps):
			clump_props: XfbinAnmClumpPropertyGroup

			arm_obj: Armature = bpy.data.objects.get(clump_props.name)

			if not arm_obj:
				#self.report({"WARNING"}, f"Armature {clump_props.name} not found, skipping...")
				continue
   
			if arm_obj.animation_data:
				if index == 0:
					action = bpy.data.actions.get(f'{anm_chunk.name}')
				else:
					action = arm_obj.animation_data.action

				arm_obj.animation_data_create()
				arm_obj.animation_data.action = action
				anm_armatures.append(AnmArmature(arm_obj))

		return anm_armatures


	def make_anm(self, anm_chunk: XfbinAnmChunkPropertyGroup, anm_armatures, struct_infos: List[NuccStructInfo]) -> NuccAnm:
		"""
		Return NuccAnm object from AnmProp object.
		"""

		anm = NuccAnm()

		anm_name = anm_chunk.name.split(' (')[0] if ' (' in anm_chunk.name else anm_chunk.name
		anm.struct_info = NuccStructInfo(f"{anm_name}", "nuccChunkAnm", anm_chunk.path)

		anm.is_looped = anm_chunk.is_looped
		anm.frame_count = anm_chunk.frame_count * 100

		# Combined struct references from all armatures for this animation
		struct_references: List[NuccStructReference] = [ref for armature in anm_armatures for ref in armature.nucc_struct_references]

		anm.clumps.extend(self.make_anm_clump(anm_armatures, struct_references))
		anm.coord_parents.extend(self.make_anm_coords(anm_armatures))

		for armature in anm_armatures:
			anm.entries.extend(self.make_coord_entries(armature, struct_references, anm.clumps))
			if anm_chunk.export_material_animations:
				anm.entries.extend(self.make_material_entries(armature, struct_references, anm.clumps))


		if anm_chunk.cameras:
			for index, camera_chunk in enumerate(anm_chunk.cameras):
				camera = bpy.data.objects.get(camera_chunk.name)
				if not camera:
					continue
				anm.entries.extend(self.make_camera_entries(camera, index))
				anm.other_entries_indices.append(len(struct_infos) + index)

		if anm_chunk.lightdircs:
			for index, light_prop in enumerate(anm_chunk.lightdircs):
				lightdirc = bpy.data.objects.get(light_prop.name)
				if not lightdirc:
					continue
				anm.entries.extend(self.make_lightdirc_entries(lightdirc, index + len(anm_chunk.cameras)))
				anm.other_entries_indices.append(len(struct_infos) + index + len(anm_chunk.cameras))
		
		if anm_chunk.lightpoints:
			for index, light_prop in enumerate(anm_chunk.lightpoints):
				lightpoint = bpy.data.objects.get(light_prop.name)
				if not lightpoint:
					continue
				anm.entries.extend(self.make_lightpoint_entries(lightpoint, index + len(anm_chunk.cameras) + len(anm_chunk.lightdircs)))
				anm.other_entries_indices.append(len(struct_infos) + index + len(anm_chunk.cameras) + len(anm_chunk.lightdircs))

		if anm_chunk.ambients:
			for index, light_prop in enumerate(anm_chunk.ambients):
				ambient = bpy.data.objects.get(light_prop.name)
				if not ambient:
					continue
				anm.entries.extend(self.make_ambient_entries(ambient, index + len(anm_chunk.cameras) + len(anm_chunk.lightdircs) + len(anm_chunk.lightpoints)))
				anm.other_entries_indices.append(len(struct_infos) + index + len(anm_chunk.cameras) + len(anm_chunk.lightdircs) + len(anm_chunk.lightpoints))

		return anm
			
	def make_anm_clump(self, anm_armatures: List[AnmArmature], struct_references: List[NuccStructReference]) -> List[AnmClump]:
		clumps: List[AnmClump] = list()


		for anm_armature in anm_armatures:
			clump = AnmClump()

			if anm_armature.models:
				clump.clump_index = struct_references.index(NuccStructReference(anm_armature.models[0], NuccStructInfo(anm_armature.name, "nuccChunkClump", anm_armature.chunk_path)))
					
			else:
				clump.clump_index = struct_references.index(NuccStructReference(anm_armature.bones[0].name, NuccStructInfo(anm_armature.name, "nuccChunkClump", anm_armature.chunk_path)))
					
			bone_material_indices: List[int] = list()

			

			bone_indices: List[int] = [struct_references.index(NuccStructReference(bone.name, NuccStructInfo(bone.name, "nuccChunkCoord", anm_armature.chunk_path))) for bone in anm_armature.bones]
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

			for bone in anm_armature.armature.data.bones:
				if bone.parent:
					parent = AnmCoord(armature_index, anm_armature.bones.index(bone.parent))
					child = AnmCoord(armature_index, anm_armature.bones.index(bone))

					coord_parents.append(CoordParent(parent, child))

				
			# Handle case where bone has constraints
			'''for bone in armature_obj.data.bones:
				if ("Copy Transforms" in anm_armatures[armature_index].armature.pose.bones[bone.name].constraints):
					target_object = anm_armatures[armature_index].armature.pose.bones[bone.name].constraints["Copy Transforms"].target
					parent_armature = next((arm for arm in anm_armatures if arm.armature == target_object), None)
					if parent_armature:
						parent_clump_index = anm_armatures.index(parent_armature)
						parent = AnmCoord(parent_clump_index, parent_armature.bones.index(armature_obj.pose.bones[bone.name].constraints["Copy Transforms"].subtarget))
						child = AnmCoord(armature_index, anm_armature.bones.index(bone.name))

						coord_parents.append(CoordParent(parent, child))'''
			

		return coord_parents


	def make_coord_entries(self, anm_armature: AnmArmature, struct_references: List[NuccStructReference], clumps: List[AnmClump]) -> List[AnmEntry]:
		entries: List[AnmEntry] = list()

		# Filter the groups that are in anm_armature.anm_bones
		bone_names = [bone.name for bone in anm_armature.armature.data.bones]
		#print([group.name for group in anm_armature.action.groups.values()])
		groups = [group for group in anm_armature.action.groups.values() if group.name in bone_names]

		for group in groups:
			if not group.channels:
				continue
			# Initialize curve lists
			location_curves = [None] * 3
			rotation_curves = [None] * 3  # Euler rotations
			quaternion_curves = [None] * 4
			scale_curves = [None] * 3
			opacity_curves = [None]

			channel_dict = {
				'location': location_curves,
				'rotation_euler': rotation_curves,
				'rotation_quaternion': quaternion_curves,
				'scale': scale_curves,
				'opacity': opacity_curves,
			}

			# Assign curves to their respective lists
			for fcurve in group.channels:
				data_path = fcurve.data_path.split('.')[-1]
				if data_path in channel_dict:
					channel_dict[data_path][fcurve.array_index] = fcurve

			# ------------------- entry -------------------
			clump_reference_index = struct_references.index(anm_armature.nucc_struct_references[0])
			clump_index = next((i for i, clump in enumerate(clumps) if clump.clump_index == clump_reference_index), None)

			coord_reference_index = struct_references.index(NuccStructReference(group.name, NuccStructInfo(group.name, "nuccChunkCoord", anm_armature.chunk_path)))
			coord_index = next((i for i, coord in enumerate(clumps[clump_index].bone_material_indices) if coord == coord_reference_index), None)

			entry = AnmEntry()
			entry.coord = AnmCoord(clump_index, coord_index)
			entry.entry_format = EntryFormat.Coord
   
			entry_bone = anm_armature.armature.data.bones[group.name]
			bone_matrix = get_edit_matrix(anm_armature.armature, entry_bone)
   
			loc, rot, scale = bone_matrix.decompose()
			

			# ------------------- location -------------------
			location_keyframes = defaultdict(list)
			last_value = [0, 0, 0]

			loc_frames = set()
			for curve in location_curves:
				if curve:
					loc_frames.update([kp.co[0] for kp in curve.keyframe_points])

			for frame in sorted(loc_frames):
				frame_values = last_value.copy()

				for curve in location_curves:
					if curve:
						curve_index = curve.array_index
						keyframe = next((kp for kp in curve.keyframe_points if kp.co[0] == frame), None)
						if keyframe:
							frame_values[curve_index] = curve.evaluate(keyframe.co[0])

				last_value = frame_values.copy()
				location_keyframes[int(frame)] = frame_values
			
			'''for i in range(3):  # Iterate over the three location axes
				curve = location_curves[i]
				if curve:
					for kp in curve.keyframe_points:
						frame = int(kp.co[0])
						value = curve.evaluate(kp.co[0])
						location_keyframes[frame].append(value)'''

			frame_count = len(location_keyframes)
			is_multiple_keyframes = frame_count > 1

			location_track_header = TrackHeader()
			location_track_header.track_index = 0
			location_track_header.key_format = NuccAnmKeyFormat.Vector3Linear if is_multiple_keyframes else NuccAnmKeyFormat.Vector3Fixed
			location_track_header.frame_count = frame_count + is_multiple_keyframes

			location_track = Track()
			location_track.keys = [
				convert_bone_value(loc, rot, scale, 'location', location_track_header, value, frame)
				for frame, value in location_keyframes.items()
			]

			if is_multiple_keyframes:
				null_key = NuccAnmKey.Vec3Linear(-1, location_track.keys[-1].values)
				location_track.keys.append(null_key)

			entry.tracks.append(location_track)
			entry.track_headers.append(location_track_header)

			# ------------------- rotation quaternion -------------------
			rotation_track_header = TrackHeader()
			rotation_track = Track()

			rotation_keyframes = defaultdict(list)
   
			if any(quaternion_curves):
			
				# Find all unique keyframe frames across all quaternion curves
				all_frames = set()
				for curve in quaternion_curves:
					if curve:
						all_frames.update([kp.co[0] for kp in curve.keyframe_points])

				# Sort frames to process in chronological order
				sorted_frames = sorted(all_frames)

				# Last known quaternion values (initialize with default quaternion [1, 0, 0, 0])
				last_quat = [1.0, 0.0, 0.0, 0.0]

				# Iterate over frames
				for frame in sorted_frames:
					#frame_values = last_quat.copy()  # Start with last known values

					for curve in quaternion_curves:
						if curve:
							curve_index = curve.array_index
							# Check if this curve has a keyframe at the current frame
							keyframe = next((kp for kp in curve.keyframe_points if kp.co[0] == frame), None)
							if keyframe:
								last_quat[curve_index] = curve.evaluate(frame)

					# Update last known values
					#last_quat = frame_values.copy()

					# Store the complete quaternion for this frame
					rotation_keyframes[int(frame)] = last_quat.copy()


				frame_count = len(rotation_keyframes)
				rotation_track_header.track_index = 1
				rotation_track_header.key_format = NuccAnmKeyFormat.QuaternionLinear
				rotation_track_header.frame_count = frame_count + 1

				rotation_track.keys = [
					convert_bone_value(loc, rot, scale, 'rotation_quaternion', rotation_track_header, value, frame)
					for frame, value in rotation_keyframes.items()
				]

				null_key = NuccAnmKey.Vec4Linear(-1, rotation_track.keys[-1].values)
				rotation_track.keys.append(null_key)

				entry.tracks.append(rotation_track)
				entry.track_headers.append(rotation_track_header)

			elif any(rotation_curves):
				rot_updated_frames = set()

				all_frames = set()
				for curve in rotation_curves:
					if curve:
						all_frames.update([kp.co[0] for kp in curve.keyframe_points])

				last_euler = [0, 0, 0]

				for frame in sorted(all_frames):
					frame_values = last_euler.copy()

					for curve in rotation_curves:
						if curve:
							curve_index = curve.array_index
							keyframe = next((kp for kp in curve.keyframe_points if kp.co[0] == frame), None)
							if keyframe:
								frame_values[curve_index] = curve.evaluate(keyframe.co[0])

					last_euler = frame_values.copy()
					rotation_keyframes[int(frame)] = frame_values

				frame_count = len(rotation_keyframes)
				rotation_track_header.track_index = 1
				rotation_track_header.key_format = NuccAnmKeyFormat.EulerXYZFixed
				rotation_track_header.frame_count = frame_count

				rotation_track.keys = [
					convert_bone_value(loc, rot, scale, 'rotation_euler', rotation_track_header, value, frame)
					for frame, value in rotation_keyframes.items()
				]

				entry.tracks.append(rotation_track)
				entry.track_headers.append(rotation_track_header)

			# ------------------- scale -------------------
			scale_track_header = TrackHeader()
			scale_track = Track()

			scale_keyframes = defaultdict(list)
			for curve in scale_curves:
				if curve:
					keyframes = [kp.co[0] for kp in curve.keyframe_points]
					values = [curve.evaluate(kp.co[0]) for kp in curve.keyframe_points]
					for frame, value in zip(keyframes, values):
						scale_keyframes[int(frame)].append(value)

			frame_count = len(scale_keyframes)
			if frame_count > 1:
				scale_track_header.track_index = 2
				scale_track_header.key_format = NuccAnmKeyFormat.Vector3Linear
				scale_track_header.frame_count = frame_count + 1

				scale_track.keys = [
					convert_bone_value(loc, rot, scale, 'scale', scale_track_header, value, frame)
					for frame, value in scale_keyframes.items()
				]

				null_key = NuccAnmKey.Vec3Linear(-1, scale_track.keys[-1].values)
				scale_track.keys.append(null_key)
			else:
				scale_track_header.track_index = 2
				scale_track_header.key_format = NuccAnmKeyFormat.Vector3Fixed
				scale_track_header.frame_count = 1

				scale_track.keys = [
					convert_bone_value(loc, rot, scale, 'scale', scale_track_header, value, frame)
					for frame, value in scale_keyframes.items()
				]

			entry.tracks.append(scale_track)
			entry.track_headers.append(scale_track_header)

			# ------------------- toggled -------------------
			opacity_track_header = TrackHeader()
			opacity_track = Track()

			opacity_keyframes = defaultdict(list)

			if any(opacity_curves):
				if opacity_curves[0]:
					keyframes = [kp.co[0] for kp in opacity_curves[0].keyframe_points]

					values = [opacity_curves[0].evaluate(kp.co[0]) for kp in opacity_curves[0].keyframe_points]

					for frame, value in zip(keyframes, values):
						opacity_keyframes[int(frame)].append(value)

				opacity_track_header.track_index = 3
				opacity_track_header.key_format = NuccAnmKeyFormat.FloatLinear
				opacity_track_header.frame_count = len(opacity_keyframes) or 1

				opacity_track.keys = [
					NuccAnmKey.FloatLinear(int(frame * 100), value[0])
					for frame, value in opacity_keyframes.items()
				]
			else:
				opacity_track_header.track_index = 3
				opacity_track_header.key_format = NuccAnmKeyFormat.FloatFixed
				opacity_track_header.frame_count = 1

				opacity_track.keys = [NuccAnmKey.Float(1.0)]

			entry.tracks.append(opacity_track)
			entry.track_headers.append(opacity_track_header)

			entries.append(entry)

		return entries
	

	def make_material_entries(self, anm_armature: AnmArmature, struct_references: List[NuccStructReference], clumps: List[AnmClump]) -> List[AnmEntry]:
		context = bpy.context

		entries: List[AnmEntry] = list()

		def get_node_input_default(node_name: str, input_index: int):
			node = nodes.get(node_name)
			if node:
				return node.inputs[input_index].default_value
			return [0, 0, 0]
		

		def get_node_output_default(node_name: str, output_index: int):
			node = nodes.get(node_name)
			if node:
				return node.outputs[output_index].default_value
			return 0
		
		def create_and_append_track(entry: AnmEntry, track_index: int, key_format: NuccAnmKeyFormat, values: List[float]):
			""" Create helper method since most material entries have the same structure """
			track_header = TrackHeader()
			track_header.track_index = track_index

			if track_index == 4:
				track_header.key_format = NuccAnmKeyFormat.FloatFixed
				track_header.frame_count = 1

			track_header.key_format = key_format
			track_header.frame_count = len(values)

			track = Track()

			for value in values:
				converted_value: NuccAnmKey = NuccAnmKey.Float(value)
				track.keys.append(converted_value)

			entry.tracks.append(track)
			entry.track_headers.append(track_header)


		for material_name in anm_armature.materials:
			material = bpy.data.materials.get(material_name)

			if not material:
				continue

			if not material.node_tree.animation_data:
				continue

			
			nodes = material.node_tree.nodes

			u1_location: List[float] = list()
			v1_location: List[float] = list()

			u1_scale: List[float] = list()
			v1_scale: List[float] = list()

			u2_location: List[float] = list()
			v2_location: List[float] = list()
			
			u2_scale: List[float] = list()
			v2_scale: List[float] = list()

			blend_values: List[float] = list()
			glare_values: List[float] = list()
			alpha_values: List[float] = list()


			for frame in range(context.scene.frame_start, context.scene.frame_end + 1):
				context.scene.frame_set(frame)

				uv1_translation = get_node_input_default("Mapping", 1) if "Mapping" in nodes else get_node_input_default("UV_0_Mapping", 1)
				uv1_scale = get_node_input_default("Mapping", 3) if "Mapping" in nodes else get_node_input_default("UV_0_Mapping", 3)

				uv2_location = get_node_input_default("UV_1_Mapping", 1)
				uv2_scale = get_node_input_default("UV_1_Mapping", 3) if "UV_1_Mapping" in nodes else [1, 1, 1]


				u1_location.append(uv1_translation[0])
				v1_location.append((-1 * uv1_scale[1]) + (1 - uv1_translation[1])) # Invert Y axis and offset by 1 to match game's UV space 
				u1_scale.append(uv1_scale[0])
				v1_scale.append(uv1_scale[1])

				u2_location.append(uv2_location[0])
				v2_location.append((-1 * uv2_scale[1])+ (1 - uv2_location[1])) 
				u2_scale.append(uv2_scale[0])
				v2_scale.append(uv2_scale[1])

				blend_values.append(get_node_output_default("BlendRate", 0) if "BlendRate" in nodes else 0)
				glare_values.append(get_node_output_default("Glare", 0) if "Glare" in nodes else 0.12)
				alpha_values.append(get_node_output_default("Alpha", 0) if "Alpha" in nodes else 205.0)
			
			# Value is a (track, track_index) tuple
			material_data_paths = {
				"u1_location": (u1_location, 0),
				"v1_location": (v1_location, 1),
				"u1_scale": (u1_scale, 8),
				"v1_scale": (v1_scale, 9),
				"u2_location": (u2_location, 2),
				"v2_location": (v2_location, 3),
				"u2_scale": (u2_scale, 10),
				"v2_scale": (v2_scale, 11),
				"blend": (blend_values, 12),
				"glare": (glare_values, 15),
				"alpha": (alpha_values, 16),
				"celshade": ([0.0], 4),
			}


			# ------------------- entry -------------------
			clump_reference_index = struct_references.index(anm_armature.nucc_struct_references[0])
			clump_index = next((i for i, clump in enumerate(clumps) if clump.clump_index == clump_reference_index), None)

			material_reference_index = struct_references.index(NuccStructReference(material_name, NuccStructInfo(material_name, "nuccChunkMaterial", anm_armature.chunk_path)))
			material_index = next((i for i, material in enumerate(clumps[clump_index].bone_material_indices) if material == material_reference_index), None)

			entry = AnmEntry()
			entry.coord = AnmCoord(clump_index, material_index)
			entry.entry_format = EntryFormat.Material

			
			for _, (values, track_index) in material_data_paths.items():
				create_and_append_track(entry, track_index, NuccAnmKeyFormat.FloatTable, values)
			


			entries.append(entry)

		return entries


	def make_camera_entries(self, camera: bpy.types.Camera, other_index: int) -> List[AnmEntry]:
		context = bpy.context

		entries: List[AnmEntry] = list()

		translations: List[Vector] = list()
		rotations: List[Vector] = list()
		fov: List[float] = list()
  
		# Last sanity check to see if camera has animation data
		if not camera.animation_data:
			return entries

		if not camera.animation_data.action:
			return entries


		# Get the camera's location + rotation matrix for each frame and the FOV
		for frame in range(context.scene.frame_start, context.scene.frame_end + 1):

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
	

	def make_lightdirc_entries(self, lightdirc: bpy.types.Light, other_index: int) -> List[AnmEntry]:
		context = bpy.context

		entries: List[AnmEntry] = list()

		colors: List[Vector] = list()
		energies: List[float] = list()
		rotations: List[Vector] = list()

		# Get the light's color, energy, and rotation matrix for each frame
		for frame in range(context.scene.frame_start, context.scene.frame_end + 1):
			# Last sanity check to see if camera has animation data
			if not lightdirc.animation_data:
				continue

			context.scene.frame_set(frame)

			colors.append(lightdirc.data.color.copy())
			energies.append(lightdirc.data.energy)
			rotations.append(lightdirc.matrix_world.to_quaternion().copy())

		# ------------------- entry -------------------
		entry = AnmEntry()
		entry.coord = AnmCoord(-1, other_index)
		entry.entry_format = EntryFormat.LightDirc

		# ------------------- color -------------------
		color_track_header = TrackHeader()
		color_track = Track()

		for value in colors:
			color_track_header.track_index = 0
			color_track_header.key_format = NuccAnmKeyFormat.ColorRGBTable
			color_track_header.frame_count = len(colors)

			converted_value: NuccAnmKey = convert_object_value("color", list(map(lambda x: round(x, 2), value[:])))

			color_track.keys.append(converted_value)

		# Pad color_track.keys with the last value so the length is a multiple of 4
		while len(color_track.keys) % 4 != 0:
			color_track.keys.append(color_track.keys[-1])

		# Update the frame count to reflect the new length
		color_track_header.frame_count = len(color_track.keys)
		
		entry.tracks.append(color_track)
		entry.track_headers.append(color_track_header)


		# ------------------- energy -------------------
		energy_track_header = TrackHeader()
		energy_track = Track()

		for value in energies:
			energy_track_header.track_index = 1
			energy_track_header.key_format = NuccAnmKeyFormat.FloatTable
			energy_track_header.frame_count = len(energies)

			energy_track.keys.append(NuccAnmKey.Float(value))
		
		entry.tracks.append(energy_track)
		entry.track_headers.append(energy_track_header)

		# ------------------- rotation quaternion -------------------
		rotation_track_header = TrackHeader()
		rotation_track = Track()

		for value in rotations:
			rotation_track_header.track_index = 2
			rotation_track_header.key_format = NuccAnmKeyFormat.QuaternionShortTable
			rotation_track_header.frame_count = len(rotations)

			converted_value: NuccAnmKey = convert_object_value("rotation_quaternion", value[:])

			rotation_track.keys.append(converted_value)

		entry.tracks.append(rotation_track)
		entry.track_headers.append(rotation_track_header)

		entries.append(entry)


		return entries

	def make_lightpoint_entries(self, lightpoint: bpy.types.Light, other_index: int) -> List[AnmEntry]:
		context = bpy.context

		entries: List[AnmEntry] = list()

		colors: List[Vector] = list()
		energies: List[float] = list()
		translations: List[Vector] = list()
		radii: List[float] = list()
		cutoffs: List[float] = list()

		# Get the light's color, energy, location, radius, and cutoff for each frame
		for frame in range(context.scene.frame_start, context.scene.frame_end + 1):
			# Last sanity check to see if camera has animation data
			if not lightpoint.animation_data:
				continue

			context.scene.frame_set(frame)

			colors.append(lightpoint.data.color.copy())
			energies.append(lightpoint.data.energy)
			translations.append(lightpoint.matrix_world.to_translation().copy())
			radii.append(lightpoint.data.shadow_soft_size)
			cutoffs.append(lightpoint.data.cutoff_distance if lightpoint.data.use_custom_distance else 0.0)
		

		# ------------------- entry -------------------
		entry = AnmEntry()
		entry.coord = AnmCoord(-1, other_index)
		entry.entry_format = EntryFormat.LightPoint

		# ------------------- color -------------------
		color_track_header = TrackHeader()
		color_track = Track()

		for value in colors:
			color_track_header.track_index = 0
			color_track_header.key_format = NuccAnmKeyFormat.ColorRGBTable
			color_track_header.frame_count = len(colors)

			converted_value: NuccAnmKey = convert_object_value("color", list(map(lambda x: round(x, 2), value[:])))

			color_track.keys.append(converted_value)
		
		
		# Pad color_track.keys with the last value so the length is a multiple of 4
		while len(color_track.keys) % 4 != 0:
			color_track.keys.append(color_track.keys[-1])

		# Update the frame count to reflect the new length
		color_track_header.frame_count = len(color_track.keys)

		entry.tracks.append(color_track)
		entry.track_headers.append(color_track_header)

		# ------------------- energy -------------------
		energy_track_header = TrackHeader()
		energy_track = Track()

		for value in energies:
			energy_track_header.track_index = 1
			energy_track_header.key_format = NuccAnmKeyFormat.FloatTable
			energy_track_header.frame_count = len(energies)

			energy_track.keys.append(NuccAnmKey.Float(value))

		entry.tracks.append(energy_track)
		entry.track_headers.append(energy_track_header)

		# ------------------- location -------------------
		location_track_header = TrackHeader()
		location_track = Track()

		for frame, value in enumerate(translations):
			location_track_header.track_index = 2
			location_track_header.key_format = NuccAnmKeyFormat.Vector3Linear
			location_track_header.frame_count = len(translations) + 1

			converted_value: NuccAnmKey = convert_object_value("location", value[:], frame)

			location_track.keys.append(converted_value)
		
		null_key = NuccAnmKey.Vec3Linear(-1, location_track.keys[-1].values)
		location_track.keys.append(null_key)

		entry.tracks.append(location_track)
		entry.track_headers.append(location_track_header)

		# ------------------- radius -------------------
		radius_track_header = TrackHeader()
		radius_track = Track()

		for value in radii:
			radius_track_header.track_index = 3
			radius_track_header.key_format = NuccAnmKeyFormat.FloatTable
			radius_track_header.frame_count = len(radii)

			radius_track.keys.append(NuccAnmKey.Float(value))

		entry.tracks.append(radius_track)
		entry.track_headers.append(radius_track_header)

		# ------------------- cutoff -------------------
		cutoff_track_header = TrackHeader()
		cutoff_track = Track()

		for value in cutoffs:
			cutoff_track_header.track_index = 4
			cutoff_track_header.key_format = NuccAnmKeyFormat.FloatTable
			cutoff_track_header.frame_count = len(cutoffs)

			cutoff_track.keys.append(NuccAnmKey.Float(value))

		entry.tracks.append(cutoff_track)
		entry.track_headers.append(cutoff_track_header)

		entries.append(entry)


		return entries

	def make_ambient_entries(self, ambient: bpy.types.Light, other_index: int) -> List[AnmEntry]:
		context = bpy.context

		entries: List[AnmEntry] = list()

		colors: List[Vector] = list()
		energies: List[float] = list()

		# Get the light's color and energy for each frame
		for frame in range(context.scene.frame_start, context.scene.frame_end + 1):
			# Last sanity check to see if camera has animation data
			if not ambient.animation_data:
				continue

			context.scene.frame_set(frame)

			colors.append(ambient.data.color.copy())
			energies.append(ambient.data.energy)

		# ------------------- entry -------------------
		entry = AnmEntry()
		entry.coord = AnmCoord(-1, other_index)

		entry.entry_format = EntryFormat.Ambient

		# ------------------- color -------------------
		color_track_header = TrackHeader()
		color_track = Track()

		for value in colors:
			color_track_header.track_index = 0
			color_track_header.key_format = NuccAnmKeyFormat.ColorRGBTable
			color_track_header.frame_count = len(colors)

			converted_value: NuccAnmKey = convert_object_value("color", list(map(lambda x: round(x, 2), value[:])))

			color_track.keys.append(converted_value)
		
		# Pad color_track.keys with the last value so the length is a multiple of 4
		while len(color_track.keys) % 4 != 0:
			color_track.keys.append(color_track.keys[-1])

		# Update the frame count to reflect the new length
		color_track_header.frame_count = len(color_track.keys)

		entry.tracks.append(color_track)
		entry.track_headers.append(color_track_header)


		# ------------------- energy -------------------
		energy_track_header = TrackHeader()
		energy_track = Track()

		for value in energies:
			energy_track_header.track_index = 1
			energy_track_header.key_format = NuccAnmKeyFormat.FloatTable
			energy_track_header.frame_count = len(energies)

			energy_track.keys.append(NuccAnmKey.Float(value))
		
		entry.tracks.append(energy_track)
		entry.track_headers.append(energy_track_header)

		entries.append(entry)


		return entries


		
def menu_export(self, context):
	self.layout.operator(ExportAnmXfbin.bl_idname, text='XFBIN Animation Container (.xfbin)')