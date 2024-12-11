import bpy
from bpy.types import Armature
from mathutils import Matrix

def get_edit_matrix(armature: Armature, bone: str) -> Matrix:
    """
    Get the original bone matrix in edit mode
    """

    mat = Matrix(bone.get('matrix', bone.matrix_local))
    parent_mat = Matrix(bone.parent.get('matrix', bone.parent.matrix_local)) if bone.parent else Matrix.Identity(4)
    mat = parent_mat.inverted() @ mat

    
    return mat


