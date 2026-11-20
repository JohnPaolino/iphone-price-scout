import json
import tempfile
import unittest
from pathlib import Path
from src.monitor import parse_eur, title_matches, normalize_item, make_alerts, shipping_eur, run

CONFIG = json.loads((Path(__file__).parents[1] / 'config.json').read_text())

class TestPriceScout(unittest.TestCase):
    def test_euro_formats(self):
        self.assertEqual(parse_eur('€ 1.199,90'), 1199.90)
        self.assertEqual(parse_eur('1,199.90 EUR'), 1199.90)
        self.assertEqual(parse_eur('1.199'), 1199.0)
        self.assertEqual(parse_eur(1249), 1249.0)

    def test_models_are_not_confused(self):
        self.assertTrue(title_matches('Apple iPhone 17 Pro 256GB Blu', 'Pro', 256))
        self.assertFalse(title_matches('Apple iPhone 17 Pro Max 256GB', 'Pro', 256))
        self.assertTrue(title_matches('iPhone 17 Pro Max 1TB Nuovo', 'Pro Max', 1024))
        self.assertFalse(title_matches('iPhone 17 Pro 512 GB', 'Pro', 256))
        self.assertTrue(title_matches('iPhone 17 Pro Max 2048 GB', 'Pro Max', 2048))

    def test_unapproved_and_refurbished_excluded(self):
        base = {'title': 'Apple iPhone 17 Pro 256GB', 'price': '1.179,00 €', 'link': 'https://www.unieuro.it/online/test'}
        self.assertIsNone(normalize_item({**base, 'source': 'Random-Shop'}, 'Pro', 256, CONFIG))
        self.assertIsNone(normalize_item({**base, 'title': base['title'] + ' ricondizionato', 'source': 'Unieuro'}, 'Pro', 256, CONFIG))
        self.assertIsNone(normalize_item({**base, 'title': 'Custodia iPhone 17 Pro 256GB', 'source': 'Unieuro'}, 'Pro', 256, CONFIG))
        self.assertIsNone(normalize_item({**base, 'title': 'Apple iPhone 17 Pro Max 256GB', 'source': 'Unieuro'}, 'Pro', 256, CONFIG))

    def test_marketplace_review_not_best(self):
        a = normalize_item({'title':'Apple iPhone 17 Pro 256GB', 'source':'MediaWorld', 'price':'999,00 €', 'link':'https://www.mediaworld.it/product'}, 'Pro', 256, CONFIG)
        b = normalize_item({'title':'Apple iPhone 17 Pro 256GB', 'source':'Unieuro', 'price':'1179,00 €', 'link':'https://www.unieuro.it/product'}, 'Pro', 256, CONFIG)
        self.assertEqual(a['trust'], 'review_seller')
        self.assertEqual(b['trust'], 'trusted_retailer')

    def test_suspicious_links_never_enter_results(self):
        base = {'title':'Apple iPhone 17 Pro 256GB', 'price':'1.050,00 €', 'source':'Unieuro'}
        for url in ('http://www.unieuro.it/iphone',
                    'https://www.unieuro.it.evil.example/buy',
                    'https://unieuro.it@evil.example/buy',
                    'https://random.example/buy',
                    'javascript:alert(1)',
                    'https://www.unieuro.it:8080/buy'):
            with self.subTest(url=url):
                self.assertIsNone(normalize_item({**base, 'link':url}, 'Pro', 256, CONFIG))

    def test_google_shopping_result_requires_seller_review(self):
        item = {'title':'Apple iPhone 17 Pro 256GB', 'price':'1.050,00 €',
                'source':'Unieuro', 'link':'https://www.google.com/shopping/product/123'}
        got = normalize_item(item, 'Pro', 256, CONFIG)
        self.assertEqual(got['trust'], 'review_seller')

    def test_google_shopping_overlay_requires_seller_review(self):
        item = {'title':'Apple iPhone 17 Pro 256GB', 'price':'1.149,00 €',
                'source':'Apple', 'link':'https://www.google.com/search?ibp=oshop&q=iphone+17+pro'}
        got = normalize_item(item, 'Pro', 256, CONFIG)
        self.assertIsNotNone(got)
        self.assertEqual(got['link_quality'], 'google_shopping')
        self.assertEqual(got['trust'], 'review_seller')
        # Normal Google searches are not product-listing links.
        item['link'] = 'https://www.google.com/search?q=iphone+17+pro'
        self.assertIsNone(normalize_item(item, 'Pro', 256, CONFIG))

    def test_stale_error_must_not_trigger_alerts(self):
        item = {'merchant':'Unieuro', 'price_eur':999, 'trust':'trusted_retailer', 'link':'https://www.unieuro.it/buy'}
        variants = {'pro-256gb':{'status':'error','model':'Pro','storage':'256GB','offers':[item]}}
        self.assertEqual(make_alerts(variants, {}, {}, {**CONFIG,'alert_on_first_discovery':True}, ''), [])

    def test_shipping(self):
        self.assertEqual(shipping_eur({'delivery':'Spedizione gratuita'}), 0)
        self.assertEqual(shipping_eur({'delivery':'Spedizione € 4,99'}), 4.99)
        self.assertIsNone(shipping_eur({'delivery':'Arrives in 2 days'}))

    def test_first_run_no_alert_or_made_up_data(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            fixtures = out / 'fixture.json'
            fixtures.write_text(json.dumps({'pro-256gb': [{'title':'Apple iPhone 17 Pro 256GB', 'source':'Unieuro', 'price':'1.149,00 €', 'link':'https://www.unieuro.it/product'}]}))
            run(Path(__file__).parents[1]/'config.json', out, api_key='', dry_run=False, fixtures=fixtures)
            latest = json.loads((out/'latest.json').read_text())
            self.assertEqual(latest['variants']['pro-256gb']['best_trusted']['price_eur'], 1149)
            self.assertIsNone(latest['variants']['pro-max-256gb']['best_trusted'])
            self.assertEqual(len(make_alerts(latest['variants'], {}, {}, CONFIG, '')), 0)
            self.assertEqual(len(json.loads((out/'history.json').read_text())['pro-256gb']), 1)

if __name__ == '__main__':
    unittest.main()
