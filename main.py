import re
from bs4 import BeautifulSoup
import undetected_chromedriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions
import json
from connect import get_start_data, record_data, create_result_file, record_no_data
import time


ua_chrome = " ".join(["Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "AppleWebKit/537.36 (KHTML, like Gecko)",
                      "Chrome/108.0.0.0 Safari/537.36"])
undetected_options = undetected_chromedriver.ChromeOptions()
timeout = 50
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
domain = "https://ozon.ru"
errors = 0


def clear_number(number):
    result = str()
    for symbol in number:
        if symbol.isdigit():
            result = f"{result}{symbol}"
    result = int(result)
    return result


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


def get_product_link_via_search_request(browser, search_request):
    result = list()
    search_url = f"https://www.ozon.ru/search/?text={search_request}&from_global=true"
    browser.get(url=search_url)
    response = browser.page_source
    bs_object = BeautifulSoup(response, "lxml")
    not_found_message = "По вашему запросу товаров сейчас нет" in bs_object.find(name="div", id=re.compile("state-fulltextResultsHeader"))["data-state"]
    if not_found_message:
        result = "Not Found"
    else:
        page = 1
        print(f"[INFO] Собираем ссылки на товары со страницы {page}")
        json_string = bs_object.find(name="div", id=re.compile("state-searchResultsV2"))["data-state"].replace("&quot;", '"')
        json_object = json.loads(json_string)
        result.extend([domain + link["action"]["link"] for link in json_object["items"]])
        while True:
            page += 1
            print(f"[INFO] Собираем ссылки на товары со страницы {page}")
            url = f"{search_url}&page={page}"
            browser.get(url=url)
            response = browser.page_source
            bs_object = BeautifulSoup(response, "lxml")
            not_found_message = "По вашему запросу товаров сейчас нет" in bs_object.find(name="div", id=re.compile("state-fulltextResultsHeader"))["data-state"]
            if not_found_message:
                break
            json_string = bs_object.find(name="div", id=re.compile("state-searchResultsV2"))["data-state"].replace("&quot;", '"')
            json_object = json.loads(json_string)
            if json_object["items"] is None:
                break
            else:
                result.extend([domain + link["action"]["link"] for link in json_object["items"]])
    return list(set(result))


def get_product_links_via_brand(browser, brand_url):
    result = list()
    browser.get(url=brand_url)
    response = browser.page_source
    bs_object = BeautifulSoup(response, "lxml")
    page = 1
    print(f"[INFO] Собираем ссылки на товары со страницы {page}")
    json_string = bs_object.find(name="div", id=re.compile("state-searchResultsV2"))["data-state"].replace("&quot;", '"')
    json_object = json.loads(json_string)
    result.extend([domain + link["action"]["link"] for link in json_object["items"]])
    while True:
        page += 1
        print(f"[INFO] Собираем ссылки на товары со страницы {page}")
        browser.get(url=f"{brand_url}/?page={page}")
        response = browser.page_source
        bs_object = BeautifulSoup(response, "lxml")
        json_string = bs_object.find(name="div", id=re.compile("state-searchResultsV2"))["data-state"].replace("&quot;", '"')
        json_object = json.loads(json_string)
        if json_object["items"] is None:
            break
        else:
            result.extend([domain + link["action"]["link"] for link in json_object["items"]])
    return list(set(result))


def get_product_links_via_seller(browser, seller_url):
    result = list()
    browser.get(url=seller_url)
    response = browser.page_source
    bs_object = BeautifulSoup(response, "lxml")
    page = 1
    print(f"[INFO] Собираем ссылки на товары со страницы {page}")
    json_string = bs_object.find(name="div", id=re.compile("state-searchResultsV2"))["data-state"].replace("&quot;", '"')
    json_object = json.loads(json_string)
    result.extend([domain + link["action"]["link"] for link in json_object["items"]])
    while True:
        page += 1
        print(f"[INFO] Собираем ссылки на товары со страницы {page}")
        browser.get(url=f"{seller_url}/?page={page}")
        response = browser.page_source
        bs_object = BeautifulSoup(response, "lxml")
        json_string = bs_object.find(name="div", id=re.compile("state-searchResultsV2"))["data-state"].replace("&quot;", '"')
        json_object = json.loads(json_string)
        if json_object["items"] is None:
            break
        else:
            result.extend([domain + link["action"]["link"] for link in json_object["items"]])
    return list(set(result))


def get_product_info(browser, product_url, file_name, search_request=None):
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

        out_of_stock = True
        for key in json_object.keys():
            if "webDetailSKU" in key:
                out_of_stock = False
                break
        if out_of_stock:
            print("[INFO] Данный товар закончился")
            record_no_data(ozon_id="ERROR", file_name=file_name, message="Данный товар закончился")
            return "out_of_stock"

        ozon_id, product_name, model_name, purchase_price, discount_card_price, full_price = "", "", "", "", "", ""
        categories, main_image, additional_images, main_image_id, rating, amount_reviews = "", "", "", "", "", ""

        for key in json_object.keys():
            if (ozon_id != "" and product_name != "" and model_name != "" and purchase_price != "" and
               discount_card_price != "" and full_price != "" and categories != "" and main_image != "" and
               additional_images != "" and main_image_id != ""):
                break
            if "webDetailSKU" in key:
                ozon_id = json.loads(json_object[key])["sku"]
                continue
            if "webProductHeading" in key:
                product_name = json.loads(json_object[key])["title"]
                model_name = get_model_name(product_name=product_name)
                continue
            if "webPrice" in key:
                prices = json.loads(json_object[key])
                purchase_price = clear_number(prices["price"].replace("₽", ""))
                if "originalPrice" in list(prices.keys()):
                    full_price = clear_number(prices["originalPrice"].replace("₽", ""))
                else:
                    full_price = purchase_price
                continue
            if "webOzonAccountPrice" in key:
                discount_card_price = clear_number(json.loads(json_object[key])["priceText"].replace("при оплате Ozon Картой", "").replace("₽", "").strip())
                continue
            if "breadCrumbs" in key:
                categories = " > ".join([category["text"] for category in json.loads(json_object[key])["breadcrumbs"]])
                continue
            if "webGallery" in key:
                images = json.loads(json_object[key])["images"]
                main_image = images[0]["src"]
                main_image_id = main_image.split("/")[-1].split(".")[0]
                additional_images = ", ".join([image["src"].replace("w50", "wc1000") for image in images[1:]])
                continue

        if "seo" in list(json.loads(bs_object.body.text).keys()):
            seo_object = json.loads(bs_object.pre.text)
            rating_object = json.loads(seo_object["seo"]["script"][0]["innerHTML"])
            if "aggregateRating" in list(rating_object.keys()):
                rating = rating_object["ratingValue"]
                amount_reviews = rating_object["reviewCount"]

        browser.get(url=characteristics_api_url)
        response = browser.page_source
        bs_object = BeautifulSoup(response, "lxml")
        characteristics_json_object = json.loads(bs_object.body.text)["widgetStates"]
        try:
            description = json.loads(characteristics_json_object["webDescription-2983286-pdpPage2column-2"])
            if "richAnnotationJson" in list(description.keys()):
                description = description["richAnnotationJson"]["content"]
                description_list = list()
                for element in description:
                    if "text" in list(element.keys()):
                        description_list.append("\n".join(element["text"]["content"]))
                description = "\n".join(description_list)
            else:
                description = description["richAnnotation"]
        except Exception as ex:
            description = ""
        characteristic_objects = json.loads(characteristics_json_object["webCharacteristics-939965-pdpPage2column-2"])["characteristics"]
        parsed_characteristics = get_characteristics(characteristic_objects=characteristic_objects)
        characteristics = parsed_characteristics["characteristics"]
        article = parsed_characteristics["article"]
        seller = json.loads(characteristics_json_object["webCurrentSeller-1752926-pdpPage2column-2"])["name"]
        record_data(article=article, ozon_id=ozon_id, product_name=product_name, model_name=model_name,
                    purchase_price=purchase_price, full_price=full_price, discount_card_price=discount_card_price,
                    categories=categories, main_image=main_image, additional_images=additional_images,
                    main_image_id=main_image_id, characteristics=characteristics, rating=rating, seller=seller,
                    amount_reviews=amount_reviews, file_name=file_name, description=description, product_url=product_url,
                    search_request=search_request)
        errors = 0
    except Exception as ex:
        errors += 1
        if errors < 5:
            print("[ERROR] Ошибка, сервер выдал некорректные данные. Пробуем получить данные еще раз")
            get_product_info(browser, product_url, file_name)
        else:
            errors = 0
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
    amount_positions = 0
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
                amount_positions += 1
                start_time = time.time()
                print(f"[INFO] Обрабатываем товар по sku: {position['value']}")
                product_url = get_product_link_via_sku(browser=browser, wait_driver=wait_driver, sku=position["value"])
                if product_url != "Not Found":
                    get_product_info(browser=browser, product_url=product_url, file_name=file_name)
                else:
                    print("[INFO] Товар с указанным sku не найден на Ozon")
                    record_no_data(ozon_id=position["sku"], file_name=file_name, message="Товар не найден")
                stop_time = time.time()
                print(f"[INFO] На парсинг позиции ушло {stop_time - start_time} секунд")

        if len(positions["product_link"]) > 0:
            file_name = create_result_file(criteria="product_link", region=region)
            for position in positions["product_link"]:
                amount_positions += 1
                start_time = time.time()
                print(f"[INFO] Обрабатываем товар по ссылке: {position['value']}")
                get_product_info(browser=browser, product_url=position["value"], file_name=file_name)
                stop_time = time.time()
                print(f"[INFO] На парсинг позиции ушло {stop_time - start_time} секунд")

        if len(positions["brand"]) > 0:
            file_name = create_result_file(criteria="brand", region=region)
            for position in positions["brand"]:
                print(f"[INFO] Обрабатываем товары по бренду: {position['value']}")
                product_urls = get_product_links_via_brand(browser=browser, brand_url=position["value"])
                for product_url in product_urls:
                    amount_positions += 1
                    start_time = time.time()
                    get_product_info(browser=browser, product_url=product_url, file_name=file_name)
                    stop_time = time.time()
                    print(f"[INFO] На парсинг позиции ушло {stop_time - start_time} секунд")

        if len(positions["seller"]) > 0:
            file_name = create_result_file(criteria="seller", region=region)
            for position in positions["seller"]:
                print(f"[INFO] Обрабатываем товары по продавцу: {position['value']}")
                product_urls = get_product_links_via_seller(browser=browser, seller_url=position["value"])
                for product_url in product_urls:
                    amount_positions += 1
                    start_time = time.time()
                    get_product_info(browser=browser, product_url=product_url, file_name=file_name)
                    stop_time = time.time()
                    print(f"[INFO] На парсинг позиции ушло {stop_time - start_time} секунд")

        if len(positions["search_request"]) > 0:
            file_name = create_result_file(criteria="search_request", region=region)
            for position in positions["search_request"]:
                print(f"[INFO] Обрабатываем товар по поисковому запросу: {position['value']}")
                product_urls = get_product_link_via_search_request(browser=browser, search_request=position["value"])
                if product_urls == "Not Found":
                    record_no_data(ozon_id="ERROR", file_name=file_name,
                                   message=f'По поисковому запросу {positions["search_request"]} не найдено товаров')
                else:
                    for product_url in product_urls:
                        amount_positions += 1
                        start_time = time.time()
                        get_product_info(browser=browser, product_url=product_url,
                                         file_name=file_name, search_request=position['value'])
                        stop_time = time.time()
                        print(f"[INFO] На парсинг позиции ушло {stop_time - start_time} секунд")
        print(f"[INFO] Всего обработано позиций: {amount_positions}")

    finally:
        browser.close()
        browser.quit()


if __name__ == "__main__":
    start_main_time = time.time()
    main()
    stop_main_time = time.time()
    print(f"[INFO] Общее время работы парсера: {stop_main_time - start_main_time} секунд")
