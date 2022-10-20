import bpy
from bpy.types import Armature
from mathutils import Matrix

def get_edit_matrix(armature: Armature, bone_name: str) -> Matrix:
	"""
	Get the edit / rest bone matrix. 
	"""
	
	# Implementation by https://github.com/SutandoTsukai181

	if armature is not None:
		bpy.context.view_layer.objects.active = armature
		bpy.ops.object.mode_set(mode='EDIT')

	bone = armature.data.edit_bones[bone_name]
	
	arm_sca = dict()
	arm_mat = dict()

	if armature is not None:
		bpy.context.view_layer.objects.active = armature
		bpy.ops.object.mode_set(mode='EDIT')

		for arm_bone in armature.data.edit_bones:
			arm_sca[arm_bone.name] = arm_bone.get('scale_signs')
			arm_mat[arm_bone.name] = arm_bone.matrix


	mat_parent = arm_mat.get(bone.parent.name, Matrix.Identity(4)) if bone.parent else Matrix.Identity(4)
	mat = arm_mat.get(bone.name, Matrix.Identity(4))
	mat = (mat_parent.inverted() @ mat)

	return mat
