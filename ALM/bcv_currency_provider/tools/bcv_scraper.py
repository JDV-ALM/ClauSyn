# -*- coding: utf-8 -*-
from odoo import fields
import requests
from bs4 import BeautifulSoup
import logging
import urllib3
from datetime import datetime
import re
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_logger = logging.getLogger(__name__)

def get_bcv_rates(company):
    """
    Obtiene las tasas de cambio del BCV mediante web scraping.
    
    Args:
        company: Instancia de res.company
        
    Returns:
        dict: {'USD': float, 'EUR': float, 'date': date} o {} si hay error
    """
    URL = "https://www.bcv.org.ve/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.8,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    _logger.info(f"[BCV Scraper] Iniciando conexión a {URL}")
    start_time = time.time()
    
    try:
        # Realizar petición
        response = requests.get(
            URL, 
            timeout=20, 
            verify=False, 
            headers=headers,
            allow_redirects=True
        )
        
        elapsed = time.time() - start_time
        _logger.info(f"[BCV Scraper] Respuesta recibida en {elapsed:.2f}s - Status: {response.status_code}")
        
        response.raise_for_status()
        
        # Parsear HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        _logger.info(f"[BCV Scraper] HTML parseado, tamaño: {len(response.content)} bytes")
        
        # Buscar fecha
        rate_date = None
        date_span = soup.find('span', class_='date-display-single')
        
        if date_span and date_span.get('content'):
            try:
                date_str = date_span['content'].split('T')[0]
                rate_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                _logger.info(f"[BCV Scraper] Fecha encontrada: {rate_date}")
            except Exception as e:
                _logger.warning(f"[BCV Scraper] Error parseando fecha: {e}")
        
        if not rate_date:
            rate_date = fields.Date.context_today(company)
            _logger.info(f"[BCV Scraper] Usando fecha actual: {rate_date}")
        
        result = {'date': rate_date}
        
        # Buscar USD
        usd_div = soup.find(id='dolar')
        if usd_div:
            usd_element = usd_div.find('div', class_='centrado')
            if usd_element:
                strong = usd_element.find('strong')
                if strong:
                    usd_text = strong.text.strip()
                    usd_value = clean_rate_value(usd_text)
                    if usd_value:
                        result['USD'] = usd_value
                        _logger.info(f"[BCV Scraper] USD encontrado: {usd_value}")
                    else:
                        _logger.warning(f"[BCV Scraper] No se pudo convertir USD: '{usd_text}'")
                else:
                    _logger.warning("[BCV Scraper] No se encontró <strong> en div USD")
            else:
                _logger.warning("[BCV Scraper] No se encontró div.centrado en #dolar")
        else:
            _logger.error("[BCV Scraper] No se encontró div#dolar en el HTML")
        
        # Buscar EUR
        eur_div = soup.find(id='euro')
        if eur_div:
            eur_element = eur_div.find('div', class_='centrado')
            if eur_element:
                strong = eur_element.find('strong')
                if strong:
                    eur_text = strong.text.strip()
                    eur_value = clean_rate_value(eur_text)
                    if eur_value:
                        result['EUR'] = eur_value
                        _logger.info(f"[BCV Scraper] EUR encontrado: {eur_value}")
                    else:
                        _logger.warning(f"[BCV Scraper] No se pudo convertir EUR: '{eur_text}'")
                else:
                    _logger.warning("[BCV Scraper] No se encontró <strong> en div EUR")
            else:
                _logger.warning("[BCV Scraper] No se encontró div.centrado en #euro")
        else:
            _logger.error("[BCV Scraper] No se encontró div#euro en el HTML")
        
        # Validación final
        if 'USD' not in result and 'EUR' not in result:
            _logger.error("[BCV Scraper] No se pudo extraer ninguna tasa")
            # Debug: guardar HTML para análisis
            debug_html_snippet = str(soup.find('body'))[:500] if soup.find('body') else "No body found"
            _logger.debug(f"[BCV Scraper] Snippet HTML: {debug_html_snippet}")
            return {}
        
        _logger.info(f"[BCV Scraper] Resultado final: {result}")
        return result
        
    except requests.exceptions.Timeout:
        _logger.error(f"[BCV Scraper] Timeout después de {time.time() - start_time:.2f}s")
        return {}
    except requests.exceptions.ConnectionError as e:
        _logger.error(f"[BCV Scraper] Error de conexión: {e}")
        return {}
    except requests.exceptions.RequestException as e:
        _logger.error(f"[BCV Scraper] Error en petición HTTP: {e}")
        return {}
    except Exception as e:
        _logger.error(f"[BCV Scraper] Error inesperado: {e}", exc_info=True)
        return {}

def clean_rate_value(text):
    """
    Limpia y convierte un texto de tasa a float.
    """
    try:
        _logger.debug(f"[BCV Scraper] Limpiando valor: '{text}'")
        
        # Eliminar espacios y caracteres no numéricos
        cleaned = re.sub(r'[^\d,.]', '', text)
        # Reemplazar coma por punto
        cleaned = cleaned.replace(',', '.')
        
        value = float(cleaned)
        _logger.debug(f"[BCV Scraper] Valor limpio: {value}")
        
        return value
    except (ValueError, AttributeError) as e:
        _logger.warning(f"[BCV Scraper] Error convirtiendo '{text}': {e}")
        return None
