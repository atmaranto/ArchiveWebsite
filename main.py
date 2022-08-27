"""

MIT License

Copyright (c) 2022 Anthony Maranto

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""


from bs4 import BeautifulSoup as _BeautifulSoup

import savepagenow
from savepagenow.exceptions import CachedPage, WaybackRuntimeError

import requests

import time, re, json, datetime
from urllib.parse import urlparse, urljoin, quote

USER_AGENT = "WebsiteArchiver/1.0 (Preserves websites on archive.org)"

def BeautifulSoup(*args, **kwargs):
    """"BeautifulSoup proxy that uses lxml as the default parser"""
    return _BeautifulSoup(*args, features='lxml', **kwargs)

def check_archived(url, log=print, retries=3):
    while True:
        retries -= 1
        if retries < 0:
            log("Ran out of retries; assuming unarchived by default")
            return False
        
        try:
            response = requests.get("https://archive.org/wayback/available?url=" + quote(url))
            
            data = json.loads(response.text)
            if isinstance(data, dict):
                snapshots = data.get("archived_snapshots")
                if isinstance(snapshots, dict) and isinstance(snapshots.get("closest"), dict) and str(snapshots["closest"].get("timestamp")).isdigit():
                    timestamp = snapshots["closest"]["timestamp"]
                    return datetime.datetime.strptime(timestamp, "%Y%m%d%H%M%S") + (datetime.datetime.now() - datetime.datetime.utcnow())
            return False
        except Exception as e:
            log(f"Archive check request encountered exception {e}. Sleeping for 5 seconds")
            time.sleep(5)

def try_request_soup(url, retries, log, user_agent):
    """Tries to request a page, returning a BeautifulSoup object on a success and None on a failure"""
    for i in range(retries):
        if i > 0:
            log("Retrying in:")
            for j in range(3, 0, -1):
                log(j)
                time.sleep(1)
            log("Retrying (" + str(retries - i - 1) + " left)")
        
        log("Requesting", url)
        
        try:
            page = requests.get(url, headers={"User-Agent": user_agent})
            
            if not page.headers.get("Content-Type", "text/html").strip().lower().startswith("text/"):
                return False
            
            soup = BeautifulSoup(page.text)
        except Exception as e:
            log("Encountered", repr(e))
            continue
        
        return soup
    
    return None

def archive_page(url, log, ignore=[], retries=3):
    """Attempts to archive the given page using savepagenow, optionally attempting to retry the archive"""
    tries = 0
    while tries < retries:
        try:
            log(savepagenow.capture(url))
        except CachedPage as e:
            log(url, "already cached")
            break
        except WaybackRuntimeError as e:
            status_code = e.args[0].get("status_code")
            if ignore == "any" or status_code in ignore:
                log(f"Error {status_code} when requesting page.")
                return False
            
            tries += 1
            log(f"(Try {tries}/{retries}) Encountered", repr(e))
            
            if tries >= retries:
                return False
            
            log("Sleeping for 60 seconds")
            time.sleep(60)
        except requests.exceptions.ConnectionError as e:
            log("Request timed out. Sleeping for 30 seconds.")
            time.sleep(30)
        except requests.exceptions.TooManyRedirects as e:
            log("Exceeded 30 redirects. Sleeping for 2 minutes.")
            time.sleep(120)
        else:
            break
    
    return True

DEFUALT_SCHEMES = ("http", "https", "ftp")
def main(base_url, as_index=False, retries=3, skip_to=None, ignore=[], quiet=False, verbose=False, dry_run=False, ignore_query=False, rearchive=False, schemes=DEFUALT_SCHEMES, user_agent=USER_AGENT):
    """Attempts to archive the website using the settings provided"""
    log = (lambda *args, **kwargs: None) if quiet else print
    
    stack = [base_url]
    done = {base_url}
    
    base_url_parse = urlparse(base_url)
    skip_done = skip_to is None
    
    while stack:
        page_url = stack.pop(-1)
        soup = try_request_soup(page_url, retries, log, user_agent)
        
        if not soup:
            if soup is None: log("Failed to request page after", retries, "tries")
            elif soup is False: log("Resultant page was not text/html")
            
            continue
        
        all_tags = soup.find_all("a", href=True)
        
        for i, tag in enumerate(all_tags):
            url = urljoin(base_url, tag["href"])
            parsed = urlparse(url)
            
            if (not parsed.netloc or parsed.netloc == base_url_parse.netloc) and (not parsed.scheme or parsed.scheme in schemes) and \
               (not base_url.lower().startswith("tel:")):
                url = url.split("#", 1)[0]
                if ignore_query: url = url.split("?", 1)[0]
                
                if url not in done:
                    if not skip_done:
                        if parsed.path.strip("/").endswith(skip_to.strip("/")):
                            skip_done = True
                        else:
                            log("Skipped", url)
                    
                    should_archive = rearchive
                    if not should_archive:
                        archived_time = check_archived(url, log=log, retries=retries)
                        if archived_time:
                            log(url, "archived on", archived_time.strftime("%m-%d-%Y %I:%M:%S %p%Z") + ". Skipping.")
                            should_archive = False
                    
                    if skip_done and should_archive:
                        log(f"({i+1}/{len(all_tags)}): Archiving", url)
                        
                        if not dry_run:
                            success = archive_page(url, log, ignore=ignore, retries=retries)
                        else:
                            success = True
                        
                        if success:
                            log(f"({i+1}/{len(all_tags)}): Archived.")
                        else:
                            log(f"({i+1}/{len(all_tags)}): Failed to archive.")
                    
                    done.add(url)
                    
                    if not as_index and parsed.path.startswith(base_url_parse.path):
                        log("Added", url, "to stack")
                        stack.append(url)
                    else:
                        if verbose:
                            log("Did not add", url, "to stack")
            #else:
                #log("Did not archive external link:", url)
        log(f"({len(all_tags)}/{len(all_tags)}): Completed archiving of URL", page_url)

if __name__ == "__main__":
    from argparse import ArgumentParser
    
    ap = ArgumentParser(description="Archives a website via archive.org")
    
    ap.add_argument("base_url", help="The base URL to request")
    ap.add_argument("--index-page", "-i", action="store_true", help="Uses the base-url as an \"index page\": all links are downloaded, but none are stepped into with any depth")
    ap.add_argument("--retries", "-r", type=int, default=3, help="The number of retries before giving up on a URL")
    ap.add_argument("--skip-to", "-s", default=None, help="A partial end to a path to skip to before we actually start archiving")
    ap.add_argument("--ignore", "-I", type=str, default="", help="Comma-separated list of HTTP error codes to ignore from the Wayback Machine. Specifying \"any\" will ignore all error codes from the Wayback Machine.")
    ap.add_argument("--ignore-query", "-Q", action="store_true", help="Ignores the query part of the URL.")
    ap.add_argument("--quiet", "-q", action="store_true", help="Suppresses most output")
    ap.add_argument("--verbose", "-v", action="store_true", help="Enables verbose output")
    ap.add_argument("--dry-run", "-d", action="store_true", help="Doesn't actually archive the URLs")
    ap.add_argument("--rearchive", "-R", action="store_true", help="Doesn't check if the Wayback Machine already has the page (may rearchive significantly)")
    
    args = ap.parse_args()
    
    ignore = args.ignore.strip()
    
    if ignore != "any":
        assert not ignore or re.match(r"^\d+(,\d+)*$", ignore), "If specified, --ignore lists must be comma-separated values of integer error codes."
        ignore = [int(code) for code in ignore.split(",")] if ignore else []
    
    main(args.base_url, as_index=args.index_page, retries=args.retries, skip_to=args.skip_to, ignore=ignore, quiet=args.quiet, verbose=args.verbose, dry_run=args.dry_run, ignore_query=args.ignore_query, rearchive=args.rearchive)