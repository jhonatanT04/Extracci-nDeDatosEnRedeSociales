from src.consolidar import consolidar
from src.scraper_facebook import ScraperFacebook
from src.scraper_tiktok import ScraperTikTok
from src.scraper_youtube import ScraperYouTube


def main():
    ScraperFacebook().ejecutar()
    # ScraperTikTok().ejecutar()
    # ScraperYouTube().ejecutar()

    # consolidar()


if __name__ == "__main__":
    main()
