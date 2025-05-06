import requests
from bs4 import BeautifulSoup
import re
import random
from time import sleep
from urllib.parse import quote
import logging
from datetime import datetime
import concurrent.futures
from functools import partial

# Configurar logging para depuração
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Lista de marcas conhecidas para extração
KNOWN_BRANDS = [
    "Growth Supplements", "Integral Medica", "Max Titanium", "Dux Nutrition",
    "Optimum Nutrition", "Black Skull", "Probiotica", "Atlhetica Nutrition",
    "Vitafor", "Essential Nutrition"
]

class SupplementScraper:
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.138 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.0.0'
        ]
        self.current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.session = requests.Session()
        self.session.max_redirects = 5
        self.session.headers.update(self._get_headers())
    
    def _get_headers(self):
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        }
    
    def _extract_brand(self, title):
        """Tenta extrair a marca do título do produto."""
        title_lower = title.lower()
        for brand in KNOWN_BRANDS:
            if brand.lower() in title_lower:
                return brand
        # Tenta pegar a primeira palavra capitalizada como último recurso
        match = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', title)
        if match and match.group(1).lower() not in ['whey', 'creatina', 'bcaa', 'glutamina', 'protein', 'capsulas', 'sabor']: # Evitar palavras genéricas
             return match.group(1)
        return "Marca Desconhecida"

    def _parse_price(self, price_text):
        """Converte texto de preço para float, lidando com diferentes formatos."""
        try:
            # Remove 'R$', espaços e troca vírgula por ponto
            price_clean = re.sub(r'[^\d,]', '', price_text).replace(',', '.')
            # Se houver múltiplos pontos (milhar), remove exceto o último
            if price_clean.count('.') > 1:
                parts = price_clean.split('.')
                price_clean = "".join(parts[:-1]) + "." + parts[-1]
            return float(price_clean)
        except (ValueError, TypeError):
            return 0.0
        except Exception as e:
             logging.error(f"Erro inesperado ao converter preço '{price_text}': {str(e)}")
             return 0.0

    def search_amazon(self, query, max_results=5):
        try:
            search_query = quote(query)
            url = f"https://www.amazon.com.br/s?k={search_query}&i=drugstore&rh=n%3A16210003011"
            
            headers = self._get_headers()
            headers.update({
                'Referer': 'https://www.amazon.com.br/',
                'sec-ch-ua': '"Chromium";v="112", "Google Chrome";v="112", "Not:A-Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            })
            
            logging.info(f"Fazendo requisição para Amazon: {url}")
            response = self.session.get(url, headers=headers, timeout=15)
            logging.info(f"Status code Amazon: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.select('div[data-asin]:not([data-asin=""])')
                
                if not items:
                    items = soup.select('.s-result-item')
                if not items:
                    items = soup.select('div[data-component-type="s-search-result"]')
                
                logging.info(f"Encontrados {len(items)} itens na Amazon")
                
                results = []
                processed_asins = set()
                
                for item in items:
                    if len(results) >= max_results:
                        break
                        
                    try:
                        asin = item.get('data-asin')
                        if not asin or asin in processed_asins:
                            continue
                        
                        title_element = item.select_one('h2 span.a-text-normal, h2.a-size-medium, .a-text-normal')
                        price_whole = item.select_one('span.a-price-whole, .a-price-whole')
                        price_fraction = item.select_one('span.a-price-fraction, .a-price-fraction')
                        image_element = item.select_one('img.s-image, .s-image')
                        link_element = item.select_one('a.a-link-normal[href*="/dp/"], a[href*="/dp/"]')
                        
                        if not all([title_element, price_whole, price_fraction, link_element]):
                            continue
                        
                        title = title_element.text.strip()
                        price_text = f"{price_whole.text.strip()}{price_fraction.text.strip()}"
                        price = self._parse_price(price_text)
                        brand = self._extract_brand(title)
                        
                        image_url = image_element.get('src') or image_element.get('data-src') if image_element else "https://via.placeholder.com/150"
                        href = link_element.get('href')
                        product_link = "https://www.amazon.com.br" + href if href and not href.startswith('http') else href
                        
                        if price > 0 and product_link:
                            results.append({
                                'title': title,
                                'price': price,
                                'image_url': image_url,
                                'link': product_link,
                                'store': 'Amazon',
                                'brand': brand,
                                'query_date': self.current_date
                            })
                            processed_asins.add(asin)
                            logging.info(f"Adicionado produto Amazon: {title[:30]}... (Marca: {brand})")
                            
                    except Exception as e:
                        logging.error(f"Erro ao processar item da Amazon: {str(e)}")
                        continue
                
                logging.info(f"Total de produtos encontrados na Amazon: {len(results)}")
                return results
                
            elif response.status_code == 503:
                logging.error("Amazon retornou erro 503 (Service Unavailable). O site pode estar bloqueando requisições.")
                return []
            else:
                logging.error(f"Amazon retornou status code inesperado: {response.status_code}")
                return []
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de conexão ao buscar na Amazon: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar na Amazon: {str(e)}", exc_info=True)
            return []

    def search_growth_suplementos(self, query, max_results=5):
        try:
            search_query = quote(query)
            url = f"https://www.gsuplementos.com.br/busca?q={search_query}"
            
            headers = self._get_headers()
            headers.update({
                'Referer': 'https://www.gsuplementos.com.br/',
                'sec-ch-ua': '"Chromium";v="112", "Google Chrome";v="112", "Not:A-Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            })
            
            logging.info(f"Fazendo requisição para Growth: {url}")
            response = self.session.get(url, headers=headers, timeout=15)
            logging.info(f"Status code Growth: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.select('.product-item, .item.product, .product, .products-grid .item, .product-list .item')
                
                logging.info(f"Encontrados {len(items)} itens na Growth")
                
                results = []
                for item in items:
                    if len(results) >= max_results:
                        break
                        
                    try:
                        title_element = item.select_one('.product-name, .product-item-name, .name, .product-title')
                        price_element = item.select_one('.price, .product-price, .price-box, .price-value')
                        image_element = item.select_one('.product-image img, .product-image-photo, img.product-image, .product-image')
                        link_element = item.select_one('a.product-item-link, a.product-item__link, a.product, a.product-link')
                        
                        if not all([title_element, price_element, link_element]):
                            continue
                        
                        title = title_element.text.strip()
                        price_text = price_element.text.strip()
                        price = self._parse_price(price_text)
                        brand = "Growth Suplementos" if "growth" in title.lower() else self._extract_brand(title)
                        
                        image_url = image_element.get('src') or image_element.get('data-src') if image_element else "https://via.placeholder.com/150"
                        product_link = link_element.get('href')
                        
                        if product_link and not product_link.startswith('http'):
                            product_link = "https://www.gsuplementos.com.br" + product_link
                        
                        if price > 0 and product_link:
                            results.append({
                                'title': title,
                                'price': price,
                                'image_url': image_url,
                                'link': product_link,
                                'store': 'Growth Suplementos',
                                'brand': brand,
                                'query_date': self.current_date
                            })
                            logging.info(f"Adicionado produto Growth: {title[:30]}... (Marca: {brand})")
                            
                    except Exception as e:
                        logging.error(f"Erro ao processar item da Growth: {str(e)}")
                        continue
                
                logging.info(f"Total de produtos encontrados na Growth: {len(results)}")
                return results
                
            else:
                logging.error(f"Growth retornou status code inesperado: {response.status_code}")
                return []
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de conexão ao buscar na Growth: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar na Growth: {str(e)}", exc_info=True)
            return []

    def search_integralmedica(self, query, max_results=5):
        try:
            url = f"https://www.integralmedica.com.br/busca?q={query}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.integralmedica.com.br/'
            }
            
            response = self.session.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.select('div.product-item, div.item-product, div.product-card')
            
            if not items:
                logging.warning(f"Nenhum item encontrado na Integral Medica para: {query}")
                return []
            
            results = []
            for item in items[:max_results]:
                try:
                    title = item.select_one('h2.product-name, h3.product-title, a.product-name')
                    price = item.select_one('span.price, div.price-box, span.product-price')
                    image = item.select_one('img.product-image, img.product-img, img.lazy')
                    link = item.select_one('a.product-link, a.product-item-link')
                    
                    if not all([title, price, image, link]):
                        continue
                        
                    results.append({
                        'title': title.text.strip(),
                        'price': price.text.strip(),
                        'image_url': image.get('src', '') or image.get('data-src', ''),
                        'link': link.get('href', ''),
                        'store': 'Integral Medica'
                    })
                except Exception as e:
                    logging.error(f"Erro ao processar item da Integral Medica: {str(e)}")
                    continue
            
            logging.info(f"Encontrados {len(results)} produtos na Integral Medica")
            return results
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de conexão com Integral Medica: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar na Integral Medica: {str(e)}")
            return []

    def search_netshoes(self, query, max_results=5):
        try:
            url = f"https://www.netshoes.com.br/busca?q={query}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.netshoes.com.br/'
            }
            
            response = self.session.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.select('div.product-item, div.item-product, div.product-card')
            
            if not items:
                logging.warning(f"Nenhum item encontrado na Netshoes para: {query}")
                return []
            
            results = []
            for item in items[:max_results]:
                try:
                    title = item.select_one('h2.product-name, h3.product-title, a.product-name')
                    price = item.select_one('span.price, div.price-box, span.product-price')
                    image = item.select_one('img.product-image, img.product-img, img.lazy')
                    link = item.select_one('a.product-link, a.product-item-link')
                    
                    if not all([title, price, image, link]):
                        continue
                        
                    results.append({
                        'title': title.text.strip(),
                        'price': price.text.strip(),
                        'image_url': image.get('src', '') or image.get('data-src', ''),
                        'link': link.get('href', ''),
                        'store': 'Netshoes'
                    })
                except Exception as e:
                    logging.error(f"Erro ao processar item da Netshoes: {str(e)}")
                    continue
            
            logging.info(f"Encontrados {len(results)} produtos na Netshoes")
            return results
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de conexão com Netshoes: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar na Netshoes: {str(e)}")
            return []

    def search_maxtitanium(self, query, max_results=5):
        try:
            url = f"https://www.maxtitanium.com.br/busca?q={query}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.maxtitanium.com.br/'
            }
            
            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.select('div.product-item, div.item-product, div.product-card')
            
            if not items:
                logging.warning(f"Nenhum item encontrado na Max Titanium para: {query}")
                return []
            
            results = []
            for item in items[:max_results]:
                try:
                    title = item.select_one('h2.product-name, h3.product-title, a.product-name')
                    price = item.select_one('span.price, div.price-box, span.product-price')
                    image = item.select_one('img.product-image, img.product-img, img.lazy')
                    link = item.select_one('a.product-link, a.product-item-link')
                    
                    if not all([title, price, image, link]):
                        continue
                        
                    results.append({
                        'title': title.text.strip(),
                        'price': price.text.strip(),
                        'image_url': image.get('src', '') or image.get('data-src', ''),
                        'link': link.get('href', ''),
                        'store': 'Max Titanium'
                    })
                except Exception as e:
                    logging.error(f"Erro ao processar item da Max Titanium: {str(e)}")
                    continue
            
            logging.info(f"Encontrados {len(results)} produtos na Max Titanium")
            return results
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de conexão com Max Titanium: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar na Max Titanium: {str(e)}")
            return []

    def search_atlhetica(self, query, max_results=5):
        search_query = quote(query)
        url = f"https://www.atlheticanutrition.com.br/busca?q={search_query}"
        results = []
        try:
            logging.info(f"Buscando na Atlhetica: {url}")
            
            headers = self._get_headers()
            headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://www.atlheticanutrition.com.br/'
            })
            
            response = requests.get(url, headers=headers, timeout=15)
            logging.info(f"Status code Atlhetica: {response.status_code}")

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.select('.product-item, .item.product, .product, .products-grid .item, .product-list .item, .product')
                
                logging.info(f"Encontrados {len(items)} itens na Atlhetica")

                count = 0
                for item in items:
                    if count >= max_results:
                        break

                    try:
                        title_element = item.select_one('.product-name, .product-item-name, .name, .product-title')
                        price_element = item.select_one('.price, .product-price, .price-box, .price-value')
                        image_element = item.select_one('.product-image img, .product-image-photo, img.product-image, .product-image')
                        link_element = item.select_one('a.product-item-link, a.product-item__link, a.product, a.product-link')

                        if not all([title_element, price_element, link_element]):
                            logging.debug(f"Item incompleto: {item}")
                            continue

                        title = title_element.text.strip()
                        price_text = price_element.text.strip()
                        price = self._parse_price(price_text)
                        brand = "Atlhetica" if "atlhetica" in title.lower() else self._extract_brand(title)

                        image_url = image_element.get('src') or image_element.get('data-src') if image_element else "https://via.placeholder.com/150"
                        product_link = link_element.get('href')

                        if product_link and not product_link.startswith('http'):
                            product_link = "https://www.atlheticanutrition.com.br" + product_link

                        if price > 0 and product_link:
                            results.append({
                                'title': title,
                                'price': price,
                                'image_url': image_url,
                                'link': product_link,
                                'store': 'Atlhetica Nutrition',
                                'brand': brand,
                                'query_date': self.current_date
                            })
                            count += 1
                            logging.info(f"Adicionado produto Atlhetica: {title[:30]}... (Marca: {brand})")
                            
                    except Exception as e:
                        logging.error(f"Erro ao processar item da Atlhetica: {str(e)}")
                        continue

        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de conexão ao buscar na Atlhetica: {str(e)}")
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar na Atlhetica: {str(e)}", exc_info=True)

        sleep(random.uniform(3.0, 5.0))
        logging.info(f"Total de produtos encontrados na Atlhetica: {len(results)}")
        return results

    def search_probiotica(self, query, max_results=5):
        search_query = quote(query)
        url = f"https://www.probiotica.com.br/busca?q={search_query}"
        results = []
        try:
            logging.info(f"Buscando na Probiótica: {url}")
            
            headers = self._get_headers()
            headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://www.probiotica.com.br/'
            })
            
            response = requests.get(url, headers=headers, timeout=15)
            logging.info(f"Status code Probiótica: {response.status_code}")

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.select('.product-item, .item.product, .product, .products-grid .item, .product-list .item, .product')
                
                logging.info(f"Encontrados {len(items)} itens na Probiótica")

                count = 0
                for item in items:
                    if count >= max_results:
                        break

                    try:
                        title_element = item.select_one('.product-name, .product-item-name, .name, .product-title')
                        price_element = item.select_one('.price, .product-price, .price-box, .price-value')
                        image_element = item.select_one('.product-image img, .product-image-photo, img.product-image, .product-image')
                        link_element = item.select_one('a.product-item-link, a.product-item__link, a.product, a.product-link')

                        if not all([title_element, price_element, link_element]):
                            logging.debug(f"Item incompleto: {item}")
                            continue

                        title = title_element.text.strip()
                        price_text = price_element.text.strip()
                        price = self._parse_price(price_text)
                        brand = "Probiótica" if "probiótica" in title.lower() else self._extract_brand(title)

                        image_url = image_element.get('src') or image_element.get('data-src') if image_element else "https://via.placeholder.com/150"
                        product_link = link_element.get('href')

                        if product_link and not product_link.startswith('http'):
                            product_link = "https://www.probiotica.com.br" + product_link

                        if price > 0 and product_link:
                            results.append({
                                'title': title,
                                'price': price,
                                'image_url': image_url,
                                'link': product_link,
                                'store': 'Probiótica',
                                'brand': brand,
                                'query_date': self.current_date
                            })
                            count += 1
                            logging.info(f"Adicionado produto Probiótica: {title[:30]}... (Marca: {brand})")
                            
                    except Exception as e:
                        logging.error(f"Erro ao processar item da Probiótica: {str(e)}")
                        continue

        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de conexão ao buscar na Probiótica: {str(e)}")
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar na Probiótica: {str(e)}", exc_info=True)

        sleep(random.uniform(3.0, 5.0))
        logging.info(f"Total de produtos encontrados na Probiótica: {len(results)}")
        return results

    def search_belezanaweb(self, query, max_results=5):
        try:
            url = f"https://www.belezanaweb.com.br/busca?q={query}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.belezanaweb.com.br/'
            }
            
            response = self.session.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.select('div.product-item, div.item-product, div.product-card')
            
            if not items:
                logging.warning(f"Nenhum item encontrado na Beleza na Web para: {query}")
                return []
            
            results = []
            for item in items[:max_results]:
                try:
                    title = item.select_one('h2.product-name, h3.product-title, a.product-name')
                    price = item.select_one('span.price, div.price-box, span.product-price')
                    image = item.select_one('img.product-image, img.product-img, img.lazy')
                    link = item.select_one('a.product-link, a.product-item-link')
                    
                    if not all([title, price, image, link]):
                        continue
                        
                    results.append({
                        'title': title.text.strip(),
                        'price': price.text.strip(),
                        'image_url': image.get('src', '') or image.get('data-src', ''),
                        'link': link.get('href', ''),
                        'store': 'Beleza na Web'
                    })
                except Exception as e:
                    logging.error(f"Erro ao processar item da Beleza na Web: {str(e)}")
                    continue
            
            logging.info(f"Encontrados {len(results)} produtos na Beleza na Web")
            return results
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de conexão com Beleza na Web: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar na Beleza na Web: {str(e)}")
            return []

    def search_epocacosmeticos(self, query, max_results=5):
        try:
            url = f"https://www.epocacosmeticos.com.br/busca?q={query}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.epocacosmeticos.com.br/'
            }
            
            response = self.session.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.select('div.product-item, div.item-product, div.product-card')
            
            if not items:
                logging.warning(f"Nenhum item encontrado na Época Cosméticos para: {query}")
                return []
            
            results = []
            for item in items[:max_results]:
                try:
                    title = item.select_one('h2.product-name, h3.product-title, a.product-name')
                    price = item.select_one('span.price, div.price-box, span.product-price')
                    image = item.select_one('img.product-image, img.product-img, img.lazy')
                    link = item.select_one('a.product-link, a.product-item-link')
                    
                    if not all([title, price, image, link]):
                        continue
                        
                    results.append({
                        'title': title.text.strip(),
                        'price': price.text.strip(),
                        'image_url': image.get('src', '') or image.get('data-src', ''),
                        'link': link.get('href', ''),
                        'store': 'Época Cosméticos'
                    })
                except Exception as e:
                    logging.error(f"Erro ao processar item da Época Cosméticos: {str(e)}")
                    continue
            
            logging.info(f"Encontrados {len(results)} produtos na Época Cosméticos")
            return results
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de conexão com Época Cosméticos: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar na Época Cosméticos: {str(e)}")
            return []

    def search_onofre(self, query, max_results=5):
        try:
            url = f"https://www.onofre.com.br/busca?q={query}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.onofre.com.br/'
            }
            
            response = self.session.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.select('div.product-item, div.item-product, div.product-card')
            
            if not items:
                logging.warning(f"Nenhum item encontrado na Onofre para: {query}")
                return []
            
            results = []
            for item in items[:max_results]:
                try:
                    title = item.select_one('h2.product-name, h3.product-title, a.product-name')
                    price = item.select_one('span.price, div.price-box, span.product-price')
                    image = item.select_one('img.product-image, img.product-img, img.lazy')
                    link = item.select_one('a.product-link, a.product-item-link')
                    
                    if not all([title, price, image, link]):
                        continue
                        
                    results.append({
                        'title': title.text.strip(),
                        'price': price.text.strip(),
                        'image_url': image.get('src', '') or image.get('data-src', ''),
                        'link': link.get('href', ''),
                        'store': 'Onofre'
                    })
                except Exception as e:
                    logging.error(f"Erro ao processar item da Onofre: {str(e)}")
                    continue
            
            logging.info(f"Encontrados {len(results)} produtos na Onofre")
            return results
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de conexão com Onofre: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar na Onofre: {str(e)}")
            return []

    def search_drogaraia(self, query, max_results=5):
        try:
            url = f"https://www.drogaraia.com.br/busca?q={query}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.drogaraia.com.br/'
            }
            
            response = self.session.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.select('div.product-item, div.item-product, div.product-card')
            
            if not items:
                logging.warning(f"Nenhum item encontrado na Droga Raia para: {query}")
                return []
            
            results = []
            for item in items[:max_results]:
                try:
                    title = item.select_one('h2.product-name, h3.product-title, a.product-name')
                    price = item.select_one('span.price, div.price-box, span.product-price')
                    image = item.select_one('img.product-image, img.product-img, img.lazy')
                    link = item.select_one('a.product-link, a.product-item-link')
                    
                    if not all([title, price, image, link]):
                        continue
                        
                    results.append({
                        'title': title.text.strip(),
                        'price': price.text.strip(),
                        'image_url': image.get('src', '') or image.get('data-src', ''),
                        'link': link.get('href', ''),
                        'store': 'Droga Raia'
                    })
                except Exception as e:
                    logging.error(f"Erro ao processar item da Droga Raia: {str(e)}")
                    continue
            
            logging.info(f"Encontrados {len(results)} produtos na Droga Raia")
            return results
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de conexão com Droga Raia: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar na Droga Raia: {str(e)}")
            return []

    def search_panvel(self, query, max_results=5):
        try:
            url = f"https://www.panvel.com/busca?q={query}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.panvel.com/'
            }
            
            response = self.session.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.select('div.product-item, div.item-product, div.product-card')
            
            if not items:
                logging.warning(f"Nenhum item encontrado na Panvel para: {query}")
                return []
            
            results = []
            for item in items[:max_results]:
                try:
                    title = item.select_one('h2.product-name, h3.product-title, a.product-name')
                    price = item.select_one('span.price, div.price-box, span.product-price')
                    image = item.select_one('img.product-image, img.product-img, img.lazy')
                    link = item.select_one('a.product-link, a.product-item-link')
                    
                    if not all([title, price, image, link]):
                        continue
                        
                    results.append({
                        'title': title.text.strip(),
                        'price': price.text.strip(),
                        'image_url': image.get('src', '') or image.get('data-src', ''),
                        'link': link.get('href', ''),
                        'store': 'Panvel'
                    })
                except Exception as e:
                    logging.error(f"Erro ao processar item da Panvel: {str(e)}")
                    continue
            
            logging.info(f"Encontrados {len(results)} produtos na Panvel")
            return results
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de conexão com Panvel: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar na Panvel: {str(e)}")
            return []

    def search_supplements(self, query, max_results=5):
        """Busca produtos em todas as lojas disponíveis."""
        logging.info(f"Iniciando busca de suplementos para: {query}")
        logging.info(f"Máximo de resultados por loja: {max_results}")
        
        if query.lower() == 'teste':
            logging.info("Modo teste ativado - retornando dados mock")
            return self._get_mock_data()
        
        stores = {
            'Amazon': self.search_amazon,
            'Growth Suplementos': self.search_growth_suplementos,
            'Integral Medica': self.search_integralmedica,
            'Netshoes': self.search_netshoes,
            'Max Titanium': self.search_maxtitanium,
            'Atlhetica Nutrition': self.search_atlhetica,
            'Probiótica': self.search_probiotica,
            'Beleza na Web': self.search_belezanaweb,
            'Época Cosméticos': self.search_epocacosmeticos,
            'Onofre': self.search_onofre,
            'Droga Raia': self.search_drogaraia,
            'Panvel': self.search_panvel
        }
        
        all_results = []
        for store_name, search_func in stores.items():
            try:
                logging.info(f"Buscando na loja: {store_name}")
                results = search_func(query, max_results)
                if results:
                    logging.info(f"Encontrados {len(results)} produtos na {store_name}")
                    all_results.extend(results)
                else:
                    logging.warning(f"Nenhum produto encontrado na {store_name}")
            except Exception as e:
                logging.error(f"Erro ao buscar na {store_name}: {str(e)}")
                continue
        
        if not all_results:
            logging.warning("Nenhum produto encontrado em nenhuma loja")
            return []
        
        logging.info(f"Total de produtos encontrados: {len(all_results)}")
        return all_results

    def _get_mock_data(self):
        """Retorna dados simulados para testes."""
        logging.info(f"Gerando 4 dados simulados para testes.") # 4 lojas
        mock_data = [
            {
                'title': 'Whey Protein Concentrado (1kg) - Growth Suplements',
                'price': random.uniform(80, 120),
                'image_url': 'https://via.placeholder.com/150?text=Growth+Whey',
                'link': 'https://www.gsuplementos.com.br/mock/whey-concentrado',
                'store': 'Growth Suplements',
                'brand': 'Growth Suplements',
                'query_date': self.current_date
            },
            {
                'title': 'Creatina Monohidratada (250g) - Growth Suplements',
                'price': random.uniform(60, 90),
                'image_url': 'https://via.placeholder.com/150?text=Growth+Creatina',
                'link': 'https://www.gsuplementos.com.br/mock/creatina',
                'store': 'Growth Suplements',
                'brand': 'Growth Suplements',
                'query_date': self.current_date
            },
            {
                'title': 'Iso Triple Zero (900g) - Integral Medica',
                'price': random.uniform(150, 220),
                'image_url': 'https://via.placeholder.com/150?text=Integral+Iso',
                'link': 'https://www.integralmedica.com.br/mock/iso-triple-zero',
                'store': 'Integral Medica',
                'brand': 'Integral Medica',
                'query_date': self.current_date
            },
            {
                'title': 'BCAA 2400 (100 Caps) - Integral Medica',
                'price': random.uniform(40, 70),
                'image_url': 'https://via.placeholder.com/150?text=Integral+BCAA',
                'link': 'https://www.integralmedica.com.br/mock/bcaa-2400',
                'store': 'Integral Medica',
                'brand': 'Integral Medica',
                'query_date': self.current_date
            },
            {
                'title': 'Gold Standard 100% Whey (907g) - Optimum Nutrition',
                'price': random.uniform(250, 350),
                'image_url': 'https://via.placeholder.com/150?text=Optimum+Whey',
                'link': 'https://www.amazon.com.br/mock/whey-gold-standard',
                'store': 'Amazon',
                'brand': 'Optimum Nutrition',
                'query_date': self.current_date
            },
            {
                'title': 'Creatine Powder (300g) - Optimum Nutrition',
                'price': random.uniform(100, 150),
                'image_url': 'https://via.placeholder.com/150?text=Optimum+Creatine',
                'link': 'https://www.amazon.com.br/mock/creatine-powder',
                'store': 'Amazon',
                'brand': 'Optimum Nutrition',
                'query_date': self.current_date
            },
             {
                'title': 'Whey Protein Isolado Dux Nutrition 900g',
                'price': random.uniform(180, 250),
                'image_url': 'https://via.placeholder.com/150?text=Dux+Whey',
                'link': 'https://www.netshoes.com.br/mock/dux-whey-isolado',
                'store': 'Netshoes',
                'brand': 'Dux Nutrition',
                'query_date': self.current_date
            },
            {
                'title': 'Creatina Max Titanium 300g',
                'price': random.uniform(90, 130),
                'image_url': 'https://via.placeholder.com/150?text=Max+Creatina',
                'link': 'https://www.netshoes.com.br/mock/max-creatina',
                'store': 'Netshoes',
                'brand': 'Max Titanium',
                'query_date': self.current_date
            }
        ]
        # Replica e mistura os dados para simular mais resultados
        full_mock_list = mock_data * 4 # Garante dados suficientes
        random.shuffle(full_mock_list)
        # Atualiza os preços para serem diferentes
        for item in full_mock_list:
            item['price'] = round(item['price'] * random.uniform(0.95, 1.05), 2)

        return full_mock_list

# Exemplo de uso (para teste local)
if __name__ == '__main__':
    scraper = SupplementScraper()
    # Teste com busca real
    # results = scraper.search_supplements('creatina', max_results=2)
    # print(f"\nResultados da busca por 'creatina':")
    # for res in results:
    #     print(f" - {res['title']} ({res['brand']}) - R$ {res['price']:.2f} [{res['store']}]")

    # Teste com dados simulados
    mock_results = scraper.search_supplements('teste', max_results=3)
    print(f"\nResultados da busca por 'teste' (simulado):")
    for res in mock_results:
        print(f" - {res['title']} ({res['brand']}) - R$ {res['price']:.2f} [{res['store']}] - Data: {res['query_date']}") 