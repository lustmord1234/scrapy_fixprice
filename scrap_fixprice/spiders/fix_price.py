import scrapy
import datetime
import json
import re


class FixPriceSpider(scrapy.Spider):
    name = "fix-price"


    def __init__(self, *args, **kwargs):
        super(FixPriceSpider, self).__init__(*args, **kwargs)
        self.start_urls = []

    def start_requests(self):
        urls = input("Введите ссылки, разделенные запятой: ")
        self.start_urls = urls.split(",")

        for url in self.start_urls:
            yield scrapy.Request(url=url.strip(), callback=self.parse)


    def parse(self, response):
        product_links = response.css('div.product__wrapper a.title::attr(href)').getall()

        num_last_page = 1
        page_links = response.css('a.button.number::attr(href)').getall()
        if page_links:
            num_last_page = int(page_links[-1].split('=')[-1])

        for page in range(1, num_last_page + 1):
            url = f"{response.url.split('?')[0]}?page={page}"  # Обрабатываем переход по каждой странице
            yield response.follow(url, callback=self.parse)

        for link in product_links:
            yield response.follow(link, callback=self.parse_product)



    def parse_product(self, response):
        title = re.sub(r'[\\/*?":<>|, ]', "_", response.xpath('.//h1[@class="title"]/text()').get().strip())
        orig_price = self.find_orig_price(response)
        curr_price = self.find_cur_price(response)
        brand = self.find_brand(response, title)
        section = self.find_section(response)
        rpc = re.search(r"p-(\d+)", response.url).group(1)
        img_links = self.find_images(response)
        link_video = self.find_video(response)

        product_data = {
            'timestamp': int(datetime.datetime.now().timestamp()),
            'RPC': rpc,
            'url': response.url,
            'title': title,
            'marketing_tags': None,
            'brand': brand,
            'section': section,
            'price_data': {
                'current': curr_price if curr_price else orig_price,
                'original': orig_price,
                'sale_tag': f"Скидка {0}%",
            },
            'stock': {
                'in_stock': True if orig_price else False,
                'count': 0
            },
            'assets': {
                'main_image': img_links.pop(0),
                'set_images': img_links,
                'view360': None,
                'video': link_video
            },
            'metadata':{
                '__description': self.find_description(response),

            },
            'variants': None
        }

        #Поиск metadata "Артикул": "5235352"
        if response.xpath('//div[@class="properties-block"]//a[@class="link"]'):
            property_keys = response.xpath('//div[@class="properties-block"]//span[@class="title"]/text()').getall()[1:]
        else:
            property_keys = response.xpath('//div[@class="properties-block"]//span[@class="title"]/text()').getall()
        property_values = response.xpath('//div[@class="properties-block"]//span[@class="value"]/text()').getall()

        for key, value in zip(property_keys, property_values):
            product_data['metadata'][key] = value

        #Отправляет словарь на запись в файл
        self.write_json_data(product_data, section[2])



    @staticmethod
    def find_section(response):
        """Иерархия разделов"""
        return [line.xpath('.//span[@class="text"]/text()').get() for line in response.xpath('.//div[@class="crumb"]')][:-1]

    @staticmethod
    def find_brand(response, title):
        "Поиск названия бренда"
        brand = response.css('.property .value a::text').get()
        if brand:
            return brand
        return re.findall(r'__(\D+?)__', title)[0]

    @staticmethod
    def find_orig_price(response):
        """Поиск цены без скидки"""
        original_price = response.xpath('//meta[@itemprop="price"]/@content').get()
        if original_price:
            return float(original_price)

    @staticmethod
    def find_cur_price(response):
        """Не понятно почему, не получается найти цену со скидкой в этом коде"""
        current_price = response.xpath('//div[@class="price-quantity-block"]//div[@class="special-price"]/text()').get()
        if current_price:
            return float(current_price)

    @staticmethod
    def find_images(response):
        """Поиск ссылок на изображения"""
        links = []
        links_img = response.xpath('//img[@class="normal"]/@src').getall()
        for link_img in links_img:
            links.append(link_img)
        return links

    @staticmethod
    def find_video(response):
        """Поиск ссылок на видео"""
        link_video = response.xpath('//iframe[@id="rt-player"]/@src').get()
        return link_video

    @staticmethod
    def find_description(response):
        """Поиск описания товара"""
        description = response.xpath('//div[@class="product-details"]//div[@class="description"]/text()').get()
        return description

    @staticmethod
    def write_json_data(product_data,title):
        """Запись словара в файл"""
        with open(f'products_json/{title}', 'a', encoding="utf-8") as file:
            json.dump(product_data, file, ensure_ascii=False, indent=4)
            file.write('\n')

