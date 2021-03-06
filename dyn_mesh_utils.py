
import bpy
import bmesh
from mathutils import Vector
import math

# def get_adj_slctd_vert(vert):
# 	adj_slctd_verts = []
# 	for edge in vert.link_edges:
# 		if edge.other_vert(vert).select:
# 			adj_slctd_verts += edge.other_vert(vert)
# 	return adj_slctd_verts

def other_vertex(vert, edge_index):
    return vert.link_edges[edge_index].other_vert(vert)

# def get_edge_direction(from_vert, to_vert):
#     prev_vert = from_vert
#     for edge in from_vert.link_edges:
#         current_vert = edge.other_vert(from_vert)
#         while current_vert != None:
#             next_vert = get_next_wire_vert(prev_vert, current_vert)
#             prev_vert, current_vert = current_vert, next_vert
#             if current_vert == to_vert:
#                 return edge
#     return None

# def generate_in_between_verts(from_vert, to_vert):
#     # should be wire (for now)
#     prev_vert = from_vert
#     edge = get_edge_direction(from_vert, to_vert)
#     current_vert = edge.other_vert(from_vert)
#     while current_vert != to_vert:
#         yield current_vert
#         next_vert = get_next_wire_vert(prev_vert, current_vert)
#         prev_vert, current_vert = current_vert, next_vert

def generate_next_verts(prev_vert, current_vert, verts_count):
    for i in range(verts_count):
        next_vert = get_next_wire_vert(prev_vert, current_vert)
        yield current_vert, next_vert, i
        prev_vert, current_vert = current_vert, next_vert

def add_additional_verts(last_vert, second_last_vert, additional_vert_count, b_wire):
    # select last edge --> subdivide --> move additional verts to last vert
    bpy.ops.mesh.select_all(action='DESELECT')
    second_last_vert.link_edges[0].select_set(True) # todo why second_last? should be last
    last_vert_co = second_last_vert.co
    bpy.ops.mesh.subdivide(number_cuts=additional_vert_count)
    b_wire.verts.ensure_lookup_table()
    added_verts = [v for v in b_wire.verts if v.select and len(v.link_edges)>1 and v.link_edges[0].select == v.link_edges[1].select]
    for added_vert in added_verts:
        added_vert.co = last_vert_co
    prev_sec_last = [v for v in b_wire.verts if len(v.link_edges)>1 and v.link_edges[0].select != v.link_edges[1].select][0]
    first_added_vert = other_vertex(prev_sec_last, 0) if prev_sec_last.link_edges[0].select else other_vertex(prev_sec_last, 1)
    return prev_sec_last, first_added_vert
    
def get_next_wire_vert(prev_vert, current_vert):
    if current_vert is None or len(current_vert.link_edges) <= 1:
        return None # todo test
    elif current_vert.link_edges[0].other_vert(current_vert) == prev_vert:
        return current_vert.link_edges[1].other_vert(current_vert)
    return current_vert.link_edges[0].other_vert(current_vert)

def sum_in_between_vectors(move_percentage, line_vectors, last_vec_ind):
    move_vector = Vector()
    sign = (-1 if move_percentage < 0 else 1)
    for j in range(int(abs(move_percentage))):
        counter = j * sign
        move_vector += line_vectors[last_vec_ind-counter]
    move_vector += line_vectors[-int(move_percentage) + last_vec_ind] * (abs(move_percentage) % 1)
    return move_vector * sign

def slide_vert(current_vert, move_percentage, line_vectors, last_vec_ind):
    if abs(move_percentage) > 1:
        # find correct target vertex
        move_vector = sum_in_between_vectors(move_percentage, line_vectors, last_vec_ind)
        current_vert.co += move_vector
        return 0
    else:
        current_vert.co += line_vectors[last_vec_ind] * move_percentage
        del line_vectors[:last_vec_ind]
        return last_vec_ind

def slide_verts(verts_count, prev_vert, current_vert, move_constant, last_vec_ind):
    line_vectors = [prev_vert.co - current_vert.co]
    for cur_vert, next_vert, i in generate_next_verts(prev_vert, current_vert, verts_count):
        move_percentage = move_constant * (i + 1)
        line_vectors.append(cur_vert.co - next_vert.co)
        slide_vert(cur_vert, move_percentage, line_vectors, last_vec_ind)

    return move_percentage, cur_vert, next_vert, line_vectors

def slide_last_verts(verts_count, prev_vert, current_vert, move_constant, move_percentage, last_vec_ind, line_vectors):
    for current_vert, _, _ in generate_next_verts(prev_vert, current_vert, verts_count):
        slide_vert(current_vert, move_percentage, line_vectors, last_vec_ind)
        move_percentage -= (1 - move_constant)

    return move_percentage, current_vert, prev_vert, line_vectors

def get_line_vectors(segment_count, prev_vert, current_vert):
    line_vector = [prev_vert.co - current_vert.co]
    for current_vert, next_vert, _ in generate_next_verts(prev_vert, current_vert, segment_count-1):
        line_vector.append(current_vert.co - next_vert.co)
    return line_vector

def dissolve_last_verts(index, line_vectors, current_vert, next_vert):
    bpy.ops.mesh.select_all(action='DESELECT')
    current_vert.select = True
    for current_vert, next_vert, _ in generate_next_verts(current_vert, next_vert, len(line_vectors)-index-1):    
        current_vert.select = True
    bpy.ops.mesh.dissolve_mode(use_verts=True)

def out_slide_verts(line_vectors, prev_vert, current_vert, move_constant):
    index = 0
    for current_vert, next_vert, i in generate_next_verts(prev_vert, current_vert, len(line_vectors)-1):
        move_percentage = move_constant * (i + 1)
        index += 1
        try:
            index_offset = slide_vert(current_vert, move_percentage, line_vectors, index)
            index -= index_offset
        except:
            # dissolve verts till the end...
            dissolve_last_verts(index, line_vectors, current_vert, next_vert)
            break

def subdivide_segment(move_constant, prev_vert, current_vert, verts_count, b_wire):
	if move_constant > 0:
		# slide existing verts
		move_percentage, last_vert, second_last_vert, line_vectors = slide_verts(len(b_wire.verts)-2,
																prev_vert, current_vert, move_constant, -2)
		# last vert and additional verts:
		move_percentage += move_constant
		additional_vert_count = math.ceil(move_percentage/(1-move_constant))
		second_last_vert, last_vert = add_additional_verts(last_vert, second_last_vert, additional_vert_count, b_wire)
		# bmesh.update_edit_mesh(wire.data)
		
		# sliding additional verts into proper position
		slide_last_verts(additional_vert_count, second_last_vert, last_vert,
							move_constant, move_percentage, -1, line_vectors)        
	else:
		line_vectors = get_line_vectors(len(b_wire.verts)-1, prev_vert, current_vert)
		out_slide_verts(line_vectors, prev_vert, current_vert, move_constant)
# todo next: operate base on start and end vertex

def calculate_subdiv_lvl(target_v_count, segment_v_count):
	if target_v_count < segment_v_count:
		rm_count = segment_v_count - target_v_count
		return -(rm_count / (target_v_count - 1) + (.01 if rm_count == 1 else 0))
	elif target_v_count > segment_v_count:
		additional_count = target_v_count - segment_v_count
		return (additional_count / (target_v_count - 1))
	return 0

def calculate_part_subdiv_lvl(start_index, end_index, target_v_count): # assumption: subdiv_lvl = 1
	current_count = end_index - start_index + 1
	if current_count < target_v_count:
		additional_verts_count = target_v_count - current_count
		return additional_verts_count / (end_index - start_index + additional_verts_count) 
		# todo hodoodie (hesab kardane index haye jadid? taghrib az kodoom taraf?)
	elif current_count > target_v_count:
		rm_verts_count = current_count - target_v_count
		return -(rm_verts_count/(end_index - start_index - rm_verts_count))
	return 0

def convert_index(current_const, current_index, target_const): # todo 1-exceptions? 2-validate wire vert count? 
	return current_index + (target_const - current_const) * current_index / (1 - target_const)

# next: tabdil (subdiv_lvl, index) ha be ham
# etmame set segments
# UX, save graph on disk? (node editor for graph edit?)
# create dependency graph
# create mesh (base on wire (extrude))
# noe connection ha: 1-connect mishan (mesh jadid sakhte mishe) 2-nesbateshoon hefz mishe
