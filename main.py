import requests
import bs4
from urllib.parse import quote
import fake_headers
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from concurrent.futures import ThreadPoolExecutor

import re
from datetime import datetime
import json
import shutil
import os


# ------------- Конфигурация -------------
QUERY = 'python, django, flask'  # Поисковый запрос
URL = f'https://hh.ru/search/vacancy?text={quote(QUERY)}&area=1&area=2&search_field=description'
# _PAGE_URL = f'https://hh.ru/search/vacancy?text={quote(QUERY)}&area=1&area=2&search_field=description&page={page}'
USE_ONLY_USD = False # Искать только объявления, в которых зарплата указана в $$$ True или False 

# URL2 = f'https://hh.ru/search/vacancy?text=python&area=1&area=2&search_field=description'

def create_driver():
    """Функция создает и возвращает объект драйвера"""
    options = Options()
    options.add_argument('headless')
    options.add_argument('--log-level=3')
    driver = webdriver.Chrome(options=options)
    return driver


def get_src_html(page_number):
    """Функция сохраняет все страницы во врменную папку temp"""
    
    print(f'Начинаю сохранение страницы {page_number}')

    new_url = URL + '&page={}'.format(page_number)
    driver = create_driver()
    driver.get(url=new_url)
    with open(f'temp/{page_number}.html', 'w', encoding='utf-8') as file:
            file.write(driver.page_source)
    print(f'Страница {page_number} сохранена')
    

def get_data_from_all_pages(url, header, count_pages):
    """Собирает все посты со всех страниц и возвращает список постов"""

    # Результируищий список словарей всех постов на странице
    all_posts_data = []
    for page in range(int(count_pages)):
        with open(f'temp/{page}.html', 'r', encoding='utf-8') as file:
            html = file.read()

        soup = bs4.BeautifulSoup(html, 'lxml')

        # Получаю все посты на странице
        all_posts = soup.find_all('div', class_='serp-item')
        all_posts_tempdata = {}
        # Паттерн для извлечения id поста
        pattern_id = r'\/(\d+)'
        # Цикл по всем постам на странице
        for post in all_posts:
            # Временный словарь для данных поста
            all_posts_tempdata = {}
            # Получаю ссылку на пост
            url = post.find('a', class_='serp-item__title')['href']
            # Получаю id поста из url
            try:
                id = re.search(pattern_id, url)
                id = id.group(0)[1:]
            except AttributeError:
                id = '-'

            all_posts_tempdata['id'] = id
            all_posts_tempdata['Ссылка'] = url
            all_posts_tempdata['Заголовок'] = post.find('h3', class_='bloko-header-section-3').find('a').text
            # Получаю зарплату. Если блок присутсвует - нормализую строку и записываю в словарь
            try:
                salary = post.find('span', class_='bloko-header-section-3').text.strip().replace('\u202f', ' ')
                all_posts_tempdata['Зарплата'] = salary
            # Если зарплата не указана
            except AttributeError:
                all_posts_tempdata['Зарплата'] = 'Не указана'
            # Получаю название компании и нормализую
            company = post.find('div', class_='vacancy-serp-item__meta-info-company').find('a').text.strip().replace('\xa0', ' ')
            all_posts_tempdata['Компания'] = company
            all_posts_tempdata['Адрес'] = post.find('div', class_='vacancy-serp-item__info').find_all('div', class_='bloko-text')[1].text.strip().replace('\xa0', ' ')
            all_posts_tempdata['Опыт'] = post.find('div', class_='bloko-h-spacing-container bloko-h-spacing-container_base-0').find('div', class_='bloko-text').text.strip()

            #Добавляю временный словарь в список всех постов
            # Если включен "Только в USD" и зарплата в объявлении в USD заношу в список
            if USE_ONLY_USD and 'USD' in all_posts_tempdata['Зарплата']:
                all_posts_data.append(all_posts_tempdata)
            # Если "Только в USD" выключен - добавляю объявление ко всем
            if not USE_ONLY_USD:
                all_posts_data.append(all_posts_tempdata)
            
        print(f'На странице {page+1} собраны все объявления')

    return all_posts_data


def main():
    # Создаю заголовки
    header = fake_headers.Headers(
        browser='chrome',
        os='win',
        headers=True
    )

    HEADER = header.generate()

    # Создаю папку для временных файлов
    if 'temp' not in os.listdir():
        os.mkdir('temp')

    # Делаю запрос к сайту
    response = requests.get(url=URL,
                            headers=HEADER)

    # Создаю суп
    soup = bs4.BeautifulSoup(response.text, 'lxml')
    # Получаю сколько вакансий нашлось
    count_vacancies = soup.find('h1', class_='bloko-header-section-3')
    print('Найдено:', count_vacancies.text)

    # Получаю количество страниц
    count_pages = soup.find('div', class_='pager').find_all(
        'span', class_='pager-item-not-in-short-range')[-1]
    count_pages = count_pages.find('span').text
    print('Количество страниц:', count_pages)

    # Создаю многопоточный pool с 10ю воркерами
    with ThreadPoolExecutor(max_workers=10) as pool:
        # мультипоточно сохраняю страницы
        pool.map(get_src_html, range(int(count_pages)))
    # ожидаю завершения работы всех воркеров
    pool.shutdown()

    # Получаю все посты со всех страниц
    result = get_data_from_all_pages(URL, HEADER, count_pages)
    # Текущее время
    current_time = datetime.now().strftime('%d%m%Y_%H%M')
    
    # Создаю файл и сохраняю в него все найденные посты
    print(f'Всего собрано объявлений: {len(result)}')

    with open(f'result_{current_time}.json', 'w', encoding='utf-8') as file:
        json.dump(result, file, indent=4, ensure_ascii=False)

    print(f'Объявления успешо сохранены в файл result_{current_time}.json')

    # Удаляю временные файлы использованные в процессе работы
    shutil.rmtree('temp')


if __name__ == '__main__':
    main()
