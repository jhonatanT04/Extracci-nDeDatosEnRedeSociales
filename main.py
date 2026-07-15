from selenium.webdriver import chrome
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from time import sleep
import os
from selenium.webdriver.common.by import By


username = os.getenv("FACEBOOK_USER", "juan")
password = os.getenv("FACEBOOK_PASSWORD","contraseña")

def main():
    service = Service(ChromeDriverManager().install())
    option = webdriver.ChromeOptions()
    option.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(service=service, options=option)
    driver.get("https://www.facebook.com/")
    
    
    sleep(20)        
    
    driver.find_element(By.XPATH, '//div[@role="button" and @aria-label="Iniciar sesión"]').click()
    
    sleep(120)
    driver.quit()
if  __name__ == "__main__":
    main()