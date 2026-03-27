# -*- coding: utf-8 -*-
"""
Created on Fri Mar 20 20:49:10 2026

@author: D0mTu
"""

from time import sleep
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


pd.set_option('display.max_columns', None)

URL = "https://www.booking.com/hotel/pt/roma.en-gb.html#tab-reviews"

driver = webdriver.Firefox()
driver.get(URL)
#sleep(5)

wait = WebDriverWait(driver, 15)

# Espera pelos reviews carregarem
wait.until(
    EC.presence_of_all_elements_located(
        (By.CLASS_NAME, "be659bb4c2")
    )
)

# class="e7addce19e"
# e7addce19e
# Aceitar cookies (se aparecer)
try:
    driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
    sleep(1)
except NoSuchElementException:
    pass

# DataFrame vazio com colunas finais
df = pd.DataFrame(columns=[
    "name", "country", "room_type", "nr_nights", "date",
    "traveler_type", "title_review", "pos_review", "neg_review", "score"
])

def safe_text(elem, xpath: str) -> str:
    try:
        return elem.find_element(By.XPATH, xpath).text.strip()
    except (NoSuchElementException, StaleElementReferenceException):
        return ""

def safe_text_with_click(elem, xpath: str) -> str:
    try:
        localvar_partial = elem.find_element(By.XPATH, xpath).text.strip()
        value = click_expand(elem)
        localvar_complete = elem.find_element(By.XPATH, xpath).text.strip()
        return localvar_complete
    except (NoSuchElementException, StaleElementReferenceException):
        return ""

def safe_score(elem) -> str:
    try:
        txt = elem.find_element(By.XPATH, ".//div[@class='f63b14ab7a dff2e52086']").text
        score = txt.split("\n")[0].strip().replace(",", ".")
        return score
    except (NoSuchElementException, StaleElementReferenceException):
        return ""

def collect_reviews() -> list[dict]:
    rows = []
    cards = driver.find_elements(By.CLASS_NAME, "be659bb4c2")
    for card in cards:
        row = {
            "name": safe_text(card, ".//div[@class='b08850ce41 f546354b44']"),
            "country": safe_text(card, ".//span[@class='d838fb5f41 aea5eccb71']"),
            "room_type": safe_text(card, ".//span[@data-testid='review-room-name']"),
            "nr_nights": safe_text(card, ".//span[@data-testid='review-num-nights']"),
            "date": safe_text(card, ".//span[@data-testid='review-stay-date']"),
            "traveler_type": safe_text(card, ".//span[@data-testid='review-traveler-type']"),
            "title_review": safe_text(card, ".//div[@data-testid='review-title']"),
            "pos_review": safe_text(card, ".//div[@data-testid='review-positive-text']"),
            "neg_review": safe_text(card, ".//div[@data-testid='review-negative-text']"),
            "hotel_response": safe_text_with_click(card, ".//div[@class='a17eaf5728']"),
            "score": safe_score(card),
        }
        rows.append(row)
    return rows

def click_expand(elem) -> bool:
    try:
        btn = elem.find_element(
            By.XPATH,
            ".//button[@class='de576f5064 bef8628e61 e0d8514d4d']"
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        sleep(0.5)
        try:
            btn.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", btn)
        sleep(2)
        return True
    except NoSuchElementException:
        return False

def click_next_page() -> bool:
    print("click_next")

    try:
        btn = driver.find_element(
            By.XPATH,
            # "http://www.w3.org/2000/svg"
            # ".//button[@class='de576f5064 b46cd7aad7 e26a59bb37 c295306d66 c7a901b0e7 aaf9b6e287 fe5e267e55']"
            # ".//button[@class='de576f5064 bd3ea87b7d']"
            ".//button[@class='M 9.91 19.24 c 0.24 0 0.47 -0.09 0.64 -0.27 l 6.06 -6.06 c 0.25 -0.25 0.39 -0.59 0.39 -0.94 s -0.12 -0.69 -0.36 -0.94 l -6.06 -6.06 a 0.909 0.909 0 0 0 -1.3 1.27 l 0.02 0.02 l 5.69 5.72 l -5.72 5.72 c -0.35 0.35 -0.36 0.91 -0.02 1.27 l 0.02 0.02 c 0.17 0.17 0.4 0.27 0.64 0.27']"
# de576f5064 bd3ea87b7d
# path("M 9.91 19.24 c 0.24 0 0.47 -0.09 0.64 -0.27 l 6.06 -6.06 c 0.25 -0.25 0.39 -0.59 0.39 -0.94 s -0.12 -0.69 -0.36 -0.94 l -6.06 -6.06 a 0.909 0.909 0 0 0 -1.3 1.27 l 0.02 0.02 l 5.69 5.72 l -5.72 5.72 c -0.35 0.35 -0.36 0.91 -0.02 1.27 l 0.02 0.02 c 0.17 0.17 0.4 0.27 0.64 0.27")
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        sleep(0.5)
        print("entrou")
        try:
            btn.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", btn)
        sleep(2)
        return True
    except NoSuchElementException:
        print("falhou")
        return False

max_pages = 10
page = 0

try:
    while page < max_pages:
        new_rows = collect_reviews()
        if new_rows:
            df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

        # prints completos (todas as colunas)
        print(f"\nPágina: {page + 1} | Total linhas: {len(df)}")
        # print(df.to_string(index=False))          # garante impressão completa
        print("\nPrimeiras 5 linhas:")
        print(df.head(5).to_string(index=False))

        if not click_next_page():
            break

        page += 1

finally:
    df.to_csv("pestana.csv", index=False)
    print(df.head(5))
    driver.quit()
    print("\nend")