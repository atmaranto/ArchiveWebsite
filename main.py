from bs4 import BeautifulSoup as SoupBase

import savepagenow
from savepagenow.exceptions import CachedPage, WaybackRuntimeError

import requests

import time, re
from urllib.parse import urlparse, urljoin
from urllib.request import urlopen, Request

USER_AGENT = "WebsiteArchiver/1.0 (Preserves websites on archive.org)"

def BeautifulSoup(*args, **kwargs):
	return SoupBase(*args, features='lxml', **kwargs)

def try_request_soup(url, retries, log, user_agent):
	for i in range(retries):
		if i > 0:
			log("Retrying in:")
			for j in range(3, 0, -1):
				log(j)
				time.sleep(1)
			log("Retrying (" + str(retries - i - 1) + " left)")
		
		log("Requesting", url)
		
		try:
			page = urlopen(Request(url, headers={"User-Agent": user_agent}))
			
			if not page.headers.get("Content-Type", "text/html").strip().lower().startswith("text/"):
				return False
			
			soup = BeautifulSoup(page.read())
		except Exception as e:
			log("Encountered", repr(e))
			continue
		
		return soup
	
	return None

def archivePage(url, log, ignore=[], retries=3):
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
def archiveWebsite(base_url, as_index=False, retries=3, skip_to=None, ignore=[], quiet=False, verbose=False, dry_run=False, schemes=DEFUALT_SCHEMES, user_agent=USER_AGENT):
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
				
				if url not in done:
					if not skip_done:
						if parsed.path.strip("/").endswith(skip_to.strip("/")):
							skip_done = True
						else:
							log("Skipped", url)
					
					if skip_done:
						log(f"({i+1}/{len(all_tags)}): Archiving", url)
						
						if not dry_run:
							success = archivePage(url, log, ignore=ignore, retries=retries)
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
		log("Completed archiving of URL", page_url)

if __name__ == "__main__":
	from argparse import ArgumentParser
	
	ap = ArgumentParser(description="Archives a website via archive.org")
	
	ap.add_argument("base_url", help="The base URL to request")
	ap.add_argument("--index-page", "-i", action="store_true", help="Uses the base-url as an \"index page\": all links are downloaded, but none are stepped into with any depth")
	ap.add_argument("--retries", "-r", type=int, default=3, help="The number of retries before giving up on a URL")
	ap.add_argument("--skip-to", "-s", default=None, help="A partial end to a path to skip to before we actually start archiving")
	ap.add_argument("--ignore", "-I", type=str, default="", help="Comma-separated list of HTTP error codes to ignore from the Wayback Machine. Specifying \"any\" will ignore all error codes from the Wayback Machine.")
	ap.add_argument("--quiet", "-q", action="store_true", help="Suppresses most output")
	ap.add_argument("--verbose", "-v", action="store_true", help="Enables verbose output")
	ap.add_argument("--dry-run", "-d", action="store_true", help="Doesn't actually archive the URLs")
	
	args = ap.parse_args()
	
	ignore = args.ignore.strip()
	
	if ignore != "any":
		assert not ignore or re.match(r"^\d+(,\d+)*$", ignore), "If specified, --ignore lists must be comma-separated values of integer error codes."
		ignore = [int(code) for code in ignore.split(",")] if ignore else []
	
	archiveWebsite(args.base_url, as_index=args.index_page, retries=args.retries, skip_to=args.skip_to, ignore=ignore, quiet=args.quiet, verbose=args.verbose, dry_run=args.dry_run)