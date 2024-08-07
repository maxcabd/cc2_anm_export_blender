import bpy


from .exporter import ExportAnmXfbin, menu_export


classes = (
    ExportAnmXfbin,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.TOPBAR_MT_file_export.append(menu_export)


def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)
   
    bpy.types.TOPBAR_MT_file_export.remove(menu_export)