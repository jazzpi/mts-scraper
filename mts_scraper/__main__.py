#!/usr/bin/env python3

from .scraper import Scraper
from .cli import CLI


def main():
    cli = CLI()
    scraper = Scraper(throttle_delay=cli.args.rate_limit)
    programs = scraper.find_programs(cli.args.program_name)
    for p in programs:
        print(f"{p['degree']} in {p['name']} -> {p['id']}")


if __name__ == "__main__":
    main()
