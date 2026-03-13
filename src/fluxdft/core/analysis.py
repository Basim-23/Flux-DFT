"""
Analysis tools for Structure Visualization.
Handles Bond Detection (CrystalNN) and Polyhedra Generation.
"""

from typing import List, Tuple, Dict, Any
import numpy as np

try:
    from pymatgen.core import Structure
    from pymatgen.analysis.local_env import CrystalNN, VoronoiNN
    from pymatgen.analysis.graphs import StructureGraph
    from scipy.spatial import ConvexHull
    HAS_ANALYSIS = True
except ImportError:
    HAS_ANALYSIS = False

class StructureAnalyzer:
    """Analyzes structure for bonds and polyhedra."""
    
    def __init__(self, structure: Structure):
        self.structure = structure
        self.bonding_strategy = CrystalNN() # Robust default
        self._graph = None
        
    def get_structure_graph(self) -> 'StructureGraph':
        """Compute chemical bonds using CrystalNN."""
        if not HAS_ANALYSIS:
            return None
            
        if self._graph is None:
            try:
                self._graph = self.bonding_strategy.get_bonded_structure(self.structure)
            except Exception as e:
                print(f"Bonding failed: {e}")
                return None
        return self._graph

    def get_bonds_data(self) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Get list of (start, end) points for all bonds.
        Returns: List of (pos1, pos2) numpy arrays.
        """
        graph = self.get_structure_graph()
        if graph is None:
            return []
            
        bonds = []
        # graph.graph.edges(data=True) returns (u, v, data)
        # u, v are site indices
        # We need to handle periodic images for visualization!
        # Pymatgen StructureGraph stores bonds. 'to_jimage' handles wrapping.
        
        for u, v, data in graph.graph.edges(data=True):
            site_u = self.structure[u]
            site_v = self.structure[v]
            
            # Simple case: cartesian coords
            pos_u = site_u.coords
            pos_v = site_v.coords
            
            # Handle PBC: if jimage (periodic image) is not (0,0,0)
            # We draw the bond from u to v's image.
            # data usually contains 'to_jimage'
            jimage = data.get("to_jimage", (0, 0, 0))
            
            # Compute actual cartesian position of v in the image
            # pos_v_image = site_v.lattice.get_cartesian_coords(site_v.frac_coords + jimage)
            # Using Pymatgen internal methods
            pos_v_image = site_v.coords + np.dot(jimage, self.structure.lattice.matrix)
            
            bonds.append((pos_u, pos_v_image))
            
        return bonds

    def get_polyhedra_data(self) -> List[Dict[str, Any]]:
        """
        Compute coordination polyhedra for cations.
        Returns list of dicts: {'vertices': np.array, 'faces': np.array, 'center': np.array, 'color': str}
        """
        if not HAS_ANALYSIS:
            return []
            
        graph = self.get_structure_graph()
        if graph is None:
            return []
            
        polyhedra_list = []
        
        # Iterate over all sites
        for i, site in enumerate(self.structure):
            # Heuristic: Only draw polyhedra around "cations" or specific atoms
            # For now, let's draw for anything with CN >= 4 and CN <= 12
            # Or use user preference. A common heuristic is Metal atoms.
            
            # Basic Metal check (very rough)
            if not site.specie.is_metal:
                continue
                
            # Get neighbors from graph
            neighbors = graph.get_connected_sites(i)
            
            if len(neighbors) < 4:
                continue # Planar or linear, not a polyhedron usually
                
            # Collect vertices
            neighbor_points = []
            for neighbor in neighbors:
                # Connected site object: site, jimage, weight...
                n_site = neighbor.site
                jimage = neighbor.jimage
                
                # Compute image position
                pos = n_site.coords + np.dot(jimage, self.structure.lattice.matrix)
                neighbor_points.append(pos)
            
            if len(neighbor_points) < 4:
                continue
                
            points = np.array(neighbor_points)
            
            # Compute Convex Hull
            try:
                hull = ConvexHull(points)
                # hull.simplices contains triangle faces (indices of points)
                # hull.points contains input points
                
                # To render in PyVista, we need vertices and faces.
                # PyVista faces format: [n_points, p0, p1, p2, n_points...]
                # ConvexHull simplices are [p0, p1, p2] triangles.
                
                faces_flat = []
                for simplex in hull.simplices:
                    faces_flat.append(3) # triangle
                    faces_flat.extend(simplex)
                    
                polyhedra_list.append({
                    'vertices': points,
                    'faces': np.array(faces_flat),
                    'center': site.coords,
                    'atomic_number': site.specie.number
                })
                
            except Exception:
                # Coplanar or degenerate
                continue
                
        return polyhedra_list
