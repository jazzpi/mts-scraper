#!/usr/bin/env python3

from .scraper import Scraper
from .cli import CLI
from .db import Database


def main():
    cli = CLI()
    scraper = Scraper(log_level=cli.log_level,
                      throttle_delay=cli.args.rate_limit)
    db = Database(cli.args.database, log_level=cli.log_level)
    cli.main(scraper, db)


if __name__ == "__main__":
    main()
