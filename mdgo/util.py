# coding: utf-8
# Copyright (c) Tingzheng Hou.
# Distributed under the terms of the MIT License.

import numpy as np
import string
from io import StringIO
import os
import re
import pandas as pd
import math
import sys
from typing import List, Dict, Union, Tuple
from typing_extensions import Final
from mdgo.volume import molecular_volume

from pymatgen.core import Molecule
from pymatgen.io.lammps.data import CombinedData

__author__ = "Tingzheng Hou"
__version__ = "1.0"
__maintainer__ = "Tingzheng Hou"
__email__ = "tingzheng_hou@berkeley.edu"
__date__ = "Feb 9, 2021"

MM_of_Elements: Final[Dict[str, float]] = {
    "H": 1.00794,
    "He": 4.002602,
    "Li": 6.941,
    "Be": 9.012182,
    "B": 10.811,
    "C": 12.0107,
    "N": 14.0067,
    "O": 15.9994,
    "F": 18.9984032,
    "Ne": 20.1797,
    "Na": 22.98976928,
    "Mg": 24.305,
    "Al": 26.9815386,
    "Si": 28.0855,
    "P": 30.973762,
    "S": 32.065,
    "Cl": 35.453,
    "Ar": 39.948,
    "K": 39.0983,
    "Ca": 40.078,
    "Sc": 44.955912,
    "Ti": 47.867,
    "V": 50.9415,
    "Cr": 51.9961,
    "Mn": 54.938045,
    "Fe": 55.845,
    "Co": 58.933195,
    "Ni": 58.6934,
    "Cu": 63.546,
    "Zn": 65.409,
    "Ga": 69.723,
    "Ge": 72.64,
    "As": 74.9216,
    "Se": 78.96,
    "Br": 79.904,
    "Kr": 83.798,
    "Rb": 85.4678,
    "Sr": 87.62,
    "Y": 88.90585,
    "Zr": 91.224,
    "Nb": 92.90638,
    "Mo": 95.94,
    "Tc": 98.9063,
    "Ru": 101.07,
    "Rh": 102.9055,
    "Pd": 106.42,
    "Ag": 107.8682,
    "Cd": 112.411,
    "In": 114.818,
    "Sn": 118.71,
    "Sb": 121.760,
    "Te": 127.6,
    "I": 126.90447,
    "Xe": 131.293,
    "Cs": 132.9054519,
    "Ba": 137.327,
    "La": 138.90547,
    "Ce": 140.116,
    "Pr": 140.90465,
    "Nd": 144.242,
    "Pm": 146.9151,
    "Sm": 150.36,
    "Eu": 151.964,
    "Gd": 157.25,
    "Tb": 158.92535,
    "Dy": 162.5,
    "Ho": 164.93032,
    "Er": 167.259,
    "Tm": 168.93421,
    "Yb": 173.04,
    "Lu": 174.967,
    "Hf": 178.49,
    "Ta": 180.9479,
    "W": 183.84,
    "Re": 186.207,
    "Os": 190.23,
    "Ir": 192.217,
    "Pt": 195.084,
    "Au": 196.966569,
    "Hg": 200.59,
    "Tl": 204.3833,
    "Pb": 207.2,
    "Bi": 208.9804,
    "Po": 208.9824,
    "At": 209.9871,
    "Rn": 222.0176,
    "Fr": 223.0197,
    "Ra": 226.0254,
    "Ac": 227.0278,
    "Th": 232.03806,
    "Pa": 231.03588,
    "U": 238.02891,
    "Np": 237.0482,
    "Pu": 244.0642,
    "Am": 243.0614,
    "Cm": 247.0703,
    "Bk": 247.0703,
    "Cf": 251.0796,
    "Es": 252.0829,
    "Fm": 257.0951,
    "Md": 258.0951,
    "No": 259.1009,
    "Lr": 262,
    "Rf": 267,
    "Db": 268,
    "Sg": 271,
    "Bh": 270,
    "Hs": 269,
    "Mt": 278,
    "Ds": 281,
    "Rg": 281,
    "Cn": 285,
    "Nh": 284,
    "Fl": 289,
    "Mc": 289,
    "Lv": 292,
    "Ts": 294,
    "Og": 294,
    "ZERO": 0,
}

SECTION_SORTER: Final[Dict[str, dict]] = {
    "atoms": {
        "in_kw": None,
        "in_header": ["atom", "charge", "sigma", "epsilon"],
        "sec_number": None,
        "desired_split": None,
        "desired_cols": None,
        "out_kw": None,
        "ff_header": ["epsilon", "sigma"],
        "topo_header": ["mol-id", "type", "charge", "x", "y", "z"],
    },
    "bonds": {
        "in_kw": "Stretch",
        "in_header": ["atom1", "atom2", "k", "r0"],
        "sec_number": 5,
        "desired_split": 2,
        "desired_cols": 4,
        "out_kw": ["Bond Coeffs", "Bonds"],
        "ff_header": ["k", "r0"],
        "topo_header": ["type", "atom1", "atom2"],
    },
    "angles": {
        "in_kw": "Bending",
        "in_header": ["atom1", "atom2", "atom3", "k", "theta0"],
        "sec_number": 6,
        "desired_split": 1,
        "desired_cols": 5,
        "out_kw": ["Angle Coeffs", "Angles"],
        "ff_header": ["k", "theta0"],
        "topo_header": ["type", "atom1", "atom2", "atom3"],
    },
    "dihedrals": {
        "in_kw": "proper Torsion",
        "in_header": ["atom1", "atom2", "atom3", "atom4", "v1", "v2", "v3", "v4"],
        "sec_number": 7,
        "desired_split": 1,
        "desired_cols": 8,
        "out_kw": ["Dihedral Coeffs", "Dihedrals"],
        "ff_header": ["v1", "v2", "v3", "v4"],
        "topo_header": ["type", "atom1", "atom2", "atom3", "atom4"],
    },
    "impropers": {
        "in_kw": "improper Torsion",
        "in_header": ["atom1", "atom2", "atom3", "atom4", "v2"],
        "sec_number": 8,
        "desired_split": 1,
        "desired_cols": 5,
        "out_kw": ["Improper Coeffs", "Impropers"],
        "ff_header": ["v1", "v2", "v3"],
        "topo_header": ["type", "atom1", "atom2", "atom3", "atom4"],
    },
}

BOX: Final[
    str
] = """{0:6f} {1:6f} xlo xhi
{0:6f} {1:6f} ylo yhi
{0:6f} {1:6f} zlo zhi"""

MOLAR_VOLUME: Final[Dict[str, Union[float, int]]] = {"lipf6": 18, "litfsi": 100}  # empirical value

ALIAS: Final[Dict[str, str]] = {
    "ethylene carbonate": "ec",
    "ec": "ec",
    "propylene carbonate": "pc",
    "pc": "pc",
    "dimethyl carbonate": "dmc",
    "dmc": "dmc",
    "diethyl carbonate": "dec",
    "dec": "dec",
    "ethyl methyl carbonate": "emc",
    "emc": "emc",
    "fluoroethylene carbonate": "fec",
    "fec": "fec",
    "vinyl carbonate": "vc",
    "vinylene carbonate": "vc",
    "vc": "vc",
    "1,3-dioxolane": "dol",
    "dioxolane": "dol",
    "dol": "dol",
    "ethylene glycol monomethyl ether": "egme",
    "2-methoxyethanol": "egme",
    "egme": "egme",
    "dme": "dme",
    "1,2-dimethoxyethane": "dme",
    "glyme": "dme",
    "monoglyme": "dme",
    "2-methoxyethyl ether": "diglyme",
    "diglyme": "diglyme",
    "triglyme": "triglyme",
    "tetraglyme": "tetraglyme",
    "acetonitrile": "acn",
    "acn": "acn",
    "water": "water",
    "h2o": "water",
}

# From PubChem
MOLAR_MASS: Final[Dict[str, float]] = {
    "ec": 88.06,
    "pc": 102.09,
    "dec": 118.13,
    "dmc": 90.08,
    "emc": 104.05,
    "fec": 106.05,
    "vc": 86.05,
    "dol": 74.08,
    "egme": 76.09,
    "dme": 90.12,
    "diglyme": 134.17,
    "triglyme": 178.23,
    "tetraglyme": 222.28,
    "acn": 41.05,
    "water": 18.01528,
}

# from Sigma-Aldrich
DENSITY: Final[Dict[str, float]] = {
    "ec": 1.321,
    "pc": 1.204,
    "dec": 0.975,
    "dmc": 1.069,
    "emc": 1.006,
    "fec": 1.454,  # from qm-ht.com
    "vc": 1.355,
    "dol": 1.06,
    "dme": 0.867,
    "egme": 0.965,
    "diglyme": 0.939,
    "triglyme": 0.986,
    "tetraglyme": 1.009,
    "acn": 0.786,
    "water": 0.99707,
}


def atom_vec(atom1, atom2, dimension):
    """
    Calculate the vector of the positions from atom2 to atom1.
    """
    vec = [0, 0, 0]
    for i in range(3):
        diff = atom1.position[i] - atom2.position[i]
        if diff > dimension[i] / 2:
            vec[i] = diff - dimension[i]
        elif diff < -dimension[i] / 2:
            vec[i] = diff + dimension[i]
        else:
            vec[i] = diff
    return np.array(vec)


def position_vec(pos1, pos2, dimension):
    """
    Calculate the vector from pos2 to pos2.
    """
    vec = [0, 0, 0]
    for i in range(3):
        diff = pos1[i] - pos2[i]
        if diff > dimension[i] / 2:
            vec[i] = diff - dimension[i]
        elif diff < -dimension[i] / 2:
            vec[i] = diff + dimension[i]
        else:
            vec[i] = diff
    return np.array(vec)


def mass_to_name(df):
    """
    Create a dict for mapping atom type id to element from the mass information.

    Args:
        df (pandas.DataFrame): The masses attribute from LammpsData object
    Return:
        dict: The element dict.
    """
    atoms = {}
    for row in df.index:
        for item in MM_of_Elements.items():
            if math.isclose(df["mass"][row], item[1], abs_tol=0.01):
                atoms[row] = item[0]
    return atoms


def assign_name(u, element_id_dict):
    """
    Assgin resnames to residues in a MDAnalysis.universe object. The function will not overwrite existing names.

    Args:
        u (MDAnalysis.universe): The universe object to assign resnames to.
        element_id_dict (dict): A dictionary of atom types, where each type is a key
                and the corresponding values are the element names.
    """
    u.add_TopologyAttr("name")
    for key, val in element_id_dict.items():
        atom_group = u.select_atoms("type {}".format(str(key)))
        atom_names = atom_group.names
        atom_names[atom_names == ""] = val
        atom_group.names = atom_names


def assign_resname(u, res_dict):
    """
    Assgin resnames to residues in a MDAnalysis.universe object. The function will not overwrite existing resnames.

    Args:
        u (MDAnalysis.universe): The universe object to assign resnames to.
        res_dict (dict): A dictionary of resnames, where each resname is a key
                and the corresponding values are the selection language.
    """
    u.add_TopologyAttr("resname")
    for key, val in res_dict.items():
        res_group = u.select_atoms(val)
        res_names = res_group.residues.resnames
        res_names[res_names == ""] = key
        res_group.residues.resnames = res_names


def res_dict_from_select_dict(u, select_dict):
    """
    Infer res_dict (residue selection) from select_dict (atom selection) in a MDAnalysis.universe object.

    Args:
        u (MDAnalysis.universe): The universe object to assign resnames to.
        select_dict (dict): A dictionary of atom species, where each atom species name is a key
                and the corresponding values are the selection language.
    return:
        dict: A dictionary of resnames.
    """
    saved_select = list()
    res_dict = dict()
    for key, val in select_dict.items():
        res_select = "same resid as (" + val + ")"
        res_group = u.select_atoms(res_select)
        if key in ["cation", "anion"] or res_group not in saved_select:
            saved_select.append(res_group)
            res_dict[key] = res_select
    if (
        "cation" in res_dict
        and "anion" in res_dict
        and u.select_atoms(res_dict.get("cation")) == u.select_atoms(res_dict.get("anion"))
    ):
        res_dict.pop("anion")
        res_dict["salt"] = res_dict.pop("cation")
    return res_dict


def res_dict_from_datafile(filename):
    """
    Infer res_dict (residue selection) from a LAMMPS data file.

    Args:
        filename (str): Path to the data file. The data file must be generated by a CombinedData object.
    return:
        dict: A dictionary of resnames.
    """
    res_dict = dict()
    with open(filename, "r") as f:
        lines = f.readlines()
        if lines[0] == "Generated by pymatgen.io.lammps.data.LammpsData\n" and lines[1].startswith("#"):
            elyte_info = re.findall(r"\w+", lines[1])
            it = iter(elyte_info)
            idx = 1
            for num in it:
                name = next(it)
                if name.isnumeric():
                    frag = int(name)
                    name = next(it)
                    names = [name + c for c in string.ascii_lowercase[0:frag]]
                    start = idx
                    idx += int(num) * frag
                    for i, n in enumerate(names):
                        res_dict[n] = "same mass as resid " + str(start + i)
                else:
                    start = idx
                    idx += int(num)
                    end = idx
                    res_dict[name] = "resid " + str(start) + "-" + str(end - 1)
            return res_dict
        else:
            return None


def res_dict_from_lammpsdata(lammps_data):
    """
    Infer res_dict (residue selection) from a LAMMPS data file.

    Args:
        lammps_data (CombinedData): A CombinedData object.
    return:
        dict: A dictionary of resnames.
    """
    assert isinstance(lammps_data, CombinedData)
    idx = 1
    res_dict = dict()

    if hasattr(lammps_data, "frags"):
        for name, num, frag in zip(lammps_data.names, lammps_data.nums, lammps_data.frags):
            if frag == 1:
                start = idx
                idx += num
                end = idx
                res_dict[name] = "resid " + str(start) + "-" + str(end - 1)
            else:
                names = [name + c for c in string.ascii_lowercase[0:frag]]
                start = idx
                idx += int(num) * frag
                for i, n in enumerate(names):
                    res_dict[n] = "same mass as resid " + str(start + i)
    else:
        for name, num in zip(lammps_data.names, lammps_data.nums):
            start = idx
            idx += num
            end = idx
            res_dict[name] = "resid " + str(start) + "-" + str(end - 1)
    return res_dict


def select_dict_from_resname(u):
    """
    Infer select_dict (possibly interested atom species selection) from resnames in a MDAnalysis.universe object.

    Args:
        u (MDAnalysis.universe): The universe object to work with.
    return:
        dict: A dictionary of resnames.
    """
    select_dict = dict()
    resnames = np.unique(u.residues.resnames)
    for resname in resnames:
        if resname == "":
            continue
        residue = u.select_atoms("resname " + resname).residues[0]
        if np.isclose(residue.charge, 0, atol=1e-5):
            if len(residue.atoms.fragments) == 2:
                for frag in residue.atoms.fragments:
                    charge = np.sum(frag.charges)
                    if charge > 0.01:
                        extract_atom_from_ion(True, frag, select_dict)
                    elif charge < -0.01:
                        extract_atom_from_ion(False, frag, select_dict)
                    else:
                        extract_atom_from_molecule(resname, residue, select_dict)
            else:
                extract_atom_from_molecule(resname, residue, select_dict)
        elif residue.charge > 0:
            extract_atom_from_ion(True, residue, select_dict)
        else:
            extract_atom_from_ion(False, residue, select_dict)
    return select_dict


def extract_atom_from_ion(positive, residue, select_dict):
    if positive:
        if len(residue.atoms.types) == 1:
            select_dict["cation"] = "type " + residue.atoms.types[0]
        else:
            pos_center = residue.atoms[np.argmax(residue.atoms.charges)]
            unique_types = np.unique(residue.atoms.types, return_counts=True)
            uni_center = unique_types[0][np.argmin(unique_types[1])]
            if pos_center.type == uni_center:
                select_dict["cation"] = "type " + uni_center
            else:
                select_dict["cation_" + pos_center.name + pos_center.type] = "type " + pos_center.type
                select_dict["cation"] = "type " + uni_center
    else:
        if len(residue.atoms.types) == 1:
            select_dict["anion"] = "type " + residue.atoms.types[0]
        else:
            neg_center = residue.atoms[np.argmin(residue.atoms.charges)]
            unique_types = np.unique(residue.atoms.types, return_counts=True)
            uni_center = unique_types[0][np.argmin(unique_types[1])]
            if neg_center.type == uni_center:
                select_dict["anion"] = "type " + uni_center
            else:
                select_dict["anion_" + neg_center.name + neg_center.type] = "type " + neg_center.type
                select_dict["anion"] = "type " + uni_center


def extract_atom_from_molecule(resname, residue, select_dict):
    # neg_center = residue.atoms[np.argmin(residue.atoms.charges)]
    # select_dict[resname + "-" + neg_center.name + neg_center.type] = "type " + neg_center.type
    # pos_center = residue.atoms[np.argmax(residue.atoms.charges)]
    # select_dict[resname + "+" + pos_center.name + pos_center.type] = "type " + pos_center.type
    neg_center = residue.atoms[np.argmin(residue.atoms.charges)]
    select_dict[resname] = "type " + neg_center.type


def ff_parser(ff_dir, xyz_dir):
    """
    A parser to convert a force field field from Maestro format
    to LAMMPS data format.

    Args:
        ff_dir (str): The path to the Maestro force field file.
        xyz_dir (str): The path to the xyz structure file.
    Return:
        str: The output LAMMPS data string.
    """
    with open(xyz_dir, "r") as f_xyz:
        molecule = pd.read_table(f_xyz, skiprows=2, delim_whitespace=True, names=["atom", "x", "y", "z"])
        coordinates = molecule[["x", "y", "z"]]
        lo = coordinates.min().min() - 0.5
        hi = coordinates.max().max() + 0.5
    with open(ff_dir, "r") as f:
        lines_org = f.read()
        lines = lines_org.split("\n\n")
        atoms = "\n".join(lines[4].split("\n", 4)[4].split("\n")[:-1])
        dfs = dict()
        dfs["atoms"] = pd.read_csv(
            StringIO(atoms),
            names=SECTION_SORTER.get("atoms").get("in_header"),
            delim_whitespace=True,
            usecols=[0, 4, 5, 6],
        )
        dfs["atoms"] = pd.concat([dfs["atoms"], coordinates], axis=1)
        dfs["atoms"].index += 1
        dfs["atoms"].index.name = "type"
        dfs["atoms"] = dfs["atoms"].reset_index()
        dfs["atoms"].index += 1
        types = dfs["atoms"].copy().reset_index().set_index("atom")["type"]
        replace_dict = {
            "atom1": dict(types),
            "atom2": dict(types),
            "atom3": dict(types),
            "atom4": dict(types),
        }
        counts = dict()
        counts["atoms"] = len(dfs["atoms"].index)
        mass_list = list()
        for index, row in dfs["atoms"].iterrows():
            mass_list.append(MM_of_Elements.get(re.split(r"(\d+)", row["atom"])[0]))
        mass_df = pd.DataFrame(mass_list)
        mass_df.index += 1
        mass_string = mass_df.to_string(header=False, index_names=False, float_format="{:.3f}".format)
        masses = ["Masses", mass_string]
        ff = ["Pair Coeffs"]
        dfs["atoms"]["mol-id"] = 1
        atom_ff_string = dfs["atoms"][SECTION_SORTER["atoms"]["ff_header"]].to_string(header=False, index_names=False)
        ff.append(atom_ff_string)
        topo = ["Atoms"]
        atom_topo_string = dfs["atoms"][SECTION_SORTER["atoms"]["topo_header"]].to_string(
            header=False, index_names=False
        )
        topo.append(atom_topo_string)
        for section in list(SECTION_SORTER.keys())[1:]:
            if SECTION_SORTER[section]["in_kw"] in lines_org:
                a, b, c, d = (
                    SECTION_SORTER[section]["sec_number"],
                    SECTION_SORTER[section]["desired_split"],
                    SECTION_SORTER[section]["desired_cols"],
                    SECTION_SORTER[section]["in_header"],
                )
                section_str = lines[a].split("\n", b)[b]
                dfs[section] = pd.read_csv(
                    StringIO(section_str),
                    names=d,
                    delim_whitespace=True,
                    usecols=list(range(c)),
                )

                dfs[section].index += 1
                dfs[section].index.name = "type"
                dfs[section] = dfs[section].replace(replace_dict)
                dfs[section] = dfs[section].reset_index()
                dfs[section].index += 1
                if section == "impropers":
                    dfs[section]["v1"] = dfs[section]["v2"] / 2
                    dfs[section]["v2"] = -1
                    dfs[section]["v3"] = 2
                ff_string = dfs[section][SECTION_SORTER[section]["ff_header"]].to_string(
                    header=False, index_names=False
                )
                ff.append(SECTION_SORTER[section]["out_kw"][0])
                ff.append(ff_string)
                topo_string = dfs[section][SECTION_SORTER[section]["topo_header"]].to_string(
                    header=False, index_names=False
                )
                topo.append(SECTION_SORTER[section]["out_kw"][1])
                topo.append(topo_string)
                counts[section] = len(dfs[section].index)
        max_stats = len(str(max(list(counts.values()))))
        stats_template = "{:>%d}  {}" % max_stats
        count_lines = [stats_template.format(v, k) for k, v in counts.items()]
        type_lines = [stats_template.format(v, k[:-1] + " types") for k, v in counts.items()]
        stats = "\n".join(count_lines + [""] + type_lines)
        header = [
            f"LAMMPS data file created by mdgo (by {__author__})\n"
            "# OPLS force field: harmonic, harmonic, opls, opls",
            stats,
            BOX.format(lo, hi),
        ]
        data_string = "\n\n".join(header + masses + ff + topo) + "\n"
        return data_string


def concentration_matcher(
    concentration: float,
    salt: Union[float, int, str, Molecule],
    solvents: List[Molecule],
    solv_ratio: List[float],
    num_salt: int = 100,
    mode: str = "v",
    radii_type: str = "Bondi",
) -> Tuple[List, float]:
    """
    Estimate the number of molecules of each species in a box,
    given the salt concentration, salt type, solvent molecular weight,
    solvent density, solvent ratio and total number of salt.

    Args:
        concentration: Salt concentration in mol/L.
        salt: Four types of input are accepted:
              1. The salt name in string ('lipf6' or 'litfsi')
              2. Salt molar volume in as a float/int (cm^3/mol)
              3. A pymatgen Molecule object of the salt structure
              4. The path to the salt structure xyz file

            Valid names are listed in the MOLAR_VOLUME dictionary at the beginning
            of this file and currently include only 'lipf6' or 'litfsi'

            If a Molecule or structure file is provided, mdgo will estimate
            the molar volume according to the VdW radii of the atoms. The
            specific radii used depend on the value of the 'radii_type' kwarg
            (see below).
        solvents: A list of solvent molecules. A molecule could either be
            a name (e.g. "water" or "ethylene carbonate") or a dict containing
            two keys "mass" and "density" in g/mol and g/mL, respectively.

            Valid names are listed in the ALIAS dictionary at the beginning
            of this file.
        solv_ratio: A list of relative weights or volumes of solvents. Must be the
            same length as solvents. For example, for a 30% / 70% (w/w) mix of
            two solvent, pass [0.3, 0.7] or [30, 70]. The sum of weights / volumes
            does not need to be normalized.
        num_salt: The number of salt in the box.
        mode: Weight mode (Weight/weight/W/w/W./w.) or volume mode
            (Volume/volume/V/v/V./v.) for interpreting the ratio of solvents.
        radii_type: "Bondi", "Lange", or "pymatgen". Bondi and Lange vdW radii
            are compiled in this package for H, B, C, N, O, F, Si, P, S, Cl, Br,
            and I. Choose 'pymatgen' to use the vdW radii from pymatgen.Element,
            which are available for most elements and reflect the latest values in
            the CRC handbook.

    Returns:
        (list, float):
            A list the number of molecules in the simulation box, starting with
            the salt and followed by each solvent in 'solvents'. The list is followed
            by a float of the approximate length of one side of the box in Å.

    """
    n_solvent = list()
    n = len(solv_ratio)
    if n != len(solvents):
        raise ValueError("solvents and solv_ratio must be the same length!")

    if isinstance(salt, float) or isinstance(salt, int):
        salt_molar_volume = salt
    elif isinstance(salt, Molecule):
        salt_molar_volume = molecular_volume(salt, salt.composition.reduced_formula, radii_type=radii_type)
    elif isinstance(salt, str):
        if MOLAR_VOLUME.get(salt.lower()):
            salt_molar_volume = MOLAR_VOLUME.get(salt.lower(), 0)
        else:
            if not os.path.exists(salt):
                print("\nError: Input file '{}' not found.\n".format(salt))
                sys.exit(1)
            name = os.path.splitext(os.path.split(salt)[-1])[0]
            ext = os.path.splitext(os.path.split(salt)[-1])[1]
            if not ext == ".xyz":
                print("Error: Wrong file format, please use a .xyz file.\n")
                sys.exit(1)
            salt_molar_volume = molecular_volume(salt, name, radii_type=radii_type)
    else:
        raise ValueError("Invalid salt type! Salt must be a number, string, or Molecule.")

    solv_mass = list()
    solv_density = list()
    for solv in solvents:
        if isinstance(solv, dict):
            solv_mass.append(solv.get("mass"))
            solv_density.append(solv.get("density"))
        else:
            solv_mass.append(MOLAR_MASS[ALIAS[solv.lower()]])
            solv_density.append(DENSITY[ALIAS[solv.lower()]])
    if mode.lower().startswith("v"):
        for i in range(n):
            n_solvent.append(solv_ratio[i] * solv_density[i] / solv_mass[i])
        n_salt = 1 / (1000 / concentration - salt_molar_volume)
        n_all = [int(m / n_salt * num_salt) for m in n_solvent]
        n_all.insert(0, num_salt)
        volume = ((1 + salt_molar_volume * n_salt) / n_salt * num_salt) / 6.022e23
        return n_all, volume ** (1 / 3) * 1e8
    elif mode.lower().startswith("w"):
        for i in range(n):
            n_solvent.append(solv_ratio[i] / solv_mass[i])
        v_solv = np.divide(solv_ratio, solv_density).sum()
        n_salt = v_solv / (1000 / concentration - salt_molar_volume)
        n_all = [int(m / n_salt * num_salt) for m in n_solvent]
        n_all.insert(0, num_salt)
        volume = ((v_solv + salt_molar_volume * n_salt) / n_salt * num_salt) / 6.022e23
        return n_all, volume ** (1 / 3) * 1e8
    else:
        mode = input("Volume or weight ratio? (w or v): ")
        return concentration_matcher(
            concentration,
            salt_molar_volume,
            solvents,
            solv_ratio,
            num_salt=num_salt,
            mode=mode,
        )


def sdf_to_pdb(sdf_file, pdb_file, write_title=True, remark4=True, credit=True, pubchem=True):
    """
    Convert SDF file to PDB file.
    """

    # parse sdf file file
    with open(sdf_file, "r") as inp:
        sdf = inp.readlines()
        sdf = map(str.strip, sdf)
    if pubchem:
        title = "cid_"
    else:
        title = ""
    pdb_atoms = list()
    # create pdb list of dictionaries
    atoms = 0
    bonds = 0
    atom1s = list()
    atom2s = list()
    orders = list()
    for i, line in enumerate(sdf):
        if i == 0:
            title += line.strip() + " "
            continue
        elif i in [1, 2]:
            continue
        elif i == 3:
            line = line.split()
            atoms = int(line[0])
            bonds = int(line[1])
            continue
        elif line.startswith("M  END"):
            break
        elif i in list(range(4, 4 + atoms)):
            line = line.split()
            newline = {
                "ATOM": "HETATM",
                "serial": int(i - 3),
                "name": str(line[3]),
                "resName": "UNK",
                "resSeq": 900,
                "x": float(line[0]),
                "y": float(line[1]),
                "z": float(line[2]),
                "occupancy": 1.00,
                "tempFactor": 0.00,
                "altLoc": str(""),
                "chainID": str(""),
                "iCode": str(""),
                "element": str(line[3]),
                "charge": str(""),
                "segment": str(""),
            }
            pdb_atoms.append(newline)
        elif i in list(range(4 + atoms, 4 + atoms + bonds)):
            atom1 = int(line.split()[0])
            atom2 = int(line.split()[1])
            order = int(line.split()[2])
            atom1s.append(atom1)
            atom2s.append(atom2)
            while order > 1:
                orders.append([atom1, atom2])
                orders.append([atom2, atom1])
                order -= 1
        else:
            continue

    # write pdb file
    with open(pdb_file, "wt") as outp:
        if write_title:
            outp.write("TITLE     {:70s}\n".format(title))
        if remark4:
            outp.write("REMARK   4      COMPLIES WITH FORMAT V. 3.3, 21-NOV-2012\n")
        if credit:
            outp.write("REMARK 888\n" "REMARK 888 WRITTEN BY MDGO (CREATED BY TINGZHENG HOU)\n")
        for n in range(atoms):
            line = pdb_atoms[n].copy()
            if len(line["name"]) == 3:
                line["name"] = " " + line["name"]
            # format pdb
            formatted_line = (
                "{:<6s}{:>5d} {:^4s}{:1s}{:>3s} {:1s}{:>4.4}{:1s}   "
                "{:>8.3f}{:>8.3f}{:>8.3f}{:>6.2f}{:>6.2f}      "
                "{:<4s}{:>2s}{:<2s}"
            ).format(
                line["ATOM"],
                line["serial"],
                line["name"],
                line["altLoc"],
                line["resName"],
                line["chainID"],
                str(line["resSeq"]),
                line["iCode"],
                line["x"],
                line["y"],
                line["z"],
                line["occupancy"],
                line["tempFactor"],
                line["segment"],
                line["element"],
                line["charge"],
            )
            # write
            outp.write(formatted_line + "\n")

        bond_lines = [[i] for i in range(atoms + 1)]
        for i, atom in enumerate(atom1s):
            bond_lines[atom].append(atom2s[i])
        for i, atom in enumerate(atom2s):
            bond_lines[atom].append(atom1s[i])
        for i in range(len(orders)):
            for j, line in enumerate(bond_lines):
                if line[0] == orders[i][0]:
                    bond_lines.insert(j + 1, orders[i])
                    break
        for i in range(1, len(bond_lines)):
            bond_lines[i][1:] = sorted(bond_lines[i][1:])
        for i in range(1, len(bond_lines)):
            outp.write("CONECT" + "".join("{:>5d}".format(num) for num in bond_lines[i]) + "\n")
        outp.write("END\n")  # final 'END'


if __name__ == "__main__":
    """
    litfsi = Molecule.from_file(
        "/Users/th/Downloads/package/packmol-17.163/LiTFSI.xyz"
    )
    mols, box_len = concentration_matcher(1.083,
                                          "litfsi",
                                          ["ec", "emc"],
                                          [0.3, 0.7],
                                          num_salt=166,
                                          mode="w")
    print(mols)
    print(box_len)
    """
    sdf_to_pdb(
        "/Users/th/Downloads/test_mdgo/EC_7303.sdf",
        "/Users/th/Downloads/test_mdgo/test_util.pdb",
    )
