
from typing import List, Dict


def make_chunk_dict(path: str, chunk_name: str, chunk_type: str, clump=None, reference=True, file=True):
	"""
	Create chunk map and chunk reference dictionaries.
	"""
	if clump is not None:
		chunk_name = clump.name

	# Map Chunk
	chunk = dict()
	chunk["Name"] = chunk_name
	chunk["Type"] = chunk_type
	chunk["Path"] = path

	
	if clump is not None:
		if len(clump.models) == 0:
			chunk_name = clump.bones[0]
			
		else:
			chunk_name = clump.models[0]

	# Reference Chunk
	chunk_ref = dict()
	chunk_ref["Name"] = chunk_name
	chunk_ref["Chunk"]: Dict = chunk
	
	if reference:
		return chunk, chunk_ref

	# File Chunk
	filename = ""

	if file:
		if chunk_type == "nuccChunkAnm":
			filename = chunk_name + '.anm'
	
		if chunk_type == "nuccChunkCamera":
			filename = chunk_name + '.camera'

		if chunk_type == "nuccChunkLightPoint":
			filename = chunk_name + '.lightpoint'
		
		if chunk_type == "nuccChunkLightDirc":
			filename = chunk_name + '.lightdirc'

		if chunk_type == "nuccChunkAmbient":
			filename = chunk_name + '.ambient'

		# File Chunk
		chunk_file = dict()
		chunk_file["File Name"] = filename
		chunk_file["Chunk"]: Dict = chunk

		return chunk_file
	
	else:
		return chunk


def make_chunk_dict_ref(path: str, chunk_ref_name: str, chunk_name: str, chunk_type: str):
	"""
	Create chunk map and chunk reference dictionaries.
	"""


	# Map Chunk
	chunk = dict()
	chunk["Name"] = chunk_name
	chunk["Type"] = chunk_type
	chunk["Path"] = path


	# Reference Chunk
	chunk_ref = dict()
	chunk_ref["Name"] = chunk_ref_name
	chunk_ref["Chunk"]: Dict = chunk
	return chunk_ref

	


def chain_list(nested_list):
    # Create an empty list to store the flattened values
    flattened_list = []

    # Iterate over the nested list and add each inner list to the flattened list
    for inner_list in nested_list:
        flattened_list.extend(inner_list)

    # Return the flattened list
    return flattened_list