import unittest
import os
import psycopg2.extras
import datetime
import pytz

from pyiem.nws.products import parser
from pyiem.nws.products.vtec import parser as vtecparser
from pyiem.nws.ugc import UGC, UGCParseException
from pyiem.nws.nwsli import NWSLI

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()

def utc(year, month, day, hour=0, minute=0):
    """UTC Timestamp generator"""
    return datetime.datetime(year, month, day, hour, minute).replace(
                        tzinfo=pytz.timezone("UTC"))

class TestProducts(unittest.TestCase):
    
    def setUp(self):
        ''' This is called for each test, beware '''
        self.dbconn = psycopg2.connect(database='postgis')
        self.txn = self.dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    def tearDown(self):
        ''' This is called after each test, beware '''
        self.dbconn.rollback()
        self.dbconn.close()

    def test_150203_exp_does_not_end(self):
        """MWWCAR a VTEC EXP action should not terminate it """
        for i in range(24):
            print('Parsing Product: %s.txt' % (i,))
            prod = vtecparser(get_file('MWWCAR/%i.txt' % (i,)))
            prod.sql(self.txn)
            self.assertEquals(len(prod.warnings), 0)

    def test_150203_null_issue(self):
        """WSWOKX had null issue times, bad! """
        for i in range(18):
            print('Parsing Product: %s.txt' % (i,))
            prod = vtecparser(get_file('WSWOKX/%i.txt' % (i,)))
            prod.sql(self.txn)
            # Make sure there are no null issue times
            self.txn.execute("""SELECT count(*) from warnings_2015
            where wfo = 'OKX' and eventid = 6
            and phenomena = 'WW' and significance = 'Y'
            and issue is null""")
            self.assertEquals(self.txn.fetchone()[0], 0)

    def test_150202_hwo(self):
        """HWORNK emitted a poorly worded error message"""
        prod = parser(get_file('HWORNK.txt'))
        self.assertRaises(Exception, prod.get_jabbers,
                          'http://localhost', 'http://localhost')

    def test_150115_correction_sbw(self):
        """ FLWMHX make sure a correction does not result in two polygons """
        prod = vtecparser(get_file('FLWMHX/0.txt'))
        prod.sql(self.txn)
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))
        prod = vtecparser(get_file('FLWMHX/1.txt'))
        prod.sql(self.txn)
        self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))

    def test_150105_considerable_tag(self):
        """ TORFSD has considerable tag """
        prod = vtecparser(get_file('TORFSD.txt'))
        j = prod.get_jabbers('http://localhost', 'http://localhost')
        self.assertEquals(j[0][0], ('FSD issues Tornado Warning '
            +'[tornado: RADAR INDICATED, tornado damage threat: CONSIDERABLE, '
            +'hail: 1.50 IN] for ((IAC035)) [IA] till 8:00 PM CDT * AT 720 '
            +'PM CDT...A SEVERE THUNDERSTORM CAPABLE OF PRODUCING A LARGE '
            +'AND EXTREMELY DANGEROUS TORNADO WAS LOCATED NEAR WASHTA...AND '
            +'MOVING NORTHEAST AT 30 MPH. '
            +'http://localhost#2013-O-NEW-KFSD-TO-W-0020'))

    def test_150105_sbw(self):
        """ FLSLBF SBW that spans two years! """
        for i in range(7):
            print('Parsing Product: %s.txt' % (i,))
            prod = vtecparser(get_file('FLSLBF/%i.txt' % (i,)))
            prod.sql(self.txn)
            self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))


    def test_150105_manycors(self):
        """ WSWGRR We had some issues with this series, lets test it """
        for i in range(15):
            print('Parsing Product: %s.txt' % (i,))
            prod = vtecparser(get_file('WSWGRR/%i.txt' % (i,)))
            prod.sql(self.txn)
            self.assertEquals(len(prod.warnings), 0,
                              "\n".join(prod.warnings))

    def test_150102_mutiyear2(self):
        """ WSWSTO See how well we span multiple years """
        for i in range(17):
            print('Parsing Product: %s.txt' % (i,))
            prod = vtecparser(get_file('NPWSTO/%i.txt' % (i,)))
            prod.sql(self.txn)
            self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))

    def test_150102_mutiyear(self):
        """ WSWOUN See how well we span multiple years """
        for i in range(13):
            print('Parsing Product: %s.txt' % (i,))
            prod = vtecparser(get_file('WSWOUN/%i.txt' % (i,)))
            prod.sql(self.txn)
            # Make sure there are no null issue times
            self.txn.execute("""SELECT count(*) from warnings_2014
            where wfo = 'OUN' and eventid = 16
            and phenomena = 'WW' and significance = 'Y'
            and issue is null""")
            self.assertEquals(self.txn.fetchone()[0], 0)
            if i == 5:
                self.txn.execute("""SELECT issue from warnings_2014
                WHERE ugc = 'OKZ036' and wfo = 'OUN' and eventid = 16
                and phenomena = 'WW' and significance = 'Y' """)
                row = self.txn.fetchone()
                self.assertEquals(row[0], utc(2015, 1, 1, 6, 0))
            self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))

    def test_141226_correction(self):
        """ Add another test for product corrections """
        self.assertRaises(UGCParseException, vtecparser, get_file('FLSRAH.txt'))

    def test_141215_correction(self):
        """ I have a feeling we are not doing the right thing for COR """
        for i in range(6):
            print('Parsing Product: %s.txt' % (i,))
            prod = vtecparser(get_file('NPWMAF/%i.txt' % (i,)))
            prod.sql(self.txn)
            self.assertEquals(len(prod.warnings), 0, 
                              "\n".join(prod.warnings))
    
    def test_141212_mqt(self):
        """ Updated four rows instead of three, better check on it """
        for i in range(4):
            print('Parsing Product: %s.txt' % (i,))
            prod = vtecparser(get_file('MWWMQT/%i.txt' % (i,)))
            prod.sql(self.txn)
            self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings)) 
    
    def test_141211_null_expire(self):
        """ Figure out why the database has a null expiration for this FL.W"""
        for i in range(0, 13):
            print('Parsing Product: %s.txt' % (i,))
            prod = vtecparser(get_file('FLSIND/%i.txt' % (i,)))
            prod.sql(self.txn)
            self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings)) 
    
    def test_141210_continues(self):
        """ See that we handle CON with infinite time A-OK """
        for i in range(0,2):
            prod = vtecparser(get_file('FFAEKA/%i.txt' % (i,)))
            prod.sql(self.txn)
            self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))            
    
    def test_141208_upgrade(self):
        """ See that we can handle the EXB case """
        for i in range(0,18):
            prod = vtecparser(get_file('MWWLWX/%02i.txt' % (i,)))
            prod.sql(self.txn)
            self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))
            
    def test_141016_tsuwca(self):
        """ Got a null vtec timestamp with this product """
        utcnow = utc(2014, 10, 16, 17, 10)
        prod = vtecparser( get_file('TSUWCA.txt'), utcnow=utcnow)
        j = prod.get_jabbers('http://localhost', 'http://localhost')
        self.assertEquals(j[0][0], ('AAQ issues Tsunami Warning for '
            +'((ORZ001)), ((ORZ002)), ((ORZ021)), ((ORZ022)) [OR] and '
            +'((WAZ001)), ((WAZ021)), ((WAZ503)), ((WAZ506)), ((WAZ507)), '
            +'((WAZ508)), ((WAZ509)), ((WAZ510)), ((WAZ511)), ((WAZ514)), '
            +'((WAZ515)), ((WAZ516)), ((WAZ517)) [WA] till 10:30 AM PDT '
            +'http://localhost#2014-T-NEW-PAAQ-TS-W-0016'))
    
    def test_tcp(self):
        """ See what we can do with TCP """
        prod = parser( get_file('TCPAT1.txt') )
        j = prod.get_jabbers('http://localhost', 'http://localhost')
        self.assertEquals(j[0][0], ('National Hurricance Center issues '
            +'ADVISORY 19 for POST-TROPICAL CYCLONE ARTHUR '
            +'http://localhost?pid=201407051500-KNHC-WTNT31-TCPAT1'))
        self.assertEquals(j[0][2]['twitter'], ('Post-Tropical Cyclone '
            +'#Arthur ADVISORY 19 issued. http://go.usa.gov/W3H'))
    
    def test_140820_badtimestamp(self):
        """ Check our invalid timestamp exception and how it is written """
        try:
            parser( get_file('RWSGTF_badtime.txt') )
        except Exception, msg:
            # Note to self, unsure how this even works :)
            self.assertEquals(msg[1], ("Invalid timestamp "
                +"[130 PM MDT WED TUE 19 2014] found in product "
                +"[NZUS01 KTFX RWSGTF] header"))
    
    def test_140731_badugclabel(self):
        """ Make sure this says zones and not counties! """
        ugc_provider = {}
        for u in range(530,550,1):
            n =  'a' * min((u+1/2),80)
            ugc_provider["ANZ%03i" % (u,)] = UGC('AN', 'Z', "%03i" % (u,), 
                              name=n, wfos=['DMX'])
            
        utcnow = utc(2014, 7, 31, 17, 35)
        prod = vtecparser( get_file('MWWLWX.txt'), utcnow=utcnow,
                           ugc_provider=ugc_provider)
        j = prod.get_jabbers('http://localhost', 'http://localhost')
        self.assertEquals(j[0][0], ('LWX issues Small Craft Advisory '
            +'valid at Jul 31, 6:00 PM EDT for 7 forecast zones in [AN] till '
            +'Aug 1, 6:00 AM EDT http://localhost#2014-O-NEW-KLWX-SC-Y-0151'))
        
    def test_tornado_emergency(self):
        """ See what we do with Tornado Emergencies """
        utcnow = utc(2012, 4, 15, 3, 27)
        prod = vtecparser( get_file('TOR_emergency.txt'), utcnow=utcnow)
        j = prod.get_jabbers('http://localhost', 'http://localhost')
        self.assertEquals(j[0][1], ("<p>ICT <a href=\"http://localhost"
        +"#2012-O-NEW-KICT-TO-W-0035\">issues Tornado Warning</a> "
        +"[tornado: OBSERVED, tornado damage threat: CATASTROPHIC, "
        +"hail: 2.50 IN] for ((KSC015)), ((KSC173)) [KS] till 11:00 PM CDT "
        +"* AT 1019 PM CDT...<span style=\"color: #FF0000;\">TORNADO "
        +"EMERGENCY</span> FOR THE WICHITA METRO AREA. A CONFIRMED LARGE..."
        +"VIOLENT AND EXTREMELY DANGEROUS TORNADO WAS LOCATED NEAR "
        +"HAYSVILLE...AND MOVING NORTHEAST AT 50 MPH.</p>"))        
    
    def test_badtimestamp(self):
        """ See what happens when the MND provides a bad timestamp """
        utcnow = utc(2005, 8, 29, 16, 56)
        self.assertRaises(Exception, vtecparser,
                          get_file('TOR_badmnd_timestamp.txt'), utcnow=utcnow) 
  
    def test_wcn_updates(self):
        """ Make sure our Tags and svs_special works for combined message """
        utcnow = utc(2014, 6, 6, 20, 37)
        ugc_provider = {}
        for u in range(1,201,2):
            n =  'a' * min((u+1/2),40)
            for st in ['AR', 'MS', 'TN', 'MO']:
                ugc_provider["%sC%03i" % (st, u)] = UGC(st, 'C', "%03i" % (u,), 
                              name=n, wfos=['DMX'])
        prod = vtecparser( get_file('WCNMEG.txt'), utcnow=utcnow,
                           ugc_provider=ugc_provider) 
        j = prod.get_jabbers('http://localhost', 'http://localhost')
        self.assertEquals(j[0][0], ('MEG updates Severe Thunderstorm Watch '
        +'(extends area of 11 counties in [TN] and '
        +'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa [MO], continues '
        +'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, aaaaaaaaaaaaaaaaaaaaaaaaa'
        +'aaaaaaaaaaaaaaa, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, aaaaaaaa'
        +'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        +'aaaaaaa, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa [TN] and aaaaaaaa'
        +'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa [MO] and 12 counties in [AR] and '
        +'22 counties in [MS]) till Jun 6, 7:00 PM CDT. '
        +'http://localhost#2014-O-EXA-KMEG-SV-A-0240'))
  
    def test_140715_condensed(self):
        """ Make sure our Tags and svs_special works for combined message """
        utcnow = utc(2014, 7, 6, 2, 1)
        prod = vtecparser( get_file('TORSVS.txt'), utcnow=utcnow) 
        j = prod.get_jabbers('http://localhost', 'http://localhost')
        self.assertEquals(j[0][0], ('DMX updates Tornado Warning '
            +'[tornado: OBSERVED, hail: &lt;.75 IN] (cancels ((IAC049)) [IA], '
            +'continues ((IAC121)) [IA]) till 9:15 PM CDT. AT 901 PM CDT...A '
            +'CONFIRMED TORNADO WAS LOCATED NEAR WINTERSET... MOVING '
            +'SOUTHEAST AT 30 MPH. '
            +'http://localhost#2014-O-CON-KDMX-TO-W-0051'))
    
    def test_140714_segmented_watch(self):
        """ Two segmented watch text formatting stinks """
        utcnow = utc(2014, 7, 14, 17, 25)
        prod = vtecparser( get_file('WCNPHI.txt'), utcnow=utcnow)
        j = prod.get_jabbers('http://localhost', 'http://localhost')
        self.assertEquals( j[0][0], ("PHI issues Severe Thunderstorm Watch "
            +"(issues ((MDC011)), ((MDC015)), ((MDC029)), ((MDC035)), "
            +"((MDC041)) [MD] and ((NJC001)), ((NJC005)), ((NJC007)), "
            +"((NJC009)), ((NJC011)), ((NJC015)), ((NJC019)), ((NJC021)), "
            +"((NJC023)), ((NJC025)), ((NJC027)), ((NJC029)), ((NJC033)), "
            +"((NJC035)), ((NJC037)), ((NJC041)) [NJ] and ((DEC001)), "
            +"((DEC003)), ((DEC005)) [DE] and ((PAC011)), ((PAC017)), "
            +"((PAC025)), ((PAC029)), ((PAC045)), ((PAC077)), ((PAC089)), "
            +"((PAC091)), ((PAC095)), ((PAC101)) [PA], issues ((ANZ430)), "
            +"((ANZ431)), ((ANZ450)), ((ANZ451)), ((ANZ452)), ((ANZ453)), "
            +"((ANZ454)), ((ANZ455)) [AN]) till Jul 14, 8:00 PM EDT. "
            +"http://localhost#2014-O-NEW-KPHI-SV-A-0418") )
    
    def test_140610_tweet_spacing(self):
        ''' Saw spacing issue in tweet message '''
        utcnow = utc(2014, 6, 10, 13, 23)
        prod = vtecparser( get_file('FLWLCH.txt'), utcnow=utcnow)
        j = prod.get_jabbers('http://localhost', 'http://localhost')
        self.assertEquals( j[0][2]['twitter'], ('LCH issues Flood Warning '
            +'valid at Jun 10, 9:48 AM CDT for ((VLSL1)) till Jun 12, 1:00 '
            +'PM CDT http://localhost#2014-O-NEW-KLCH-FL-W-0015') )

    def test_routine(self):
        ''' what can we do with a ROU VTEC product '''
        utcnow = utc(2014, 6, 19, 2, 56)
        prod = vtecparser( get_file('FLWMKX_ROU.txt'), utcnow=utcnow)
        prod.sql( self.txn )
        self.assertEquals( len(prod.warnings), 0)
    
    def test_correction(self):
        ''' Can we properly parse a product correction '''
        utcnow = utc(2014, 6, 6, 21, 30)
        prod = vtecparser( get_file('CCA.txt'), utcnow=utcnow)
        self.assertTrue( prod.is_correction() )
    
    def test_140610_no_vtec_time(self):
        """ A VTEC Product with both 0000 for start and end time, sigh """
        utcnow = utc(2014,6,10, 0, 56)
        prod = vtecparser( get_file('FLSLZK_notime.txt'), utcnow=utcnow)
        prod.sql(self.txn)
        self.assertTrue(prod.segments[0].vtec[0].begints is None)
        self.assertTrue(prod.segments[0].vtec[0].endts is None)
    
    def test_140609_ext_backwards(self):
        """ Sometimes the EXT goes backwards in time, so we have fun """
        utcnow = utc(2014, 6, 6, 15, 40)

        self.txn.execute("""DELETE from warnings_2014 where wfo = 'LBF'
        and eventid = 2 and phenomena = 'FL' and significance = 'W' """)
        self.txn.execute("""DELETE from sbw_2014 where wfo = 'LBF'
        and eventid = 2 and phenomena = 'FL' and significance = 'W' """)

        # --> num  issue   expire  p_begin  p_end
        # 1040 AM CDT FRI JUN 6 2014 NEW 140608T1800Z-000000T0000Z
        # --> 1    08 18   09 18   08 18    09 18 
        #  915 PM CDT FRI JUN 6 2014 EXT 140608T0900Z-000000T0000Z
        # --> 1    08 18   09 18   08 18    08 18!
        # --> 2    08 09   09 09   08 09    09 09
        # 1043 AM CDT SAT JUN 7 2014 EXT 140608T1000Z-000000T0000Z
        # --> 1    08 18   09 18   08 18    08 18
        # --> 2    08 09   09 09   08 09    08 10! set to vtec bts
        # --> 3    08 10   09 10   08 10    09 10
        # 1048 AM CDT SUN JUN 8 2014 EXT 000000T0000Z-140613T0600Z
        # --> 1    08 18   09 18   08 18    08 18
        # --> 2    08 09   09 09   08 09    08 09
        # --> 3    08 10   09 10   08 10    08 15! set to product issue
        # --> 4    08 10   13 06   08 15    13 06 
        # 1030 AM CDT MON JUN 9 2014 CON 000000T0000Z-140613T0600Z
        # --> 1    08 18   09 18   08 18    08 18
        # --> 2    08 09   09 09   08 09    08 09
        # --> 3    08 10   09 10   08 10    08 15
        # --> 4    08 10   13 06   08 15    09 15! set to product issue 
        # --> 5    08 10   13 06   09 15    13 06
        for i in range(1,6):
            prod = vtecparser( get_file('FLWLBF/FLWLBF_%s.txt' % (i,)) , 
                               utcnow=utcnow)
            prod.sql( self.txn )

        self.txn.execute("""SET TIME ZONE 'UTC'""")      
        
        self.txn.execute("""SELECT max(length(svs)) from warnings_2014 WHERE
        eventid = 2 and phenomena = 'FL' and significance = 'W' and wfo = 'LBF'
        """)
        row = self.txn.fetchone()
        self.assertEqual(6693, 6693)
              
        self.txn.execute("""
        select status, updated, issue, expire, init_expire, polygon_begin, 
        polygon_end from sbw_2014 where eventid = 2 and phenomena = 'FL' and 
        significance = 'W' and wfo = 'LBF' ORDER by updated ASC
        """)
        print 'sta update issue  expire init_e p_begi p_end'
        rows = []
        def safe(val):
            if val is None:
                return '(null)'
            return val.strftime("%d%H%M")
        for row in self.txn:
            rows.append( row )
            print '%s %s %s %s %s %s %s' % (row[0], safe(row[1]),
                    safe(row[2]), safe(row[3]), safe(row[4]), safe(row[5]),
                    safe(row[6]))
    
        self.assertEqual(rows[0][6], 
                         datetime.datetime(2014, 6, 7, 2, 15).replace(
                                                tzinfo=pytz.timezone("UTC")))
    
    def test_svs_search(self):
        ''' See that we get the SVS search done right '''
        utcnow = datetime.datetime(2014, 6, 6, 20)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        
        prod = vtecparser( get_file('TORBOU_ibw.txt') , utcnow=utcnow)
        j = prod.segments[0].svs_search()
        self.assertEqual(j, ('* AT 250 PM MDT...A SEVERE THUNDERSTORM '
            +'CAPABLE OF PRODUCING A TORNADO WAS LOCATED 9 MILES WEST OF '
            +'WESTPLAINS...OR 23 MILES SOUTH OF KIMBALL...MOVING EAST AT '
            +'20 MPH.'))
        
    def test_jabber_lsrtime(self):
        ''' Make sure delayed LSRs have proper dates associated with them'''
        utcnow = datetime.datetime(2014, 6, 6, 16)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        prod = parser( get_file('LSRFSD.txt') , utcnow=utcnow)
        j = prod.get_jabbers('http://iem.local')
        self.assertEqual(j[0][1], ('<p>2 SSE Harrisburg [Lincoln Co, SD] '
            +'TRAINED SPOTTER <a href="http://iem.local#FSD/201406052040/'
            +'201406052040">reports TORNADO</a> at 5 Jun, 3:40 PM CDT -- '
            +'ON GROUND ALONG HIGHWAY 11 NORTH OF 275TH ST</p>'))
    
    def test_tortag(self):
        ''' See what we can do with warnings with tags in them '''
        utcnow = datetime.datetime(2011, 8, 7, 4, 36)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        
        prod = vtecparser( get_file('TORtag.txt') , utcnow=utcnow)
        j = prod.get_jabbers('http://localhost/', 'http://localhost/')
        self.assertTrue(prod.is_homogeneous())
        self.assertEqual(j[0][1], ("<p>DMX <a href=\"http://localhost/#2011-"
            +"O-NEW-KDMX-TO-W-0057\">issues Tornado Warning</a> [tornado: "
            +"OBSERVED, tornado damage threat: SIGNIFICANT, hail: 2.75 IN] "
            +"for ((IAC117)), ((IAC125)), ((IAC135)) [IA] till 12:15 AM CDT "
            +"* AT 1132 PM CDT...NATIONAL WEATHER SERVICE DOPPLER RADAR "
            +"INDICATED A SEVERE THUNDERSTORM CAPABLE OF PRODUCING A TORNADO. "
            +"THIS DANGEROUS STORM WAS LOCATED 8 MILES EAST OF CHARITON..."
            +"OR 27 MILES NORTHWEST OF CENTERVILLE...AND MOVING NORTHEAST "
            +"AT 45 MPH.</p>"))
        
    def test_wcn(self):
        ''' See about processing a watch update that cancels some and
        continues others, we want special tweet logic for this '''
        utcnow = datetime.datetime(2014,6,3)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))        
        ugc_provider = {}
        for u in range(1,201,2):
            n =  'a' * min((u+1/2),40)
            ugc_provider["IAC%03i" % (u,)] = UGC('IA', 'C', "%03i" % (u,), 
                              name=n, wfos=['DMX'])

        prod = vtecparser( get_file('SVS.txt') , utcnow=utcnow,
                           ugc_provider=ugc_provider)
        j = prod.get_jabbers('http://localhost/', 'http://localhost/')
        self.assertTrue(prod.is_homogeneous())
        self.assertEqual(j[0][2]['twitter'], ('DMX updates Severe '
            +'Thunderstorm Warning (cancels 1 area, continues 1 area) '
            +'till 10:45 PM CDT '
            +'http://localhost/#2014-O-CON-KDMX-SV-W-0143'))


        prod = vtecparser( get_file('WCN.txt') , utcnow=utcnow,
                           ugc_provider=ugc_provider)
        j = prod.get_jabbers('http://localhost/', 'http://localhost/')
        self.assertTrue(prod.is_homogeneous())
        self.assertEqual(j[0][2]['twitter'], ('DMX updates Tornado Watch '
            +'(cancels 5 areas, continues 12 areas) till Jun 4, 1:00 AM CDT '
            +'http://localhost/#2014-O-CON-KDMX-TO-A-0210'))
        self.assertEqual(j[0][0], ('DMX updates Tornado Watch (cancels a, '
            +'aaaaaaaaaaaaaaaaaaaaaaaaaaaaa, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
            +'aaaaaaaa, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, aaaaaaaaaaa'
            +'aaaaaaaaaaaaaaaaaaaaaaaaaaaaa [IA], continues 12 counties '
            +'in [IA]) till Jun 4, 1:00 AM CDT. '
            +'http://localhost/#2014-O-CON-KDMX-TO-A-0210'))
    
    def test_spacewx(self):
        ''' See if we can parse a space weather product '''
        utcnow = datetime.datetime(2014,5,10)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        prod = parser( get_file('SPACEWX.txt'), utcnow=utcnow)
        j = prod.get_jabbers('http://localhost/')
        self.assertEqual(j[0][0], ('Space Weather Prediction Center issues '
            +'CANCEL WATCH: Geomagnetic Storm Category G3 Predicted '
            +'http://localhost/?pid=201405101416-KWNP-WOXX22-WATA50'))
    
    def test_140604_sbwupdate(self):
        ''' Make sure we are updating the right info in the sbw table '''
        utcnow = datetime.datetime(2014,6,4)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))        

        self.txn.execute("""DELETE from sbw_2014 where
        wfo = 'LMK' and eventid = 95 and phenomena = 'SV' and 
        significance = 'W' """)
        self.txn.execute("""DELETE from warnings_2014 where
        wfo = 'LMK' and eventid = 95 and phenomena = 'SV' and 
        significance = 'W' """)

        prod = vtecparser( get_file('SVRLMK_1.txt') , utcnow=utcnow)
        prod.sql( self.txn )    

        self.txn.execute("""SELECT expire from sbw_2014 WHERE
        wfo = 'LMK' and eventid = 95 and phenomena = 'SV' and 
        significance = 'W' """)
        self.assertEqual( self.txn.rowcount, 1)

        prod = vtecparser( get_file('SVRLMK_2.txt') , utcnow=utcnow)
        prod.sql( self.txn )    

        self.txn.execute("""SELECT expire from sbw_2014 WHERE
        wfo = 'LMK' and eventid = 95 and phenomena = 'SV' and 
        significance = 'W' """)
        self.assertEqual( self.txn.rowcount, 3)
        
        self.assertEqual( len(prod.warnings), 0, "\n".join(prod.warnings))

    
    def test_140321_invalidgeom(self):
        ''' See what we do with an invalid geometry from IWX '''
        prod = vtecparser( get_file('FLW_badgeom.txt') )
        self.assertEqual(prod.segments[0].giswkt, ('SRID=4326;MULTIPOLYGON ((('
            +'-85.680000 41.860000, -85.640000 41.970000, '
            +'-85.540000 41.970000, -85.540000 41.960000, '
            +'-85.610000 41.930000, -85.660000 41.840000, '
            +'-85.680000 41.860000)))'))
    
    def test_140522_blowingdust(self):
        ''' Make sure we can deal with invalid LSR type '''
        prod = parser( get_file('LSRTWC.txt') )
        self.assertEqual(len(prod.lsrs), 1)
        self.assertEqual( prod.lsrs[0].get_dbtype(), None)
    
    def test_140527_astimezone(self):
        ''' Test the processing of a begin timestamp '''
        utcnow = datetime.datetime(2014, 5, 27, 16, 3)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        prod = vtecparser( get_file('MWWSEW.txt') , utcnow=utcnow)
        prod.sql( self.txn )
        j = prod.get_jabbers('http://localhost/', 'http://localhost/')
        self.assertEqual(j[0][0], ('SEW continues Small Craft Advisory '
            +'valid at May 27, 4:00 PM PDT for ((PZZ131)), ((PZZ132)) [PZ] till '
            +'May 28, 5:00 AM PDT '
            +'http://localhost/#2014-O-CON-KSEW-SC-Y-0113'))
    
    def test_140527_00000_hvtec_nwsli(self):
        ''' Test the processing of a HVTEC NWSLI of 00000 '''
        utcnow = datetime.datetime(2014,5,27)
        utcnow = utcnow.replace(tzinfo=pytz.timezone("UTC"))
        prod = vtecparser( get_file('FLSBOU.txt') , utcnow=utcnow)
        prod.sql( self.txn )
        j = prod.get_jabbers('http://localhost/', 'http://localhost/')
        self.assertEqual(j[0][0], ('BOU extends time of Areal Flood Advisory '
            +'for ((COC049)), ((COC057)) [CO] till May 29, 9:30 PM MDT '
            +'http://localhost/#2014-O-EXT-KBOU-FA-Y-0018'))
        self.assertEqual(j[0][2]['twitter'], ('BOU extends time of Areal Flood '
            +'Advisory for ((COC049)), ((COC057)) [CO] till '
            +'May 29, 9:30 PM MDT http://localhost/#2014-O-EXT-KBOU-FA-Y-0018'))
    

 
    def test_affected_wfos(self):
        ''' see what affected WFOs we have '''
        ugc_provider = {'IAZ006': UGC('IA', 'Z', '006', wfos=['DMX'])}
        prod = vtecparser( get_file('WSWDMX/WSW_00.txt') , ugc_provider=ugc_provider)
        self.assertEqual(prod.segments[0].get_affected_wfos()[0], 'DMX')
    
    def test_141023_upgrade(self):
        """ See that we can handle the upgrade and downgrade dance """
        for i in range(1,8):
            prod = vtecparser(get_file('NPWBOX/NPW_%02i.txt' % (i,)))
            prod.sql(self.txn)
            self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))
    
    def test_141205_vtec_series(self):
        """ Make sure we don't get any warnings processing this series """
        for i in range(9):
            print("Processing product: %s" % (i,))
            fn = "WSWOTX/WSW_%02i.txt" % (i,)
            prod = vtecparser(get_file(fn))
            prod.sql(self.txn)
            self.assertEquals(len(prod.warnings), 0, "\n".join(prod.warnings))
    
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
        answer = datetime.datetime(2013,1,28,5, 38).replace(
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

        msgs = prod.get_jabbers('http://localhost', 'http://localhost/')
        self.assertEqual( msgs[0][0], ('JAN issues Tornado Warning for '
            +'((MSC035)), ((MSC073)), DARYL [MS] till Aug 29, 1:15 PM CDT * AT '
            +'1150 AM CDT...THE NATIONAL WEATHER SERVICE HAS ISSUED A '
            +'TORNADO WARNING FOR DESTRUCTIVE WINDS OVER 110 MPH IN THE EYE '
            +'WALL AND INNER RAIN BANDS OF HURRICANE KATRINA. THESE WINDS '
            +'WILL OVERSPREAD MARION...FORREST AND LAMAR COUNTIES DURING '
            +'THE WARNING PERIOD. http://localhost#2005-O-NEW-KJAN-TO-W-0130'))
    
    def test_01(self):
        """ process a valid LSR without blemish """
        prod = parser( get_file("LSR.txt") )
        self.assertEqual(len(prod.lsrs), 58)
        
        self.assertAlmostEqual(prod.lsrs[57].magnitude_f, 73, 0)
        self.assertEqual(prod.lsrs[57].county, "MARION")
        self.assertEqual(prod.lsrs[57].state, "IA")
        self.assertAlmostEqual(prod.lsrs[57].get_lon(), -93.11, 2)
        self.assertAlmostEqual(prod.lsrs[57].get_lat(), 41.3, 1)
        
        self.assertEqual(prod.is_summary(), True)
        self.assertEqual(prod.lsrs[57].wfo , 'DMX')
        
        answer = datetime.datetime(2013,7,23,3,55)
        answer = answer.replace(tzinfo=pytz.timezone("UTC"))
        self.assertEqual(prod.lsrs[57].valid, answer)
        j = prod.get_jabbers('http://localhost')
        self.assertEqual(j[57][0], ("Knoxville Airport "
        +"[Marion Co, IA] AWOS reports NON-TSTM WND GST of M73 MPH at 22 "
        +"Jul, 10:55 PM CDT -- HEAT BURST. TEMPERATURE ROSE FROM 70 TO 84 IN "
        +"15 MINUTES AND DEW POINT DROPPED FROM 63 TO 48 IN 10 MINUTES. "
        +"http://localhost#DMX/201307230355/201307230355"))
        
        self.assertEqual(prod.lsrs[5].tweet(), ("At 4:45 PM, Dows "
                         +"[Wright Co, IA] LAW ENFORCEMENT "
                         +"reports TSTM WND DMG #DMX"))
    
    def test_mpd_mcdparser(self):
        ''' The mcdparser can do WPC's MPD as well, test it '''
        prod = parser( get_file('MPD.txt') )
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
        prod = parser( get_file('SWOMCD.txt') )
        self.assertAlmostEqual(prod.geometry.area, 4.302, 3)
        self.assertEqual(prod.discussion_num, 1525 )
        self.assertEqual(prod.attn_wfo[2], 'DLH')
        self.assertEqual(prod.areas_affected, ("PORTIONS OF NRN WI AND "
                                               +"THE UPPER PENINSULA OF MI"))

        # With probability this time
        prod = parser( get_file('SWOMCDprob.txt') )
        self.assertAlmostEqual(prod.geometry.area, 2.444, 3)
        self.assertEqual(prod.watch_prob, 20)

        self.assertEqual(prod.get_jabbers('http://localhost')[1], ('<p>Storm '
            +'Prediction Center issues <a href="http://www.spc.noaa.gov/'
            +'products/md/2013/md1678.html">Mesoscale Discussion #1678</a> '
            +'[watch probability: 20%] (<a href="http://localhost'
            +'?pid=201308091725-KWNS-ACUS11-SWOMCD">View text</a>)</p>'))
