#!/usr/bin/env python3

import argparse
import sys
import time


class CLI:
    def __init__(self):
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
        self.args = parser.parse_args()

        if self.args.cont is not None:
            print("--continue is not implemented yet!", file=sys.stderr)
            sys.exit(1)
        if self.args.program_id is not None:
            print("--program-id is not implemented yet!", file=sys.stderr)
            sys.exit(1)
        if self.args.save is None:
            self.args.save = time.strftime("%Y-%m-%dT%H:%M:%S.json")
