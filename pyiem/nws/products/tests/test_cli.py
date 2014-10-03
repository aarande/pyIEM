import os
import datetime
import pytz
import unittest
from pyiem.nws.products.cli import parser as cliparser
from pyiem.nws.products.cli import CLIException

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()



class TestProducts(unittest.TestCase):
    """ Tests """
    
    def test_141003_alaska(self):
        """ Some alaska data was not getting processed"""
        prod = cliparser(get_file("CLIBET.txt"))
        self.assertEqual(prod.data['temperature_maximum'], 17)
        self.assertEqual(prod.data['snow_jul1'], 14.4)
    
    def test_141002_houston(self):
        """ See what we do with this invalid product """
        self.assertRaises(CLIException, cliparser, get_file('CLIHOU.txt'))
    
    def test_140930_negative_temps(self):
        """ Royal screwup not supporting negative numbers """
        prod = cliparser(get_file('CLIALO.txt'))
        self.assertEqual(prod.data.get('temperature_minimum'), -21)
        self.assertEqual(prod.data.get('temperature_minimum_record'), -21)
    
    def test_140930_mm_precip(self):
        """ Make sure having MM as today's precip does not error out """
        prod = cliparser(get_file('CLIABY.txt'))
        self.assertTrue(prod.data.get('precip_today') is None)
    
    def test_cli(self):
        """ Test the processing of a CLI product """
        prod = cliparser(get_file('CLIJNU.txt'))
        self.assertEqual(prod.cli_valid, datetime.datetime(2013,6,30))
        self.assertEqual(prod.valid, datetime.datetime(2013,7,1,0,36).replace(
                                    tzinfo=pytz.timezone("UTC")))
        self.assertEqual(prod.data['temperature_maximum'], 75)
        self.assertEqual(prod.data['temperature_maximum_time'], "259 PM")
        self.assertEqual(prod.data['temperature_minimum_time'], "431 AM")
        self.assertEqual(prod.data['precip_today'], 0.0001)
        
        prod = cliparser(get_file('CLIDSM.txt'))
        self.assertEqual(prod.cli_valid, datetime.datetime(2013,8,1))
        self.assertEqual(prod.data['temperature_maximum'], 89)
        self.assertEqual(prod.data['snow_month'], 0)
        self.assertEqual(prod.data['temperature_minimum_record_years'][0], 
                         1898)
        self.assertEqual(prod.data['snow_today'], 0)
        
        prod = cliparser(get_file('CLINYC.txt'))
        self.assertEqual(prod.data['snow_today_record_years'][0], 1925)
        self.assertEqual(prod.data['snow_today_record'], 11.5)
