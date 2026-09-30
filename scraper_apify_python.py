"""
Lance des actors Apify directement depuis Python (au lieu de l'interface web).
Nécessite : pip install apify-client
Ton token Apify : console Apify -> Settings -> Integrations
"""

from apify_client import ApifyClient
APIFY_TOKEN = os.environ.get( "APIFY_API_TOKEN","")
client = ApifyClient(APIFY_TOKEN)


def scraper_instagram_posts(profile_urls: list[str], max_posts: int = 20) -> list[dict]:
    """Scrape les posts de plusieurs comptes Instagram en une seule fois."""
    run_input = {
        "directUrls": profile_urls,
        "resultsType": "posts",
        "resultsLimit": max_posts,
    }
    run = client.actor("apify/instagram-scraper").call(run_input=run_input)
    return list(client.dataset(run.default_dataset_id).iterate_items())


def scraper_facebook_posts(page_urls: list[str], max_posts: int = 20) -> list[dict]:
    """Scrape les posts de plusieurs pages Facebook en une seule fois."""
    run_input = {
        "startUrls": [{"url": u} for u in page_urls],
        "resultsLimit": max_posts,
    }
    run = client.actor("apify/facebook-pages-scraper").call(run_input=run_input)
    return list(client.dataset(run.default_dataset_id).iterate_items())


if __name__ == "__main__":
    # Exemple : scrape 2 agences média en une seule commande
    comptes_insta = [

"https://www.instagram.com/tunisia/?hl=fr",
"https://www.instagram.com/tunisia/?hl=fr",
"https://www.instagram.com/mediahouseldn/?hl=fr",
"https://www.instagram.com/lba.media/",
"https://www.instagram.com/wild.vision.production/",
"https://www.instagram.com/tunisiesms/",
"https://www.instagram.com/reel/DMIpfHVoa8M/",
"https://www.instagram.com/mofiprod/",
"https://www.instagram.com/reel/DQugMFTjmwO/",
"https://www.instagram.com/outsourcia_tunisie/?hl=fr",
"https://www.instagram.com/declicagency/?hl=fr",
"https://www.instagram.com/216mediaservices/",
"https://www.instagram.com/agencewepub/",
"https://www.instagram.com/carwaystunisie/?hl=fr",
"https://www.instagram.com/digitaltunis/",
"https://www.instagram.com/reel/DRhJpV6DLiK/",
"https://www.instagram.com/recraftai/?hl=fr",
"https://www.instagram.com/code_nd_craft/",
"https://www.instagram.com/guiga.marketing/",
"https://www.instagram.com/p/C6Dl2CyiSDB/?hl=am-et",
"https://www.instagram.com/tunisiaexport/",
"https://www.instagram.com/echocom_tunisie/",
"https://www.instagram.com/emmakprod/",
"https://www.instagram.com/splash_distribution_/",
"https://www.instagram.com/tunisia/?hl=fr",
"https://www.instagram.com/p/DXEd8XKiLLE/",
"https://www.instagram.com/tV/?hl=en",
"https://www.instagram.com/p/DTQQ9cvl22o/",
"https://www.instagram.com/ste_visioad/",
"https://www.instagram.com/msit_digital/",
"https://www.instagram.com/laboratoiressvrtunisie/?hl=fr",
"https://www.instagram.com/graphic_art_agency/",
"https://www.instagram.com/jawhara_pub__events/",
"https://www.instagram.com/association_almadanya/",
"https://www.instagram.com/bilsimaging/",
"https://www.instagram.com/les_editions_iris/",
"https://www.instagram.com/urban___communication/",
"https://www.instagram.com/hellotunisia/",
"https://www.instagram.com/p/C9UlRxboMwf/",
"https://www.instagram.com/forzaess/",
"https://www.instagram.com/reel/DPT3GtyiAqe/",
"https://www.instagram.com/reel/DZvKRT7igJ-/",
"https://www-fallback.instagram.com/globalprintpackaging/",
"https://www.instagram.com/lesaprod/",
"https://www.instagram.com/touchmediama/",
"https://www.instagram.com/yacine__ramedi/",
"https://www.instagram.com/cillium.fm/",
"https://www.instagram.com/tunisie.design/",
"https://www.instagram.com/globale_media/"

    ]
    posts = scraper_instagram_posts(comptes_insta, max_posts=15)
    print(f"{len(posts)} posts récupérés.")
