import unittest
from src import reliable_monitor as m

class TestMultiSource(unittest.TestCase):
    def test_individual_comparison_prices_and_seller(self):
        sample='''<html><title>Apple iPhone 17 Pro 256GB - Trovaprezzi</title><body>
        <ul><li><a href="/offer/one">Apple iPhone 17 Pro 256GB Deep Blue</a>
        <a href="/shop">PricePlanet</a><span>1.054,00 €</span><div>+ Sped. 9,90 €</div></li>
        <li><a href="/offer/two">Apple iPhone 17 Pro 256GB Cosmic Orange</a>
        <a href="/shop2">OtherShop</a><span>1.059,00 €</span></li>
        <li><a>Apple iPhone 17 Pro Max 256GB</a><span>999,00 €</span></li>
        <li><a>Apple iPhone 17 Pro 256GB ricondizionato</a><span>650,00 €</span></li>
        </ul></body></html>'''
        offers=m.parse_comparison_html(sample,
            "https://www.trovaprezzi.it/cellulari/prezzi-scheda-prodotto/apple_iphone_17_pro_256gb-v",
            "Pro",256,"2026-11-23T07:00:00Z")
        self.assertEqual(2,len(offers), offers)
        self.assertEqual([1054,1059],[x["price_eur"] for x in offers])
        self.assertEqual(["PricePlanet","OtherShop"],[x["merchant"] for x in offers])
        self.assertTrue(all(x["trust"]=="unverified_seller" for x in offers))

    def test_alerts_on_new_low_any_seller_not_stale(self):
        cur={"pro-256gb":{"model":"Pro","storage":"256GB","offers":[{
             "price_eur":1049,"merchant":"Cheapest","link":"https://example.com/new",
             "trust":"unverified_seller"}]}}
        previous={"pro-256gb":{"offers":[{"price_eur":1150,"merchant":"Unieuro"}]}}
        config={"alert_on_first_discovery":True,"alert_min_drop_eur":5}
        out=m.calculate_alerts(cur,previous,{},config)
        self.assertEqual(1,len(out))
        self.assertIn("UNVERIFIED",out[0]["message"])
        cur["pro-256gb"]["offers"][0]["stale"]=True
        self.assertEqual([],m.calculate_alerts(cur,previous,{},config))

    def test_exact_target_url(self):
        self.assertEqual("https://www.trovaprezzi.it/cellulari/prezzi-scheda-prodotto/apple_iphone_17_pro_max_1tb-v",
                         m.trobaprezzi_url("Pro Max",1024))
