from lib.clients.base import BaseClient
from lib.utils.kodi_utils import translation
from lib import xmltodict
from lib.utils.settings import get_jackett_timeout
from lib.api.jacktook.kodi import kodilog


class Jackett(BaseClient):
    def __init__(self, host, apikey, notification):
        super().__init__(host, notification)
        self.apikey = apikey
        self.base_url = f"{self.host}/api/v2.0/indexers/all/results/torznab/api?apikey={self.apikey}"

    def search(self, query, mode, season=None, episode=None):
        try:
            urls = []

            if mode == "tv":
                urls = [
                    f"{self.base_url}&t=tvsearch&q={query}&season={season}&ep={episode}" if season and episode else None,
                    f"{self.base_url}&t=tvsearch&q={query}&season={season}" if season else None,
                    f"{self.base_url}&t=tvsearch&q={query}",
                ]
            elif mode == "movies":
                urls = [f"{self.base_url}&q={query}"]
            else:
                urls = [f"{self.base_url}&t=search&q={query}"]

            # Filter out None URLs
            urls = [url for url in urls if url]

            all_results = []
            for url in urls:
                response = self.session.get(url, timeout=get_jackett_timeout())
                
                if response.status_code != 200:
                    self.notification(f"{translation(30229)} ({response.status_code})")
                    continue
                
                results = self.parse_response(response)
                if results:
                    all_results.extend(results)
                    break  # Stop processing once results are found

            # Remove duplicates by 'guid'
            unique_results = self.deduplicate_results(all_results)

            return unique_results
        except Exception as e:
            self.notification(f"{translation(30229)}: {str(e)}")

    def parse_response(self, res):
        res = xmltodict.parse(res.content)
        kodilog("Response JACKETT PREY v3")
        kodilog(res)
        if "item" in res["rss"]["channel"]:
            item = res["rss"]["channel"]["item"]
            results = []
            for i in item if isinstance(item, list) else [item]:
                extract_result(results, i)
            kodilog(results)
            return results

    def deduplicate_results(self, results):
        seen = set()
        unique_results = []
        for result in results:
            guid = result.get("guid", "")
            if guid not in seen:
                seen.add(guid)
                unique_results.append(result)
        return unique_results


def extract_result(results, item):
    attributes = {
        attr["@name"]: attr["@value"] for attr in item.get("torznab:attr", [])
    }
    results.append(
        {
            "title": item.get("title", ""),
            "type": "Torrent",
            "indexer": "Jackett",
            "publishDate": item.get("pubDate", ""),
            "provider": item.get("jackettindexer", {}).get("#text", ""),
            "guid": item.get("guid", ""),
            "downloadUrl": item.get("link", ""),
            "size": item.get("size", ""),
            "magnetUrl": attributes.get("magneturl", ""),
            "seeders": int(attributes.get("seeders", 0)),
            "peers": int(attributes.get("peers", 0)),
            "infoHash": attributes.get("infohash", ""),
        }
    )
