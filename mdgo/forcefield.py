# coding: utf-8
# Copyright (c) Tingzheng Hou.
# Distributed under the terms of the MIT License.

"""
This module implements two core class FFcrawler and MaestroRunner
for generating LAMMPS/GROMACS data files from molecule structure using
the LigParGen web server and Maestro, respectively.

For using the FFcrawler class:

  * Download the ChromeDriver executable that
    matches your Chrome version via https://chromedriver.chromium.org/downloads

For using the MaestroRunner class:

  * Download a free Maestro via https://www.schrodinger.com/freemaestro

  * Install the package and set the environment variable $SCHRODINGER
    (e.g. 'export SCHRODINGER=/opt/schrodinger/suites2020-4', please
    check https://www.schrodinger.com/kb/446296 or
    https://www.schrodinger.com/kb/1842 for details.

"""

from pymatgen.io.lammps.data import LammpsData
from mdgo.util import mass_to_name, ff_parser, sdf_to_pdb
import pubchempy as pcp
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)
from string import Template
from urllib.parse import quote
import time
import os
import re
import shutil
import signal
import subprocess
import numpy as np

from typing import Optional
from typing_extensions import Final

__author__ = "Tingzheng Hou"
__version__ = "1.0"
__maintainer__ = "Tingzheng Hou"
__email__ = "tingzheng_hou@berkeley.edu"
__date__ = "Feb 9, 2021"

MAESTRO: Final[str] = "$SCHRODINGER/maestro -console -nosplash"
FFLD: Final[str] = "$SCHRODINGER/utilities/ffld_server -imae {} -version 14 -print_parameters -out_file {}"
MolecularWeight: Final[str] = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{}/property/MolecularWeight/txt"
MODULE_DIR: Final[str] = os.path.dirname(os.path.abspath(__file__))
DATA_DIR: Final[str] = os.path.join(MODULE_DIR, "data")
DATA_MODELS: Final[dict] = {
    "water": {
        "spc": "water_spc.lmp",
        "spce": "water_spce.lmp",
        "tip3pew": "water_tip3p_ew.lmp",
        "tip4p2005": "water_tip4p_2005.lmp",
        "tip4pew": "water_tip4p_ew.lmp",
    },
    "ion": {
        "aq": ["default"],
        "aqvist": ["default"],
        "jj": ["default"],
        "jensen_jorgensen": ["default"],
        "jc": ["spce", "tip3p", "tip4pew"],
        "joung_cheatham": ["spce", "tip3p", "tip4pew"],
    },
    "alias": {"aq": "aqvist", "jj": "jensen_jorgensen", "jc": "joung_cheatham"},
}


class FFcrawler:
    """
    Web scrapper that can automatically upload structure to the LigParGen
    server and download LAMMPS/GROMACS data file.

    Args:
        write_dir (str): Directory for writing output.
        chromedriver_dir (str): Directory to the ChromeDriver executable.
        headless (bool): Whether to run Chrome in headless (silent) mode.
            Default to True.
        xyz (bool): Whether to write the structure in the LigParGen
            generated data file as .xyz. Default to False. This is useful
            because the order and the name of the atoms could be
            different from the initial input.)
        gromacs (bool): Whether to save GROMACS format data files.
            Default to False.

    Examples:

        >>> lpg = FFcrawler('/path/to/work/dir', '/path/to/chromedriver')
        >>> lpg.data_from_pdb("/path/to/pdb")
    """

    def __init__(self, write_dir, chromedriver_dir=None, headless=True, xyz=False, gromacs=False):
        """Base constructor."""
        self.write_dir = write_dir
        self.xyz = xyz
        self.gromacs = gromacs
        self.preferences = {
            "download.default_directory": write_dir,
            "safebrowsing.enabled": "false",
            "profile.managed_default_content_settings.images": 2,
        }
        self.options = webdriver.ChromeOptions()
        self.options.add_argument(
            'user-agent="Mozilla/5.0 '
            "(Macintosh; Intel Mac OS X 10_14_6) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            'Chrome/88.0.4324.146 Safari/537.36"'
        )
        self.options.add_argument("--window-size=1920,1080")
        if headless:
            self.options.add_argument("--headless")
        self.options.add_experimental_option("prefs", self.preferences)
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        if chromedriver_dir is None:
            self.web = webdriver.Chrome(options=self.options)
        else:
            self.web = webdriver.Chrome(chromedriver_dir, options=self.options)
        self.wait = WebDriverWait(self.web, 10)
        self.web.get("http://zarbi.chem.yale.edu/ligpargen/")
        time.sleep(1)
        print("LigParGen server connected.")

    def quit(self):
        self.web.quit()

    def data_from_pdb(self, pdb_dir):
        """
        Use the LigParGen server to generate a LAMMPS data file from a pdb file.

        Arg:
            pdb_dir (str): The path to the input pdb structure file.

        Write out a LAMMPS data file.
        """
        self.web.get("http://zarbi.chem.yale.edu/ligpargen/")
        time.sleep(1)
        upload = self.web.find_element_by_xpath('//*[@id="exampleMOLFile"]')
        try:
            upload.send_keys(pdb_dir)
            submit = self.web.find_element_by_xpath("/html/body/div[2]/div/div[2]/form/button[1]")
            submit.click()
            pdb_filename = os.path.basename(pdb_dir)
            self.download_data(os.path.splitext(pdb_filename)[0] + ".lmp")
        except TimeoutException:
            print("Timeout! Web server no response for 10s, file download failed!")
        except WebDriverException as e:
            print(e)
        finally:
            self.quit()

    def data_from_smiles(self, smiles_code):
        """
        Use the LigParGen server to generate a LAMMPS data file
        from a SMILES code.

        Arg:
            smiles_code (str): The SMILES code for the LigParGen input.

        Write out a LAMMPS data file.
        """
        self.web.get("http://zarbi.chem.yale.edu/ligpargen/")
        time.sleep(1)
        smile = self.web.find_element_by_xpath('//*[@id="smiles"]')
        smile.send_keys(smiles_code)
        submit = self.web.find_element_by_xpath("/html/body/div[2]/div/div[2]/form/button[1]")
        submit.click()
        try:
            self.download_data(smiles_code + ".lmp")
        except TimeoutException:
            print("Timeout! Web server no response for 10s, file download failed!")
        finally:
            self.quit()

    def download_data(self, lmp_name):
        """
        Helper function that download and write out the LAMMPS data file.

        Arg:
            lmp_name (str): Name of the LAMMPS data file.
        """
        print("Structure info uploaded. Rendering force field...")
        self.wait.until(EC.presence_of_element_located((By.NAME, "go")))
        data_lmp = self.web.find_element_by_xpath("/html/body/div[2]/div[2]/div[1]/div/div[14]/form/input[1]")
        data_lmp.click()
        print("Force field file downloaded.")
        time.sleep(1)
        lmp_file = max(
            [self.write_dir + "/" + f for f in os.listdir(self.write_dir) if os.path.splitext(f)[1] == ".lmp"],
            key=os.path.getctime,
        )
        if self.xyz:
            data_obj = LammpsData.from_file(lmp_file)
            element_id_dict = mass_to_name(data_obj.masses)
            coords = data_obj.atoms[["type", "x", "y", "z"]]
            lines = list()
            lines.append(str(len(coords.index)))
            lines.append("")
            for _, r in coords.iterrows():
                line = element_id_dict.get(int(r["type"])) + " " + " ".join(str(r[loc]) for loc in ["x", "y", "z"])
                lines.append(line)

            with open(os.path.join(self.write_dir, lmp_name + ".xyz"), "w") as xyz_file:
                xyz_file.write("\n".join(lines))
            print(".xyz file saved.")
        if self.gromacs:
            data_gro = self.web.find_element_by_xpath("/html/body/div[2]/div[2]/div[1]/div/div[8]/form/input[1]")
            data_itp = self.web.find_element_by_xpath("/html/body/div[2]/div[2]/div[1]/div/div[9]/form/input[1]")
            data_gro.click()
            data_itp.click()
            time.sleep(1)
            gro_file = max(
                [self.write_dir + "/" + f for f in os.listdir(self.write_dir) if os.path.splitext(f)[1] == ".gro"],
                key=os.path.getctime,
            )
            itp_file = max(
                [self.write_dir + "/" + f for f in os.listdir(self.write_dir) if os.path.splitext(f)[1] == ".itp"],
                key=os.path.getctime,
            )
            shutil.move(gro_file, os.path.join(self.write_dir, lmp_name[:-4] + ".gro"))
            shutil.move(itp_file, os.path.join(self.write_dir, lmp_name[:-4] + ".itp"))
        shutil.move(lmp_file, os.path.join(self.write_dir, lmp_name))
        print("Force field file saved.")


class MaestroRunner:
    """
    Wrapper for the Maestro software that can be used to generate the OPLS_2005
    force field parameter for a molecule.

    Args:
        structure_dir (str): Path to the structure file.
            Supported input format please check
            https://www.schrodinger.com/kb/1278
        working_dir (str): Directory for writing intermediate
            and final output.
        out (str): Force field output form. Default to "lmp",
            the data file for LAMMPS. Other supported formats
            are under development.
        cmd_template (str): String template for input script
            with placeholders. Default to None, i.e., using
            the default template.
        assign_bond (bool): Whether to assign bond to the input
            structure. Default to None.

    Supported input format please check https://www.schrodinger.com/kb/1278

    The OPLS_2005 parameters are described in

    Banks, J.L.; Beard, H.S.; Cao, Y.; Cho, A.E.; Damm, W.; Farid, R.;
    Felts, A.K.; Halgren, T.A.; Mainz, D.T.; Maple, J.R.; Murphy, R.;
    Philipp, D.M.; Repasky, M.P.; Zhang, L.Y.; Berne, B.J.; Friesner, R.A.;
    Gallicchio, E.; Levy. R.M. Integrated Modeling Program, Applied Chemical
    Theory (IMPACT). J. Comp. Chem. 2005, 26, 1752.

    The OPLS_2005 parameters are located in

    $SCHRODINGER/mmshare-vversion/data/f14/

    Examples:

        >>> mr = MaestroRunner('/path/to/structure', '/path/to/working/dir')
        >>> mr.get_mae()
        >>> mr.get_ff()
    """

    template_assignbond = os.path.join(MODULE_DIR, "templates", "mae_cmd_assignbond.txt")

    template_noassignbond = os.path.join(MODULE_DIR, "templates", "mae_cmd_noassignbond.txt")

    def __init__(
        self,
        structure_dir,
        working_dir,
        out="lmp",
        cmd_template=None,
        assign_bond=False,
    ):
        """Base constructor."""
        self.structure = structure_dir
        self.out = out
        self.structure_format = os.path.splitext(self.structure)[1][1:]
        self.name = os.path.splitext(os.path.split(self.structure)[-1])[0]
        print("Input format:", self.structure_format)
        self.work = working_dir
        self.cmd = os.path.join(self.work, "maetro_script.cmd")
        self.mae = os.path.join(self.work, self.name)
        self.ff = os.path.join(self.work, self.name + ".out")
        self.xyz = os.path.join(self.work, self.name + ".xyz")
        if cmd_template:
            self.cmd_template = cmd_template
        else:
            if assign_bond:
                with open(self.template_assignbond, "r") as f:
                    cmd_template = f.read()
                self.cmd_template = cmd_template
            else:
                with open(self.template_noassignbond, "r") as f:
                    cmd_template = f.read()
                self.cmd_template = cmd_template

    def get_mae(self):
        """Write a Maestro command script and execute it to generate a
        maestro file containing all the info needed."""
        with open(self.cmd, "w") as f:
            cmd_template = Template(self.cmd_template)
            cmd_script = cmd_template.substitute(file=self.structure, mae=self.mae, xyz=self.xyz)
            f.write(cmd_script)
        try:
            p = subprocess.Popen(
                f"{MAESTRO} -c {self.cmd}",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
            )

            counter = 0
            while not os.path.isfile(self.mae + ".mae"):
                time.sleep(1)
                counter += 1
                if counter > 30:
                    raise TimeoutError("Failed to generate Maestro file in 30 secs!")
            print("Maestro file generated.")

        except subprocess.CalledProcessError as e:
            raise ValueError("Maestro failed with errorcode {}  and stderr: {}".format(e.returncode, e.stderr))
        finally:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)

    def get_ff(self):
        """Read the Maestro file and save the force field as LAMMPS data file."""
        try:
            subprocess.run(
                FFLD.format(self.mae + ".mae", self.ff),
                check=True,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise ValueError("Maestro failed with errorcode {} and stderr: {}".format(e.returncode, e.stderr))
        print("Maestro force field file generated.")
        if self.out:
            if self.out == "lmp":
                with open(os.path.join(self.work, self.name + "." + self.out), "w") as f:
                    f.write(ff_parser(self.ff, self.xyz))
                print("LAMMPS data file generated.")
            else:
                print("Output format not supported, ff format not converted.")


class PubChemRunner:
    """Wrapper for accessing PubChem data that can be used to retriving compound
    structure and information.

    Args:
        write_dir (str): Directory for writing output.
        chromedriver_dir (str): Directory to the ChromeDriver executable.
        api (bool): Whether to use the PUG REST web interface for accessing
            PubChem data. If None, then all search/download will be
            performed via web browser mode. Default to True.
        headless (bool): Whether to run Chrome in headless (silent) mode.
            Default to False.

    Examples:
        >>> web = PubChemRunner('/path/to/work/dir', '/path/to/chromedriver')
        >>> long_name, short_name = "ethylene carbonate", "PC"
        >>> cid = web.obtain_entry(long_name, short_name)
    """

    def __init__(
        self,
        write_dir,
        chromedriver_dir,
        api=True,
        headless=False,
    ):
        """Base constructor."""
        self.write_dir = write_dir
        self.api = api
        if not self.api:
            self.preferences = {
                "download.default_directory": write_dir,
                "safebrowsing.enabled": "false",
                "profile.managed_default_content_settings.images": 2,
            }
            self.options = webdriver.ChromeOptions()
            self.options.add_argument(
                'user-agent="Mozilla/5.0 '
                "(Macintosh; Intel Mac OS X 10_14_6) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                'Chrome/88.0.4324.146 Safari/537.36"'
            )
            self.options.add_argument("--window-size=1920,1080")
            if headless:
                self.options.add_argument("--headless")
            self.options.add_experimental_option("prefs", self.preferences)
            self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
            self.web = webdriver.Chrome(chromedriver_dir, options=self.options)
            self.wait = WebDriverWait(self.web, 10)
            self.web.get("https://pubchem.ncbi.nlm.nih.gov/")
            time.sleep(1)
            print("PubChem server connected.")

    def quit(self):
        if not self.api:
            self.web.quit()

    def obtain_entry(self, search_text, name, output_format="sdf"):
        """
        Search the PubChem database with a text entry and save the
        structure in desired format.

        Args:
            search_text (str): The text to use as a search query.
            name (str): The short name for the molecule.
            output_format (str): The output format of the structure.
                Default to sdf.
        """
        if self.api:
            return self._obtain_entry_api(search_text, name, output_format=output_format)
        else:
            return self._obtain_entry_web(search_text, name, output_format=output_format)

    def smiles_to_pdb(self, smiles):
        convertor_url = "https://cactus.nci.nih.gov/translate/"
        input_xpath = "/html/body/div/div[2]/div[1]/form/table[1]/tbody/tr[2]/td[1]/input[1]"
        pdb_xpath = "/html/body/div/div[2]/div[1]/form/table[1]/tbody/tr[2]/td[2]/div/input[4]"
        translate_xpath = "/html/body/div/div[2]/div[1]/form/table[2]/tbody/tr/td/input[2]"
        download_xpath = "/html/body/center/b/a"
        self.web.get(convertor_url)
        self.web.find_element_by_xpath(input_xpath).clear()
        self.web.find_element_by_xpath(input_xpath).send_keys(smiles)
        self.web.find_element_by_xpath(pdb_xpath).click()
        self.web.find_element_by_xpath(translate_xpath).click()
        time.sleep(1)
        self.web.find_element_by_xpath(download_xpath).click()
        print("Waiting for downloads.", end="")
        time.sleep(1)
        while any([filename.endswith(".crdownload") for filename in os.listdir(self.write_dir)]):
            time.sleep(1)
            print(".", end="")
        print("\nStructure file saved.")

    def _obtain_entry_web(self, search_text, name, output_format):
        cid = None

        try:
            query = quote(search_text)
            url = "https://pubchem.ncbi.nlm.nih.gov/#query=" + query
            self.web.get(url)
            time.sleep(1)
            best_xpath = '//*[@id="featured-results"]/div/div[2]' "/div/div[1]/div[2]/div[1]/a/span/span"
            relevant_xpath = (
                '//*[@id="collection-results-container"]'
                "/div/div/div[2]/ul/li[1]/div/div/div[1]"
                "/div[2]/div[1]/a/span/span"
            )
            if EC.presence_of_element_located((By.XPATH, best_xpath)):
                match = self.web.find_element_by_xpath(best_xpath)
            else:
                match = self.web.find_element_by_xpath(relevant_xpath)
            match.click()
            # density_locator = '//*[@id="Density"]/div[2]/div[1]/p'
            cid_locator = '//*[@id="main-content"]/div/div/div[1]/' "div[3]/div/table/tbody/tr[1]/td"
            smiles_locator = '//*[@id="Canonical-SMILES"]/div[2]/div[1]/p'
            self.wait.until(EC.presence_of_element_located((By.XPATH, cid_locator)))
            cid = self.web.find_element_by_xpath(cid_locator).text
            smiles = self.web.find_element_by_xpath(smiles_locator).text
            print("Best match found, PubChem ID:", cid)
            if output_format.lower() == "smiles":
                print("SMILES code:", smiles)
            elif output_format.lower() == "pdb":
                self.smiles_to_pdb(smiles)
            else:
                self.web.get(
                    f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/CID/"
                    f"{cid}/record/{output_format.upper()}/?record_type=3d&"
                    f'response_type=save&response_basename={name + "_" + cid}'
                )
                print("Waiting for downloads.", end="")
                time.sleep(1)
                while any([filename.endswith(".crdownload") for filename in os.listdir(self.write_dir)]):
                    time.sleep(1)
                    print(".", end="")
                print("\nStructure file saved.")
        except TimeoutException:
            print("Timeout! Web server no response for 10s, file download failed!")
        except NoSuchElementException:
            print(
                "The download link was not correctly generated, "
                "file download failed!\n"
                "Please try another search text or output format."
            )
        finally:
            self.quit()
        return cid

    def _obtain_entry_api(self, search_text, name, output_format):
        cid = None
        cids = pcp.get_cids(search_text, "name", record_type="3d")
        if len(cids) == 0:
            print("No exact match found, please try the web search")
        else:
            cid = str(cids[0])
            if output_format.lower() == "smiles":
                compound = pcp.Compound.from_cid(int(cid))
                print("SMILES code:", compound.canonical_smiles)
            elif output_format.lower() == "pdb":
                sdf_file = os.path.join(self.write_dir, name + "_" + cid + ".sdf")
                pdb_file = os.path.join(self.write_dir, name + "_" + cid + ".pdb")
                pcp.download("SDF", sdf_file, cid, record_type="3d", overwrite=True)
                sdf_to_pdb(sdf_file, pdb_file)
            else:
                pcp.download(
                    output_format.upper(),
                    os.path.join(self.write_dir, name + "_" + cid + "." + output_format.lower()),
                    cid,
                    record_type="3d",
                    overwrite=True,
                )
        return cid


class Aqueous:
    """
    A class for retreiving water and ion force field parameters.

    Examples:
        Retreive SPC/E water model:
        >>> spce_data = Aqueous.get_water()
        Retreive Li+ ion by Jensen and Jorgensen:
        >>> li_data = Aqueous.get_ion(model="jj", ion="li+")
        Retreive a customized water data file:
        >>> spce_data = Aqueous.get_ion(file_name="path/to/data/file")
    """

    @staticmethod
    def get_water(model: str = "spce") -> Optional[LammpsData]:
        """
        Retrieve water model parameters.

        Args:
            model: Water model to use. Valid choices are "spc", "spce",
                "tip3pew", "tip4p2005", and "tip4pew". (Default: "spce")
        Returns:
            LammpsData: Force field parameters for the chosen water model.
                If you specify an invalid water model, None is returned.
        """
        data_path = DATA_DIR
        signature = "".join(re.split(r"[\W|_]+", model)).lower()
        if DATA_MODELS["water"].get(signature):
            return LammpsData.from_file(os.path.join(data_path, "water", DATA_MODELS["water"].get(signature)))
        else:
            print("Water model not found. Please specify a customized data path or try another water model.\n")
            return None

    @staticmethod
    def get_ion(model: str = "jensen_jorgensen", water: str = "default", ion: str = "li+") -> Optional[LammpsData]:
        """
        Retrieve force field parameters for an ion in water.

        Args:
            model: Force field to use. Valid choices are "aqvist" (or "aq"),
                "jensen_jorgensen" (or "jj"), ""joung_cheatham" (or "jc").
            water: Water model to use. For the jensen_jorgensen and aqvist
                models, the only choice is 'default'. For the joung_cheatham
                model, valid choices are "spce", "tip3p", and "tip4pew".
            ion: Formula of the ion (e.g., "Li+").
        Returns:
            LammpsData: Force field parameters for the chosen water model.
                If the desired combination of force field and water model
                for the given ion is not available, None is returned.
        """
        data_path = DATA_DIR
        alias = DATA_MODELS.get("alias", {})
        signature = model.lower()
        if signature in alias:
            signature = alias.get(model)
        ion_type = ion.capitalize()
        for key in DATA_MODELS["ion"].keys():
            if key.startswith(signature):
                ion_model = DATA_MODELS["ion"].get(key)
                if water in ion_model:
                    if water == "default":
                        file_path = os.path.join(data_path, "ion", key, ion_type + ".lmp")
                    else:
                        file_path = os.path.join(data_path, "ion", key, water, ion_type + ".lmp")
                    if os.path.exists(file_path):
                        return LammpsData.from_file(file_path)
                    else:
                        print("Ion not found. Please try another ion.\n")
                        return None
                else:
                    print("Water model not found. Please try another water model.\n")
                    return None
        print("Ion model not found. Please try another ion model.\n")
        return None


class ChargeWriter:
    """
    A class for write, overwrite, scale charges of a LammpsData object.

    """

    def __init__(self, data, precision=10):
        self.data = data
        self.precision = precision

    def scale(self, factor):
        items = dict()
        items["box"] = self.data.box
        items["masses"] = self.data.masses
        atoms = self.data.atoms.copy(deep=True)
        atoms["q"] = atoms["q"] * factor
        assert np.around(atoms.q.sum(), decimals=self.precision) == np.around(
            self.data.atoms.q.sum() * factor, decimals=self.precision
        )
        digit_count = 0
        for q in atoms["q"]:
            rounded = self.count_significant_figures(q)
            if rounded > digit_count:
                digit_count = rounded
        print("No. of significant figures to output for charges: ", digit_count)
        items["atoms"] = atoms
        items["atom_style"] = self.data.atom_style
        items["velocities"] = self.data.velocities
        items["force_field"] = self.data.force_field
        items["topology"] = self.data.topology
        return LammpsData(**items)

    def count_significant_figures(self, number):
        number = repr(float(number))
        tokens = number.split(".")
        if len(tokens) > 2:
            raise ValueError("Invalid number '{}' only 1 decimal allowed".format(number))
        if len(tokens) == 2:
            decimal_num = tokens[1][: self.precision].rstrip("0")
            return len(decimal_num)
        return 0


if __name__ == "__main__":
    # w = pcp.get_properties('MolecularWeight', 7303,)[0].get("MolecularWeight")
    # print(w)

    """
    pcr = PubChemRunner(
        "/Users/th/Downloads/test_pc/",
        "/Users/th/Downloads/package/chromedriver/chromedriver",
        api=True
    )
    long_name = "ethylene carbonate"
    short_name = "EC"
    cid = pcr.obtain_entry(long_name, short_name, "sdf")


    LPG = FFcrawler(
        "/Users/th/Downloads/test_selenium",
        "/Users/th/Downloads/package/chromedriver/chromedriver",
        xyz=True,
        gromacs=True
    )
    LPG.data_from_pdb("/Users/th/Downloads/test_selenium/EMC.pdb")

    MR = MaestroRunner("/Users/th/Downloads/test_mr/EC.sdf",
                       "/Users/th/Downloads/test_mr")
    MR.get_mae()
    MR.get_ff()

    pcr = PubChemCrawler(
        "/Users/th/Downloads/test_pc/",
        "/Users/th/Downloads/package/chromedriver/chromedriver",
        headless=True
    )
    long_name = "Propylene Carbonate"
    short_name = "PC"
    cid = pcr.obtain_entry(long_name, short_name)
    MR = MaestroRunner(
        f"/Users/th/Downloads/test_pc/{short_name}_{cid}.sdf",
        "/Users/th/Downloads/test_pc")
    MR.get_mae()
    MR.get_ff()

    pcr = PubChemRunner(
        "/Users/th/Downloads/test_pc/",
        "/Users/th/Downloads/package/chromedriver/chromedriver",
        api=True
    )
    long_name = "Ethyl Methyl Carbonate"
    short_name = "EMC"
    cid = pcr.obtain_entry(long_name, short_name)
    MR = MaestroRunner(
        f"/Users/th/Downloads/test_pc/{short_name}_{cid}.sdf",
        "/Users/th/Downloads/test_pc")
    MR.get_mae()
    MR.get_ff()

    pcr = PubChemRunner(
        "/Users/th/Downloads/test_mdgo/",
        "/Users/th/Downloads/package/chromedriver/chromedriver",
        api=True
    )
    long_name = "Ethyl Methyl Carbonate"
    short_name = "EMC"
    cid = pcr.obtain_entry(long_name, short_name, "pdb")
    """
    # lmp_data = Aqueous().get_ion(model="aq", ion="Na+")
    # print(lmp_data.get_string())
    pcr = PubChemRunner(
        "/Users/th/Downloads/test_mdgo/",
        "/Users/th/Downloads/package/chromedriver/chromedriver",
        api=True,
    )
    long_name = "Ethyl Methyl Carbonate"
    short_name = "EMC"
    cid = pcr.obtain_entry(long_name, short_name, "pdb")
