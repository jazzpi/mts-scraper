#!/usr/bin/env python3
"""Command-Line Interface for the scraper."""

import argparse
import sys
import time
import logging


class CLI:
    """Command-Line Interface for the scraper."""

    def __init__(self):
        """Parse and check the arguments."""
        parser = argparse.ArgumentParser(
            description="Scrape the MTS",
            epilog="""If no target is given by any option, it can be selected
            interactively."""
        )
        parser.add_argument("-r", "--rate-limit", default=2.0, type=float,
                            help="""Minimum delay between to requests (default:
                            %(default)s)""")
        parser.add_argument("-c", "--continue", metavar="FILE", dest="cont",
                            help="Continue a previous scraping session")
        parser.add_argument("-p", "--program-id", metavar="ID",
                            help="Scrape a degree program given by ID")
        parser.add_argument("-n", "--program-name", metavar="NAME",
                            help="""Search for a degree program by name and
                            scrape it""")
        parser.add_argument("-d", "--database", metavar="FILE",
                            default="mts.sqlite",
                            help="""SQLite database for output (default:
                            %(default)s)""")
        parser.add_argument("-s", "--save", metavar="FILE",
                            help="""JSON file for saving the scraping progress
                            (default: CURRENT_DATETIME.json)""")
        parser.add_argument("-v", "--verbosity", default="INFO",
                            choices=["DEBUG", "INFO", "WARN", "ERROR",
                                     "CRITICAL"])
        self.args = parser.parse_args()
        self.log_level = getattr(logging, self.args.verbosity)

        logging.basicConfig()
        self._logger = logging.getLogger("CLI")
        self._logger.setLevel(self.log_level)

        if self.args.save is None:
            self.args.save = time.strftime("%Y-%m-%dT%H:%M:%S.json")

        self._check_args()
        self._scraper = None

    def _check_args(self):
        """Check if specified arguments are valid, abort otherwise."""
        if self.args.cont is not None:
            self._logger.warning("--continue is not implemented yet!")
            sys.exit(1)
        if self._count_actions() > 1:
            self._logger.warning(
                "Only one of -c, -p and -n can be specified at once!")
            sys.exit(1)

    def _count_actions(self):
        """Count the number of actions specified (-c, -p or -n)."""
        return (
            (self.args.cont is not None) +
            (self.args.program_id is not None) +
            (self.args.program_name is not None)
        )

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
        for a in area.subareas:
            self._print_area(a, level + 1)

    def main(self, scraper):
        """Execute whatever was specified on the command line.

        After figuring out the program ID, the following steps are
        executed:
        1. Get a list of study areas in the program
        2. Get the list of modules for each study area (TODO)
        3. Save the study areas and list of modules (TODO)
        4. Get the module description for each module (TODO)

        If -c was specified, only step 4 is executed  (i.e. continued)
        """
        self._scraper = scraper
        # TODO: --continue
        if self.args.program_id is None:
            self.args.program_id = self._ask_for_program_id()

        self._logger.info(f"Scraping course with ID {self.args.program_id}")
        areas = self._scraper.get_areas(self.args.program_id)
        print("Areas:")
        for area in areas:
            self._print_area(area)
