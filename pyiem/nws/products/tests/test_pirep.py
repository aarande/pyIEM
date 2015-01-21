import os
import datetime
import pytz
import unittest
from pyiem.nws.products.pirep import parser as pirepparser

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()

def utc(year, month, day, hour=0, minute=0):
    """UTC Timestamp generator"""
    return datetime.datetime(year, month, day, hour, minute).replace(
                        tzinfo=pytz.timezone("UTC"))

class TestProducts(unittest.TestCase):
    """ Tests """
    
    def test_150121_fourchar(self):
        """ Another coding edition with four char identifiers """
        nwsli_provider = {'FAR': {'lat': 44, 'lon': -99}}
        prod = pirepparser(get_file('PIREPS/fourchar.txt'),
                           nwsli_provider=nwsli_provider)
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))
        self.assertAlmostEquals(prod.reports[0].latitude, 44.10, 2)
    
    def test_150120_latlonloc(self):
        """ latlonloc.txt Turns out there is a LAT/LON option for OV """
        prod = pirepparser(get_file('PIREPS/latlonloc.txt'))
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))
        self.assertEquals(prod.reports[0].latitude, 25.00)
        self.assertEquals(prod.reports[0].longitude, -70.00)

        prod = pirepparser(get_file('PIREPS/latlonloc2.txt'))
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))

        nwsli_provider = {'PKTN': {'lat': 44, 'lon': -99}}
        prod = pirepparser(get_file('PIREPS/PKTN.txt'), nwsli_provider=nwsli_provider)
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))

    
    def test_150120_OVO(self):
        """ PIREPS/OVO.txt has a location of OV 0 """
        nwsli_provider = {'AVK': {'lat': 44, 'lon': 99}}
        prod = pirepparser(get_file('PIREPS/OVO.txt'),
                           nwsli_provider=nwsli_provider)
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))

    def test_offset(self):
        """ Test out our displacement logic """
        lat = 42.5
        lon = -92.5
        nwsli_provider = {'BIL': {'lat': lat, 'lon': lon}}
        p = pirepparser("\001\r\r\n000 \r\r\nUBUS01 KMSC 090000\r\r\n", 
                        nwsli_provider=nwsli_provider)
        lon2, lat2 = p.compute_loc("BIL", 0, 0)
        self.assertEquals(lon2, lon)
        self.assertEquals(lat2, lat)

        lon2, lat2 = p.compute_loc("BIL", 100, 90)
        self.assertAlmostEquals(lon2, -90.54, 2)
        self.assertEquals(lat2, lat)

        lon2, lat2 = p.compute_loc("BIL", 100, 0)
        self.assertEquals(lon2, lon)
        self.assertAlmostEquals(lat2, 43.95, 2)


    def test_1(self):
        """ PIREP.txt, can we parse it! """
        utcnow = utc(2015,1,9,0,0)
        nwsli_provider = {'BIL': {'lat': 44, 'lon': 99},
                          'LBY': {'lat': 45, 'lon': 100},
                          'PUB': {'lat': 46, 'lon': 101},
                          'HPW': {'lat': 47, 'lon': 102}}
        prod = pirepparser(get_file('PIREP.txt'), utcnow=utcnow,
                           nwsli_provider=nwsli_provider)
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))
        
        j = prod.get_jabbers()
        self.assertEquals(j[0][2]['channels'], 'UA.None,UA.PIREP')
