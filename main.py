from consolidar import consolidar
from scraper_facebook import ScraperFacebook
from scraper_tiktok import ScraperTikTok
from scraper_youtube import ScraperYouTube


def main():
    ScraperFacebook().ejecutar()
    ScraperTikTok().ejecutar()
    ScraperYouTube().ejecutar()

    consolidar()


if __name__ == "__main__":
    main()
