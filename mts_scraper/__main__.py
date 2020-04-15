#!/usr/bin/env python3

from .scraper import Scraper
from .cli import CLI


def main():
    cli = CLI()
    scraper = Scraper(throttle_delay=cli.args.rate_limit)
    cli.main(scraper)


if __name__ == "__main__":
    main()
