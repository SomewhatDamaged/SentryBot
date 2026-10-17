import logging
import re
from typing import List, Union

from simhash import Simhash, SimhashIndex

from mock_logging import MockLogger

log = logging.getLogger()
if log is not None:
    log = MockLogger()

HAMMING_DISTANCE = 10

class TextCompare:
    known_scams: Union[list[str],None] = None
    def __init__(self):
        pass

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Splits text by common sentence bounds (. ! ? or newlines)
        while filtering out empty strings caused by multiple spaces.
        """
        text = text.lower()
        sentences = re.split(r'[.!?\n]+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def clean_text_output(self, text: str) -> str:
        # text = re.sub(r'[*#_\->`•]', '', text)
        # replacements = {'1': 'l', '!': 'l', '4': 'a', '0': 'o', '3': 'e', '5': 's', '7': 't'}
        # for target, replacement in replacements.items():
        #     text = text.replace(target, replacement)
        text = re.sub(r'\s+', '', text)
        return text

    def mask_strings(self, text: str) -> str:
        """Masks certain features out of the text"""

        url_pattern = r'(https?://\S+|www\.\S+|\b\s*[a-z0-9-]+(?:\.[a-z0-9-]+)+/\S*)'
        text = re.sub(url_pattern, '[url]', text)

        phone_pattern = r'\+?\d[\d\s-]{7,14}\d'
        text = re.sub(phone_pattern, '[phone]', text)

        email_pattern = r'\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b'
        text = re.sub(email_pattern, '[email]', text)

        dollar_pattern = r'\$[\d,\.]+(?:k|m)?'
        text = re.sub(dollar_pattern, '[dollar]', text)

        percentage_pattern = r'[\d,\.]+\%'
        text = re.sub(percentage_pattern, '[percentage]', text)

        number_pattern = r'\d+'
        text = re.sub(number_pattern, '[number]', text)

        return text

    def get_features(self, text, width=4):
        """
        Generates n-grams
        """
        text = self.clean_text_output(text)
        text = self.mask_strings(text)
        return [text[i:i + width] for i in range(max(1, len(text) - width + 1))]

    hash_index: Union[SimhashIndex, None] = None

    def build_hash_index(self, string_list: List[str]):
        temp_index = SimhashIndex([], k=HAMMING_DISTANCE)
        for i, sentence in enumerate(string_list):
            sentence = sentence.lower()
            features = self.get_features(sentence)
            temp_index.add(str(i), Simhash(features))
        self.hash_index = temp_index

    def check_against_hash_index(self, text: str) -> tuple[bool, Union[str, None], Union[int, None]]:
        sentence: str = ""
        distance: int = 0
        for sentence in self.split_into_sentences(text):
            sentence = sentence.lower()
            incoming_hash = Simhash(self.get_features(sentence))
            matches = self.hash_index.get_near_dups(incoming_hash)

            if matches:
                for match_id in matches:
                    matched_template = self.known_scams[int(match_id)]
                    template_features = self.get_features(matched_template)
                    template_hash = Simhash(template_features)
                    bit_distance = incoming_hash.distance(template_hash)
                    if bit_distance < HAMMING_DISTANCE:
                        return True, sentence, bit_distance
        return False, None, None

