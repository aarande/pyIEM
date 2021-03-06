import unittest

from pyiem import datatypes, meteorology


class TestDatatypes(unittest.TestCase):

    def test_windchill(self):
        """Wind Chill Conversion"""
        temp = datatypes.temperature(0, 'F')
        sknt = datatypes.speed(30, 'MPH')
        val = meteorology.windchill(temp, sknt).value('F')
        self.assertAlmostEquals(val, -24.50, 2)

    def test_dewpoint_from_pq(self):
        """ See if we can produce dew point from pressure and mixing ratio """
        p = datatypes.pressure(1013.25, "MB")
        mr = datatypes.mixingratio(0.012, "kg/kg")
        dwpk = meteorology.dewpoint_from_pq(p, mr)
        self.assertAlmostEqual(dwpk.value("C"), 16.84, 2)

    def test_dewpoint(self):
        """ test out computation of dew point """
        for t0,r0,a0 in [[80,80,73.42], [80,20,35.87]]:
            t = datatypes.temperature(t0, 'F')
            rh = datatypes.humidity(r0, '%')
            dwpk = meteorology.dewpoint(t, rh)
            self.assertAlmostEqual( dwpk.value("F"), a0, 2)

    def test_heatindex(self):
        ''' Test our heat index calculations '''
        t = datatypes.temperature(80.0, 'F')
        td = datatypes.temperature(70.0, 'F')
        hdx = meteorology.heatindex(t, td)
        self.assertAlmostEqual( hdx.value("F"), 83.93, 2)

        t = datatypes.temperature(30.0, 'F')
        hdx = meteorology.heatindex(t, td)
        self.assertAlmostEqual( hdx.value("F"), 30.00, 2)


    def test_uv(self):
        """ Test calculation of uv wind components """
        speed = datatypes.speed([10,], 'KT')
        mydir = datatypes.direction([0,], 'DEG')
        u,v = meteorology.uv(speed, mydir)
        self.assertEqual(u.value("KT"), 0.)
        self.assertEqual(v.value("KT"), -10.)

        speed = datatypes.speed([10,20,15], 'KT')
        mydir = datatypes.direction([90,180,135], 'DEG')
        u,v = meteorology.uv(speed, mydir)
        self.assertEqual(u.value("KT")[0], -10)
        self.assertEqual(v.value("KT")[1], 20.)
        self.assertAlmostEquals(v.value("KT")[2], 10.6, 1)


    def test_relh(self):
        """ Simple check of bad units in temperature """
        tmp = datatypes.temperature(24, 'C')
        dwp = datatypes.temperature(24, 'C')
        relh = meteorology.relh(tmp, dwp)
        self.assertEquals(100.0, relh.value("%"))

        tmp = datatypes.temperature(32, 'C')
        dwp = datatypes.temperature(10, 'C')
        relh = meteorology.relh(tmp, dwp)
        self.assertAlmostEquals(25.79, relh.value("%"), 2)
        
        tmp = datatypes.temperature(32, 'C')
        dwp = datatypes.temperature(15, 'C')
        relh = meteorology.relh(tmp, dwp)
        self.assertAlmostEquals(35.81, relh.value("%"), 2)
        
        tmp = datatypes.temperature(5, 'C')
        dwp = datatypes.temperature(4, 'C')
        relh = meteorology.relh(tmp, dwp)
        self.assertAlmostEquals(93.24, relh.value("%"), 2)