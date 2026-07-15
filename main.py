from scraper_facebook import ScraperFacebook
from scraper_tiktok import ScraperTikTok
from scraper_youtube import ScraperYouTube


def main():
    # scraper = ScraperFacebook()
    # scraper = ScraperTikTok()
    scraper = ScraperYouTube()
    scraper.ejecutar()


if __name__ == "__main__":
    main()
