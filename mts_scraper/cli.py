#!/usr/bin/env python3
"""Command-Line Interface for the scraper."""

import argparse
import sys
import logging
import itertools


class CLI:
    """Command-Line Interface for the scraper."""

    def __init__(self):
        """Parse and check the arguments."""
        parser = argparse.ArgumentParser(
            prog="mts_scraper",
            description="Scrape the MTS",
            epilog="""If neither -p nor -n are specified, the degree program
            can be selected interactively.""",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        parser.add_argument("-r", "--rate-limit", default=2.0, type=float,
                            help="""Minimum delay between to requests (default:
                            %(default)s)""")
        parser.add_argument("-p", "--program-id", metavar="ID",
                            help="Scrape a degree program given by ID")
        parser.add_argument("-n", "--program-name", metavar="NAME",
                            help="""Search for a degree program by name and
                            scrape it""")
        parser.add_argument("-d", "--database", metavar="FILE",
                            default="mts.sqlite",
                            help="""SQLite database for output. If the database
                            exists, only modules that are not in it already
                            will be fetched.""")
        parser.add_argument("-f", "--force-refetch", action="store_true",
                            help="""Force a refetch of study areas/module
                            lists, even if they are already stored in the
                            database.""")
        parser.add_argument("-v", "--verbosity", default="INFO",
                            choices=["DEBUG", "INFO", "WARN", "ERROR",
                                     "CRITICAL"])
        self.args = parser.parse_args()
        self.log_level = getattr(logging, self.args.verbosity)

        logging.basicConfig()
        fh = logging.FileHandler("mts.err")
        fh.setLevel(logging.WARN)
        fh.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s:%(message)s"))
        logging.getLogger("").addHandler(fh)
        logging.getLogger(__name__).setLevel(self.log_level)
        self._logger = logging.getLogger(__name__ + ".CLI")

        self._check_args()
        self._scraper = None
        self._db = None

    def _check_args(self):
        """Check if specified arguments are valid, abort otherwise."""
        if self.args.program_id is not None and \
           self.args.program_name is not None:
            self._logger.warning(
                "Only one of -p and -n can be specified!")
            sys.exit(1)

    def _ask_for_program_id(self):
        """Figure out what program ID we should scrape.

        Returns the ID.
        """
        if self.args.program_name is None:
            self.args.program_name = self._ask_for_program_name()

        programs = self._scraper.find_programs(self.args.program_name)
        if len(programs) == 1:
            p = programs[0]
            ans = input(
                f"Scrape `{p['name']}' ({p['degree']}, ID: {p['id']})? [Y/n] "
            )
            if ans == "n":
                self._logger.error("Aborting.")
                sys.exit(1)
            return p['id']

        print("Found the following degree programs for "
              f"{self.args.program_name}:")
        for i, p in enumerate(programs):
            print(f"  [{i+1}]\t`{p['name']}', ({p['degree']}, ID: {p['id']})")
        ans = input(f"Select a program from the list [1-{len(programs)},Q] ")
        try:
            n = int(ans)
            return programs[n-1]['id']
        except (ValueError, IndexError):
            self._logger.error("Aborting.")
            sys.exit(1)

    def _ask_for_program_name(self):
        """Figure out what program we should scrape (by name).

        Returns the name.
        """
        ans = input("Enter program name (leave empty to abort): ")
        if not ans:
            self._logger.error("Aborting.")
            sys.exit(1)
        return ans

    def _print_area(self, area, level=0):
        """Print an area and all of its subareas."""
        print("  " * level + area.title)
        for m in area.modules:
            print("  " * level + " -> " + str(m))
        for a in area.subareas:
            self._print_area(a, level + 1)

    def _fetch_areas_and_modules(self):
        areas = self._scraper.get_areas()
        modules = set()
        for area in areas:
            area.fetch_modules(self._scraper)
            area_modules = itertools.chain.from_iterable(
                (a.modules for a in area.flatten())
            )
            for m in area_modules:
                modules.add(m)

        print("Areas:")
        for area in areas:
            self._print_area(area)
            self._db.save_area(area, self.args.program_id)
        found_modules = len(modules)
        modules -= set(self._db.get_modules(True))
        self._logger.debug("Saving %d modules (of %d modules in program)",
                           len(modules), found_modules)
        for module in modules:
            self._db.save_module(module)

    def main(self, scraper, db):
        """Execute whatever was specified on the command line.

        After figuring out the program ID, the following steps are
        executed:
        1. Get a list of study areas in the program
        2. Get the list of modules for each study area
        3. Save the study areas and list of modules
        4. Get the module description for each module (TODO)

        If -c was specified, only step 4 is executed  (i.e. continued)
        """
        self._scraper = scraper
        self._db = db
        if self.args.program_id is None:
            self.args.program_id = self._ask_for_program_id()

        self._logger.info(f"Scraping program with ID {self.args.program_id}")

        if self._db.program_exists(self.args.program_id):
            self._logger.info(
                "Program already exists in DB, continuing previous session.")
            title, degree = self._db.get_program_info(self.args.program_id)
        else:
            self._logger.info(
                "Program does not exist in DB, fetching study areas/modules.")
            self._scraper.load_program(self.args.program_id)
            title, degree = self._scraper.get_program_info()
            self._fetch_areas_and_modules()
            self._db.save_program(self.args.program_id, title, degree)

        for module in self._db.unfetched_modules(self.args.program_id):
            self._logger.info("Fetching details for `%s' (ID=%d, V=%d)",
                              module[2], module[0], module[1])
            print(repr(self._scraper.get_module_details(module[0], module[1])))
