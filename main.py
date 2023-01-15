from bs4 import BeautifulSoup
import undetected_chromedriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions
import json
from connect import get_start_data, record_data, create_result_file
import time


ua_chrome = " ".join(["Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "AppleWebKit/537.36 (KHTML, like Gecko)",
                      "Chrome/108.0.0.0 Safari/537.36"])
undetected_options = undetected_chromedriver.ChromeOptions()
# undetected_options.add_argument("--headless")
timeout = 50
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
domain = "https://ozon.ru"
errors = 0


def get_model_name(product_name):
    result = list()
    for symbol in product_name:
        if symbol.lower() in ALPHABET or symbol == " " or symbol.isdigit():
            result.append(symbol)
    result = "".join(result)
    return result.strip()


def get_characteristics(characteristic_objects):
    characteristics = dict()
    article = str()
    for characteristic_object in characteristic_objects:
        characteristic_sub_objects = characteristic_object["short"]
        for characteristic in characteristic_sub_objects:
            if characteristic["name"] != "Артикул":
                characteristics[characteristic["name"]] = characteristic["values"][0]["text"]
            else:
                article = characteristic["values"][0]["text"]
    return {"characteristics": characteristics, "article": article}


def get_many_links(browser, wait_driver, url, container_class):
    result = list()
    page = 0
    while True:
        page += 1
        print(f"[INFO] Собираем ссылки на товары со страницы {page}")
        browser.get(url=f"{url}page={page}")
        wait_driver.until(expected_conditions.presence_of_element_located((By.CLASS_NAME, container_class)))
        response = browser.page_source
        bs_object = BeautifulSoup(response, "lxml")
        link_objects = bs_object.find_all(name="a", class_="tile-hover-target")
        if len(link_objects) > 0:
            first_link = domain + link_objects[0]["href"]
            if first_link in result:
                break
            links = [domain + href["href"] for href in link_objects]
            result.extend(links)
        else:
            result = set(result)
            break
    return result


def get_product_link_via_sku(browser, wait_driver, sku):
    browser.get(url=f"https://www.ozon.ru/search/?text={sku}&from_global=true")
    wait_driver.until(expected_conditions.presence_of_element_located((By.CLASS_NAME, "b4")))
    response = browser.page_source
    bs_object = BeautifulSoup(response, "lxml")
    not_found_message = bs_object.find(name="div", attrs={"data-widget": "searchResultsError"})
    if not_found_message is not None:
        result = "Not Found"
    else:
        result = domain + bs_object.find(name="a", class_="tile-hover-target")["href"]
    return result


def get_product_link_via_search_request(browser, wait_driver, search_request):
    browser.get(url=f"https://www.ozon.ru/search/?text={search_request}&from_global=true")
    wait_driver.until(expected_conditions.presence_of_element_located((By.CLASS_NAME, "b4")))
    response = browser.page_source
    bs_object = BeautifulSoup(response, "lxml")
    not_found_message = bs_object.find(name="div", attrs={"data-widget": "searchResultsError"})
    if not_found_message is None:
        result = "Not Found"
    else:
        url = f"https://www.ozon.ru/search/?text={search_request}&from_global=true&"
        result = get_many_links(browser=browser, wait_driver=wait_driver, url=url, container_class="b4")
    return result


def get_product_links_via_brand(browser, wait_driver, brand_url):
    url = f"{brand_url}/?"
    result = get_many_links(browser=browser, wait_driver=wait_driver, url=url, container_class="b4")
    return result


def get_product_links_via_seller(browser, wait_driver, seller_url):
    url = f"{seller_url}&"
    result = get_many_links(browser=browser, wait_driver=wait_driver, url=url, container_class="lo7")
    return result


def get_product_info(browser, product_url, file_name):
    global errors
    try:
        print(f'[INFO] Собираем информацию о товаре {product_url}')
        correct_product_url = product_url.split("/")[4]
        keywords = correct_product_url.split("-")[-1]
        main_api_url = f"https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url=/product/{correct_product_url}&keywords={keywords}"
        characteristics_api_url = f"https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url=/product/{correct_product_url}&keywords={keywords}&layout_container=pdpPage2column&layout_page_index=2"
        browser.get(url=main_api_url)
        response = browser.page_source
        bs_object = BeautifulSoup(response, "lxml")
        json_object = json.loads(bs_object.body.text)["widgetStates"]
        if "webDetailSKU-909751-default-1" not in list(json_object.keys()):
            print("[INFO] Данный товар закончился")
            return "Out of Stock"
        ozon_id = json.loads(json_object["webDetailSKU-909751-default-1"])["sku"]
        product_name = json.loads(json_object["webProductHeading-943796-default-1"])["title"]
        model_name = get_model_name(product_name=product_name)
        prices = json.loads(json_object["webPrice-952422-default-1"])
        purchase_price = prices["price"].replace("₽", "")
        if "originalPrice" in list(prices.keys()):
            full_price = prices["originalPrice"].replace("₽", "")
        else:
            full_price = purchase_price
        if "webOzonAccountPrice-1587460-default-1" in list(json_object.keys()):
            discount_card_price = float(json.loads(json_object["webOzonAccountPrice-1587460-default-1"])["priceText"].replace("при оплате Ozon Картой", "").strip().replace("₽", ""))
        else:
            discount_card_price = purchase_price
        categories = " > ".join([category["text"] for category in json.loads(json_object["breadCrumbs-1477770-default-1"])["breadcrumbs"]])
        images = json.loads(json_object["webGallery-2912937-default-1"])["images"]
        main_image = images[0]["src"]
        main_image_id = main_image.split("/")[-1].split(".")[0]
        additional_images = ", ".join([image["src"].replace("w50", "wc1000") for image in images[1:]])
        rating_object = json.loads(json.loads(bs_object.pre.text)["seo"]["script"][0]["innerHTML"])["aggregateRating"]
        rating = rating_object["ratingValue"]
        amount_reviews = rating_object["reviewCount"]
        browser.get(url=characteristics_api_url)
        response = browser.page_source
        bs_object = BeautifulSoup(response, "lxml")
        characteristics_json_object = json.loads(bs_object.body.text)["widgetStates"]
        description = json.loads(characteristics_json_object["webDescription-2983286-pdpPage2column-2"])["richAnnotation"]
        characteristic_objects = json.loads(characteristics_json_object["webCharacteristics-939965-pdpPage2column-2"])["characteristics"]
        parsed_characteristics = get_characteristics(characteristic_objects=characteristic_objects)
        characteristics = parsed_characteristics["characteristics"]
        article = parsed_characteristics["article"]
        seller = json.loads(characteristics_json_object["webCurrentSeller-1752926-pdpPage2column-2"])["name"]
        record_data(article=article, ozon_id=ozon_id, product_name=product_name, model_name=model_name,
                    purchase_price=purchase_price, full_price=full_price, discount_card_price=discount_card_price,
                    categories=categories, main_image=main_image, additional_images=additional_images,
                    main_image_id=main_image_id, characteristics=characteristics, rating=rating, seller=seller,
                    amount_reviews=amount_reviews, file_name=file_name, description=description)
        errors = 0
    except Exception as ex:
        errors += 1
        if errors < 5:
            print("[ERROR] Ошибка, сервер выдал некорректные данные. Пробуем получить данные еще раз")
            get_product_info(browser, product_url, file_name)
        else:
            print("[ERROR] Не получилось получить данные о товаре за 5 попыток. Продолжаем парсинг")


def init_browser():
    try:
        browser = undetected_chromedriver.Chrome(options=undetected_options)
        return browser
    except Exception as ex:
        print(f"[ERROR] {ex}")
        print("[ERROR] Не удалось подключиться к серверу. Проверьте интернет и попробуйте запустить парсер снова")
        return "Error"


def main():
    print("[INFO] Подготавливаем систему к запуску парсера...")
    browser = init_browser()
    if browser == "Error":
        return browser
    wait_driver = WebDriverWait(driver=browser, timeout=timeout)
    print("[INFO] Собираем данные из исходного файла...")
    positions = get_start_data()
    try:
        browser.get(url="https://ozon.ru/")
        region = input("[INPUT] Выберете регион и введите его название: ")
        if len(positions["sku"]) > 0:
            file_name = create_result_file(criteria="sku", region=region)
            for position in positions["sku"]:
                start_time = time.time()
                print(f"[INFO] Обрабатываем товар по sku: {position['value']}")
                product_url = get_product_link_via_sku(browser=browser, wait_driver=wait_driver, sku=position["value"])
                if product_url != "Not Found":
                    get_product_info(browser=browser, product_url=product_url, file_name=file_name)
                else:
                    print("[INFO] Товар с указанным sku не найден на Ozon")
                stop_time = time.time()
                print(f"[INFO] На парсинг позиции ушло {stop_time - start_time} секунд")

        if len(positions["product_link"]) > 0:
            file_name = create_result_file(criteria="product_link", region=region)
            for position in positions["product_link"]:
                start_time = time.time()
                print(f"[INFO] Обрабатываем товар по ссылке: {position['value']}")
                get_product_info(browser=browser, product_url=position["value"], file_name=file_name)
                stop_time = time.time()
                print(f"[INFO] На парсинг позиции ушло {stop_time - start_time} секунд")

        if len(positions["brand"]) > 0:
            file_name = create_result_file(criteria="brand", region=region)
            for position in positions["brand"]:
                print(f"[INFO] Обрабатываем товары по бренду: {position['value']}")
                product_urls = get_product_links_via_brand(browser=browser, wait_driver=wait_driver, brand_url=position["value"])
                for product_url in product_urls:
                    start_time = time.time()
                    get_product_info(browser=browser, product_url=product_url, file_name=file_name)
                    stop_time = time.time()
                    print(f"[INFO] На парсинг позиции ушло {stop_time - start_time} секунд")

        if len(positions["seller"]) > 0:
            file_name = create_result_file(criteria="seller", region=region)
            for position in positions["seller"]:
                print(f"[INFO] Обрабатываем товары по продавцу: {position['value']}")
                product_urls = get_product_links_via_seller(browser=browser, wait_driver=wait_driver, seller_url=position["value"])
                for product_url in product_urls:
                    start_time = time.time()
                    get_product_info(browser=browser, product_url=product_url, file_name=file_name)
                    stop_time = time.time()
                    print(f"[INFO] На парсинг позиции ушло {stop_time - start_time} секунд")

        if len(positions["search_request"]) > 0:
            file_name = create_result_file(criteria="search_request", region=region)
            for position in positions["search_request"]:
                print(f"[INFO] Обрабатываем товар по поисковому запросу: {position['value']}")
                product_urls = get_product_link_via_search_request(browser=browser, wait_driver=wait_driver, search_request=position["value"])
                for product_url in product_urls:
                    start_time = time.time()
                    get_product_info(browser=browser, product_url=product_url, file_name=file_name)
                    stop_time = time.time()
                    print(f"[INFO] На парсинг позиции ушло {stop_time - start_time} секунд")

    finally:
        browser.close()
        browser.quit()


if __name__ == "__main__":
    main()
