# ArchiveWebsite
 A simple Python script that uses BeautifulSoup and savepagenow to archive entire websites with archive.org.

## Usage

Just run:
```python
python3 main.py <base_url>
```
By default, the crawler will follow and archive every URL that can be reached through HTML anchor (`<a>`)
elements from the base_url that have the base_url as a prefix. For instance, if you want to archive every
page on a website under https://example.com/comic, just use that URL. If you'd prefer to provide an index
page, where every archivable link is present on a single page and no crawling needs to be done directly,
you can use the `-i` flag.

I would recommend viewing
```python
python3 main.py --help
```
for more options.