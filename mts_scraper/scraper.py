#!/usr/bin/env python3
"""Selenium-based scraper for MTS."""

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class Scraper:
    """Selenium-based scraper for MTS."""

    MTS_BASE = "https://moseskonto.tu-berlin.de/moses/modultransfersystem/"
    PROGRAM_SEARCH = MTS_BASE + "studiengaenge/suchen.html"
    PROGRAM_SEARCH_FORM_ID = "j_idt99"

    def __init__(self, throttle_delay=2.0):
        """Create the Selenium WebDriver."""
        option = webdriver.ChromeOptions()
        option.add_argument("--incognito")
        self.browser = webdriver.Chrome(options=option)
        self._last_request = 0
        self._throttle_delay = throttle_delay

    def __del__(self):
        """Close the Selenium WebDriver."""
        self.browser.close()

    def _throttle_request(self):
        """Check rate limit and (potentially) wait."""
        print(f"{time.time()}, {self._last_request}")
        diff = self._throttle_delay - (time.time() - self._last_request)
        while diff > 0:
            time.sleep(diff)
            diff = self._throttle_delay - (time.time() - self._last_request)
        self._last_request = time.time()

    def _load_page(self, url, wait_for, timeout=10.0):
        """Load a page and wait for it to load.

        url -- URL of page to load
        wait_for -- See _wait_for()
        timeout -- See _wait_for()
        """
        self._throttle_request()
        self.browser.get(url)
        self._wait_for(wait_for, timeout)

    def _wait_for(self, wait_for, timeout=10.0):
        """Wait for a condition.

        wait_for -- A tuple defining the condition to wait for.
                    The first element defines the type of condition, the
                    second defines the condition itself.
                    Possible types:
                    "cond" -> Condition from support.expected_conditions
                    "css_vs" -> CSS selector of an element that should
                                be visible
        timeout -- Maximum time to wait for the condition. If this is
                   exceeded, a TimeoutException is raised.
        """
        if wait_for[0] == "cond":
            until = wait_for[1]
        elif wait_for[0] == "css_vis":
            print("Waiting for CSS selector " + wait_for[1])
            until = EC.visibility_of_element_located((
                By.CSS_SELECTOR, wait_for[1]
            ))
        else:
            raise RuntimeError("Unknown wait-for " + repr(wait_for))

        WebDriverWait(self.browser, timeout).until(until)

    def find_programs(self, query):
        """Find degree programs.

        Returns a list of programs. Each program is a dict of the form
        {
          "name": PROGRAM_NAME,
          "degree": DEGREE (MSc/BSc etc.),
          "id": PROGRAM_ID,
        }
        """
        self._load_page(
            self.PROGRAM_SEARCH,
            ("css_vis", f"#{self.PROGRAM_SEARCH_FORM_ID} a.btn.btn-default")
        )

        search_box = self.browser.find_element_by_css_selector(
            f"#{self.PROGRAM_SEARCH_FORM_ID} input[type=text]")

        self._throttle_request()
        search_box.send_keys(query + Keys.ENTER)
        self._wait_for(
            ("css_vis", f"#{self.PROGRAM_SEARCH_FORM_ID} table.table")
        )

        table = self.browser.find_element_by_css_selector(
            f"#{self.PROGRAM_SEARCH_FORM_ID} table.table")
        programs = []
        rows = table.find_elements_by_tag_name("tr")[1:]  # Skip header row
        for row in rows:
            cells = row.find_elements_by_tag_name("td")
            link = cells[3].find_element_by_tag_name("a")
            pid = self._extract_combined_id(link.get_attribute("href"))
            programs.append({
                "name": cells[0].text,
                "degree": cells[1].text,
                "id": pid,
            })

        return programs

    @classmethod
    def _extract_combined_id(self, href):
        """Extract the ID from an `anzeigenKombiniert.html` link."""
        return int(href.rsplit("=", 1)[1])
