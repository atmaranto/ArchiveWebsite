from bs4 import BeautifulSoup as SoupBase

import savepagenow
from savepagenow.exceptions import CachedPage, WaybackRuntimeError

import requests

import time
from urllib.parse import urlparse, urljoin
from urllib.request import urlopen, Request

USER_AGENT = "WebsiteArchiver/1.0 (Preserves websites on archive.org)"

def BeautifulSoup(*args, **kwargs):
	return SoupBase(*args, features='lxml', **kwargs)

def try_request(url, retries, log, user_agent):
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
		except Exception as e:
			log("Encountered", repr(e))
			continue
		
		return page
	
	return None

def archivePage(url, log, ignore_523=False, ):
	while True:
		try:
			log(savepagenow.capture(url))
		except CachedPage as e:
			log(url, "already cached")
			break
		except WaybackRuntimeError as e:
			if e.args[0].get("status_code") == 523 and ignore_523:
				log("Error 523 when requesting page.")
				return False
			
			log("Encountered", repr(e))
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

def archiveWebsite(base_url, as_index=False, retries=3, skip_to=None, ignore_523=False, quiet=False, user_agent=USER_AGENT):
	log = (lambda *args, **kwargs: None) if quiet else print
	
	stack = [base_url]
	done = {base_url}
	
	base_url_parse = urlparse(base_url)
	skip_done = skip_to is None
	
	while stack:
		page_url = stack.pop(-1)
		page = try_request(page_url, retries, log, user_agent)
		
		if not page:
			log("Failed to request page after", retries, "tries")
			
			continue
		
		soup = BeautifulSoup(page.read())
		all_tags = soup.find_all("a", href=True)
		
		for i, tag in enumerate(all_tags):
			url = tag["href"]
			parsed = urlparse(url)
			
			if not parsed.netloc or parsed.netloc == base_url_parse.netloc:
				url = urljoin(base_url, url)
				
				if not url in done:
					if not skip_done:
						if parsed.path.endswith(skip_to):
							skip_done = True
						else:
							log("Skipped", url)
					
					if skip_done:
						log(f"({i+1}/{len(all_tags)}): Archiving", url)
						archivePage(url, log, ignore_523=ignore_523)
						log(f"({i+1}/{len(all_tags)}): Archived.")
					
					done.add(url)
					
					if not as_index and parsed.path.startswith(base_url_parse.path):
						log("Added", url, "to stack")
						stack.append(url)
			else:
				log("Did not archive external link:", url)
		log("Completed archiving of URL", page_url)

if __name__ == "__main__":
	from argparse import ArgumentParser
	
	ap = ArgumentParser(description="Archives a website via archive.org")
	
	ap.add_argument("base_url", help="The base URL to request")
	ap.add_argument("--index-page", "-i", action="store_true", help="Uses the base-url as an \"index page\": all links are downloaded, but none are stepped into with any depth")
	ap.add_argument("--retries", "-r", type=int, default=3, help="The number of retries before giving up on a URL")
	ap.add_argument("--skip-to", "-s", default=None, help="A partial end to a path to skip to before we actually start archiving")
	ap.add_argument("--ignore-523", action="store_true", help="Ignore 523 (Origin is Unreachable) errors produced by the Wayback Machine")
	ap.add_argument("--quiet", "-q", action="store_true", help="Suppresses most output")
	
	args = ap.parse_args()
	
	archiveWebsite(args.base_url, as_index=args.index_page, retries=args.retries, skip_to=args.skip_to, ignore_523=args.ignore_523, quiet=args.quiet)