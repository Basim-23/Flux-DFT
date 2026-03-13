from pymatgen.core import Structure

txt = """data_Si
_symmetry_space_group_name_H-M   'F d -3 m'
_cell_length_a   5.468728
_cell_length_b   5.468728
_cell_length_c   5.468728
_cell_angle_alpha   90.000000
_cell_angle_beta   90.000000
_cell_angle_gamma   90.000000
loop_
 _symmetry_equiv_pos_site_id
 _symmetry_equiv_pos_as_xyz
  1  'x, y, z'
loop_
 _atom_site_label
 _atom_site_type_symbol
 _atom_site_fract_x
 _atom_site_fract_y
 _atom_site_fract_z
 Si1 Si 0.000000 0.000000 0.000000
 Si2 Si 0.250000 0.250000 0.250000"""

try:
    s = Structure.from_str(txt, fmt='cif')
    print("Success:", s.num_sites)
except Exception as e:
    print("Error:", repr(e))
