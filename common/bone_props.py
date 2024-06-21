import bpy
from bpy.types import Armature
from mathutils import Matrix

def get_edit_matrix(armature: Armature, bone_name: str) -> Matrix:
    """
    Get the edit / rest bone matrix.
    """
    if armature is not None:
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='EDIT')

    bone = armature.data.edit_bones[bone_name]
    arm_mat = dict()

    if armature is not None:
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='EDIT')

        for arm_bone in armature.data.edit_bones:
            arm_mat[arm_bone.name] = arm_bone.matrix.copy()

    mat_parent = arm_mat.get(bone.parent.name, Matrix.Identity(4)) if bone.parent else Matrix.Identity(4)
    mat = arm_mat.get(bone.name, Matrix.Identity(4))
    mat = (mat_parent.inverted() @ mat)

    return mat


# Get the current matrix of the armature at the specified frame without using frame_set which is slow
def get_matrix_world(armature: Armature, edit_matrix: Matrix, bone_name: str) -> Matrix:
    """if armature is not None:
        bpy.context.view_layer.objects.active = armature

    matrix_world = armature.matrix_world.copy()
    
    bpy.context.scene.frame_set(frame_no)
    bpy.context.view_layer.update()

    return matrix_world"""

    # What if we try a different approach, ie multiply the matrix of the armature with the local matrix of the bone
    # to get the world matrix of the bone at the specified frame

    if armature is not None:
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='POSE')

    bone = armature.pose.bones[bone_name]

    local_matrix = bone.matrix.copy()

    world_matrix = edit_matrix @ local_matrix

    return world_matrix

    




# The above method is very slow, so we can use this method instead, the issue is the frame_set method is slow
# and we need to set the frame to the desired frame, so we can use this method to get the matrix world of the armature
# at the specified frame without using frame_set which is slow
