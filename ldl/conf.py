'''LDL Global Configuration Variables and Constants'''

#
# Configuration Variables
#

debug_printing = 0  # do we print out debug messages?
lip = 8  # thickness of wall brushes.
lip_small = lip/2  # thickness of door brushes.
lip_small_margin = lip_small/2 # thickness of margins around door brushes.
wadfile = 'quake.wad'  # name of texture-containing WAD file.
boilerplate = '<!-- This file was generated by a Level Description Language (LDL) script from\n	 the AGRIP project (http://www.agrip.org.uk/). -->\n'
boilerplate_map = '// This file was generated by a Level Description Language (LDL) script from\n// the AGRIP project (http://www.agrip.org.uk/).\n'
stackdescs = {
	'00':'Stage 00: Raw .map files to simple XML',
	'01':'Stage 01: Brush origins and extents',
	'02':'Stage 02: Rooms\'n\'Stuff',
	'03':'Stage 03: Lighting styles.',
	'04':'Stage 04: Builder Macros',
	'05':'Stage 0y: 3D Connections Level'
}
stage = None  # set by each stage, for use in error msgs
STYLE_FILE = 'style.xml'  # the style file for our maps (contains textures, sounds and lighting presets)
concretion_attempts = 3  # number of times the top level tries to parse the hash for info required for the lower levels.
MAP_ORIGIN = (0,0,0)
ELEV_DIST = 30


#
# Constants
#

DCP_NORTH = 'n'
DCP_SOUTH = 's'
DCP_EAST = 'e'
DCP_WEST = 'w'
DCP_NORTHEAST = 'ne'
DCP_SOUTHEAST = 'se'
DCP_SOUTHWEST = 'sw'
DCP_NORTHWEST = 'nw'
DCP_UP = 'u'
DCP_DOWN = 'd'
DCP_CENTRE = 'c'

DCP_TOP = 't'
DCP_BOTTOM = 'b'
DCP_RIGHT = 'r'
DCP_LEFT = 'l'
DCP_TOPRIGHT = 'tr'
DCP_BOTTOMRIGHT = 'br'
DCP_BOTTOMLEFT = 'bl'
DCP_TOPLEFT = 'tl'

RT_DOOR = 'door'
RT_PLAT = ST_PLAT = 'plat'
RT_STEP = ST_STEP = 'step'

ST_STAIRS = 'stairs'

WT_BASE = 'base'
WT_MED = 'medieval'
WT_RUNIC = 'runic'

PROPS_K_KEY = 'key'
PROPS_K_POS = 'position'

PT_INT = 'int'
PT_TEXT = 'text'

DIM_X = 'x'
DIM_Y = 'y'
DIM_Z = 'z'

worldtypes = {
	WT_MED: '0',
	WT_RUNIC: '1',
	WT_BASE: '2'
}

key_ents = {
	'silver': 'item_key1',
	'gold': 'item_key2'
}
key_access = {
	'silver': '16',
	'gold': '8'
}

# FIXME needs expansion
soundtypes_door = {
	WT_BASE: '2',
	WT_MED: '2'
}

# FIXME needs expansion
soundtypes_plat = {
	WT_BASE: '2',
	WT_MED: '2'
}

# lighting styles
LS_GRID = 'grid'
LS_CENTRE = 'centre'
LS_PERIMETER = 'perimeter'
LS_DEF = ''

# Valid items
valid_entities = [
	'air_bubbles',
	'ambient_drip',
	'ambient_drone',
	'ambient_comp_hum',
	'ambient_flouro_buzz',
	'ambient_light_buzz',
	'ambient_suck_wind',
	'ambient_swamp1',
	'ambient_swamp2',
	'ambient_thunder',
	'event_lightning',
	'func_door',
	'func_door_secret',
	'func_wall',
	'func_button',
	'func_train',
	'func_plat',
	'func_dm_only',
	'func_illusionary',
	'info_null',
	'info_notnull',
	'info_intermission',
	'info_player_start',
	'info_player_deathmatch',
	'info_player_coop',
	'info_player_start2',
	'info_teleport_destination',
	'item_cells',
	'item_rockets',
	'item_shells',
	'item_spikes',
	'item_weapon',
	'item_health',
	'item_artifact_envirosuit',
	'item_artifact_super_damage',
	'item_artifact_invulnerability',
	'item_artifact_invisibility',
	'item_armorInv',
	'item_armor2',
	'item_armor1',
	'item_key1',
	'item_key2',
	'item_sigil',
	'light',
	'light_torch_small_walltorch',
	'light_flame_large_yellow',
	'light_flame_small_yellow',
	'light_flame_small_white',
	'light_fluoro',
	'light_fluorospark',
	'light_globe',
	'monster_army',
	'monster_dog',
	'monster_ogre',
	'monster_ogre_marksman',
	'monster_knight',
	'monster_zombie',
	'monster_wizard',
	'monster_demon1',
	'monster_shambler',
	'monster_boss',
	'monster_enforcer',
	'monster_hell_knight',
	'monster_shalrath',
	'monster_tarbaby',
	'monster_fish',
	'monster_oldone',
	'misc_fireball',
	'misc_explobox',
	'misc_explobox2',
	'misc_teleporttrain',
	'path_corner',
	'trap_spikeshooter',
	'trap_shooter',
	'trigger_teleport',
	'trigger_changelevel',
	'trigger_setskill',
	'trigger_counter',
	'trigger_once',
	'trigger_multiple',
	'trigger_onlyregistered',
	'trigger_secret',
	'trigger_monsterjump',
	'trigger_relay',
	'trigger_push',
	'trigger_hurt',
	'weapon_supershotgun',
	'weapon_nailgun',
	'weapon_supernailgun',
	'weapon_grenadelauncher',
	'weapon_rocketlauncher',
	'weapon_lightning'
]
