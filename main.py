from scraper_facebook import ScraperFacebook
from scraper_tiktok import ScraperTikTok


def main():
    # scraper = ScraperFacebook()
    scraper = ScraperTikTok()
    scraper.ejecutar()


if __name__ == "__main__":
    main()
