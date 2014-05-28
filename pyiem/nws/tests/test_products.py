import unittest
import os
import psycopg2
import datetime
import pytz

from pyiem.nws.products.mcd import parser as mcdparser
from pyiem.nws.products.lsr import parser as lsrparser
from pyiem.nws.products.vtec import parser as vtecparser
from pyiem.nws.products.cli import parser as cliparser
from pyiem.nws.ugc import UGC
from pyiem.nws.nwsli import NWSLI

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()

class TestProducts(unittest.TestCase):
    
    def setUp(self):
        ''' This is called for each test, beware '''
        self.dbconn = psycopg2.connect(database='postgis')
        self.txn = self.dbconn.cursor()
    
    def tearDown(self):
        ''' This is called after each test, beware '''
        self.dbconn.rollback()
        self.dbconn.close()
    
    def test_140522_blowingdust(self):
        ''' Make sure we can deal with invalid LSR type '''
        prod = lsrparser( get_file('LSRTWC.txt') )
        self.assertEqual(len(prod.lsrs), 1)
        self.assertEqual( prod.lsrs[0].get_dbtype(), None)
    
    def test_140527_astimezone(self):
        ''' Test the processing of a begin timestamp '''
        prod = vtecparser( get_file('MWWSEW.txt') )
        prod.sql( self.txn )
        j = prod.get_jabbers('http://localhost/')
        self.assertEqual(j[0][0], ('SEW continues Small Craft Advisory valid '
            +'at May 27, 4:00 PM PDT for ((PZZ131)), ((PZZ132)) [PZ] till '
            +'May 28, 5:00 AM PDT '
            +'http://localhost/#2014-O-CON-KSEW-SC-Y-0113'))
    
    def test_140527_00000_hvtec_nwsli(self):
        ''' Test the processing of a HVTEC NWSLI of 00000 '''
        prod = vtecparser( get_file('FLSBOU.txt') )
        prod.sql( self.txn )
        j = prod.get_jabbers('http://localhost/')
        self.assertEqual(j[0][0], ('BOU extends time of Areal Flood Advisory '
            +'for ((COC049)), ((COC057)) [CO] till May 29, 9:30 PM MDT '
            +'http://localhost/#2014-O-EXT-KBOU-FA-Y-0018'))
        self.assertEqual(j[0][2]['tweet'], ('BOU extends time of Areal Flood '
            +'Advisory for ((COC049)), ((COC057)) [CO] till '
            +'May 29, 9:30 PM MDT'))
    
    def test_cli(self):
        ''' Test the processing of a CLI product '''
        prod = cliparser( get_file('CLIJNU.txt') )
        self.assertEqual(prod.cli_valid, datetime.datetime(2013,6,30))
        self.assertEqual(prod.valid, datetime.datetime(2013,7,1,0,36).replace(
                                    tzinfo=pytz.timezone("UTC")))
        self.assertEqual(prod.data['temperature_maximum'], 75)
        
        prod = cliparser( get_file('CLIDSM.txt') )
        self.assertEqual(prod.cli_valid, datetime.datetime(2013,8,1))
        self.assertEqual(prod.data['temperature_maximum'], 89)
        self.assertEqual(prod.data['snow_month'], 0)
        self.assertEqual(prod.data['snow_today'], 0)
 
    
    def test_vtec_series(self):
        ''' Test a lifecycle of WSW products '''
        prod = vtecparser( get_file('WSWDMX/WSW_00.txt') )
        self.assertEqual(prod.afos, 'WSWDMX')
        prod.sql( self.txn )
    
        ''' Did Marshall County IAZ049 get a ZR.Y '''
        self.txn.execute("""SELECT issue from warnings_2013 WHERE
        wfo = 'DMX' and eventid = 1 and phenomena = 'ZR' and 
        significance = 'Y' and status = 'EXB'
        and ugc = 'IAZ049' """)
        self.assertEqual( self.txn.rowcount, 1)

        prod = vtecparser( get_file('WSWDMX/WSW_01.txt') )
        self.assertEqual(prod.afos, 'WSWDMX')
        prod.sql( self.txn )
    
        ''' Is IAZ006 in CON status with proper end time '''
        answer = datetime.datetime(2013,1,28,6).replace(
                                                tzinfo=pytz.timezone("UTC"))
        self.txn.execute("""SELECT expire from warnings_2013 WHERE
        wfo = 'DMX' and eventid = 1 and phenomena = 'WS' and 
        significance = 'W' and status = 'CON'
        and ugc = 'IAZ006' """)

        self.assertEqual( self.txn.rowcount, 1)
        row = self.txn.fetchone()
        self.assertEqual( row[0], answer )
 
        # No change
        for i in range(2,9):
            prod = vtecparser( get_file('WSWDMX/WSW_%02i.txt' % (i,)) )
            self.assertEqual(prod.afos, 'WSWDMX')
            prod.sql( self.txn )

        prod = vtecparser( get_file('WSWDMX/WSW_09.txt') )
        self.assertEqual(prod.afos, 'WSWDMX')
        prod.sql( self.txn )

        # IAZ006 should be cancelled
        answer = datetime.datetime(2013,1,28,6).replace(
                                                tzinfo=pytz.timezone("UTC"))
        self.txn.execute("""SELECT expire from warnings_2013 WHERE
        wfo = 'DMX' and eventid = 1 and phenomena = 'WS' and 
        significance = 'W' and status = 'CAN'
        and ugc = 'IAZ006' """)

        self.assertEqual( self.txn.rowcount, 1)
        row = self.txn.fetchone()
        self.assertEqual( row[0], answer )

    
    def test_vtec(self):
        ''' Simple test of VTEC parser '''
        # Remove cruft first
        self.txn.execute("""
            DELETE from warnings_2005 WHERE 
            wfo = 'JAN' and eventid = 130 and phenomena = 'TO' and 
            significance = 'W' 
        """)
        self.txn.execute("""
            DELETE from sbw_2005 WHERE
            wfo = 'JAN' and eventid = 130 and phenomena = 'TO' and 
            significance = 'W' and status = 'NEW'
        """)
        
        ugc_provider = {'MSC091': UGC('MS', 'C', '091', 'DARYL', ['XXX'])}
        nwsli_provider = {'AMWI4': NWSLI('AMWI4', 'Ames', ['XXX'], -99, 44)}
        prod = vtecparser( get_file('TOR.txt') , ugc_provider=ugc_provider,
                           nwsli_provider=nwsli_provider)
        self.assertEqual(prod.skip_con, False)
        self.assertAlmostEqual(prod.segments[0].sbw.area, 0.3053, 4)
    
        prod.sql( self.txn )
        
        # See if we got it in the database!
        self.txn.execute("""SELECT issue from warnings_2005 WHERE
        wfo = 'JAN' and eventid = 130 and phenomena = 'TO' and 
        significance = 'W' and status = 'NEW' """)
        self.assertEqual( self.txn.rowcount, 3)

        self.txn.execute("""SELECT issue from sbw_2005 WHERE
        wfo = 'JAN' and eventid = 130 and phenomena = 'TO' and 
        significance = 'W' and status = 'NEW' """)
        self.assertEqual( self.txn.rowcount, 1)

        msgs = prod.get_jabbers('http://localhost')
        self.assertEqual( msgs[0][0], ('JAN issues Tornado Warning for '
            +'((MSC035)), ((MSC073)), DARYL [MS] till 1:15 PM CDT * AT '
            +'1150 AM CDT...THE NATIONAL WEATHER SERVICE HAS ISSUED A '
            +'TORNADO WARNING FOR DESTRUCTIVE WINDS OVER 110 MPH IN THE EYE '
            +'WALL AND INNER RAIN BANDS OF HURRICANE KATRINA. THESE WINDS '
            +'WILL OVERSPREAD MARION...FORREST AND LAMAR COUNTIES DURING '
            +'THE WARNING PERIOD. http://localhost#2005-O-NEW-KJAN-TO-W-0130'))
    
    def test_01(self):
        """ process a valid LSR without blemish """
        prod = lsrparser( get_file("LSR.txt") )
        self.assertEqual(len(prod.lsrs), 58)
        
        self.assertAlmostEqual(prod.lsrs[57].magnitude_f, 73, 0)
        self.assertEqual(prod.lsrs[57].county, "Marion")
        self.assertEqual(prod.lsrs[57].state, "IA")
        self.assertAlmostEqual(prod.lsrs[57].get_lon(), -93.11, 2)
        self.assertAlmostEqual(prod.lsrs[57].get_lat(), 41.3, 1)
        
        self.assertEqual(prod.is_summary(), True)
        self.assertEqual(prod.lsrs[57].wfo , 'DMX')
        
        answer = datetime.datetime(2013,7,23,3,55)
        answer = answer.replace(tzinfo=pytz.timezone("UTC"))
        self.assertEqual(prod.lsrs[57].valid, answer)
        
        self.assertEqual(prod.lsrs[57].get_jabbers()[0], ("Knoxville Airport "
        +"[Marion Co, IA] AWOS reports NON-TSTM WND GST of 73.00 MPH at 22 "
        +"Jul, 10:55 PM CDT -- HEAT BURST. TEMPERATURE ROSE FROM 70 TO 84 IN "
        +"15 MINUTES AND DEW POINT DROPPED FROM 63 TO 48 IN 10 MINUTES. "
        +"http://localhost"))
        
        self.assertEqual(prod.lsrs[5].tweet(), ("At 4:45 PM, Dows "
                         +"[Wright Co, IA] LAW ENFORCEMENT "
                         +"reports TSTM WND DMG #DMX"))
    
    def test_mpd_mcdparser(self):
        ''' The mcdparser can do WPC's MPD as well, test it '''
        prod = mcdparser( get_file('MPD.txt') )
        self.assertAlmostEqual(prod.geometry.area, 4.657, 3)
        self.assertEqual(prod.attn_wfo, ['PHI', 'AKQ', 'CTP', 'LWX'])
        self.assertEqual(prod.attn_rfc, ['MARFC'])
        self.assertEqual(prod.tweet(), ('#WPC issues MPD 98: NRN VA...D.C'
                                        +'....CENTRAL MD INTO SERN PA '
        +'http://www.wpc.ncep.noaa.gov/metwatch/metwatch_mpd_multi.php'
        +'?md=98&yr=2013'))
        self.assertEqual(prod.find_cwsus(self.txn), ['ZDC', 'ZNY'])
        self.assertEqual(prod.get_jabbers('http://localhost')[0], ('Weather '
    +'Prediction Center issues Mesoscale Precipitation Discussion #98'
    +' http://www.wpc.ncep.noaa.gov/metwatch/metwatch_mpd_multi.php'
    +'?md=98&amp;yr=2013'))
    
    def test_mcdparser(self):
        ''' Test Parsing of MCD Product '''
        prod = mcdparser( get_file('SWOMCD.txt') )
        self.assertAlmostEqual(prod.geometry.area, 4.302, 3)
        self.assertEqual(prod.discussion_num, 1525 )
        self.assertEqual(prod.attn_wfo[2], 'DLH')
        self.assertEqual(prod.areas_affected, ("PORTIONS OF NRN WI AND "
                                               +"THE UPPER PENINSULA OF MI"))

        # With probability this time
        prod = mcdparser( get_file('SWOMCDprob.txt') )
        self.assertAlmostEqual(prod.geometry.area, 2.444, 3)
        self.assertEqual(prod.watch_prob, 20)

        self.assertEqual(prod.get_jabbers('http://localhost')[1], ('Storm '
            +'Prediction Center issues <a href="http://www.spc.noaa.gov/'
            +'products/md/2013/md1678.html">Mesoscale Discussion #1678</a> '
            +'[watch probability: 20%] (<a href="http://localhost'
            +'?pid=201308091725-KWNS-ACUS11-SWOMCD">View text</a>)'))
