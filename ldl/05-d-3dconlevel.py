#!/usr/bin/python2.5
"""
	05-d-3dconlevel.py
	Part of the Level Description Language (LDL) from the AGRIP project. 
	Copyright 2005-2008 Matthew Tylee Atkinson
	Released under the GNU GPL v2 -- See ``COPYING'' for more information.
"""

# FIXME hole_origin still fails due to the 0.5 ``rounding'' error. hack fix doesn't always work
# FIXME sizes not checked for validity; cause obscure other errors - ``smal'' should not match the regexp
# FIXME con_elev types not checked for validity
# FIXME check for overlapping children
# FIXME check for overlapping builders and solids
# FIXME implement compass points (even for connectors) via convert_coords
# FIXME check for two connectoins to rooms on different walls
# FIXME check for two non-opposite compass dirs on supposedly opposite connections

import sys, ldl, pprint, re  # standard/mine
import xml.parsers.expat, xml2dict
from plane import Point

'''Convert coords to numbers, from a range of possible formats.
2D formats:
	'100 200'		relative to inner origin of brush/face
	'[100 200]'		absolute
	'35% 42%'		percentages inside brush/face
	'nw'			compass point insice brush/face
	'+'				fill available area
3D formats:
	'100 200 50'	relative to inner origin of hollow
	'[100 200 50]'	absolute
	'20% 40% 5%'	percentages inside hollow
	'nw c'			compass point inside hollow
	'nw'			compass point inside hollow, with only top-down coords given
	'+'				fill available area
'''

CC_COMPASS = 'compass'
CC_FACEPOS = 'facepos'

OT_ROOM = 'room'
OT_CON = 'con'
OT_CON_ELEV = 'con_elev'
OT_ITEM = 'item'
OT_BUILDER = 'builder'

dir_to_angle = {
	ldl.DCP_SOUTHWEST:	225,
	ldl.DCP_WEST:		180,
	ldl.DCP_NORTHWEST:	135,
	ldl.DCP_SOUTH:		270,
	ldl.DCP_NORTH:		90,
	ldl.DCP_SOUTHEAST:	315,
	ldl.DCP_EAST:		0,
	ldl.DCP_NORTHEAST:	45,
}
	
facepos_to_fract = {
	ldl.DCP_BOTTOMLEFT:		( 0.25, 0.25 ),
	ldl.DCP_LEFT:			( 0.25, 0.50 ),
	ldl.DCP_TOPLEFT:		( 0.25,	0.75 ),

	ldl.DCP_BOTTOM:			( 0.50, 0.25 ),
	ldl.DCP_CENTRE:			( 0.50, 0.50 ),
	ldl.DCP_TOP:			( 0.50,	0.75 ),

	ldl.DCP_BOTTOMRIGHT:	( 0.75, 0.25 ),
	ldl.DCP_RIGHT:			( 0.75,	0.50 ),
	ldl.DCP_TOPRIGHT:		( 0.75, 0.75 )
}

compass_to_fract = {
	ldl.DCP_SOUTHWEST:	( 0.25, 0.25 ),
	ldl.DCP_WEST:		( 0.25, 0.50 ),
	ldl.DCP_NORTHWEST:	( 0.25,	0.75 ),

	ldl.DCP_SOUTH:		( 0.50, 0.25 ),
	ldl.DCP_CENTRE:		( 0.50, 0.50 ),
	ldl.DCP_NORTH:		( 0.50,	0.75 ),

	ldl.DCP_SOUTHEAST:	( 0.75, 0.25 ),
	ldl.DCP_EAST:		( 0.75,	0.50 ),
	ldl.DCP_NORTHEAST:	( 0.75, 0.75 )
}

sizes_con = {
	'small': 64,
	'med': 112,
	'big': 200,
	'large': 250,
	'vlarge': 275,
	'xlarge': 300,
	'huge': 350,
	'vhuge': 400,
	'xhuge':500
}

sizes_room_xy = {
	'vsmall': 128,
	'small': 256,
	'med': 512,
	'big': 768,
	'large': 1024,
	'vlarge': 1280,
	'xlarge': 1536,
	'huge': 2048,
	'vhuge': 2750,
	'xhuge': 4096
}

sizes_room_z = {
	'vsmall': 80,
	'small': 128,
	'med': 190,
	'big': 256,
	'large': 400,
	'vlarge': 512,
	'xlarge': 768,
	'huge': 1024,
	'vhuge': 1536,
	'xhuge': 2048
}

r_size2d = re.compile(r'\d+(.\d+)? \d+(.\d+)?')
r_size3d = re.compile(r'\d+(.\d+)? \d+(.\d+)? \d+(.\d+)?')

r_sizeword = re.compile(r'(v?small|med|big|(v|x)?large|(v|x)?huge)')
r_compass = re.compile(r'^(([nsew][ew]?)|c)$')
r_facepos = re.compile(r'^(([tblr][lr]?)|c)$')
r_extentsym = re.compile(r'\+')

def con_elev_err_msg(rid, tid, msg):
	if tid:
		targ = ' (to room \'' + tid + '\') '
	else:
		targ = ''
	boiler_h = 'A connection in room \'' + rid + '\'' + targ + 'may require the construction of an elevation device to allow access. The current error is that '
	boiler_f = ' If you don\'t want to provide access from this direction, set the \'elevtype\' attribute of the connection to \'none\'.'
	return boiler_h + msg + boiler_f

def add_subsection(parent, secname):
	'''Add a new subhash under the parent.'''
	if parent.has_key(secname):
		return False
	else:
		parent[secname] = []
	return True

def add_subsection_element(parent, secname, hash):
	if not parent.has_key(secname):
		#ldl.warning('add_subsection_element: parent doesn\'t have subsection \'' + str(secname) + '\'; creating it...')
		add_subsection(parent, secname)
	# Now add the thing we were here to add...	
	if isinstance(secname, dict):
		tmp = parent[secname]
		parent[secname] = [tmp]
	parent[secname].append(hash)
	return True

def check_childroom_size(parent, cs, cc, id):
	'''Checks if a child room is too big to fit into its parent.'''
	ps = ldl.getPoint(get_property(parent, 'size'))
	cr = cs/2
	# Get corners of child room
	ar = []
	ar.append(cc + Point(cr.x ,  cr.y ,  cr.z))
	ar.append(cc + Point(cr.x ,  cr.y , -cr.z))
	ar.append(cc + Point(cr.x , -cr.y ,  cr.z))
	ar.append(cc + Point(cr.x , -cr.y , -cr.z))
	ar.append(cc - Point(cr.x ,  cr.y ,  cr.z))
	ar.append(cc - Point(cr.x ,  cr.y , -cr.z))
	ar.append(cc - Point(cr.x , -cr.y ,  cr.z))
	ar.append(cc - Point(cr.x , -cr.y , -cr.z))
	# test points
	ldl.uprint('ps: ' + str(ps))
	ldl.uprint('cs: ' + str(cs))
	ldl.uprint('cc: ' + str(cc))
	ldl.uprint('cr: ' + str(cr))
	for cn in ar:
		ldl.uprint(str(cn))
		# FIXME can we do this just by comparing Point objects?
		if cn.x >= ps.x \
		or cn.x <= 0 \
		or cn.y >= ps.y \
		or cn.y <= 0 \
		or cn.z >  ps.z: \
			ldl.error('Your inner room with id \'' + id + '\' does not fit within the parent at the sizes you\'ve specified.  To avoid this error, try either reducing the size of the contained room, or increasing the size of the parent room.')

def get_childroom_origin(child_size, parent, pos, id):
	'''Given the size of a child and the parent room object and position within parent of child,
	return the origin coords (absolute) of the child.'''
	# FIXME 'pos' must be a 2d coord value
	cc_pos = ldl.getPoint2D(convert_coords(OT_ROOM, pos, parent))
	child_centre = child_size/2
	parent_origin = ldl.getPoint(parent['origin'])
	parent_size = ldl.getPoint(parent['size'])

	inparent_child_centre = Point(0,0,0)
	inparent_child_centre.x = cc_pos.x
	inparent_child_centre.y = cc_pos.y
	inparent_child_centre.z = child_size.z/2

	check_childroom_size(parent, child_size, inparent_child_centre, id)

	child_origin = inparent_child_centre - child_size/2
	
	# Fix Z...
	# FIXME can this be improved? (absentwalls? - but that would affect other things...)
	child_origin.z = -ldl.lip

	ldl.uprint('get_childroom_origin:\n\tchild centre: ' + str(child_centre) + ';\n\tparent origin: ' + str(parent_origin) + ';\n\tparent_size: ' + str(parent_size) + ';\n\tcc_pos: ' + str(cc_pos) + ';\n\tinparent_child_centre: ' + str(inparent_child_centre) + ';\n\tchild_origin: ' + str(child_origin))
	return child_origin

def rwo_num():
	global rwo
	ctr = 0
	for v in rwo.values():
		if not v:
			ctr = ctr + 1
	#ldl.uprint(pp.pformat(rwo))
	return ctr

def rwo_update(id, origin):
	global rwo
	if rwo.has_key(id):
		rwo[id] = origin

def cwo_num_room(r):
	ctr = 0
	for c in get_children(r, OT_CON):
		if not c.has_key('origin'):
			#ldl.uprint('cwo_num_room: con w/o origin field; target: ' + str(get_property(c, 'target')))
			ctr = ctr + 1
		else:
			if not get_property(c, 'origin'):
				#ldl.uprint('cwo_num_room: con w/ null origin field; target: ' + str(get_property(c, 'target')))
				ctr = ctr + 1
			else:
				#ldl.uprint('cwo_num_room: con w/ origin ' + str(get_property(c, 'origin')) + '; target: ' + str(get_property(c, 'target')))
				pass
	for x in get_children(r, OT_ROOM):
		ctr = ctr + cwo_num_room(x)
	return ctr

def cwo_num(m):
	'''pass in the map structure and get the number of connections w/o origins.'''
	ctr = 0
	for r in get_children(m, OT_ROOM):
		ctr = ctr + cwo_num_room(r)
	#ldl.uprint('cwo_num: ' + str(ctr))
	return ctr
		
def cwo_update(id, origin):
	global cwo
	if cwo.has_key(id):
		cwo[id] = origin

def ri_clear():
	global ril
	ril = []

def ri_add(id):
	global ril
	if id in ril:
		ldl.error('It seems that you have two or more elements with the ID \'' + id + '\'.  IDs are meant to be unique.  Please ensure that you do not use the same one twice (or more).')
	else:
		ril.append(id)
	# Room doesn't have an origin...
	rwo[id] = None	
	
def set_room_size(r):
	'''Convert into game units a room's size, then update the master hash with it.
	Returns a Point object corresponding to the size.'''
	r_size = get_room_size(r)
	set_property(r, 'size', r_size)
	return r_size

def get_room_size(r):
	'''Given a room, return a Point corresponding to its size/extent.'''
	r_size = get_property(r, 'size')
	r_id = get_property(r, 'id')
	if r_size:
		if not r_size2d.match(r_size):
			r_size = convert_coords(OT_ROOM, r_size)
	else:
		#ldl.warning('no size specified for room \'' + r_id + '\'; using default (medium).')
		r_size = convert_coords(OT_ROOM, 'med')
	return ldl.getPoint(r_size)

def hole_origin(hole_centre, hole_size, hole_wall, brush_origin, brush_size, floating=False):
	'''Given
			centre of hole (absolute),
			size of hole,
			wall of hole,
			origin of brush (absolute),
			size of brush
	work out the origin of the hole wrt its wall in the room.'''
	# FIXME refactor -- common stuff here again!

	if not brush_origin:
		ldl.error('hole_origin: called without the origin for the parent brush')
	
	if hole_wall == ldl.DCP_NORTH or hole_wall == ldl.DCP_SOUTH:
		hole_centre2d = ldl.Point2D(hole_centre.x, hole_centre.z)
		brush_origin2d = ldl.Point2D(brush_origin.x, brush_origin.z)
		brush_size2d = real_wall_size(ldl.Point2D(brush_size.x, brush_size.z))
	elif hole_wall == ldl.DCP_WEST or hole_wall == ldl.DCP_EAST:
		hole_centre2d = ldl.Point2D(hole_centre.y, hole_centre.z)
		brush_origin2d = ldl.Point2D(brush_origin.y, brush_origin.z)
		brush_size2d = real_wall_size(ldl.Point2D(brush_size.y, brush_size.z))
	elif hole_wall == ldl.DCP_UP or hole_wall == ldl.DCP_DOWN:
		hole_centre2d = ldl.Point2D(hole_centre.x, hole_centre.y)
		brush_origin2d = ldl.Point2D(brush_origin.x, brush_origin.y)
		brush_size2d = real_wall_size(ldl.Point2D(brush_size.x, brush_size.y))
	else:
		ldl.error('hole_origin: invalid wall specified whilst trying to put a hole into a wall.')

	if not floating:
		if hole_wall == ldl.DCP_NORTH or hole_wall == ldl.DCP_SOUTH:
			hole_centre2d_rel = hole_centre2d - brush_origin2d + ldl.Point2D(ldl.lip,0)
		else:
			hole_centre2d_rel = hole_centre2d - brush_origin2d
		# FIXME why must we add ldl.lip here and to x only?
	else:
		hole_centre2d_rel = brush_size2d/2
		hole_centre2d_rel.y = hole_size.y/2

	hole_origin2d_rel = hole_centre2d_rel - hole_size/2

	ldl.uprint('hole_origin:\n\thole_centre: ' + str(hole_centre) + ';\n\thole_size: ' + str(hole_size) + ';\n\thole_wall: ' + hole_wall + ';\n\tbrush_origin: ' + str(brush_origin) + ';\n\tbrush_size: ' + str(brush_size) + ';\n\tbrush_size2d: ' + str(brush_size2d) + '\n\tfloating: ' + str(floating) + ';\n\thole centre 2D rel: ' + str(hole_centre2d_rel) + ';\n\thole origin 2D r: ' + str(hole_origin2d_rel))
	return hole_origin2d_rel

def target_brush_origin_core(hole_centre2d, wall_size, hole_size, pos=None):
	'''Work out wall origin in 2d, as an offset from the absolute hole centre.'''
	# FIXME very similar to hole_centre_core !
	if not pos:
		return hole_centre2d - ldl.Point2D( wall_size.x/2, hole_size.y/2 )
	else:
		# work out hole centre rel to wall...
		hole_centre = fit_hole_in_wall(wall_size, hole_size, pos)
		# absolute wall origin is absolute hole centre - rel hole centre...
		return hole_centre2d - hole_centre

def target_brush_origin(hole_centre, hole_size, room_size, hole_wall, pos=None):
	'''Given
			centre of hole (absolute),
			size of hole,
			size of room,
			wall of hole,
	work out the origin of the face the hole is on.'''
	wall_offset = Point(0,0,0)  # the origin of the wall wrt the origin of the room
	room_offset = Point(0,0,0)  # FIXME

	if hole_wall == ldl.DCP_NORTH or hole_wall == ldl.DCP_SOUTH:
		hole_centre2d = ldl.Point2D(hole_centre.x, hole_centre.z)
		wall_size2d = real_wall_size(ldl.Point2D(room_size.x, room_size.z))
		if hole_wall == ldl.DCP_NORTH:
			wall_offset = wall_offset + Point(0, room_size.y, 0)
			room_offset.y = -room_size.y
		wall_origin2d = target_brush_origin_core(hole_centre2d, wall_size2d, hole_size, pos)
		wall_origin3d = Point(wall_origin2d.x, hole_centre.y, wall_origin2d.y)
	elif hole_wall == ldl.DCP_WEST or hole_wall == ldl.DCP_EAST:
		hole_centre2d = ldl.Point2D(hole_centre.y, hole_centre.z)
		wall_size2d = real_wall_size(ldl.Point2D(room_size.y, room_size.z))
		if hole_wall == ldl.DCP_EAST:
			wall_offset = wall_offset + Point(room_size.x, 0, 0)
			room_offset.x = -room_size.x
		wall_origin2d = target_brush_origin_core(hole_centre2d, wall_size2d, hole_size, pos)
		wall_origin3d = Point(hole_centre.x, wall_origin2d.x, wall_origin2d.y)
	elif hole_wall == ldl.DCP_UP or hole_wall == ldl.DCP_DOWN:
		# default hole pos for hole is 'c'...
		if not pos: pos = ldl.DCP_CENTRE
		# now continue with calculation...
		hole_centre2d = ldl.Point2D(hole_centre.x, hole_centre.y)
		wall_size2d = real_wall_size(ldl.Point2D(room_size.x, room_size.y))
		if hole_wall == ldl.DCP_UP:
			wall_offset = wall_offset + Point(0, 0, room_size.z)
			room_offset.z = -room_size.z
		wall_origin2d = target_brush_origin_core(hole_centre2d, wall_size2d, hole_size, pos)
		wall_origin3d = Point(wall_origin2d.x, wall_origin2d.y, hole_centre.z)
	else:
		ldl.error('target_brush_origin: invalid wall specified whilst trying to put a hole into a wall.')

	# Map back to 3D...
	target_brush_origin = wall_origin3d + room_offset

	ldl.uprint('target_brush_origin:\n\thole_centre: ' + str(hole_centre) + '\n\twall size: ' + str(wall_size2d) + ';\n\tpos: ' +str(pos) + ';\n\tdir: ' + hole_wall + '\n\twall offset (from room origin): ' + str(wall_offset) + '\n\twall origin2d: ' + str(wall_origin2d) + '\n\twall origin3d: ' + str(wall_origin3d) + '\n\troom_offset: ' + str(room_offset) + '\n\ttarget brush origin: ' + str(target_brush_origin))
	return target_brush_origin

def real_wall_size(wall_size):
	'''Account for the fact that the rooms will have borders when computing with face sizes.'''
	# FIXME need to know direction (and if other walls will be absent) to get this really right.
	rws = ldl.Point2D(wall_size.x - ldl.lip*2, wall_size.y - ldl.lip*2)
	ldl.uprint('real_wall_size: ws = ' + wall_size.__str__() + '; rws = ' + str(rws))
	return rws

def fit_hole_in_wall(wall_size, hole_size, pos):
	prelim = ldl.getPoint2D(convert_coords(OT_CON, pos, wall_size, dir))
	ldl.uprint('fit_hole_in_wall: wall_size: ' + str(wall_size) + '; prelim: ' + str(prelim))
	# We need to move it up/down and left/right to make it fit...
	attempts = 0
	pos_x_ok = neg_x_ok = pos_y_ok = neg_y_ok = False
	exitflag = False

	while not exitflag and attempts < 100:
		# Do the +ve and -ve extents of the hole fit?
		pos_x = prelim.x + hole_size.x/2
		neg_x = prelim.x - hole_size.x/2
		pos_y = prelim.y + hole_size.y/2
		neg_y = prelim.y - hole_size.y/2
		if not pos_x_ok and pos_x <= wall_size.x:
			ldl.uprint('fit_hole_in_wall: hole +ve x extent fits.')
			pos_x_ok = True
		if not neg_x_ok and neg_x >= 1:  # FIXME setting to 0 makes targ wall totally solid!
			ldl.uprint('fit_hole_in_wall: hole -ve x extent fits.')
			neg_x_ok = True
		if not pos_y_ok and pos_y <= wall_size.y:
			ldl.uprint('fit_hole_in_wall: hole +ve y extent fits.')
			pos_y_ok = True
		if not neg_y_ok and neg_y >= 1:  # FIXME setting to 0 makes targ wall totally solid!
			ldl.uprint('fit_hole_in_wall: hole -ve y extent fits.')
			neg_y_ok = True
		# Can we leave?
		if pos_x_ok and neg_x_ok and pos_y_ok and neg_y_ok:
			exitflag = True
		elif not neg_x_ok:
			prelim = prelim + ldl.Point2D(1,0)
		elif not pos_x_ok:
			prelim = prelim - ldl.Point2D(1,0)
		elif not neg_y_ok:
			prelim = prelim + ldl.Point2D(0,1)
		elif not pos_y_ok:
			prelim = prelim - ldl.Point2D(0,1)
		else:
			ldl.uprint('fit_hole_in_wall: couldn\'t fit hole (' + str(hole_size) + ') in face (' + str(wall_size) + ') - it is larger than the face.')
			return False
		attempts = attempts + 1

	if exitflag:
		return prelim
	else:
		ldl.uprint('fit_hole_in_wall: couldn\'t fit hole (' + str(hole_size) + ') in face (' + str(wall_size) + ') - ran out of adjustment attempts.')
		return False

def hole_centre_core(wall_size, h_extent, dir, pos=None):
	# FIXME very simliar to target_brush_origin_core!
	if not pos:
		return ldl.Point2D(wall_size.x/2, h_extent.y/2)
	else:
		return fit_hole_in_wall(wall_size, h_extent, pos)

def hole_centre(r_origin, r_extent, h_wall, h_extent, pos=None):
	'''Work out centre of hole.
	in
		r_origin : origin of parent room
		r_extent : extent of parent room
		h_wall   : wall of parent room that hole is on
		h_extent : extent of hole
		pos		 : compass point of hole in wall face
	out
		centre : of hole (absolute)
	'''
	if not r_origin: return None

	wall_origin = Point(0,0,0)  # eventually the hole origin will be constructed from room origin + wall offset + hole centre offset

	# Get size of wall (2D)...
	if h_wall == ldl.DCP_NORTH or h_wall == ldl.DCP_SOUTH:
		wall_size = real_wall_size(ldl.Point2D(r_extent.x, r_extent.z))
		if h_wall == ldl.DCP_NORTH:
			wall_origin = wall_origin + Point(0, r_extent.y, 0)
		hc = hole_centre_core(wall_size, h_extent, h_wall, pos)
		out = r_origin + wall_origin + Point(hc.x, 0, hc.y)
	elif h_wall == ldl.DCP_WEST or h_wall == ldl.DCP_EAST:
		wall_size = real_wall_size(ldl.Point2D(r_extent.y, r_extent.z))
		if h_wall == ldl.DCP_EAST:
			wall_origin = wall_origin + Point(r_extent.x, 0, 0)
		hc = hole_centre_core(wall_size, h_extent, h_wall, pos)
		out = r_origin + wall_origin + Point(0, hc.x, hc.y)
	elif h_wall == ldl.DCP_UP or h_wall == ldl.DCP_DOWN:
		# Default pos should be centre...
		if not pos: pos = ldl.DCP_CENTRE
		# Now calculate as normal...
		wall_size = real_wall_size(ldl.Point2D(r_extent.x, r_extent.y))
		if h_wall == ldl.DCP_UP:
			wall_origin = wall_origin + Point(0, 0, r_extent.z)
		hc = hole_centre_core(wall_size, h_extent, h_wall, pos)
		out = r_origin + wall_origin + Point(hc.x, hc.y, 0)
	else:
		ldl.error('hole_centre: invalid wall specified whilst trying to put a hole into a wall.')
	
	ldl.uprint('hole_centre:\n\tr_origin: ' + str(r_origin) + ';\n\tr_extent: ' + str(r_extent) + ';\n\th_wall: ' + str(h_wall) + ';\n\th_extent: ' + str(h_extent) + ';\n\tpos: ' + str(pos) + '\n\thc: ' + str(hc) + ';\n\tout: ' + str(out))

	# Check for holes that are too big...
	if h_extent.x > wall_size.x or h_extent.y > wall_size.y:
		ldl.uprint('hole_centre: h_extent ' + str(h_extent) + ' > wall_size ' + str(wall_size))
		ldl.error('hole in wall \'' + con_info['wall'] + '\' of room \'' + r_id + '\' is bigger than the wall.  Try making the hole smaller, or the room larger.')
	else:
		ldl.uprint('hole_centre: h_extent ' + str(h_extent) + ' <= wall_size ' + str(wall_size))
		return out

def get_room_by_id(parentgroup, id):
	'''go through array of rooms, find one with matching id and return it.'''
	for room in parentgroup:
		this_id = get_property(room, 'id')
		if this_id:
			if this_id == id:
				return room
		else:
			error_room_id()
	return None

def opposite_dir(dir):
	if dir == ldl.DCP_NORTH: return ldl.DCP_SOUTH
	if dir == ldl.DCP_SOUTH: return ldl.DCP_NORTH
	if dir == ldl.DCP_EAST: return ldl.DCP_WEST
	if dir == ldl.DCP_WEST: return ldl.DCP_EAST
	if dir == ldl.DCP_UP: return ldl.DCP_DOWN
	if dir == ldl.DCP_DOWN: return ldl.DCP_UP

def convert_coords_extentsym(objtype, word, index, parent=None):
	'''Convert coords based on extent symbols.'''
	if not parent:
		ldl.error('convert_coords_extentsym: trying to place object of type \'' + objtype + '\' but not given a parent to place this object within.')

	if type(parent) == type(Point(0,0,0)):
		parent_size = [parent.x, parent.y, parent.z]
	else:
		parent_size = parent['size']

	if objtype == OT_ROOM:
		ldl.error('convert_coords_extentsym: rooms not implemented yet.')
	elif objtype == OT_CON:
		ldl.error('convert_coords_extentsym: connections not implemented yet.')
	elif objtype == OT_CON_ELEV:
		return parent_size[index]
	elif objtype == OT_ITEM:
		ldl.error('convert_coords_extentsym: items not implemented yet.')
	else:
		ldl.error('convert_coords_extentsym: invalid object type \'' + objtype + '\' specified.')

def convert_coords_compass_facepos(mode, objtype, word, index, parent, dir):
	'''Convert coords based on facepos directions.
	If we're positioning a room or item within parent, we always take it to be top-down.
	If we're dealing with connections, it's based on the wall they're on.'''
	if mode == CC_COMPASS:
		answer_hash = compass_to_fract
	elif mode == CC_FACEPOS:
		answer_hash = facepos_to_fract
	else:
		ldl.error('convert_coords_compass_facepos: invalid mode \'' + str(mode) + '\' specified - expected \'' + str(CC_COMPASS) + '\' or \'' + str(CC_FACEPOS) + '\'.')

	if not parent:
		ldl.error('convert_coords_compass_facepos: trying to place object of type \'' + objtype + '\' but not given a parent to place this object within.')
	
	if objtype == OT_ROOM:
		if answer_hash.has_key(word):
			x = answer_hash[word][0] * parent.x
			y = answer_hash[word][1] * parent.y
			return str(x) + ' ' + str(y)
		else:
			ldl.error('convert_coords_compass_facepos: invalid facepos size \'' + str(word) + '\'.')
	elif objtype == OT_CON:
		# Do we have the direction/wall?
		if not dir:
			ldl.error('convert_coords_compass_facepos: whilst trying to position a connection on a wall, the wall was not specified.')
		if dir == ldl.DCP_SOUTH or dir == ldl.DCP_EAST:
			flip = True
		else:
			flip = False  # FIXME what about u and d?
		# Work out coords...
		if answer_hash.has_key(word):
			if not flip:
				x = answer_hash[word][0] * parent.x
			else:
				x = (1-answer_hash[word][0]) * parent.x
			y = answer_hash[word][1] * parent.y
			return str(x) + ' ' + str(y)
	elif objtype == OT_ITEM:
		if answer_hash.has_key(word):
			x = answer_hash[word][0] * parent.x
			y = answer_hash[word][1] * parent.y
			return str(x) + ' ' + str(y)
		else:
			ldl.error('convert_coords_compass_facepos: invalid facepos size \'' + str(word) + '\'.')
	else:
		ldl.error('convert_coords_compass_facepos: invalid object type \'' + objtype + '\' specified.')

def convert_coords_word(objtype, word, index, parent=None):
	if objtype == OT_ROOM:
		if index < 2:
			return get_property(sizes_room_xy, word, 'You\'ve requested an invalid size for rooms (width and depth dimensions).  It might be a valid size for rooms (in the vertical dimension) or for other objects, but it isn\'t for connectors.  Valid sizes are:\n\t' + '\n\t'.join([str(s) for s in sizes_room_xy]))
		else:
			return get_property(sizes_room_z, word, 'You\'ve requested an invalid size for rooms (vertical dimension).  It might be a valid size for rooms (in the horizontal dimensions) or for other objects, but it isn\'t for connectors.  Valid sizes are:\n\t' + '\n\t'.join([str(s) for s in sizes_room_z]))
	elif objtype == OT_CON or objtype == OT_CON_ELEV:
		return get_property(sizes_con, word, 'You\'ve requested an invalid size for connectors.  It might be a valid size for rooms but it isn\'t for connectors.  Valid sizes are:\n\t' + '\n\t'.join([str(s) for s in sizes_con]))
	else:
		ldl.error('convert_coords_words: invalid object type \'' + objtype + '\' specified.')

def convert_coords_dispatch(objtype, part, index, parent, dir):
	'''This function takes one part of the overall coordinate string.
	It works out its format and calls the appropriate conversion routein.'''
	# Currently all of thse require strings, so convert now...
	if type(part) != type('hello'):
		part = str(part)
	# Now process...
	if r_sizeword.match(part):
		out = convert_coords_word(objtype, part, index, parent)
	elif r_compass.match(part):
		out = convert_coords_compass_facepos(CC_COMPASS, objtype, part, index, parent, dir)
	elif r_facepos.match(part):
		out = convert_coords_compass_facepos(CC_FACEPOS, objtype, part, index, parent, dir)
	elif r_extentsym.match(part):
		out = convert_coords_extentsym(objtype, part, index, parent)
	else:
		ldl.error('convert_coords_dispatch: unknown size string format \'' + part + '\'.')
	return out

def convert_coords_check_size_type(objtype, size):
	'''Given the object type and size, return
	the split size string,
	whether we think we're looking at a 2D, or a 3D, conversion (based on objtype).'''
	size_parts = []
	if type(size) == type('hello'):
		size_parts = size.split()
		if len(size_parts) == 3:
			mode3d = True
		elif len(size_parts) == 2:
			mode3d = False
		elif len(size_parts) == 1:
			# We can't be sure if we're meant to be in mode3d or not.  Look at boject type.
			if objtype == OT_CON or objtype == OT_CON_ELEV:
				mode3d = False
			else:
				mode3d = True
		else:
			ldl.error('conert_coords: it seems the input coordinate string you specified, \'' + str(size) + '\' is not valid.')
	elif isinstance(size, Point):
		size_parts = [size.x, size.y, size.z]
		mode3d = True
	elif isinstance(size, ldl.Point2D):
		size_parts = [size.x, size.y]
		mode3d = False
	else:
		ldl.error('convert_coords: don\'t know how to deal with type of \'' + str(size) + '\'.')
	return size_parts, mode3d

def convert_coords_check_parent_type(parent):
	'''Try to turn the parent object into some coords that represent the bbox of the parent.'''
	if isinstance(parent, dict):
		parent = parent['size']
		return convert_coords_check_parent_type(parent)
	elif type(parent) == type('hello'):
		# It can be a string that is made of numbers, but it can't be 'med big med'.
		# FIXME where is this checked?
		parent_parts = parent.split()
		if len(parent_parts) == 3:
			return ldl.getPoint(parent)
		elif len(parent_parts) == 2:
			return ldl.getPoint2D(parent)
		else:
			ldl.error('convert_coords_check_parent_type: a parent for this item/connection/room was specified as \'' + str(parent) + '\' which seems to be invalid.')
	elif isinstance(parent, Point) or isinstance(parent, ldl.Point2D):
		return parent
	else:
		ldl.error('convert_coords_check_parent_type: unkown parent type \'' + str(parent) + '\'.')

def convert_coords(objtype, size, parent=None, dir=None):
	'''Convert a size to game units.
	This function checks the length of the incoming coordinate string,
	it then passes the parts of the string to be converted seperately.'''
	#ldl.uprint('convert_coords: ' + str(objtype) + '; ' + str(size) + '; ' + pp.pformat(parent))
	# FIXME items can't be 'nw 10% <x>' but they can be '25% 70% 10%'
	out = []
	flat_out = None
	
	# Work out type of input...
	size_parts, mode3d = convert_coords_check_size_type(objtype, size)
	if mode3d:
		dim_range = 3
	else:
		dim_range = 2

	# work out type of parent...
	if parent: parent = convert_coords_check_parent_type(parent)
	#ldl.uprint('convert_coords: parent is ' + str(parent))
	
	# make sure we've got the right number of coords
	#ldl.uprint('convert_coords: ' + size)
	if objtype == OT_ROOM:
		if len(size_parts) == 1:
			# We need to check if it's a size or a position...
			if r_sizeword.match(size):
				# NB: even though only one dim spec'd, becuase we use different sizes
				#     based on x/y/z dim, we still do it 3 times.
				for i in range(dim_range):
					out.append(convert_coords_dispatch(OT_ROOM, size, i, parent, dir))
				flat_out = ' '.join([str(o) for o in out])
			else:
				# it's a position so don't repeat it thrice -- i.e. it could be ``nw'' for example.
				flat_out = convert_coords_dispatch(OT_ROOM, size, 0, parent, dir)
		elif not mode3d and len(size_parts) == 2:
			for i in range(3):
				out.append(convert_coords_dispatch(OT_ROOM, size_parts[i], i, parent, dir))
			flat_out = ' '.join([str(o) for o in out])
		elif mode3d and len(size_parts) == 3:
			for i in range(3):
				out.append(convert_coords_dispatch(OT_ROOM, size_parts[i], i, parent, dir))
			flat_out = ' '.join([str(o) for o in out])
		else:
			ldl.error('convert_coords: you must specify either only 1 or all 3 portions of the size/coordinates for rooms.')
	elif objtype == OT_CON:
		# NB: always in 2d mode for these
		if mode3d:
			ldl.error('convert_coords: connection specified but I got more then 2 coordinates.')
		if len(size_parts) == 1:
			conv = convert_coords_dispatch(OT_CON, size, 0, parent, dir)
			flat_out = str(conv) + ' ' + str(conv)
		elif len(size_parts) == 2:
			for i in range(2):
				out.append(convert_coords_dispatch(OT_CON, size_parts[i], i, parent, dir))
			flat_out = ' '.join([str(o) for o in out])
		else:
			ldl.error('convert_coords: you must specify either only 1 or both portions of the size/coordinates for connections.')
	elif objtype == OT_CON_ELEV:
		# NB: always in 2d mode for these
		if mode3d:
			ldl.error('convert_coords: connection elevator device specified but I got more then 2 coordinates.')
		if len(size_parts) == 1:
			if r_sizeword.match(size):
				conv = convert_coords_dispatch(OT_CON, size, 0, parent, dir)
				flat_out = str(conv) + ' ' + str(conv)
			elif r_extentsym.match(size):
				for i in range(2):
					out.append(convert_coords_dispatch(OT_CON_ELEV, size, i, parent, dir))
				flat_out = ' '.join([str(o) for o in out])
			else:
				ldl.error('convert_coords: currently the only supported coordinate types for connection elevatoin devices (stairs and plats) are size names and the expansion symbol (+).')
		elif len(size_parts) == 2:
			for i in range(2):
				out.append(convert_coords_dispatch(OT_CON_ELEV, size_parts[i], i, parent, dir))
			flat_out = ' '.join([str(o) for o in out])
		else:
			ldl.error('convert_coords: you must specify only 1 or both portions of the size/coordinates for connector elevation device (e.g. \'' + ldl.ST_STAIRS + '\' or \'' + ldl.ST_PLAT + '\' extents.')
	elif objtype == OT_ITEM:
		# FIXME enforce being always in mode3d?
		if len(size_parts) == 1:
			conv = convert_coords_dispatch(OT_ITEM, size_parts[0], 0, parent, dir)
			flat_out = str(conv)  # nw maps to x,y
			# Now add z back on...
			flat_out = flat_out + ' 50'
		elif not mode3d and len(size_parts) == 2:
			for i in range(2):
				out.append(convert_coords_dispatch(OT_ITEM, size_parts[i], i, parent, dir))
			flat_out = ' '.join([str(o) for o in out])
		elif mode3d and len(size_parts) == 3:
			for i in range(3):
				out.append(convert_coords_dispatch(OT_ITEM, size_parts[i], i, parent, dir))
			flat_out = ' '.join([str(o) for o in out])
		else:
			ldl.error('convert_coords: you must specify either 1, 2 or all 3 portions of the coordinates for items.')
	else:
		ldl.error('convert_coords: unkown object type \'' + objtype + '\' specified.')
	#ldl.uprint('convert_coords: returning \'' + str(flat_out) + '\'.')
	return flat_out

def get_children(base, req):
	'''Return a list of the children (req) of base.'''
	out = []
	if base.has_key(req):
		if isinstance(base[req], dict):
			out = [base[req]]
		else:
			for child in base[req]:
				out.append(child)
		return out
	else:
		return out

def get_property(obj, field, mandatory=None):
	'''Get a property, or return None if there isn't one.
	Returns a string.'''
	retval = None
	if obj.has_key(field):
		retval = obj[field]
	else:
		retval = None
	
	if not retval and mandatory:
		if obj.has_key('id') and obj['id']:
			ldl.error('Field \'' + str(field) + '\' in element with id \'' + str(obj['id']) + '\' was not specified in your map, but is mandatory.')
		elif obj.has_key('type') and obj['type']:
			ldl.error('Field \'' + str(field) + '\' in element of type \'' + str(obj['type']) + '\' was not specified in your map, but is mandatory.')
		else:
			if type(mandatory) == type(''):
				ldl.error(mandatory)
			else:
				ldl.error('Field \'' + str(field) + '\' is required for an element in your map, but was not supplied.')
	else:
		return retval

def set_property(obj, field, value, overwrite=True):
	'''Set a property to a particular value.
	If overwrite is False, we leave what's there there.
	values are converted to strings automatically.
	Returns the non-converted value.'''
	if obj.has_key(field):
		if overwrite:
			if value is not None:
				obj[field] = str(value)
			else:
				obj[field] = None
		else:
			pass
	else:
		if value is not None:
			obj[field] = str(value)
		else:
			obj[field] = None
	return value

def coords_origin(centre, size):
	'''Return the origin of a room given the centre and its size.'''
	return centre - Point(size.x/2, size.y/2, size.z/2)

def coords_centre(origin, size):
	'''Return the centre of a room given the origin and its size.'''
	return origin + Point(size.x/2, size.y/2, size.z/2)

def coninfostr(ci):
	return 'connection from \'' + ci['thisroom'] + '\' to \'' + str(ci['target']) + '\' via wall \'' + str(ci['wall']) + '\' of size \'' + str(ci['size']) + '\', offset \'' + str(ci['origin']) + '\' and type \'' + str(ci['type']) + '\'.'

def process_rooms(parentgroup, parent):
	'''FIXME'''
	for room in parentgroup:
		process_rooms_core(parentgroup, room, parent)

def process_rooms_core(parentgroup, r, parent):
	global f_firstroom
	r_id = get_property(r, 'id', True)
	ri_add(r_id)
	ldl.uprint('===== IN ROOM ' + r_id)

	# Get origin, or set it to MAP_ORIGIN if it's the first room, or just wait...
	r_origin = get_property(r, 'origin')
	if r_origin:
		r_origin = ldl.getPoint(r_origin)
		rwo_update(r_id, r_origin)
	else:
		if f_firstroom:
			r_origin = set_property(r, 'origin', Point(ldl.MAP_ORIGIN[0], ldl.MAP_ORIGIN[1], ldl.MAP_ORIGIN[2]))
			f_firstroom = False
			rwo_update(r_id, r_origin)
		else:
			pass  # wait until we have more info

	# Work out size...
	r_size = set_room_size(r)

	# Update hash...
	#if r_origin: set_property(r, 'origin', str(r_origin))
	set_property(r, 'style', default_style, overwrite=False)

	# Process connections...
	# If there are no connections (would this happen?)
	# or there are no connections with targets
	# then we can't place the room as there's no point to anchor onto.
	# In that case, we need to use it's position element,
	# or position it in the centre (on face DCP_DOWN) of the parent.
	nontargetted_cons = False
	for c in get_children(r, OT_CON):
		if parent:
			if parent.has_key('origin'):
				ldl.uprint('; parent: ' + str(parent['origin']))
			else:
				ldl.uprint('; parent: <>')
		else:
			ldl.uprint('; no parent')
		# Check for errors...
		con_info = {
			# required...
			'thisroom': r_id,
			'wall': get_property(c, 'wall', True),
			# optioinal...
			'size': set_property(c, 'size', get_property(c, 'size')),
			'target': get_property(c, 'target'),
			'type': get_property(c, 'type'),
			'pos': get_property(c, 'pos'),
			'origin': get_property(c, 'origin'),
			'elevtype': get_property(c, 'elevtype'),
			'extent': get_property(c, 'extent')
		}
		#ldl.uprint(r_id + ': connection ' + pp.pformat(con_info))
		#ldl.uprint('CONNECTION:' + pp.pformat(c))

		# FIXME error-check type; is this done elsewhere?
		con_type = con_info['type']
		if con_type:
			if con_type == 'door':
				pass
			else:
				ldl.error('Invalid connection type \'' + str(con_type) + '\' specified in connection from \'' + r_id + '\'.')
		else:
			pass

		# Set the size, only if it's not valid atm...
		if con_info['size']:
			if not r_size2d.match(con_info['size']):
				con_info['size'] = convert_coords(OT_CON, con_info['size'])
		else:
			con_info['size'] = convert_coords(OT_CON, 'med')
		con_info['size'] = ldl.getPoint2D(con_info['size'])
		# FIXME isn't this done elsewhere?
		set_property(c, 'size', con_info['size'])

		# Work out centre of the connection on our current side...
		if not con_info['origin']:
			if r_origin:
				con_centre = hole_centre(
					ldl.getPoint(get_property(r, 'origin')),
					ldl.getPoint(get_property(r, 'size')),
					con_info['wall'],
					ldl.getPoint2D(get_property(c, 'size')),
					get_property(c, 'pos')
				)
			else:
				con_centre = None
		else:
			con_centre = None

		# The target must also have this connection...
		if con_info['target'] and not con_info['target'] == r_id:
			# ought to be a room on the same level in the XML tree as we're in now
			# (FIXME enforce?)
			con_target = get_room_by_id(parentgroup, con_info['target'])
			if con_target:
				# Set its size (to be used later on for origin determination)...
				set_room_size(con_target)
				# Prepare targets connections storage area in target...
				# If there's only one connection it'll've been read in as a hash.
				# Ensure that it's an array so we can add connections easily.
				if con_target.has_key(OT_CON):
					if isinstance(con_target[OT_CON], dict):
						tmp = con_target[OT_CON]
						con_target[OT_CON] = []
						con_target[OT_CON].append(tmp)
				else:
					con_target[OT_CON] = []
					# FIXME doesn't seem to do what I want

				# Get ready to add the corresponding connection to our target...
				# Don't specify type as a door is only needed once.
				# FIXME but if the connection is back to an earlier room the door will be lost on next pass.
				target_con_info = {
					'size': str(con_info['size']),
					'target': r_id,  # target points back to this room
					'wall': opposite_dir(con_info['wall']),
					'pos': None
				}

				# FIXME	
				ldl.uprint(coninfostr(con_info))
				ldl.uprint(str(target_con_info))

				# Do we need to remove the existing entry for this connection, in con_target?
				already_there = False
				if con_target[OT_CON]:
					ldl.uprint(r_id + ' to ' + con_target['id'] + ': checking cons in target.')
					# Check each connection...
					for entry in con_target[OT_CON]:
						if get_property(entry, 'origin'):
							if entry['target'] == target_con_info['target']:
								already_there = True
								ldl.uprint(r_id + ' to ' + con_target['id'] + ': existing con has origin.')
						else:
							if entry['target'] == target_con_info['target']:
								# If elevtype attributes are not equal, copy this one across...
								if get_property(entry, 'elevtype'):
									ldl.uprint(r_id + ' to ' + con_target['id'] + ': using existing con w/o origin\'s \'elevtype\' attribute.')
									target_con_info['elevtype'] = entry['elevtype']
								# If extent attributes are not equal, copy this one across...
								if get_property(entry, 'extent'):
									ldl.uprint(r_id + ' to ' + con_target['id'] + ': using existing con w/o origin\'s \'extent\' attribute.')
									target_con_info['extent'] = entry['extent']
								# If pos attributes are not equal, copy this one across...
								if get_property(entry, 'pos'):
									ldl.uprint(r_id + ' to ' + con_target['id'] + ': using existing con w/o origin\'s \'pos\' attribute.')
									target_con_info['pos'] = entry['pos']
								# If type attributes are not equal, copy this one across...
								if get_property(entry, 'type'):
									ldl.uprint(r_id + ' to ' + con_target['id'] + ': using existing con w/o origin\'s \'type\' attribute.')
									target_con_info['type'] = entry['type']
								# Now remove exisiting connection...
								con_target[OT_CON].remove(entry)
								ldl.uprint(r_id + ' to ' + con_target['id'] + ': removing existing con w/o origin from target')
					# Add the ``new'' connection to our target?
					if not already_there:
						con_target[OT_CON].append(target_con_info)
						ldl.uprint(r_id + ' to ' + con_target['id'] + ': adding opposite con to target')
				else:
					# Target has no connections; just add this one...
					# FIXME should we be able to do this in the above loop instead?
					ldl.uprint(r_id + ' to ' + con_target['id'] + ': target has no cons; adding.')
					con_target[OT_CON].append(target_con_info)
			else:
				ldl.error('Couldn\'t find room \'' + r_id + '\' whilst processing the ' + coninfostr(con_info))

			# Do we need to work out the origin of the target?
			targ_origin = get_property(con_target, 'origin')
			if con_centre and not targ_origin:
				# Work out target origin and hole origin (on this side)...
				ldl.uprint('con_centre: ' + str(con_centre) + '; target_con_info: ' + pp.pformat(target_con_info))
				targ_origin = target_brush_origin(
						con_centre,
						con_info['size'],
						ldl.getPoint(con_target['size']),
						target_con_info['wall'],
						target_con_info['pos'])
				set_property(con_target, 'origin', targ_origin)
				rwo_update(con_target['id'], targ_origin)
				ldl.uprint('Origin of target room \'' + con_target['id'] + '\' is \'' + str(targ_origin) + '\'.')
			else:
				pass  # target already has origin computed
				# FIXME should we check it's ``right''?
		elif con_info['target'] and con_info['target'] == r_id:
			ldl.error('A connection in room \'' + r_id + '\' points to itself.  Please ensure all connections in this room point to other rooms.')
		else:
			#ldl.warning('No target specified for ' + coninfostr(con_info))  # FIXME check it's inside another room
			nontargetted_cons = True
			con_centre = hole_centre(
				Point(0,0,0),
				ldl.getPoint(get_property(r, 'size')),
				con_info['wall'],
				ldl.getPoint2D(get_property(c, 'size')))

		# Regardless of if connection has target, compute the hole's offset...
		if r_origin and not con_info['origin'] and con_centre:
			con_offset = hole_origin(
				con_centre,
				con_info['size'],
				con_info['wall'],
				r_origin,
				r_size,
				nontargetted_cons)
			set_property(con_info, 'origin', con_offset)
			set_property(c, 'origin', con_offset)

			# Might we need stairs/plat to reach it?
			dist = con_centre - r_origin
			if dist.z > ldl.ELEV_DIST:
				# Work out more accurate reading of dist, based on wall the conection is on...
				wall = con_info['wall']
				if wall == ldl.DCP_UP or wall == ldl.DCP_DOWN:
					ldl.warning('con_elev: vertical connection elevation devices not implemented yet.')
				else:  # N/S/E/W
					dist.z = dist.z - con_info['size'].y/2

				# Do we still need an elev?  Only go ahead if user hasn't told us not to.
				if dist.z > ldl.ELEV_DIST and get_property(con_info, 'elevtype') != 'none':
					# Sanity Check -- have we all the info we need?
					elevtype = get_property(con_info, 'elevtype', con_elev_err_msg(r_id, con_target['id'], 'you have not specified an elevation device type (e.g. \'' + ldl.ST_STAIRS + '\' or \'' + ldl.ST_PLAT + '\'); please do so.'))
					#extent = get_property(con_info, 'extent', con_elev_err_msg(r_id, con_target['id'], 'you have not specifed an \'extent\' attribute for this connection, so I cannot determine how big the elevation device must be.'))
					extent = get_property(con_info, 'extent')
		
					# Work out real area available (inside brush)...
					area2d = real_wall_size(r_size)
					area3d = Point(area2d.x, area2d.y, dist.z)#-con_info['size'].y/2-ldl.lip)
					ldl.uprint('con_elev: area availalbe: ' + str(area3d))
					# Convert extent size...
					if not extent:
						#ldl.warning('con_elev: size of elevation device (stirs or lift) not specifed; attempting to use a sensible value...')
						extent2d = ldl.Point2D(con_info['size'].x, con_info['size'].x)
					else:
						extent2d = ldl.getPoint2D(convert_coords(OT_CON_ELEV, extent, area3d))
					extent3d = Point(extent2d.x, extent2d.y, dist.z)
					ldl.uprint('con_elev: area to be used: ' + str(extent3d))
					elevtype = con_info['elevtype']
					ldl.uprint('con_elev: elevtype to be used: ' + str(elevtype))
					# work out origin:
					origin2d = ldl.getPoint2D(con_info['origin'])
					origin3d = None
					# FIXME again we seem to only need to account for ldl.lip in the x dir!
					if con_info['wall'] == ldl.DCP_EAST:
						origin3d = str(Point(
							r_size.x - extent2d.x,
							origin2d.x,
							0))
					elif con_info['wall'] == ldl.DCP_WEST:
						origin3d = str(Point(
							0,
							origin2d.x,
							0))
					elif con_info['wall'] == ldl.DCP_NORTH:
						origin3d = str(Point(
							origin2d.x - ldl.lip,
							r_size.y - extent2d.y,
							0))
					elif con_info['wall'] == ldl.DCP_SOUTH:
						origin3d = str(Point(
							origin2d.x - ldl.lip,
							0,
							0))
					# now populate builder hash...
					hash = {
						'origin': origin3d,
						'extent': str(extent3d),
						'shape': elevtype,
						'dir': con_info['wall']
					}
					add_subsection_element(r, 'builder', hash)
					ldl.uprint('con_elev: origin3d is ' + str(origin3d))
				else:
					pass  # elevtype set to 'none' -- user doesn't want one
			else:
				pass  # didn't trigger original ELEV_DIST check.
		else:
			pass  # don't set_property(c, 'origin', None)

		# Finished processing this connection...
	
	# This room has no connections to other rooms.
	# It could be an unconnected child of a room that does have an origin.
	if parent and get_property(parent, 'origin'):
		if nontargetted_cons and not get_property(r, 'origin'):
			# We need to have the room's position set to work out the origin...
			r_pos = get_property(r, 'pos')
			if r_pos:
				r_origin = get_childroom_origin(r_size, parent, r_pos, r_id)
				set_property(r, 'origin', r_origin)
				rwo_update(r_id, r_origin)
			else:
				ldl.error('Room ' + r_id + ' has no connections that touch other rooms.  It also does not have a \'pos\' attribute set so that it can be placed somewhere within its parent room (\'' + parent['id'] + '\').  Without thsi information it is not possible to place the room in the map.  Please add either a connection that leads directly onto another room or, if you wish to place \'' + r_id + '\' somewhere inside its parent room then provide it with a \'pos\' attribute -- pos=\'nw\' for example would place it in the north west of the parent room.')
		else:
			pass  # we can -- have or will -- work out the origin eventually.
	else:
		pass  # let's hope we get the origin of this parent sooner or later...

	# Process items...
	for i in get_children(r, OT_ITEM):
		ldl.check_entity_name(get_property(i, 'type'))
		i_pos = get_property(i, 'pos', True)
		if r_compass.match(i_pos):
			set_property(i, 'pos', convert_coords(OT_ITEM, i_pos, r))
	
	# Process child rooms (can't connect to anything but themselves and this room)...
	process_rooms(get_children(r, OT_ROOM), r)

def serialise_room(r):
	'''Output XML for a given room'''
	padding_update(True)
	padded_print('<hollow id=\'' + r['id'] + '\' origin=\'' + r['origin'] + '\' extent=\'' + r['size'] + '\' style=\'' + r['style'] + '\'>')
	# Connections
	connections = get_property(r, OT_CON)
	if connections:
		padding_update(True)
		padded_print('<holes>')
		padding_update(True)
		if isinstance(connections, dict):
			connections = [connections]
		for c in connections:
			if c.has_key('type'):
				type = ' type=\'' + c['type'] + '\''
			else:
				type = ''
			padded_print('<hole wall=\'' + c['wall'] + '\' origin=\'' + c['origin'] + '\' extent=\'' + c['size'] + '\'' + type + ' />')
		padding_update(False)
		padded_print('</holes>')
		padding_update(False)
	# Builders
	roombuilders = get_property(r, OT_BUILDER)
	if roombuilders:
		if isinstance(roombuilders, dict):
			roombuilders = [roombuilders]
		for i in roombuilders:
			serialise_builder(i)
	# Items
	roomitems = get_property(r, OT_ITEM)
	if roomitems:
		if isinstance(roomitems, dict):
			roomitems = [roomitems]
		for i in roomitems:
			serialise_item(i)
	# Child rooms
	childrooms = get_property(r, OT_ROOM)
	if childrooms:
		if isinstance(childrooms, dict):
			childrooms = [childrooms]
		for x in childrooms:
			serialise_room(x)
	padded_print('</hollow>')
	padding_update(False)

def serialise_builder(b):
	padding_update(True)
	padded_print('<builder origin=\'' + b['origin'] + '\' extent=\'' + b['extent'] + '\'>')
	padding_update(True)
	if b['shape'] == ldl.ST_STAIRS:
		padded_print('<shape type=\'stairs\' stepheight=\'15\' dir=\'' + b['dir'] + '\' />')
	elif b['shape'] == ldl.ST_PLAT:
		padded_print('<shape type=\'plat\' position=\'d\' />')
	else:
		ldl.error('You specifed an elevator device type of \'' + b['shape'] + '\' for one of your connections.  This is not valid.  Please use either \'' + ldl.ST_STAIRS + '\' or \'' + ldl.ST_PLAT + '\'.')
	padding_update(False)
	padded_print('</builder>')
	padding_update(False)

def serialise_item(i):
	padding_update(True)
	padded_print('<entity>')
	padding_update(True)
	padded_print('<property name=\'classname\' value=\'' + i['type'] + '\' />')
	# FIXME inconsistency: we store other aboslute coords in an 'origin' field
	padded_print('<property name=\'origin\' value=\'' + i['pos'] + '\' />')
	# The player starts must face the chosen way, or North...
	if i['type'] == 'info_player_start' \
	or i['type'] == 'info_player_deathmatch' \
	or i['type'] == 'info_player_coop':
		if not i.has_key('angle'):
			padded_print('<property name=\'angle\' value=\'90\' />')
		else:
			padded_print('<property name=\'angle\' value=\'' + str(compdir_to_angle(i['angle'])) + '\' />')
	padding_update(False)
	padded_print('</entity>')
	padding_update(False)

def compdir_to_angle(dir):
	'''Convert a compass direction to Quake angle.'''
	if not dir:
		ldl.error('compdir_to_angle: no direction specified!')
	else:
		if r_compass.match(dir):
			if dir_to_angle.has_key(dir):
				return dir_to_angle[dir]
			else:
				ldl.error('compdir_to_angle: I don\'t know the angle for compass direction \'' + dir + '\'.')
		else:
			ldl.error('compdir_to_angle: specified direction \'' + str(dir) + '\' doesn\'t seem to be a valid compass direction (or a supported one for translation).')

def serialise(m):
	'''Output XML'''
	padding_update(True)
	mapname = m['name']
	worldtype = m['style']
	padded_print('<?xml version=\'1.0\' encoding=\'utf-8\'?>\n<!-- This is an automatically-generated intermediate map file, created by the Level Description Language (LDL) system from The AGRIP Project - see http://www.agrip.org.uk/ for more information. -->\n<map>')
	padding_update(True)
	padded_print('<info>')
	padding_update(True)
	padded_print('<property name=\'mapname\' value=\'' + mapname + '\' />')
	padded_print('<property name=\'worldtype\' value=\'' + worldtype + '\' />')
	padding_update(False)
	padded_print('</info>')
	padding_update(False)
	toplevelrooms = get_property(m, OT_ROOM)
	if isinstance(m[OT_ROOM], dict):
		toplevelrooms = [toplevelrooms]
	for room in toplevelrooms:
		serialise_room(room)
	padded_print('</map>')
	padding_update(False)

def padding_update(inc):
	global serialise_padding_level
	if inc:
		serialise_padding_level = serialise_padding_level + 1
	else:
		serialise_padding_level = serialise_padding_level - 1
	return

def padded_print(str):
	for i in range(serialise_padding_level):
		print serialise_padding,
	print str

if __name__ == "__main__":
	ldl.stage = '05'
	pp = pprint.PrettyPrinter()
	serialise_padding_level = -1
	serialise_padding = '  '
	f_firstroom = True
	ril = []
	rwo = {}
	default_style = None
	input = sys.stdin.read()

	# Try to parse the XML file...
	try:
		x = xml2dict.fromstring(input)
	except xml.parsers.expat.ExpatError, detail:
		ldl.error('The XML you supplied is not valid: ' + str(detail))

	# Sanity check...
	if x.has_key('map'):
		m = x['map']
	else:
		ldl.error('It appears your map file doesn\'t start with a \'map\' element.')
	# Parse properties in map info...
	if m.has_key('name'):
		pass  # FIXME include as <property>
	else:
		ldl.error('It appears your map doesn\'t have a \'name\' attribute; please specify a name for your map.')
	if m.has_key('style'):
		default_style = m['style']
	else:
		ldl.error('It appears your map doesn\'t have a \'style\' attribute; please specify a style (e.g. base or medieval).')

	# Parse rooms...
	# NB: we give 3 attempts at this because if the user has not specifed rooms in connectivity order (probably impossible for compolex maps) we won't be able to work out all of their origins on the first, or maybe even second, go.
	# FIXME do we need 3 passes in the worst case?  do we need more?
	toplevelrooms = get_property(m, OT_ROOM)
	# if there is only one room...
	if isinstance(toplevelrooms, dict):
		toplevelrooms = [toplevelrooms]
	# Process the rooms for a given number of attempts...
	# FIXME change this to make it see if we're making progress and pull the plug when we are not
	exitflag = False
	i = 0
	if toplevelrooms:
		while not exitflag and i < ldl.concretion_attempts:
			ldl.uprint('\n\nPROCESSING ROOMS -- ATTEMPT ' + str(i) + '...')
			process_rooms(toplevelrooms, None)
			ri_clear()
			if rwo_num() == 0 and cwo_num(m) == 0:
				exitflag = True
			else:
				i = i + 1
		# Did we get all the room origins?
		if not exitflag:
			ldl.error('There are still some rooms or connections between rooms that it was not possible to allocate positions in the 3D world for, even after ' + str(i) + ' attempts.  This is probably because these rooms are not connected to any other rooms.  Please ensure all rooms in your map are connected.')

		# If we got here, we're OK...
		#ldl.uprint(pp.pformat(x))
		serialise(m)
	else:
		ldl.error('There doesn\'t seem to be at least \'room\' element inside the \'map\' element.')
