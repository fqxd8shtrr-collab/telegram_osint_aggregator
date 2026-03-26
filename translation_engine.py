import aiohttp
import asyncio
import logging
import config
from utils import detect_language

logger = logging.getLogger(__name__)

async def translate_text(text, target_lang="ar", source_lang=None):
    """
    Translate text using the configured translation API.
    """
    if not text:
        return ""

    if source_lang is None:
        source_lang = detect_language(text)

    if source_lang == target_lang:
        return text

    if config.TRANSLATION_API == "google":
        return await _translate_google(text, target_lang, source_lang)
    elif config.TRANSLATION_API == "deepl":
        return await _translate_deepl(text, target_lang, source_lang)
    else:
        logger.warning("No translation API configured")
        return text

async def _translate_google(text, target_lang, source_lang):
    url = "https://translation.googleapis.com/language/translate/v2"
    params = {
        "key": config.GOOGLE_TRANSLATE_API_KEY,
        "q": text,
        "target": target_lang,
        "source": source_lang,
        "format": "text"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["data"]["translations"][0]["translatedText"]
            else:
                logger.error(f"Google Translate error: {resp.status}")
                return text

async def _translate_deepl(text, target_lang, source_lang):
    url = "https://api-free.deepl.com/v2/translate"
    # Map target language to DeepL codes
    lang_map = {"ar": "AR"}
    target = lang_map.get(target_lang, target_lang.upper())
    data = {
        "auth_key": config.DEEPL_API_KEY,
        "text": text,
        "target_lang": target,
    }
    if source_lang != "unknown":
        data["source_lang"] = source_lang.upper()
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as resp:
            if resp.status == 200:
                result = await resp.json()
                return result["translations"][0]["text"]
            else:
                logger.error(f"DeepL error: {resp.status}")
                return text
